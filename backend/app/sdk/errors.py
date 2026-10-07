"""SDK 的结构化错误：稳定的类别（kind）供智能体分支处理，code 与 message 沿用业务错误。"""

from typing import Any

from pydantic import ValidationError

from app.errors import AppError

ERROR_KINDS = (
    "invalid_input",
    "not_found",
    "forbidden",
    "unauthenticated",
    "needs_user_confirmation",
    "conflict",
    "module_unavailable",
    "internal",
)

DEFAULT_HINTS: dict[str, str] = {
    "invalid_input": "请按能力的输入说明修正参数后重试",
    "not_found": "记录不存在或不属于当前用户；请先用列表类能力确认编号",
    "forbidden": "当前凭证不允许这项操作；请告知用户，不要换着方式重试",
    "unauthenticated": "凭证缺失、无效、过期或已吊销；请让用户在应用里重新创建授权",
    "needs_user_confirmation": "这一步需要用户本人在应用里完成，请如实告知用户",
    "conflict": "与已有数据冲突；请先查询最新状态，再决定是否重试",
    "module_unavailable": "该模块对当前用户未开放；请先调用 profile.get_capabilities 查看可用模块",
    "internal": "服务内部出错；请稍后重试，仍失败时请告知用户",
}

DISCLAIMER_HINT = "请让用户先在应用里阅读并确认免责声明"

_INVALID_INPUT_STATUSES = {400, 413, 415, 422}


class SdkError(Exception):
    def __init__(
        self,
        kind: str,
        code: str,
        message: str,
        hint: str | None = None,
        details: list[dict[str, Any]] | None = None,
    ):
        if kind not in ERROR_KINDS:
            raise ValueError(f"unknown error kind: {kind}")
        super().__init__(message)
        self.kind = kind
        self.code = code
        self.message = message
        self.hint = hint if hint is not None else DEFAULT_HINTS[kind]
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "code": self.code, "message": self.message, "hint": self.hint,
                "details": self.details}


def from_app_error(err: AppError) -> SdkError:
    status, code = err.status_code, err.code
    hint = None
    if status == 401:
        kind = "unauthenticated"
    elif status == 403 and code.endswith("_not_available"):
        kind = "module_unavailable"
    elif status == 403 and code == "disclaimer_not_accepted":
        kind, hint = "needs_user_confirmation", DISCLAIMER_HINT
    elif status == 403:
        kind = "forbidden"
    elif status == 404:
        kind = "not_found"
    elif status == 409:
        kind = "conflict"
    elif status in _INVALID_INPUT_STATUSES:
        kind = "invalid_input"
    else:
        kind = "internal"
    return SdkError(kind, code, err.message, hint)


def from_validation_error(err: ValidationError) -> SdkError:
    details = [
        {"field": ".".join(str(part) for part in e["loc"]), "message": e["msg"]}
        for e in err.errors(include_url=False, include_input=False)
    ]
    return SdkError("invalid_input", "validation_error", "参数不合法", details=details)
