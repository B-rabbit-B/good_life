"""OpenAI 兼容格式（通义千问、DeepSeek、豆包、智谱、OpenAI 等）。"""

import json
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit

from app.llm.adapters.base import (
    ChatMessage,
    ChatResult,
    HttpAdapter,
    ListedModel,
    ToolCall,
    ToolSpec,
    Usage,
    optional_int,
    sorted_unique,
)


def _content(message: ChatMessage) -> str | list[dict]:
    if not message.images:
        return message.text
    parts: list[dict] = [{"type": "text", "text": message.text}] if message.text else []
    for image in message.images:
        parts.append({"type": "image_url",
                      "image_url": {"url": f"data:{image.mime_type};base64,{image.data_base64}"}})
    return parts


def _arguments(raw: Any) -> dict:
    """arguments 按规范是 JSON 字符串；空串视为没有参数，个别兼容服务直接给对象时原样使用。"""
    if isinstance(raw, dict):
        return raw
    if not raw.strip():
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("tool arguments must be a JSON object")
    return parsed


def _host(url: str) -> str | None:
    try:
        return urlsplit(url).hostname
    except ValueError:  # 地址格式不对时交给发请求那一步报 unreachable
        return None


class OpenAICompatibleAdapter(HttpAdapter):
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def list_models(self) -> list[ListedModel]:
        data = self._request("GET", "/models", during="list")
        return self._parse(lambda d: sorted_unique([ListedModel(str(item["id"]), None) for item in d["data"]]), data)

    def chat(self, model: str, messages: Sequence[ChatMessage], *, tools: Sequence[ToolSpec] = (),
             max_tokens: int = 1024) -> ChatResult:
        # OpenAI 官方的新模型只接受 max_completion_tokens；其它兼容服务仍用 max_tokens
        limit_field = "max_completion_tokens" if _host(self.base_url) == "api.openai.com" else "max_tokens"
        body: dict[str, Any] = {
            "model": model,
            limit_field: max_tokens,
            "messages": [{"role": m.role, "content": _content(m)} for m in messages],
        }
        if tools:
            body["tools"] = [{"type": "function", "function": {
                "name": t.name, "description": t.description, "parameters": t.parameters}} for t in tools]
        data = self._request("POST", "/chat/completions", during="chat", body=body)
        return self._parse(lambda d: self._result(d, model), data)

    @staticmethod
    def _result(data: dict, requested_model: str) -> ChatResult:
        message = data["choices"][0]["message"]
        text = message.get("content") or ""
        if not isinstance(text, str):
            raise TypeError("message content must be a string")
        calls = tuple(
            ToolCall(call["function"]["name"], _arguments(call["function"].get("arguments", "")), call.get("id"))
            for call in message.get("tool_calls") or ()
        )
        usage = data.get("usage") or {}
        model = data.get("model")
        return ChatResult(
            text=text,
            tool_calls=calls,
            model=model if isinstance(model, str) and model else requested_model,
            usage=Usage(optional_int(usage.get("prompt_tokens")), optional_int(usage.get("completion_tokens"))),
        )
