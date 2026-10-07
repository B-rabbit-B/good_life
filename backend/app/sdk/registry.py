"""能力注册表：能力名 module.action、级别、参数模型、输出类型与处理函数。"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth.models import User

LEVELS = ("read", "write", "user_confirmed")
MODULES = ("profile", "cycle", "medical", "nutrition", "fitness")


@dataclass(frozen=True)
class Notice:
    kind: str
    message: str


@dataclass(frozen=True)
class CallContext:
    db: Session
    user: User
    today: date
    actor: str  # agent（智能体授权令牌）或 user（用户登录令牌），写入业务事件的来源


@dataclass(frozen=True)
class Capability:
    name: str
    module: str
    level: str
    summary: str
    input_model: type[BaseModel]
    output_type: Any
    handler: Callable[[CallContext, BaseModel], Any]
    notices: Callable[[Any], list[Notice]] | None = None


class NoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


def build_registry(capabilities: Iterable[Capability]) -> dict[str, Capability]:
    registry: dict[str, Capability] = {}
    for cap in capabilities:
        if cap.module not in MODULES:
            raise ValueError(f"{cap.name}: unknown module {cap.module!r}")
        if cap.level not in LEVELS:
            raise ValueError(f"{cap.name}: unknown level {cap.level!r}")
        if not cap.name.startswith(cap.module + "."):
            raise ValueError(f"{cap.name}: name must start with {cap.module}.")
        if cap.name in registry:
            raise ValueError(f"{cap.name}: duplicate capability")
        registry[cap.name] = cap
    return registry


def _build_default() -> dict[str, Capability]:
    from app.sdk.capabilities import ALL

    return build_registry(ALL)


REGISTRY = _build_default()
