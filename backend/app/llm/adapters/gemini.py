"""Gemini（Generative Language API v1beta）。密钥放在 x-goog-api-key 请求头里，不放进地址。"""

import json
from collections.abc import Sequence
from typing import Any
from urllib.parse import quote

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
    sanitize_schema_for_gemini,
    sorted_unique,
    validate_messages,
)

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_ROLES = {"user": "user", "assistant": "model"}


def _parts(message: ChatMessage) -> list[dict]:
    parts: list[dict] = [{"text": message.text}] if message.text or not message.images else []
    parts.extend({"inline_data": {"mime_type": image.mime_type, "data": image.data_base64}}
                 for image in message.images)
    return parts


def _model_parts(message: ChatMessage) -> list[dict]:
    """助手的工具调用变成 functionCall 片段；thoughtSignature 必须放回原来那个片段里（Gemini 3 缺了会报 400）。"""
    parts: list[dict] = [{"text": message.text}] if message.text else []
    for call in message.tool_calls:
        part: dict[str, Any] = {"functionCall": {"name": call.name, "args": call.arguments}}
        signature = (call.provider_state or {}).get("thoughtSignature")
        if signature is not None:
            part["thoughtSignature"] = signature
        parts.append(part)
    return parts


def _function_response(message: ChatMessage) -> dict:
    """工具结果放进 response.result：能解析成 JSON 就用解析后的值，否则用原文。"""
    try:
        result = json.loads(message.text)
    except ValueError:
        result = message.text
    return {"functionResponse": {"name": message.tool_name, "response": {"result": result}}}


def _contents(messages: Sequence[ChatMessage]) -> list[dict]:
    """连续的工具结果合并成一条 user 内容（并行调用的结果要放在一起，不能与调用交错）。"""
    out: list[dict] = []
    previous: ChatMessage | None = None
    for message in messages:
        if message.role == "system":
            continue
        if message.role == "tool":
            if previous is not None and previous.role == "tool":
                out[-1]["parts"].append(_function_response(message))
            else:
                out.append({"role": "user", "parts": [_function_response(message)]})
        elif message.tool_calls:
            out.append({"role": "model", "parts": _model_parts(message)})
        else:
            out.append({"role": _ROLES[message.role], "parts": _parts(message)})
        previous = message
    return out


def _declaration(tool: ToolSpec) -> dict:
    """参数结构先转成 Gemini 认得的子集；没有参数时不带 parameters（Gemini 不接受 properties 为空的对象）。"""
    declaration: dict[str, Any] = {"name": tool.name, "description": tool.description}
    parameters = sanitize_schema_for_gemini(tool.parameters)
    if parameters.get("properties") or parameters.get("type") != "object":
        declaration["parameters"] = parameters
    return declaration


def _is_rate_limit(details: Any) -> bool:
    """RESOURCE_EXHAUSTED 带 RetryInfo，或 QuotaFailure 指向每分钟、每天的请求配额时，属于限流而不是额度用尽。"""
    for detail in details if isinstance(details, list) else ():
        if not isinstance(detail, dict):
            continue
        kind = str(detail.get("@type", ""))
        if kind.endswith("google.rpc.RetryInfo"):
            return True
        if kind.endswith("google.rpc.QuotaFailure"):
            for violation in detail.get("violations") or ():
                if not isinstance(violation, dict):
                    continue
                quota = f"{violation.get('quotaId', '')} {violation.get('quotaMetric', '')}".lower()
                per_minute = "perminute" in quota or "per_minute" in quota
                # 每天的请求次数上限次日恢复，算限流；每天的 token 用量上限算额度用尽
                per_day_requests = ("perday" in quota or "per_day" in quota) and "request" in quota
                if per_minute or per_day_requests:
                    return True
    return False


# 这些结束原因表示内容被拦截；其它原因（例如 MAX_TOKENS）没有内容时按空回复处理
_BLOCK_REASONS = ("SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII")
_FINISH_REASONS: dict[Any, FinishReason] = {
    "STOP": "stop", "MAX_TOKENS": "length", **{reason: "content_filter" for reason in _BLOCK_REASONS},
    "IMAGE_SAFETY": "content_filter", "IMAGE_PROHIBITED_CONTENT": "content_filter"}


def _blocked(reason: Any) -> LlmError:
    return LlmError("bad_request", f"内容被 Gemini 的安全过滤拦截（原因：{reason}），请修改提问内容后再试")


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
                code = "rate_limited" if _is_rate_limit(error.get("details")) else "quota_exceeded"
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
        validate_messages(messages)
        system = "\n\n".join(m.text for m in messages if m.role == "system")
        body: dict[str, Any] = {
            "contents": _contents(messages),
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if tools:
            body["tools"] = [{"functionDeclarations": [_declaration(t) for t in tools]}]
        model = model.removeprefix("models/")
        data = self._request("POST", f"/models/{quote(model, safe='')}:generateContent", during="chat", body=body)
        return self._parse(lambda d: self._result(d, model), data)

    @staticmethod
    def _result(data: dict, requested_model: str) -> ChatResult:
        candidates = data.get("candidates")
        block_reason = (data.get("promptFeedback") or {}).get("blockReason")
        if not candidates and block_reason:
            raise _blocked(block_reason)
        candidate = candidates[0]
        if "content" not in candidate:
            reason = candidate.get("finishReason")
            if reason in _BLOCK_REASONS:
                raise _blocked(reason)
            if not reason:
                raise KeyError("content")
        content = candidate.get("content") or {}  # 没有内容（例如 MAX_TOKENS 时全部用在了思考上）按空回复处理
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
                # 没有 id 时按出现顺序合成一个，便于把工具结果对应回去；thoughtSignature 留着下一轮原样放回
                call_id = call.get("id") or f"gemini-call-{len(calls) + 1}"
                signature = part.get("thoughtSignature")
                state = {"thoughtSignature": signature} if signature is not None else None
                calls.append(ToolCall(call["name"], arguments, call_id, state))
        usage = data.get("usageMetadata") or {}
        model = data.get("modelVersion")
        return ChatResult(
            text="".join(texts),
            tool_calls=tuple(calls),
            model=model if isinstance(model, str) and model else requested_model,
            usage=Usage(optional_int(usage.get("promptTokenCount")), optional_int(usage.get("candidatesTokenCount"))),
            finish_reason=finish_with_calls(_FINISH_REASONS.get(candidate.get("finishReason"), "other"), calls),
        )
