"""请求日志：访问日志只记“方法 路由模板 状态码”，未处理的异常只记类名、方法与路由模板。

路径参数（例如经期每日记录的日期）、查询串、请求与响应内容、异常文字与堆栈一律不进日志。
服务器自带的访问日志（uvicorn.access）记完整路径与查询串，整条丢弃，由这里的 app.access 代替。
"""

import json
import logging
import re

from fastapi import FastAPI
from fastapi.routing import iter_route_contexts
from starlette.types import ASGIApp, Message, Receive, Scope, Send

ACCESS_LOGGER = "app.access"
UNMATCHED = "<unmatched>"

logger = logging.getLogger(__name__)
access_logger = logging.getLogger(ACCESS_LOGGER)

_INTERNAL_ERROR = json.dumps(
    {"error": {"code": "internal_error", "message": "服务器内部错误"}}, ensure_ascii=False
).encode()

# 方法集合（None 表示任意方法）、编译后的完整路径、模板
_RouteEntry = tuple[frozenset[str] | None, re.Pattern[str], str]


def _route_table(app: FastAPI) -> list[_RouteEntry]:
    table = getattr(app.state, "route_templates", None)
    if table is None:
        table = []
        for ctx in iter_route_contexts(app.routes):
            regex = getattr(ctx, "path_regex", None)
            template = ctx.path_format
            if regex is None or template is None:
                continue
            methods = frozenset(ctx.methods) if ctx.methods else None
            table.append((methods, regex, template))
        app.state.route_templates = table
    return table


def route_template(app: FastAPI, scope: Scope) -> str:
    """按方法与路径找到路由，返回带前缀的完整模板（例如 /api/cycle/day-logs/{log_date}）；找不到返回 UNMATCHED。"""
    method = scope.get("method", "")
    method = "GET" if method == "HEAD" else method
    path = scope.get("path", "")
    for methods, regex, template in _route_table(app):
        if (methods is None or method in methods) and regex.match(path):
            return template
    return UNMATCHED


class RequestLogMiddleware:
    """纯 ASGI 中间件：每个请求结束后记一行访问日志；兜住未处理的异常，不让它带着文字与堆栈到服务器。"""

    def __init__(self, app: ASGIApp, fastapi_app: FastAPI) -> None:
        self.app = app
        self.fastapi_app = fastapi_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        status: int | None = None

        async def recording_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        failed: str | None = None
        try:
            try:
                await self.app(scope, receive, recording_send)
            except Exception as exc:  # 未处理的异常到此为止，不再抛给服务器；这里只置标志，日志与响应都在 except 之外
                failed = type(exc).__name__
            if failed is not None:
                logger.error("未处理的异常：%s %s %s", failed, scope["method"], route_template(self.fastapi_app, scope))
                if status is None:
                    status = 500
                    await send({"type": "http.response.start", "status": 500, "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(_INTERNAL_ERROR)).encode()),
                    ]})
                    await send({"type": "http.response.body", "body": _INTERNAL_ERROR})
        finally:
            access_logger.info("%s %s %s", scope["method"], route_template(self.fastapi_app, scope),
                               status if status is not None else "-")


class _DropAll(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return False


def install_log_hygiene() -> None:
    """幂等：丢弃 uvicorn.access 的全部记录；把 sqlalchemy 的引擎与连接池记录器、PIL 记录器钉在 WARNING
    （sqlalchemy 在 DEBUG 时记结果行，Pillow 在 DEBUG 时记 EXIF 标签与值）。"""
    uvicorn_access = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, _DropAll) for item in uvicorn_access.filters):
        uvicorn_access.addFilter(_DropAll())
    for name in ("sqlalchemy.engine", "sqlalchemy.pool", "PIL"):
        logging.getLogger(name).setLevel(logging.WARNING)
