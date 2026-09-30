"""证据文件上传的请求体大小限制。

FastAPI 会先把整个 multipart 请求体解析到临时文件，之后才轮到鉴权和文件大小检查，
所以必须在最外层就拦住过大的请求体。
"""

import json
import re

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.medical.orders import MAX_EVIDENCE_BYTES

EVIDENCE_PATH = re.compile(r"^/api/medical/orders/[^/]+/evidence$")
MAX_BODY_BYTES = MAX_EVIDENCE_BYTES + 64 * 1024  # 留出 multipart 边界与表头的余量
_TOO_LARGE = json.dumps(
    {"error": {"code": "evidence_too_large", "message": "文件不能超过 10 MB"}}, ensure_ascii=False
).encode()


class _BodyTooLarge(Exception):
    pass


class EvidenceBodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or not EVIDENCE_PATH.match(scope["path"]):
            await self.app(scope, receive, send)
            return

        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
            await self._reject(send)
            return

        received = 0
        exceeded = False
        started = False  # 应用已经开始发送自己的响应
        rejected = False  # 已经发出 413

        async def counting_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_BODY_BYTES and not started:
                    exceeded = True
                    raise _BodyTooLarge
            return message

        async def guarded_send(message: Message) -> None:
            # FastAPI 解析请求体时会吞掉 receive 里抛出的异常并回复 400，
            # 所以超限之后应用发出的任何响应都换成 413，且只发一次。
            nonlocal started, rejected
            if not exceeded:
                started = started or message["type"] == "http.response.start"
                await send(message)
            elif not rejected:
                rejected = True
                await self._reject(send)

        try:
            await self.app(scope, counting_receive, guarded_send)
        except _BodyTooLarge:
            pass
        if exceeded and not rejected:
            await self._reject(send)

    @staticmethod
    async def _reject(send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(_TOO_LARGE)).encode()),
                    (b"connection", b"close"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _TOO_LARGE})
