"""Claude（Anthropic Messages API，anthropic-version 2023-06-01）。"""

from collections.abc import Sequence
from typing import Any

from app.llm.adapters.base import (
    MAX_LIST_PAGES,
    ChatMessage,
    ChatResult,
    During,
    FinishReason,
    HttpAdapter,
    ListedModel,
    LlmError,
    ToolCall,
    ToolSpec,
    Usage,
    error_body,
    finish_with_calls,
    http_error,
    optional_int,
    require_call_ids,
    sorted_unique,
    validate_messages,
)

DEFAULT_BASE_URL = "https://api.anthropic.com"
API_VERSION = "2023-06-01"
_STOP_REASONS: dict[Any, FinishReason] = {
    "end_turn": "stop", "stop_sequence": "stop", "tool_use": "tool_calls", "max_tokens": "length",
    "refusal": "content_filter"}


def _content(message: ChatMessage) -> str | list[dict]:
    if not message.images:
        return message.text
    parts: list[dict] = [
        {"type": "image", "source": {"type": "base64", "media_type": image.mime_type, "data": image.data_base64}}
        for image in message.images
    ]
    if message.text:  # Claude 不接受空的文字块
        parts.append({"type": "text", "text": message.text})
    return parts


def _blocks(content: str | list[dict]) -> list[dict]:
    return [{"type": "text", "text": content}] if isinstance(content, str) else content


def _messages(conversation: Sequence[ChatMessage]) -> list[dict]:
    """助手的工具调用变成 tool_use 块；工具结果变成用户消息里的 tool_result 块。

    相邻的用户消息（工具结果、后面紧跟的用户文字或图片）合并成一条，tool_result 块排在最前面（Claude 要求如此）。
    """
    out: list[dict] = []
    for message in conversation:
        if message.role == "tool":
            entry: dict = {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": message.tool_call_id, "content": message.text}]}
        elif message.tool_calls:
            blocks: list[dict] = [{"type": "text", "text": message.text}] if message.text else []
            blocks.extend({"type": "tool_use", "id": call.call_id, "name": call.name, "input": call.arguments}
                          for call in message.tool_calls)
            entry = {"role": "assistant", "content": blocks}
        else:
            entry = {"role": message.role, "content": _content(message)}
        if entry["role"] == "user" and out and out[-1]["role"] == "user":
            merged = _blocks(out[-1]["content"]) + _blocks(entry["content"])
            out[-1]["content"] = ([b for b in merged if b["type"] == "tool_result"]
                                  + [b for b in merged if b["type"] != "tool_result"])
        else:
            out.append(entry)
    return out


class AnthropicAdapter(HttpAdapter):
    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self._api_key, "anthropic-version": API_VERSION}

    def _classify(self, status: int, body_text: str, during: During) -> LlmError:
        error = error_body(body_text).get("error")
        error_type = error.get("type") if isinstance(error, dict) else None
        if error_type in ("authentication_error", "permission_error"):
            return http_error("invalid_key", status, body_text, self._api_key)
        if error_type == "not_found_error":
            code = "model_not_found" if during == "chat" else "not_found"
            return http_error(code, status, body_text, self._api_key)
        if error_type == "rate_limit_error":
            return http_error("rate_limited", status, body_text, self._api_key)
        if error_type == "overloaded_error":
            return http_error("provider_error", status, body_text, self._api_key, "Claude 服务繁忙，请稍后再试")
        return super()._classify(status, body_text, during)

    def list_models(self) -> list[ListedModel]:
        models: list[ListedModel] = []
        params: dict[str, str] = {}
        for _ in range(MAX_LIST_PAGES):
            data = self._request("GET", "/v1/models", during="list", params=params or None)
            page, last_id = self._parse(self._page, data)
            models.extend(page)
            if last_id is None:
                break
            params = {"after_id": last_id}
        return sorted_unique(models)

    @staticmethod
    def _page(data: dict) -> tuple[list[ListedModel], str | None]:
        page = [ListedModel(str(item["id"]), item.get("display_name") or None) for item in data["data"]]
        last_id = data.get("last_id")
        more = data.get("has_more") is True and isinstance(last_id, str) and last_id
        return page, last_id if more else None

    def chat(self, model: str, messages: Sequence[ChatMessage], *, tools: Sequence[ToolSpec] = (),
             max_tokens: int = 1024) -> ChatResult:
        validate_messages(messages)
        require_call_ids(messages)
        conversation = [m for m in messages if m.role != "system"]
        if not conversation:
            raise LlmError("bad_request", "Claude 需要至少一条用户消息，只有系统提示无法发起对话")
        if any(not m.text and not m.images and not m.tool_calls and m.role != "tool" for m in conversation):
            raise LlmError("bad_request", "Claude 不接受空消息：每条消息都需要有文字或图片")
        system = "\n\n".join(m.text for m in messages if m.role == "system" and m.text)
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": _messages(conversation),
        }
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [{"name": t.name, "description": t.description, "input_schema": t.parameters}
                             for t in tools]
        data = self._request("POST", "/v1/messages", during="chat", body=body)
        return self._parse(lambda d: self._result(d, model), data)

    @staticmethod
    def _result(data: dict, requested_model: str) -> ChatResult:
        texts: list[str] = []
        calls: list[ToolCall] = []
        for block in data["content"]:
            if block["type"] == "text":
                texts.append(block["text"])
            elif block["type"] == "tool_use":
                arguments = block["input"]
                if not isinstance(arguments, dict):
                    raise TypeError("tool_use input must be an object")
                calls.append(ToolCall(block["name"], arguments, block.get("id")))
        usage = data.get("usage") or {}
        model = data.get("model")
        return ChatResult(
            text="".join(texts),
            tool_calls=tuple(calls),
            model=model if isinstance(model, str) and model else requested_model,
            usage=Usage(optional_int(usage.get("input_tokens")), optional_int(usage.get("output_tokens"))),
            finish_reason=finish_with_calls(_STOP_REASONS.get(data.get("stop_reason"), "other"), calls),
        )
