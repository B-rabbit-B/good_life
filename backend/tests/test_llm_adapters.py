import json

import httpx2
import pytest

from app.llm.adapters import make_adapter
from app.llm.adapters.base import (
    ADAPTER_ERROR_CODES,
    MAX_LIST_PAGES,
    ChatMessage,
    ImagePart,
    ListedModel,
    LlmError,
    ToolCall,
    ToolSpec,
    Usage,
    classify_http,
    redact,
)

SECRET = "sk-test-0123456789abcdef"
BASES = {
    "openai_compatible": "https://api.example.com/v1",
    "anthropic": "https://api.anthropic.com",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}
KINDS = tuple(BASES)
IMAGE = ImagePart("image/png", "iVBORw0KGgo=")
WEATHER = ToolSpec("get_weather", "查询天气", {"type": "object", "properties": {"city": {"type": "string"}}})


class Recorder:
    """按顺序返回预设响应，并记录收到的请求。"""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        item = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(item, Exception):
            raise item
        status, body = item
        if isinstance(body, (dict, list)):
            return httpx2.Response(status, json=body)
        return httpx2.Response(status, text=body)

    @property
    def body(self) -> dict:
        return json.loads(self.requests[-1].content)


def _adapter(kind, recorder, base=None):
    return make_adapter(kind, base or BASES[kind], SECRET, transport=httpx2.MockTransport(recorder))


def _assert_no_key_in_url(recorder):
    for request in recorder.requests:
        assert SECRET not in str(request.url)
        assert "key" not in request.url.params


# ---------- 列表 ----------

def test_openai_list_sorted_deduped_and_bearer_header():
    rec = Recorder((200, {"object": "list", "data": [{"id": "qwen-plus"}, {"id": "deepseek-chat"}, {"id": "qwen-plus"}]}))
    models = _adapter("openai_compatible", rec, base="https://api.example.com/v1/").list_models()
    assert models == [ListedModel("deepseek-chat", None), ListedModel("qwen-plus", None)]
    request = rec.requests[0]
    assert (request.method, str(request.url)) == ("GET", "https://api.example.com/v1/models")
    assert request.headers["authorization"] == f"Bearer {SECRET}"
    _assert_no_key_in_url(rec)


def test_anthropic_list_pages_and_headers():
    rec = Recorder(
        (200, {"data": [{"id": "claude-sonnet-4-5", "display_name": "Claude Sonnet 4.5"}],
               "has_more": True, "first_id": "claude-sonnet-4-5", "last_id": "claude-sonnet-4-5"}),
        (200, {"data": [{"id": "claude-haiku-4-5", "display_name": "Claude Haiku 4.5"}],
               "has_more": False, "first_id": "claude-haiku-4-5", "last_id": "claude-haiku-4-5"}),
    )
    models = _adapter("anthropic", rec).list_models()
    assert models == [ListedModel("claude-haiku-4-5", "Claude Haiku 4.5"),
                      ListedModel("claude-sonnet-4-5", "Claude Sonnet 4.5")]
    first, second = rec.requests
    assert str(first.url) == "https://api.anthropic.com/v1/models"
    assert second.url.params["after_id"] == "claude-sonnet-4-5"
    for request in rec.requests:
        assert request.headers["x-api-key"] == SECRET
        assert request.headers["anthropic-version"] == "2023-06-01"
        assert "authorization" not in request.headers
    _assert_no_key_in_url(rec)


def test_anthropic_list_stops_after_max_pages():
    page = {"data": [{"id": "claude-x", "display_name": None}], "has_more": True, "last_id": "claude-x"}
    rec = Recorder((200, page))
    assert _adapter("anthropic", rec).list_models() == [ListedModel("claude-x", None)]
    assert len(rec.requests) == MAX_LIST_PAGES


def test_gemini_list_pages_filters_and_strips_prefix():
    rec = Recorder(
        (200, {"models": [
            {"name": "models/gemini-2.5-flash", "displayName": "Gemini 2.5 Flash",
             "supportedGenerationMethods": ["generateContent", "countTokens"]},
            {"name": "models/text-embedding-004", "displayName": "Text Embedding 004",
             "supportedGenerationMethods": ["embedContent"]},
        ], "nextPageToken": "page-2"}),
        (200, {"models": [
            {"name": "models/gemini-2.0-flash", "displayName": "Gemini 2.0 Flash",
             "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/aqa", "displayName": "AQA"},
        ]}),
    )
    models = _adapter("gemini", rec).list_models()
    assert models == [ListedModel("gemini-2.0-flash", "Gemini 2.0 Flash"),
                      ListedModel("gemini-2.5-flash", "Gemini 2.5 Flash")]
    first, second = rec.requests
    assert str(first.url) == "https://generativelanguage.googleapis.com/v1beta/models"
    assert second.url.params["pageToken"] == "page-2"
    for request in rec.requests:
        assert request.headers["x-goog-api-key"] == SECRET
    _assert_no_key_in_url(rec)


def test_gemini_list_stops_after_max_pages():
    page = {"models": [{"name": "models/gemini-x", "supportedGenerationMethods": ["generateContent"]}],
            "nextPageToken": "again"}
    rec = Recorder((200, page))
    assert _adapter("gemini", rec).list_models() == [ListedModel("gemini-x", None)]
    assert len(rec.requests) == MAX_LIST_PAGES


# ---------- 对话：OpenAI 兼容 ----------

def test_openai_chat_text_system_and_usage():
    rec = Recorder((200, {"model": "deepseek-chat", "choices": [{"message": {"role": "assistant", "content": "好"}}],
                          "usage": {"prompt_tokens": 12, "completion_tokens": 1, "total_tokens": 13}}))
    result = _adapter("openai_compatible", rec).chat(
        "deepseek-chat", [ChatMessage("system", "你是助手"), ChatMessage("user", "请只回复：好")], max_tokens=50)
    assert result.text == "好"
    assert result.tool_calls == ()
    assert result.model == "deepseek-chat"
    assert result.usage == Usage(12, 1)
    request = rec.requests[0]
    assert (request.method, str(request.url)) == ("POST", "https://api.example.com/v1/chat/completions")
    assert request.headers["authorization"] == f"Bearer {SECRET}"
    assert rec.body == {"model": "deepseek-chat", "max_tokens": 50, "messages": [
        {"role": "system", "content": "你是助手"}, {"role": "user", "content": "请只回复：好"}]}
    _assert_no_key_in_url(rec)


def test_openai_chat_image_structure():
    rec = Recorder((200, {"choices": [{"message": {"content": "红色"}}]}))
    result = _adapter("openai_compatible", rec).chat("qwen-vl-max", [ChatMessage("user", "什么颜色？", (IMAGE,))])
    assert result.text == "红色"
    assert result.model == "qwen-vl-max"
    assert result.usage == Usage(None, None)
    assert rec.body["messages"] == [{"role": "user", "content": [
        {"type": "text", "text": "什么颜色？"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgo="}},
    ]}]


def test_openai_chat_tools_and_tool_calls():
    rec = Recorder((200, {"choices": [{"message": {"content": None, "tool_calls": [
        {"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": "{\"city\": \"北京\"}"}},
    ]}}], "usage": {"prompt_tokens": 30, "completion_tokens": 8}}))
    result = _adapter("openai_compatible", rec).chat("qwen-plus", [ChatMessage("user", "北京天气")], tools=[WEATHER])
    assert result.text == ""
    assert result.tool_calls == (ToolCall("get_weather", {"city": "北京"}, "call_1"),)
    assert rec.body["tools"] == [{"type": "function", "function": {
        "name": "get_weather", "description": "查询天气", "parameters": WEATHER.parameters}}]


def test_openai_chat_bad_tool_arguments_is_provider_error():
    rec = Recorder((200, {"choices": [{"message": {"content": None, "tool_calls": [
        {"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": "{not json"}},
    ]}}]}))
    with pytest.raises(LlmError) as caught:
        _adapter("openai_compatible", rec).chat("qwen-plus", [ChatMessage("user", "北京天气")], tools=[WEATHER])
    assert caught.value.code == "provider_error"


# ---------- 对话：Claude ----------

def test_anthropic_chat_text_system_and_usage():
    rec = Recorder((200, {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-sonnet-4-5",
                          "content": [{"type": "text", "text": "好"}], "stop_reason": "end_turn",
                          "usage": {"input_tokens": 20, "output_tokens": 2}}))
    result = _adapter("anthropic", rec).chat("claude-sonnet-4-5", [
        ChatMessage("system", "你是助手"), ChatMessage("system", "回答要简短"),
        ChatMessage("user", "你好"), ChatMessage("assistant", "你好！"), ChatMessage("user", "请只回复：好"),
    ], max_tokens=64)
    assert (result.text, result.model, result.usage, result.tool_calls) == ("好", "claude-sonnet-4-5", Usage(20, 2), ())
    request = rec.requests[0]
    assert (request.method, str(request.url)) == ("POST", "https://api.anthropic.com/v1/messages")
    assert request.headers["x-api-key"] == SECRET
    assert request.headers["anthropic-version"] == "2023-06-01"
    assert rec.body == {"model": "claude-sonnet-4-5", "max_tokens": 64, "system": "你是助手\n\n回答要简短", "messages": [
        {"role": "user", "content": "你好"}, {"role": "assistant", "content": "你好！"},
        {"role": "user", "content": "请只回复：好"}]}
    _assert_no_key_in_url(rec)


def test_anthropic_chat_image_structure_and_no_system():
    rec = Recorder((200, {"model": "claude-sonnet-4-5", "content": [{"type": "text", "text": "红色"}],
                          "usage": {"input_tokens": 50, "output_tokens": 3}}))
    _adapter("anthropic", rec).chat("claude-sonnet-4-5", [ChatMessage("user", "什么颜色？", (IMAGE,))])
    assert "system" not in rec.body
    assert rec.body["messages"] == [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "iVBORw0KGgo="}},
        {"type": "text", "text": "什么颜色？"},
    ]}]


def test_anthropic_chat_tools_and_tool_use():
    rec = Recorder((200, {"model": "claude-sonnet-4-5", "stop_reason": "tool_use", "content": [
        {"type": "text", "text": "我来查一下。"},
        {"type": "tool_use", "id": "toolu_1", "name": "get_weather", "input": {"city": "北京"}},
    ], "usage": {"input_tokens": 300, "output_tokens": 40}}))
    result = _adapter("anthropic", rec).chat("claude-sonnet-4-5", [ChatMessage("user", "北京天气")], tools=[WEATHER])
    assert result.text == "我来查一下。"
    assert result.tool_calls == (ToolCall("get_weather", {"city": "北京"}, "toolu_1"),)
    assert rec.body["tools"] == [{"name": "get_weather", "description": "查询天气", "input_schema": WEATHER.parameters}]


# ---------- 对话：Gemini ----------

def test_gemini_chat_text_system_roles_and_usage():
    rec = Recorder((200, {"candidates": [{"content": {"role": "model", "parts": [{"text": "好"}]}, "finishReason": "STOP"}],
                          "usageMetadata": {"promptTokenCount": 9, "candidatesTokenCount": 1, "totalTokenCount": 10},
                          "modelVersion": "gemini-2.5-flash"}))
    result = _adapter("gemini", rec).chat("gemini-2.5-flash", [
        ChatMessage("system", "你是助手"), ChatMessage("user", "你好"), ChatMessage("assistant", "你好！"),
        ChatMessage("user", "请只回复：好"),
    ], max_tokens=32)
    assert (result.text, result.model, result.usage, result.tool_calls) == ("好", "gemini-2.5-flash", Usage(9, 1), ())
    request = rec.requests[0]
    assert (request.method, str(request.url)) == (
        "POST", "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent")
    assert request.headers["x-goog-api-key"] == SECRET
    assert rec.body == {
        "contents": [
            {"role": "user", "parts": [{"text": "你好"}]},
            {"role": "model", "parts": [{"text": "你好！"}]},
            {"role": "user", "parts": [{"text": "请只回复：好"}]},
        ],
        "systemInstruction": {"parts": [{"text": "你是助手"}]},
        "generationConfig": {"maxOutputTokens": 32},
    }
    _assert_no_key_in_url(rec)


def test_gemini_chat_image_structure():
    rec = Recorder((200, {"candidates": [{"content": {"parts": [{"text": "红色"}]}}]}))
    result = _adapter("gemini", rec).chat("gemini-2.5-flash", [ChatMessage("user", "什么颜色？", (IMAGE,))])
    assert (result.text, result.usage) == ("红色", Usage(None, None))
    assert "systemInstruction" not in rec.body
    assert rec.body["contents"] == [{"role": "user", "parts": [
        {"text": "什么颜色？"}, {"inline_data": {"mime_type": "image/png", "data": "iVBORw0KGgo="}},
    ]}]


def test_gemini_chat_tools_and_function_call():
    rec = Recorder((200, {"candidates": [{"content": {"role": "model", "parts": [
        {"functionCall": {"name": "get_weather", "args": {"city": "北京"}}},
    ]}}], "usageMetadata": {"promptTokenCount": 40, "candidatesTokenCount": 6}}))
    result = _adapter("gemini", rec).chat("gemini-2.5-flash", [ChatMessage("user", "北京天气")], tools=[WEATHER])
    assert result.text == ""
    assert result.tool_calls == (ToolCall("get_weather", {"city": "北京"}, None),)
    assert rec.body["tools"] == [{"functionDeclarations": [
        {"name": "get_weather", "description": "查询天气", "parameters": WEATHER.parameters}]}]


# ---------- 错误归类 ----------

ZHIPU_400 = {"error": {"code": "1211", "message": "模型不存在，请检查模型代码。"}}
ARK_400 = {"error": {"code": "InvalidEndpointOrModel.NotFound",
                     "message": "The model or endpoint doubao-x does not exist or you do not have access to it.",
                     "param": "", "type": "NotFound"}}

COMMON_CASES = [
    # (说明, 场景, 状态码, 正文, 期望)
    ("401", "chat", 401, {"error": {"message": "Incorrect API key provided"}}, "invalid_key"),
    ("403", "list", 403, {"error": {"message": "forbidden"}}, "invalid_key"),
    ("402", "chat", 402, {"error": {"message": "Insufficient Balance"}}, "quota_exceeded"),
    ("429 余额不足", "chat", 429, {"error": {"code": "1113", "message": "您的账户已欠费，请充值后重试。"}}, "quota_exceeded"),
    ("429 insufficient_quota", "chat", 429, {"error": {"code": "insufficient_quota", "message": "exceeded"}},
     "quota_exceeded"),
    ("429 Arrearage", "chat", 429, {"code": "Arrearage", "message": "Access denied"}, "quota_exceeded"),
    ("429 限流", "chat", 429, {"error": {"message": "Too many requests, please slow down"}}, "rate_limited"),
    ("404 列表", "list", 404, "404 page not found", "not_found"),
    ("404 列表 路径含 models", "list", 404, "Cannot GET /v1/models", "not_found"),
    ("404 对话 地址错", "chat", 404, "404 page not found", "not_found"),
    ("404 对话 模型", "chat", 404, {"error": {"message": "The model `x` does not exist", "code": "model_not_found"}},
     "model_not_found"),
    ("400 智谱", "chat", 400, ZHIPU_400, "model_not_found"),
    ("400 火山方舟", "chat", 400, ARK_400, "model_not_found"),
    ("400 model not found", "chat", 400, {"error": {"message": "Model Not Found"}}, "model_not_found"),
    ("400 其它", "chat", 400, {"error": {"message": "max_tokens is too large"}}, "bad_request"),
    ("500", "chat", 500, "Internal Server Error", "provider_error"),
    ("503 列表", "list", 503, "<html>bad gateway</html>", "provider_error"),
    ("529", "chat", 529, "overloaded", "provider_error"),
    ("422", "chat", 422, {"error": {"message": "unprocessable"}}, "bad_request"),
]


def _fail(kind, during, rec):
    adapter = _adapter(kind, rec)
    with pytest.raises(LlmError) as caught:
        if during == "list":
            adapter.list_models()
        else:
            adapter.chat("some-model", [ChatMessage("user", "你好")])
    error = caught.value
    assert error.code in ADAPTER_ERROR_CODES
    assert error.message and SECRET not in error.message
    return error


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("label, during, status, body, expected", COMMON_CASES, ids=[c[0] for c in COMMON_CASES])
def test_common_error_classification(kind, label, during, status, body, expected):
    error = _fail(kind, during, Recorder((status, body)))
    assert error.code == expected, label
    assert error.status == status


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("during", ["list", "chat"])
@pytest.mark.parametrize("exc, expected", [
    (httpx2.ReadTimeout("timed out"), "timeout"),
    (httpx2.ConnectTimeout("timed out"), "timeout"),
    (httpx2.ConnectError("[Errno 11001] getaddrinfo failed"), "unreachable"),
    (httpx2.RemoteProtocolError("peer closed connection"), "unreachable"),
])
def test_network_errors(kind, during, exc, expected):
    error = _fail(kind, during, Recorder(exc))
    assert (error.code, error.status) == (expected, None)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("during", ["list", "chat"])
@pytest.mark.parametrize("body", ["<html>hello</html>", {"unexpected": True}, {"data": "x", "models": 3, "choices": []}])
def test_malformed_success_body_is_provider_error(kind, during, body):
    assert _fail(kind, during, Recorder((200, body))).code == "provider_error"


@pytest.mark.parametrize("error_type, status, during, expected", [
    ("authentication_error", 400, "chat", "invalid_key"),
    ("permission_error", 400, "list", "invalid_key"),
    ("not_found_error", 404, "chat", "model_not_found"),
    ("not_found_error", 404, "list", "not_found"),
    ("rate_limit_error", 429, "chat", "rate_limited"),
    ("overloaded_error", 529, "chat", "provider_error"),
    ("api_error", 500, "chat", "provider_error"),
    ("invalid_request_error", 400, "chat", "bad_request"),
])
def test_anthropic_error_types(error_type, status, during, expected):
    body = {"type": "error", "error": {"type": error_type, "message": "Your quota of things: details"}}
    error = _fail("anthropic", during, Recorder((status, body)))
    assert error.code == expected
    if error_type == "overloaded_error":
        assert "服务繁忙" in error.message


@pytest.mark.parametrize("code, status, message, during, expected", [
    (400, "INVALID_ARGUMENT", "API key not valid. Please pass a valid API key.", "list", "invalid_key"),
    (403, "PERMISSION_DENIED", "Method doesn't allow unregistered callers.", "chat", "invalid_key"),
    (400, "UNAUTHENTICATED", "Request had invalid authentication credentials.", "chat", "invalid_key"),
    (429, "RESOURCE_EXHAUSTED", "You exceeded your current quota, please check your plan and billing details.",
     "chat", "quota_exceeded"),
    (429, "RESOURCE_EXHAUSTED", "Resource has been exhausted (e.g. check rate limits).", "chat", "rate_limited"),
    (404, "NOT_FOUND", "models/gemini-x is not found for API version v1beta.", "chat", "model_not_found"),
    (404, "NOT_FOUND", "Requested entity was not found.", "list", "not_found"),
    (400, "INVALID_ARGUMENT", "Invalid JSON payload received.", "chat", "bad_request"),
    (503, "UNAVAILABLE", "The model is overloaded. Please try again later.", "chat", "provider_error"),
])
def test_gemini_error_status(code, status, message, during, expected):
    body = {"error": {"code": code, "status": status, "message": message}}
    assert _fail("gemini", during, Recorder((code, body))).code == expected


# ---------- 密钥不外泄 ----------

@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("status, body", [
    (401, {"error": {"message": f"Incorrect API key provided: {SECRET}. You can find your API key at ..."}}),
    (400, {"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": f"API key not valid: {SECRET}"}}),
    (500, f"crash while handling key={SECRET}"),
    (200, f"not json {SECRET}"),
    (200, {"echo": SECRET}),
])
def test_key_never_leaks_into_errors(kind, status, body):
    for during in ("list", "chat"):
        error = _fail(kind, during, Recorder((status, body)))
        for text in (error.message, error.detail, str(error), repr(error)):
            assert SECRET not in text
            assert "0123456789abcdef" not in text


def test_redact_removes_secret_sk_strings_and_truncates():
    other = "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUV_wxyz-0123"
    text = f"bad key {SECRET} and {other}; short sk-abc stays"
    cleaned = redact(text, SECRET)
    assert SECRET not in cleaned and other not in cleaned
    assert "sk-abc stays" in cleaned
    assert redact("x" * 1000, None) == "x" * 300
    assert len(redact(("y" * 299) + SECRET, SECRET)) <= 300
    assert SECRET[:10] not in redact(("y" * 295) + SECRET, SECRET)
    assert redact("plain text", "") == "plain text"
    assert redact("plain AIza-key text", "AIza-key") == "plain **** text"


def test_classify_http_direct_and_error_str():
    error = classify_http(429, "Insufficient balance", during="chat", secret=None)
    assert (error.code, error.status) == ("quota_exceeded", 429)
    assert "quota_exceeded" in str(error)
    assert classify_http(404, '{"message":"模型不存在"}', during="chat", secret=None).code == "model_not_found"
    assert classify_http(404, '{"message":"模型不存在"}', during="list", secret=None).code == "not_found"


def test_make_adapter_rejects_unknown_kind():
    with pytest.raises(ValueError):
        make_adapter("cohere", "https://example.com", SECRET)
