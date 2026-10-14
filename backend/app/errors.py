import logging
import re
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.request_log import route_template

logger = logging.getLogger(__name__)


class AppError(Exception):
    """业务错误，统一转成 {"error": {"code", "message"}}。"""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


VALIDATION_FALLBACK = "输入内容不符合要求，请检查后重试"

_CJK = re.compile(r"[一-鿿]")


def _num(value: Any) -> str:
    """限制值写成人看的数：50.0 写作 50。"""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _options(expected: Any) -> str:
    """枚举的可选值：pydantic 写成 "'a', 'b' or 'c'"，改成 a、b、c。"""
    parts = re.split(r",\s*|\s+or\s+", str(expected))
    return "、".join(part.strip().strip("'\"") for part in parts if part.strip())


def _value_error(err: dict[str, Any]) -> str:
    """自定义校验器抛出的说明本来就是中文时直接用（去掉 pydantic 加的 "Value error, " 前缀）。"""
    error = (err.get("ctx") or {}).get("error")
    text = str(error) if error is not None else str(err.get("msg", "")).removeprefix("Value error, ")
    return text if _CJK.search(text) else VALIDATION_FALLBACK


def validation_message(err: dict[str, Any]) -> str:
    """把 pydantic 的英文校验说明按错误类型换成中文：说清哪里不对、该怎么改；限制值取自 ctx。不认识的类型用通用说明。"""
    kind = str(err.get("type", ""))
    ctx = err.get("ctx") or {}
    if kind == "missing":
        return "这一项必须填写"
    if kind == "string_too_short":
        minimum = ctx.get("min_length", 1)
        return "不能为空，请填写" if minimum == 1 else f"至少 {_num(minimum)} 个字符，请补全"
    if kind == "string_too_long":
        return f"最多 {_num(ctx.get('max_length'))} 个字符，请删减"
    if kind == "too_short":
        return f"至少要有 {_num(ctx.get('min_length'))} 项"
    if kind == "too_long":
        return f"最多 {_num(ctx.get('max_length'))} 项，请删去一些"
    if kind == "string_pattern_mismatch":
        return "格式不符合要求，请按提示修改"
    if kind in ("string_type", "string_unicode"):
        return "应填写文字"
    if kind in ("int_parsing", "int_type", "int_from_float"):
        return "请填写整数"
    if kind in ("float_parsing", "float_type", "decimal_parsing", "decimal_type"):
        return "请填写数字"
    if kind == "greater_than":
        return f"必须大于 {_num(ctx.get('gt'))}"
    if kind == "greater_than_equal":
        return f"不能小于 {_num(ctx.get('ge'))}"
    if kind == "less_than":
        return f"必须小于 {_num(ctx.get('lt'))}"
    if kind == "less_than_equal":
        return f"不能大于 {_num(ctx.get('le'))}"
    if kind in ("literal_error", "enum"):
        expected = ctx.get("expected")
        return f"只能从这些选项中选：{_options(expected)}" if expected else "取值不在允许的选项里，请重新选择"
    if kind in ("value_error", "assertion_error"):
        return _value_error(err)
    if kind == "extra_forbidden":
        return "不能提交这一项，请去掉后重试"
    if kind in ("date_parsing", "date_type", "date_from_datetime_parsing", "date_from_datetime_inexact"):
        return "日期格式不对，请按“年-月-日”填写，例如 2026-10-12"
    if kind in ("datetime_parsing", "datetime_type", "datetime_from_date_parsing", "datetime_object_invalid"):
        return "时间格式不对，请按“年-月-日 时:分”填写"
    if kind in ("uuid_parsing", "uuid_type", "uuid_version"):
        return "编号格式不对，请重新选择"
    if kind in ("bool_parsing", "bool_type"):
        return "只能是“是”或“否”"
    if kind == "json_invalid":
        return "提交的内容不是有效的 JSON，请检查后重试"
    return VALIDATION_FALLBACK


def _body(code: str, message: str, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in err["loc"][1:]),
                "message": validation_message(err),
                "type": err.get("type", ""),
                "original": err.get("msg", ""),
            }
            for err in exc.errors()
        ]
        return JSONResponse(status_code=422, content=_body("validation_error", "请求参数不合法", details))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_body("http_error", str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        # 并发写入撞上唯一约束：异常文字带数据库的 DETAIL（键值原样出现），只记约束名。
        diag = getattr(getattr(exc, "orig", None), "diag", None)
        constraint = getattr(diag, "constraint_name", None) or "unknown"
        logger.warning("数据冲突：%s %s（%s）", request.method, route_template(request.app, request.scope), constraint)
        return JSONResponse(status_code=409, content=_body("conflict", "数据刚刚被修改过，请刷新后重试"))

    # 未处理的异常不在这里处理：common/request_log.py 的 RequestLogMiddleware 兜底，只记类名、方法与路由模板。
