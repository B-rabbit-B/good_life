"""Gemini（Generative Language API v1beta）。密钥放在 x-goog-api-key 请求头里，不放进地址。"""

from collections.abc import Sequence
from typing import Any
from urllib.parse import quote

from app.llm.adapters.base import (
    MAX_LIST_PAGES,
    ChatMessage,
    ChatResult,
    During,
    HttpAdapter,
    ListedModel,
    LlmError,
    ToolCall,
    ToolSpec,
    Usage,
    error_body,
    http_error,
    optional_int,
    sorted_unique,
)

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_ROLES = {"user": "user", "assistant": "model"}


def _parts(message: ChatMessage) -> list[dict]:
    parts: list[dict] = [{"text": message.text}] if message.text or not message.images else []
    parts.extend({"inline_data": {"mime_type": image.mime_type, "data": image.data_base64}}
                 for image in message.images)
    return parts


class GeminiAdapter(HttpAdapter):
    def _headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self._api_key}

    def _classify(self, status: int, body_text: str, during: During) -> LlmError:
        error = error_body(body_text).get("error")
        if isinstance(error, dict):
            state = error.get("status")
            message = str(error.get("message") or "")
            if (status == 400 and "API key not valid" in message) or state in ("PERMISSION_DENIED", "UNAUTHENTICATED"):
                return http_error("invalid_key", status, body_text, self._api_key)
            if state == "RESOURCE_EXHAUSTED":
                code = "quota_exceeded" if "quota" in body_text.lower() else "rate_limited"
                return http_error(code, status, body_text, self._api_key)
            if state == "NOT_FOUND":
                code = "model_not_found" if during == "chat" else "not_found"
                return http_error(code, status, body_text, self._api_key)
        return super()._classify(status, body_text, during)

    def list_models(self) -> list[ListedModel]:
        models: list[ListedModel] = []
        params: dict[str, str] = {}
        for _ in range(MAX_LIST_PAGES):
            data = self._request("GET", "/models", during="list", params=params or None)
            page, token = self._parse(self._page, data)
            models.extend(page)
            if token is None:
                break
            params = {"pageToken": token}
        return sorted_unique(models)

    @staticmethod
    def _page(data: dict) -> tuple[list[ListedModel], str | None]:
        page = [
            ListedModel(str(item["name"]).removeprefix("models/"), item.get("displayName") or None)
            for item in data["models"]
            if "generateContent" in (item.get("supportedGenerationMethods") or ())
        ]
        token = data.get("nextPageToken")
        return page, token if isinstance(token, str) and token else None

    def chat(self, model: str, messages: Sequence[ChatMessage], *, tools: Sequence[ToolSpec] = (),
             max_tokens: int = 1024) -> ChatResult:
        system = "\n\n".join(m.text for m in messages if m.role == "system")
        body: dict[str, Any] = {
            "contents": [{"role": _ROLES[m.role], "parts": _parts(m)} for m in messages if m.role != "system"],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if tools:
            body["tools"] = [{"functionDeclarations": [
                {"name": t.name, "description": t.description, "parameters": t.parameters} for t in tools]}]
        data = self._request("POST", f"/models/{quote(model, safe='')}:generateContent", during="chat", body=body)
        return self._parse(lambda d: self._result(d, model), data)

    @staticmethod
    def _result(data: dict, requested_model: str) -> ChatResult:
        content = data["candidates"][0]["content"]
        texts: list[str] = []
        calls: list[ToolCall] = []
        for part in content.get("parts") or ():  # 输出被截断或拦截时可能没有 parts
            if "text" in part:
                texts.append(part["text"])
            elif "functionCall" in part:
                call = part["functionCall"]
                arguments = call.get("args") or {}
                if not isinstance(arguments, dict):
                    raise TypeError("functionCall args must be an object")
                calls.append(ToolCall(call["name"], arguments, call.get("id")))
        usage = data.get("usageMetadata") or {}
        model = data.get("modelVersion")
        return ChatResult(
            text="".join(texts),
            tool_calls=tuple(calls),
            model=model if isinstance(model, str) and model else requested_model,
            usage=Usage(optional_int(usage.get("promptTokenCount")), optional_int(usage.get("candidatesTokenCount"))),
        )
