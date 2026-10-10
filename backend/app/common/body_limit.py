"""文件上传的请求体大小限制（医嘱证据、餐食照片）。

FastAPI 会先把整个 multipart 请求体解析到临时文件，之后才轮到鉴权和文件大小检查，
所以必须在最外层就拦住过大的请求体。
"""

import json
import re
from dataclasses import dataclass

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.medical.orders import MAX_EVIDENCE_BYTES
from app.photos.images import MAX_UPLOAD_BYTES

MULTIPART_SLACK = 64 * 1024  # 留出 multipart 边界与表头的余量
EVIDENCE_PATH = re.compile(r"^/api/medical/orders/[^/]+/evidence$")
MAX_BODY_BYTES = MAX_EVIDENCE_BYTES + MULTIPART_SLACK
PHOTO_PATH = re.compile(r"^/api/photos/recognitions$")
MAX_PHOTO_BODY_BYTES = MAX_UPLOAD_BYTES + MULTIPART_SLACK


@dataclass(frozen=True)
class BodyLimitRule:
    path: re.Pattern[str]
    max_bytes: int
    response: bytes  # 超限时返回的 413 响应体


def _too_large(code: str, message: str) -> bytes:
    return json.dumps({"error": {"code": code, "message": message}}, ensure_ascii=False).encode()


DEFAULT_RULES: tuple[BodyLimitRule, ...] = (
    BodyLimitRule(EVIDENCE_PATH, MAX_BODY_BYTES, _too_large("evidence_too_large", "文件不能超过 10 MB")),
    BodyLimitRule(
        PHOTO_PATH, MAX_PHOTO_BODY_BYTES, _too_large("photo_too_large", "图片不能超过 8 MB，请压缩或重拍后再上传")
    ),
)


class _BodyTooLarge(Exception):
    pass


class UploadBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, rules: tuple[BodyLimitRule, ...] = DEFAULT_RULES) -> None:
        self.app = app
        self.rules = rules

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        rule = None
        if scope["type"] == "http" and scope["method"] == "POST":
            rule = next((r for r in self.rules if r.path.match(scope["path"])), None)
        if rule is None:
            await self.app(scope, receive, send)
            return

        limit = rule.max_bytes
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await self._reject(send, rule)
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
                if received > limit and not started:
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
                await self._reject(send, rule)

        try:
            await self.app(scope, counting_receive, guarded_send)
        except _BodyTooLarge:
            pass
        if exceeded and not rejected:
            await self._reject(send, rule)

    @staticmethod
    async def _reject(send: Send, rule: BodyLimitRule) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(rule.response)).encode()),
                    (b"connection", b"close"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": rule.response})
