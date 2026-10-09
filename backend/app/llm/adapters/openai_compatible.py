"""OpenAI 兼容格式（通义千问、DeepSeek、豆包、智谱、OpenAI 等）。"""

import json
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit

from app.llm.adapters.base import (
    ChatMessage,
    ChatResult,
    FinishReason,
    HttpAdapter,
    ListedModel,
    ToolCall,
    ToolSpec,
    Usage,
    finish_with_calls,
    optional_int,
    require_call_ids,
    sorted_unique,
    validate_messages,
)

_FINISH_REASONS: dict[Any, FinishReason] = {
    "stop": "stop", "tool_calls": "tool_calls", "length": "length", "content_filter": "content_filter"}


def _content(message: ChatMessage) -> str | list[dict]:
    if not message.images:
        return message.text
    parts: list[dict] = [{"type": "text", "text": message.text}] if message.text else []
    for image in message.images:
        parts.append({"type": "image_url",
                      "image_url": {"url": f"data:{image.mime_type};base64,{image.data_base64}"}})
    return parts


def _message(message: ChatMessage) -> dict:
    if message.role == "tool":
        return {"role": "tool", "tool_call_id": message.tool_call_id, "content": message.text}
    out: dict[str, Any] = {"role": message.role, "content": _content(message)}
    if message.tool_calls:
        out["content"] = message.text or None
        out["tool_calls"] = [{"id": call.call_id, "type": "function", "function": {
            "name": call.name, "arguments": json.dumps(call.arguments, ensure_ascii=False)}}
            for call in message.tool_calls]
    state = message.provider_state or {}
    if "reasoning_content" in state:  # DeepSeek 等思考模式：带工具时必须把思考内容原样放回这条助手消息
        out["reasoning_content"] = state["reasoning_content"]
    return out


def _arguments(raw: Any) -> dict:
    """arguments 按规范是 JSON 字符串；空串与 null 视为没有参数，个别兼容服务直接给对象时原样使用。"""
    if raw is None:
        return {}
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
        validate_messages(messages)
        require_call_ids(messages)
        # OpenAI 官方的新模型只接受 max_completion_tokens；其它兼容服务仍用 max_tokens
        limit_field = "max_completion_tokens" if _host(self.base_url) == "api.openai.com" else "max_tokens"
        body: dict[str, Any] = {
            "model": model,
            limit_field: max_tokens,
            "messages": [_message(m) for m in messages],
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
        # 个别兼容服务的工具调用不带 id：按出现顺序合成一个本次回复内唯一的编号，历史才能原样回传
        calls = tuple(
            ToolCall(call["function"]["name"], _arguments(call["function"].get("arguments", "")),
                     call.get("id") or f"call-{index}")
            for index, call in enumerate(message.get("tool_calls") or (), start=1)
        )
        usage = data.get("usage") or {}
        model = data.get("model")
        reasoning = message.get("reasoning_content")
        reason = _FINISH_REASONS.get(data["choices"][0].get("finish_reason"), "other")
        return ChatResult(
            text=text,
            tool_calls=calls,
            model=model if isinstance(model, str) and model else requested_model,
            usage=Usage(optional_int(usage.get("prompt_tokens")), optional_int(usage.get("completion_tokens"))),
            finish_reason=finish_with_calls(reason, calls),
            provider_state={"reasoning_content": reasoning} if isinstance(reasoning, str) else None,
        )
