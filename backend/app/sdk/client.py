"""SDK 调用入口：认证、级别、模块准入、参数校验、执行、序列化与审计，顺序固定。"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session, sessionmaker

from app.agent_grants.service import now
from app.cycle.deps import require_cycle_user
from app.db import get_sessionmaker
from app.disclaimer.deps import require_disclaimer_user
from app.errors import AppError
from app.fitness.deps import require_fitness_user
from app.medical.deps import require_medical_user
from app.nutrition.deps import require_nutrition_user
from app.sdk import audit
from app.sdk.credentials import AgentCredential, AgentGrantToken, UserAccessToken, authenticate
from app.sdk.errors import SdkError, from_app_error, from_validation_error
from app.sdk.registry import REGISTRY, CallContext, Capability, Notice

logger = logging.getLogger(__name__)

SDK_VERSION = "1.2"

CONFIRMATION_HINT = "这一步只能由用户本人在应用里操作；如需解除医嘱，可以调用 medical.propose_resolution 提出解除建议"
WRITE_HINT = "当前授权只允许读取；需要写入时请让用户创建读写授权"
UNKNOWN_CAPABILITY_HINT = "请先列出可用能力，再使用其中的能力名"

_MODULE_GATES: dict[str, Callable[..., Any]] = {
    "cycle": lambda user, db, today: require_cycle_user(user=user, db=db),
    "medical": lambda user, db, today: require_medical_user(user=user, db=db, today=today),
    "nutrition": lambda user, db, today: require_nutrition_user(user=user, db=db),
    "fitness": lambda user, db, today: require_fitness_user(user=user, db=db),
}


@dataclass(frozen=True)
class SdkResult:
    data: Any
    notices: tuple[Notice, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "sdk_version": SDK_VERSION,
            "data": self.data,
            "notices": [{"kind": n.kind, "message": n.message} for n in self.notices],
        }


def error_envelope(err: SdkError) -> dict[str, Any]:
    return {"ok": False, "sdk_version": SDK_VERSION, "error": err.to_dict()}


def _printable(value: str, fallback: str) -> str:
    """写进审计与日志的名字只保留可打印字符、最多 64 个；NUL 等字符会让审计写入失败。"""
    return "".join(ch for ch in str(value) if ch.isprintable())[:64] or fallback


class GoodLife:
    """进程内 SDK。用户身份只来自凭证；每次调用都重新认证并记一行审计。"""

    def __init__(
        self,
        session_factory: Callable[[], Session] | sessionmaker[Session] | None = None,
        today: Callable[[], date] = date.today,
        registry: dict[str, Capability] | None = None,
    ):
        self._session_factory = session_factory
        self._today = today
        self._registry = REGISTRY if registry is None else registry

    def capabilities(self) -> list[Capability]:
        return list(self._registry.values())

    def call(
        self,
        credential: AgentGrantToken | UserAccessToken | AgentCredential | None,
        capability: str,
        params: dict | None = None,
        *,
        client_name: str = "sdk",
    ) -> SdkResult:
        started = time.perf_counter()
        db = (self._session_factory or get_sessionmaker())()
        user_id = grant_id = None
        credential_kind = "none"
        error_code: str | None = None
        succeeded = False
        try:
            caller = authenticate(db, credential, now())
            user_id, grant_id, credential_kind = caller.user.id, caller.grant_id, caller.credential_kind
            cap = self._registry.get(capability)
            if cap is None:
                raise SdkError("invalid_input", "unknown_capability", f"没有名为 {capability} 的能力",
                               UNKNOWN_CAPABILITY_HINT)
            if cap.level == "user_confirmed" and not caller.user_confirmed:
                raise SdkError("needs_user_confirmation", "user_confirmation_required",
                               "这项能力需要用户本人确认", CONFIRMATION_HINT)
            if cap.level == "write" and not caller.can_write:
                raise SdkError("forbidden", "write_not_granted", "当前授权不允许写入", WRITE_HINT)
            today = self._today()
            require_disclaimer_user(user=caller.user, db=db)
            if cap.module != "profile":
                _MODULE_GATES[cap.module](caller.user, db, today)
            try:
                parsed = cap.input_model.model_validate(params or {})
            except ValidationError as err:
                raise from_validation_error(err) from None
            actor = "agent" if caller.credential_kind in ("agent_grant", "agent") else "user"
            raw = cap.handler(CallContext(db, caller.user, today, actor), parsed)
            data = _serialize(cap, raw)
            notices = tuple(cap.notices(data)) if cap.notices is not None else ()
            result = SdkResult(data, notices)
            succeeded = True
            return result
        except SdkError as err:
            error_code = err.code
            db.rollback()
            raise
        except AppError as err:
            converted = from_app_error(err)
            error_code = converted.code
            db.rollback()
            raise converted from None
        except Exception as err:
            error_code = "internal_error"
            db.rollback()
            # 只记能力名与异常类名：异常文字与堆栈里可能带参数或返回内容。
            logger.error("SDK 调用出错：%s %s", _printable(capability, "unknown"), type(err).__name__)
            raise SdkError("internal", "internal_error", "服务内部出错") from None
        finally:
            db.close()
            if not succeeded and error_code is None:
                error_code = "interrupted"  # KeyboardInterrupt、任务取消等 BaseException
            audit.record_call(
                user_id=user_id,
                grant_id=grant_id,
                credential_kind=credential_kind,
                client_name=_printable(client_name, "sdk"),
                capability=_printable(capability, "unknown"),
                outcome="ok" if succeeded else "error",
                error_code=error_code,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )


def _serialize(cap: Capability, raw: Any) -> Any:
    """输出按能力声明的类型校验后转成 JSON 友好的数据；不符合声明是内部错误，不是参数错误。"""
    adapter = TypeAdapter(cap.output_type)
    try:
        return adapter.dump_python(adapter.validate_python(raw, from_attributes=True), mode="json")
    except ValidationError as err:
        # 不链上原异常：pydantic 的错误文本带有输出内容，不能进日志。
        problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['type']}" for e in err.errors(include_input=False))
        raise RuntimeError(f"{cap.name} 的输出不符合声明的类型（{problems}）") from None
