"""工具回传、停止原因与跨轮状态：三家格式的请求体与解析，以及先解析目标再多次调用的统一入口。绝不访问真实网络。"""

import datetime
import json
import uuid
from typing import Literal

import httpx2
import pytest
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import event, select

from app.auth.models import User
from app.config import get_settings
from app.db import get_engine, get_sessionmaker
from app.errors import AppError
from app.llm import service
from app.llm.adapters import make_adapter
from app.llm.adapters.base import (
    FINISH_REASONS,
    ChatMessage,
    ImagePart,
    LlmError,
    ToolCall,
    ToolSpec,
    sanitize_schema_for_gemini,
)
from app.llm.capabilities import Capabilities
from tests.helpers import ready_user

SECRET = "sk-test-0123456789abcdef"
BASES = {
    "openai_compatible": "https://api.example.com/v1",
    "anthropic": "https://api.anthropic.com",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}
KINDS = tuple(BASES)
WEATHER = ToolSpec("get_weather", "查询天气", {"type": "object", "properties": {"city": {"type": "string"}}})
IMAGE = ImagePart("image/png", "iVBORw0KGgo=")


class Recorder:
    """总是返回同一个预设响应，并记录收到的请求。"""

    def __init__(self, status: int, body: dict):
        self.status, self.reply = status, body
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return httpx2.Response(self.status, json=self.reply)

    @property
    def body(self) -> dict:
        return json.loads(self.requests[-1].content)


def _adapter(kind, recorder):
    return make_adapter(kind, BASES[kind], SECRET, transport=httpx2.MockTransport(recorder))


OPENAI_TEXT = {"choices": [{"message": {"content": "好"}, "finish_reason": "stop"}]}
CLAUDE_TEXT = {"content": [{"type": "text", "text": "好"}], "stop_reason": "end_turn"}
GEMINI_TEXT = {"candidates": [{"content": {"parts": [{"text": "好"}]}, "finishReason": "STOP"}]}
TEXT_REPLY = {"openai_compatible": OPENAI_TEXT, "anthropic": CLAUDE_TEXT, "gemini": GEMINI_TEXT}


def test_finish_reasons_constant():
    assert FINISH_REASONS == ("stop", "tool_calls", "length", "content_filter", "other")


# ---------- OpenAI 兼容（含 DeepSeek 的 reasoning_content） ----------

def test_openai_parses_tool_calls_finish_reason_and_reasoning():
    rec = Recorder(200, {"choices": [{"finish_reason": "tool_calls", "message": {
        "role": "assistant", "content": None, "reasoning_content": "先查天气再回答",
        "tool_calls": [
            {"id": "call_1", "type": "function",
             "function": {"name": "get_weather", "arguments": "{\"city\": \"北京\"}"}},
            {"id": "call_2", "type": "function",
             "function": {"name": "get_weather", "arguments": "{\"city\": \"上海\"}"}},
        ]}}]})
    result = _adapter("openai_compatible", rec).chat("deepseek-chat", [ChatMessage("user", "北京和上海天气")],
                                                      tools=[WEATHER])
    assert result.tool_calls == (ToolCall("get_weather", {"city": "北京"}, "call_1"),
                                 ToolCall("get_weather", {"city": "上海"}, "call_2"))
    assert result.finish_reason == "tool_calls"
    assert result.provider_state == {"reasoning_content": "先查天气再回答"}


def test_openai_without_reasoning_has_no_provider_state():
    result = _adapter("openai_compatible", Recorder(200, OPENAI_TEXT)).chat("qwen-plus", [ChatMessage("user", "你好")])
    assert (result.text, result.finish_reason, result.provider_state) == ("好", "stop", None)


def test_openai_sends_tool_round_trip_and_reasoning_back():
    rec = Recorder(200, OPENAI_TEXT)
    calls = (ToolCall("get_weather", {"city": "北京"}, "call_1"), ToolCall("get_weather", {"city": "上海"}, "call_2"))
    _adapter("openai_compatible", rec).chat("deepseek-chat", [
        ChatMessage("system", "你是助手"),
        ChatMessage("user", "北京和上海天气"),
        ChatMessage("assistant", "", tool_calls=calls, provider_state={"reasoning_content": "先查天气"}),
        ChatMessage("tool", "{\"temp\": 20}", tool_call_id="call_1", tool_name="get_weather"),
        ChatMessage("tool", "{\"temp\": 25}", tool_call_id="call_2", tool_name="get_weather"),
        ChatMessage("assistant", "北京 20 度，上海 25 度。", provider_state={"reasoning_content": "整理结果"}),
        ChatMessage("user", "谢谢"),
    ], tools=[WEATHER])
    assert rec.body["messages"] == [
        {"role": "system", "content": "你是助手"},
        {"role": "user", "content": "北京和上海天气"},
        {"role": "assistant", "content": None, "reasoning_content": "先查天气", "tool_calls": [
            {"id": "call_1", "type": "function",
             "function": {"name": "get_weather", "arguments": "{\"city\": \"北京\"}"}},
            {"id": "call_2", "type": "function",
             "function": {"name": "get_weather", "arguments": "{\"city\": \"上海\"}"}},
        ]},
        {"role": "tool", "tool_call_id": "call_1", "content": "{\"temp\": 20}"},
        {"role": "tool", "tool_call_id": "call_2", "content": "{\"temp\": 25}"},
        {"role": "assistant", "content": "北京 20 度，上海 25 度。", "reasoning_content": "整理结果"},
        {"role": "user", "content": "谢谢"},
    ]


def test_openai_assistant_text_with_tool_calls_keeps_the_text():
    rec = Recorder(200, OPENAI_TEXT)
    _adapter("openai_compatible", rec).chat("qwen-plus", [
        ChatMessage("user", "北京天气"),
        ChatMessage("assistant", "我查一下", tool_calls=(ToolCall("get_weather", {}, "c1"),)),
        ChatMessage("tool", "晴", tool_call_id="c1", tool_name="get_weather"),
    ])
    assert rec.body["messages"][1] == {"role": "assistant", "content": "我查一下", "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "get_weather", "arguments": "{}"}}]}


@pytest.mark.parametrize("raw, expected", [
    ("stop", "stop"), ("tool_calls", "tool_calls"), ("length", "length"), ("content_filter", "content_filter"),
    ("insufficient_system_resource", "other"), (None, "other"),
])
def test_openai_finish_reason_mapping(raw, expected):
    reply = {"choices": [{"message": {"content": "好"}, "finish_reason": raw}]}
    assert _adapter("openai_compatible", Recorder(200, reply)).chat(
        "qwen-plus", [ChatMessage("user", "你好")]).finish_reason == expected


def test_openai_missing_finish_reason_is_other():
    reply = {"choices": [{"message": {"content": "好"}}]}
    assert _adapter("openai_compatible", Recorder(200, reply)).chat(
        "qwen-plus", [ChatMessage("user", "你好")]).finish_reason == "other"


def test_openai_tool_calls_with_stop_reason_report_tool_calls():
    # 个别兼容服务带了工具调用却报 stop；停止原因与工具调用保持一致，智能体循环不会漏掉工具调用
    reply = {"choices": [{"finish_reason": "stop", "message": {"content": None, "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "get_weather", "arguments": "{}"}}]}}]}
    assert _adapter("openai_compatible", Recorder(200, reply)).chat(
        "qwen-plus", [ChatMessage("user", "天气")], tools=[WEATHER]).finish_reason == "tool_calls"


def test_openai_tool_calls_without_ids_get_synthetic_ids():
    # 个别兼容服务的工具调用不带 id；合成一个本次回复内唯一的编号，历史才能原样回传
    reply = {"choices": [{"finish_reason": "tool_calls", "message": {"content": None, "tool_calls": [
        {"type": "function", "function": {"name": "get_weather", "arguments": "{\"city\": \"北京\"}"}},
        {"id": "call_x", "type": "function", "function": {"name": "get_weather", "arguments": "{}"}},
        {"id": "", "type": "function", "function": {"name": "get_weather", "arguments": "{}"}},
    ]}}]}
    result = _adapter("openai_compatible", Recorder(200, reply)).chat(
        "qwen-plus", [ChatMessage("user", "天气")], tools=[WEATHER])
    assert [call.call_id for call in result.tool_calls] == ["call-1", "call_x", "call-3"]
    rec = Recorder(200, OPENAI_TEXT)
    _adapter("openai_compatible", rec).chat("qwen-plus", [
        ChatMessage("user", "天气"), ChatMessage("assistant", "", tool_calls=result.tool_calls[:1]),
        ChatMessage("tool", "晴", tool_call_id="call-1", tool_name="get_weather")])
    assert rec.body["messages"][1]["tool_calls"][0]["id"] == "call-1"
    assert rec.body["messages"][2] == {"role": "tool", "tool_call_id": "call-1", "content": "晴"}


# ---------- Claude ----------

def test_anthropic_parses_tool_use_and_finish_reason():
    rec = Recorder(200, {"model": "claude-sonnet-4-5", "stop_reason": "tool_use", "content": [
        {"type": "text", "text": "我来查一下。"},
        {"type": "tool_use", "id": "toolu_1", "name": "get_weather", "input": {"city": "北京"}},
        {"type": "tool_use", "id": "toolu_2", "name": "get_weather", "input": {"city": "上海"}},
    ]})
    result = _adapter("anthropic", rec).chat("claude-sonnet-4-5", [ChatMessage("user", "天气")], tools=[WEATHER])
    assert result.tool_calls == (ToolCall("get_weather", {"city": "北京"}, "toolu_1"),
                                 ToolCall("get_weather", {"city": "上海"}, "toolu_2"))
    assert (result.text, result.finish_reason, result.provider_state) == ("我来查一下。", "tool_calls", None)


def test_anthropic_sends_tool_use_blocks_and_merges_tool_results():
    rec = Recorder(200, CLAUDE_TEXT)
    calls = (ToolCall("get_weather", {"city": "北京"}, "toolu_1"), ToolCall("get_weather", {"city": "上海"}, "toolu_2"))
    _adapter("anthropic", rec).chat("claude-sonnet-4-5", [
        ChatMessage("system", "你是助手"),
        ChatMessage("user", "北京和上海天气"),
        ChatMessage("assistant", "我来查一下。", tool_calls=calls),
        ChatMessage("tool", "{\"temp\": 20}", tool_call_id="toolu_1", tool_name="get_weather"),
        ChatMessage("tool", "{\"temp\": 25}", tool_call_id="toolu_2", tool_name="get_weather"),
        ChatMessage("assistant", "", tool_calls=(ToolCall("get_weather", {"city": "广州"}, "toolu_3"),)),
        ChatMessage("tool", "{\"temp\": 30}", tool_call_id="toolu_3", tool_name="get_weather"),
        ChatMessage("assistant", "都查好了。"),
        ChatMessage("user", "谢谢"),
    ], tools=[WEATHER])
    assert rec.body["system"] == "你是助手"
    assert rec.body["messages"] == [
        {"role": "user", "content": "北京和上海天气"},
        {"role": "assistant", "content": [
            {"type": "text", "text": "我来查一下。"},
            {"type": "tool_use", "id": "toolu_1", "name": "get_weather", "input": {"city": "北京"}},
            {"type": "tool_use", "id": "toolu_2", "name": "get_weather", "input": {"city": "上海"}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_1", "content": "{\"temp\": 20}"},
            {"type": "tool_result", "tool_use_id": "toolu_2", "content": "{\"temp\": 25}"},
        ]},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "toolu_3", "name": "get_weather", "input": {"city": "广州"}},
        ]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_3", "content": "{\"temp\": 30}"}]},
        {"role": "assistant", "content": "都查好了。"},
        {"role": "user", "content": "谢谢"},
    ]


def test_anthropic_merges_tool_results_with_following_user_text():
    rec = Recorder(200, CLAUDE_TEXT)
    _adapter("anthropic", rec).chat("claude-sonnet-4-5", [
        ChatMessage("user", "北京天气"),
        ChatMessage("assistant", "", tool_calls=(ToolCall("get_weather", {"city": "北京"}, "toolu_1"),)),
        ChatMessage("tool", "{\"temp\": 20}", tool_call_id="toolu_1", tool_name="get_weather"),
        ChatMessage("user", "顺便说一下明天呢"),
        ChatMessage("user", "看这张图", (IMAGE,)),
    ], tools=[WEATHER])
    assert rec.body["messages"] == [
        {"role": "user", "content": "北京天气"},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "toolu_1", "name": "get_weather", "input": {"city": "北京"}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_1", "content": "{\"temp\": 20}"},
            {"type": "text", "text": "顺便说一下明天呢"},
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "iVBORw0KGgo="}},
            {"type": "text", "text": "看这张图"},
        ]},
    ]


def test_anthropic_merges_consecutive_plain_user_messages():
    rec = Recorder(200, CLAUDE_TEXT)
    _adapter("anthropic", rec).chat("claude-sonnet-4-5", [ChatMessage("user", "第一句"), ChatMessage("user", "第二句")])
    assert rec.body["messages"] == [{"role": "user", "content": [
        {"type": "text", "text": "第一句"}, {"type": "text", "text": "第二句"}]}]


@pytest.mark.parametrize("raw, expected", [
    ("end_turn", "stop"), ("stop_sequence", "stop"), ("tool_use", "tool_calls"), ("max_tokens", "length"),
    ("refusal", "content_filter"), ("pause_turn", "other"), (None, "other"),
])
def test_anthropic_stop_reason_mapping(raw, expected):
    reply = {"content": [{"type": "text", "text": "好"}], "stop_reason": raw}
    assert _adapter("anthropic", Recorder(200, reply)).chat(
        "claude-sonnet-4-5", [ChatMessage("user", "你好")]).finish_reason == expected


# ---------- Gemini ----------

def test_gemini_parses_function_calls_with_synthetic_ids_and_signatures():
    rec = Recorder(200, {"candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": [
        {"text": "我来查一下。"},
        {"functionCall": {"name": "get_weather", "args": {"city": "北京"}}, "thoughtSignature": "sig-A"},
        {"functionCall": {"name": "get_weather", "args": {"city": "上海"}}},
        {"functionCall": {"id": "fc-9", "name": "get_weather", "args": {"city": "广州"}}},
    ]}}]})
    result = _adapter("gemini", rec).chat("gemini-3-flash", [ChatMessage("user", "天气")], tools=[WEATHER])
    assert result.tool_calls == (
        ToolCall("get_weather", {"city": "北京"}, "gemini-call-1", {"thoughtSignature": "sig-A"}),
        ToolCall("get_weather", {"city": "上海"}, "gemini-call-2"),
        ToolCall("get_weather", {"city": "广州"}, "fc-9"),
    )
    assert (result.text, result.finish_reason, result.provider_state) == ("我来查一下。", "tool_calls", None)


def test_gemini_sends_function_call_signature_and_function_responses_back():
    rec = Recorder(200, GEMINI_TEXT)
    calls = (ToolCall("get_weather", {"city": "北京"}, "gemini-call-1", {"thoughtSignature": "sig-A"}),
             ToolCall("get_weather", {"city": "上海"}, "gemini-call-2"))
    _adapter("gemini", rec).chat("gemini-3-flash", [
        ChatMessage("system", "你是助手"),
        ChatMessage("user", "北京和上海天气"),
        ChatMessage("assistant", "我来查一下。", tool_calls=calls),
        ChatMessage("tool", "{\"temp\": 20}", tool_call_id="gemini-call-1", tool_name="get_weather"),
        ChatMessage("tool", "接口暂时不可用", tool_call_id="gemini-call-2", tool_name="get_weather"),
        ChatMessage("assistant", "", tool_calls=(
            ToolCall("get_weather", {"city": "广州"}, "gemini-call-1", {"thoughtSignature": "sig-B"}),)),
        ChatMessage("tool", "[1, 2]", tool_call_id="gemini-call-1", tool_name="get_weather"),
        ChatMessage("assistant", "都查好了。"),
        ChatMessage("user", "谢谢"),
    ], tools=[WEATHER])
    assert rec.body["systemInstruction"] == {"parts": [{"text": "你是助手"}]}
    assert rec.body["contents"] == [
        {"role": "user", "parts": [{"text": "北京和上海天气"}]},
        {"role": "model", "parts": [
            {"text": "我来查一下。"},
            {"functionCall": {"name": "get_weather", "args": {"city": "北京"}}, "thoughtSignature": "sig-A"},
            {"functionCall": {"name": "get_weather", "args": {"city": "上海"}}},
        ]},
        {"role": "user", "parts": [
            {"functionResponse": {"name": "get_weather", "response": {"result": {"temp": 20}}}},
            {"functionResponse": {"name": "get_weather", "response": {"result": "接口暂时不可用"}}},
        ]},
        {"role": "model", "parts": [
            {"functionCall": {"name": "get_weather", "args": {"city": "广州"}}, "thoughtSignature": "sig-B"},
        ]},
        {"role": "user", "parts": [{"functionResponse": {"name": "get_weather", "response": {"result": [1, 2]}}}]},
        {"role": "model", "parts": [{"text": "都查好了。"}]},
        {"role": "user", "parts": [{"text": "谢谢"}]},
    ]


def test_gemini_merges_function_responses_with_following_user_text():
    rec = Recorder(200, GEMINI_TEXT)
    _adapter("gemini", rec).chat("gemini-2.5-flash", [
        ChatMessage("user", "北京天气"),
        ChatMessage("assistant", "", tool_calls=(ToolCall("get_weather", {"city": "北京"}, "gemini-call-1"),)),
        ChatMessage("tool", "{\"temp\": 20}", tool_call_id="gemini-call-1", tool_name="get_weather"),
        ChatMessage("user", "顺便说一下明天呢"),
        ChatMessage("user", "再看看这张", (IMAGE,)),
    ], tools=[WEATHER])
    assert rec.body["contents"] == [
        {"role": "user", "parts": [{"text": "北京天气"}]},
        {"role": "model", "parts": [{"functionCall": {"name": "get_weather", "args": {"city": "北京"}}}]},
        {"role": "user", "parts": [
            {"functionResponse": {"name": "get_weather", "response": {"result": {"temp": 20}}}},
            {"text": "顺便说一下明天呢"},
            {"text": "再看看这张"},
            {"inline_data": {"mime_type": "image/png", "data": "iVBORw0KGgo="}},
        ]},
    ]


def test_gemini_echoes_real_call_ids_but_not_synthetic_ones():
    rec = Recorder(200, GEMINI_TEXT)
    calls = (ToolCall("get_weather", {"city": "北京"}, "fc-9", {"thoughtSignature": "sig-A"}),
             ToolCall("get_weather", {"city": "上海"}, "gemini-call-2"))
    _adapter("gemini", rec).chat("gemini-3-flash", [
        ChatMessage("user", "天气"),
        ChatMessage("assistant", "", tool_calls=calls),
        ChatMessage("tool", "{\"temp\": 20}", tool_call_id="fc-9", tool_name="get_weather"),
        ChatMessage("tool", "{\"temp\": 25}", tool_call_id="gemini-call-2", tool_name="get_weather"),
    ], tools=[WEATHER])
    assert rec.body["contents"][1:] == [
        {"role": "model", "parts": [
            {"functionCall": {"id": "fc-9", "name": "get_weather", "args": {"city": "北京"}},
             "thoughtSignature": "sig-A"},
            {"functionCall": {"name": "get_weather", "args": {"city": "上海"}}},
        ]},
        {"role": "user", "parts": [
            {"functionResponse": {"id": "fc-9", "name": "get_weather", "response": {"result": {"temp": 20}}}},
            {"functionResponse": {"name": "get_weather", "response": {"result": {"temp": 25}}}},
        ]},
    ]


@pytest.mark.parametrize("raw, expected", [
    ("STOP", "stop"), ("MAX_TOKENS", "length"), ("SAFETY", "content_filter"), ("RECITATION", "content_filter"),
    ("PROHIBITED_CONTENT", "content_filter"), ("SPII", "content_filter"), ("BLOCKLIST", "content_filter"),
    ("MALFORMED_FUNCTION_CALL", "other"), ("OTHER", "other"), (None, "other"),
])
def test_gemini_finish_reason_mapping(raw, expected):
    candidate = {"content": {"parts": [{"text": "好"}]}}
    if raw is not None:
        candidate["finishReason"] = raw
    assert _adapter("gemini", Recorder(200, {"candidates": [candidate]})).chat(
        "gemini-2.5-flash", [ChatMessage("user", "你好")]).finish_reason == expected


class _Portion(BaseModel):
    amount: float = Field(description="克数", ge=0)
    unit: Literal["g"] = "g"


class _MealArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", title="记录一餐")

    food: str = Field(description="食物名称", examples=["米饭"])
    main: _Portion = Field(description="主食份量")
    extra: _Portion | None = None
    sides: list[_Portion] = []
    eaten_on: datetime.date | None = None
    eaten_at: datetime.datetime
    kind: Literal["早餐", "午餐"] = "午餐"
    title: str = Field(default="", description="名为 title 的参数不能被当作关键字去掉")
    tags: dict[str, int] = Field(default_factory=dict, description="自由键值")


_SANITIZED_MEAL = {
    "type": "object",
    "properties": {
        "food": {"type": "string", "description": "食物名称"},
        "main": {"type": "object", "description": "主食份量", "properties": {
            "amount": {"type": "number", "description": "克数"},
            "unit": {"type": "string", "enum": ["g"]},
        }, "required": ["amount"]},
        "extra": {"type": "object", "nullable": True, "properties": {
            "amount": {"type": "number", "description": "克数"},
            "unit": {"type": "string", "enum": ["g"]},
        }, "required": ["amount"]},
        "sides": {"type": "array", "items": {"type": "object", "properties": {
            "amount": {"type": "number", "description": "克数"},
            "unit": {"type": "string", "enum": ["g"]},
        }, "required": ["amount"]}},
        "eaten_on": {"type": "string", "nullable": True},
        "eaten_at": {"type": "string", "format": "date-time"},
        "kind": {"type": "string", "enum": ["早餐", "午餐"]},
        "title": {"type": "string", "description": "名为 title 的参数不能被当作关键字去掉"},
        "tags": {"type": "object", "description": "自由键值"},  # 自由键值对象：保留为没有 properties 的 object
    },
    "required": ["food", "main", "eaten_at"],
}
_GEMINI_UNKNOWN_KEYS = {"title", "additionalProperties", "$defs", "$ref", "default", "examples", "const", "minimum",
                        "allOf", "$schema"}


def _keywords(schema):
    """收集结构里出现的关键字（properties 下面是参数名，不算关键字）。"""
    found = set()
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key == "properties":
                for sub in value.values():
                    found |= _keywords(sub)
            else:
                found.add(key)
                found |= _keywords(value)
    elif isinstance(schema, list):
        for item in schema:
            found |= _keywords(item)
    return found


def test_sanitize_schema_for_gemini_inlines_defs_and_drops_unknown_keys():
    raw = _MealArgs.model_json_schema()
    assert {"title", "additionalProperties", "$defs"} <= set(raw)  # 确认用来测试的结构确实带着这些键
    sanitized = sanitize_schema_for_gemini(raw)
    assert sanitized == _SANITIZED_MEAL
    assert not _keywords(sanitized) & _GEMINI_UNKNOWN_KEYS
    assert "$defs" in raw  # 不改动传入的结构


def test_sanitize_schema_handles_allof_ref_type_lists_and_rejects_recursion():
    schema = {"type": "object", "properties": {
        "a": {"allOf": [{"$ref": "#/definitions/X"}], "description": "包了一层"},
        "b": {"type": ["integer", "null"], "format": "int64"},
        "c": {"type": "string", "format": "uuid"},
        "d": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
    }, "definitions": {"X": {"type": "string", "title": "X"}}}
    assert sanitize_schema_for_gemini(schema) == {"type": "object", "properties": {
        "a": {"type": "string", "description": "包了一层"},
        "b": {"type": "integer", "nullable": True, "format": "int64"},
        "c": {"type": "string"},
        "d": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
    }}
    recursive = {"$ref": "#/$defs/Node", "$defs": {"Node": {"type": "object", "properties": {
        "child": {"$ref": "#/$defs/Node"}}}}}
    with pytest.raises(ValueError):
        sanitize_schema_for_gemini(recursive)


def test_gemini_tool_declaration_uses_sanitized_parameters():
    rec = Recorder(200, GEMINI_TEXT)
    meal = ToolSpec("log_meal", "记录一餐", _MealArgs.model_json_schema())
    empty = ToolSpec("today_summary", "今日汇总", {"type": "object", "properties": {}, "additionalProperties": False})
    _adapter("gemini", rec).chat("gemini-2.5-flash", [ChatMessage("user", "记一下午饭")], tools=[meal, empty])
    assert rec.body["tools"] == [{"functionDeclarations": [
        {"name": "log_meal", "description": "记录一餐", "parameters": _SANITIZED_MEAL},
        {"name": "today_summary", "description": "今日汇总"},  # 没有参数时不带 parameters（Gemini 不接受空 properties）
    ]}]
    assert not _keywords(rec.body["tools"][0]["functionDeclarations"][0]["parameters"]) & _GEMINI_UNKNOWN_KEYS


# ---------- 消息组合校验：统一报 LlmError("bad_request")，不发请求 ----------

BAD_MESSAGES = [
    ("助手带图片", ChatMessage("assistant", "看", (IMAGE,))),
    ("系统带图片", ChatMessage("system", "看", (IMAGE,))),
    ("工具带图片", ChatMessage("tool", "{}", (IMAGE,), tool_call_id="c1", tool_name="get_weather")),
    ("用户带工具调用", ChatMessage("user", "你好", tool_calls=(ToolCall("get_weather", {}, "c1"),))),
    ("用户带跨轮状态", ChatMessage("user", "你好", provider_state={"reasoning_content": "x"})),
    ("工具带跨轮状态", ChatMessage("tool", "{}", tool_call_id="c1", tool_name="get_weather", provider_state={"a": 1})),
    ("工具缺调用编号", ChatMessage("tool", "{}", tool_name="get_weather")),
    ("工具缺工具名", ChatMessage("tool", "{}", tool_call_id="c1")),
    ("非工具消息带调用编号", ChatMessage("user", "你好", tool_call_id="c1")),
    ("非工具消息带工具名", ChatMessage("assistant", "好", tool_name="get_weather")),
    ("未知角色", ChatMessage("robot", "你好")),  # type: ignore[arg-type]
]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("label, bad", BAD_MESSAGES, ids=[label for label, _ in BAD_MESSAGES])
def test_invalid_message_combinations_are_bad_request_without_sending(kind, label, bad):
    rec = Recorder(200, TEXT_REPLY[kind])
    with pytest.raises(LlmError) as caught:
        _adapter(kind, rec).chat("m", [ChatMessage("user", "开始"), bad])
    assert caught.value.code == "bad_request"
    assert rec.requests == []


@pytest.mark.parametrize("kind", ["openai_compatible", "anthropic"])
def test_tool_calls_without_ids_are_bad_request_for_id_based_formats(kind):
    rec = Recorder(200, TEXT_REPLY[kind])
    with pytest.raises(LlmError) as caught:
        _adapter(kind, rec).chat("m", [ChatMessage("user", "天气"), ChatMessage(
            "assistant", "", tool_calls=(ToolCall("get_weather", {}, None),))])
    assert caught.value.code == "bad_request"
    assert rec.requests == []


# ---------- 统一调用入口：先解析目标，循环里多次调用不再查库 ----------

BASE = "http://127.0.0.1:9/v1"


class FakeOpenAI:
    def __init__(self):
        self.requests: list[httpx2.Request] = []
        self.reply = {"choices": [{"message": {"content": "好"}, "finish_reason": "stop"}], "model": "deepseek-chat"}

    def __call__(self, request):
        self.requests.append(request)
        return httpx2.Response(200, json=self.reply)

    def factory(self, kind, base_url, api_key):
        return make_adapter(kind, base_url, api_key, transport=httpx2.MockTransport(self))


def _setup(client, *, overrides=None, purpose="chat"):
    headers = ready_user(client, "alice")
    response = client.post("/api/llm/providers", headers=headers, json={
        "name": "我的DeepSeek", "kind": "openai_compatible", "base_url": BASE, "api_key": SECRET})
    assert response.status_code == 201, response.text
    provider = response.json()
    response = client.post(f"/api/llm/providers/{provider['id']}/models", json={"model_id": "deepseek-chat"},
                           headers=headers)
    assert response.status_code == 201, response.text
    model = response.json()
    if overrides:
        client.patch(f"/api/llm/models/{model['id']}", json=overrides, headers=headers)
    response = client.put(f"/api/llm/assignments/{purpose}", json={"model_id": model["id"]}, headers=headers)
    assert response.status_code == 200, response.text
    with get_sessionmaker()() as db:
        user_id = db.scalar(select(User.id).where(User.username == "alice"))
    return user_id, provider, model, headers


def _capture_sql():
    statements: list[str] = []

    def capture(conn, cursor, statement, *args):
        statements.append(statement)

    return statements, capture


def test_resolve_target_fields_and_repr_hide_the_key(client):
    user_id, provider, model, _headers = _setup(client)
    target = service.resolve_target(user_id, "chat")
    assert isinstance(target, service.ResolvedTarget)
    assert (target.kind, target.base_url, target.model_id, target.provider_name, target.model_pk) == (
        "openai_compatible", BASE, "deepseek-chat", provider["name"], uuid.UUID(model["id"]))
    assert target.api_key == SECRET
    assert isinstance(target.capabilities, Capabilities)
    assert SECRET not in repr(target)
    with pytest.raises(AttributeError):
        target.model_id = "other"  # type: ignore[misc]


def test_complete_with_target_does_not_touch_the_database(client):
    user_id, provider, model, _headers = _setup(client)
    fake = FakeOpenAI()
    target = service.resolve_target(user_id, "chat")
    statements, capture = _capture_sql()
    engine = get_engine()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        messages = [ChatMessage("user", "天气"),
                    ChatMessage("assistant", "", tool_calls=(ToolCall("get_weather", {}, "c1"),),
                                provider_state={"reasoning_content": "想"}),
                    ChatMessage("tool", "{}", tool_call_id="c1", tool_name="get_weather")]
        for _ in range(3):
            done = service.complete(user_id, "chat", messages, tools=(WEATHER,), factory=fake.factory, target=target)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert statements == []
    assert len(fake.requests) == 3
    assert (done.result.text, done.result.finish_reason, done.model_id, done.model_pk, done.provider_name) == (
        "好", "stop", "deepseek-chat", uuid.UUID(model["id"]), provider["name"])
    assert json.loads(fake.requests[-1].content)["messages"][1]["reasoning_content"] == "想"


def test_complete_with_target_still_checks_capabilities(client):
    user_id, *_rest = _setup(client, overrides={"tools": False, "vision": False})
    fake = FakeOpenAI()
    target = service.resolve_target(user_id, "chat")
    with pytest.raises(AppError) as caught:
        service.complete(user_id, "chat", [ChatMessage("user", "你好")], tools=(WEATHER,), factory=fake.factory,
                         target=target)
    assert caught.value.code == "llm_model_lacks_tools"
    with pytest.raises(AppError) as caught:
        service.complete(user_id, "chat", [ChatMessage("user", "看图", (IMAGE,))], factory=fake.factory,
                         target=target)
    assert caught.value.code == "llm_model_lacks_vision"
    with pytest.raises(AppError) as caught:
        service.complete(user_id, "vision", [ChatMessage("user", "看")], factory=fake.factory, target=target)
    assert caught.value.code == "llm_model_lacks_vision"
    assert fake.requests == []


def test_complete_with_target_rechecks_the_address(client, monkeypatch):
    user_id, *_rest = _setup(client)
    fake = FakeOpenAI()
    target = service.resolve_target(user_id, "chat")
    monkeypatch.setattr(get_settings(), "llm_allow_private_hosts", False)
    with pytest.raises(AppError) as caught:
        service.complete(user_id, "chat", [ChatMessage("user", "你好")], factory=fake.factory, target=target)
    assert caught.value.code == "llm_invalid_url"
    assert fake.requests == []


def test_resolve_target_checks_configuration_and_purpose(client):
    user_id, _provider, model, headers = _setup(client)
    client.patch(f"/api/llm/models/{model['id']}", json={"chat": False}, headers=headers)  # 分配后再改标注
    with pytest.raises(AppError) as caught:
        service.resolve_target(user_id, "chat")
    assert caught.value.code == "llm_model_not_chat"
    with pytest.raises(AppError) as caught:
        service.resolve_target(user_id, "vision")
    assert caught.value.code == "llm_not_configured"
    with pytest.raises(AppError) as caught:
        service.resolve_target(user_id, "drawing")
    assert caught.value.code == "llm_unknown_purpose"


def test_resolve_target_refuses_vision_purpose_without_vision(client):
    user_id, _provider, model, headers = _setup(client, purpose="vision", overrides={"vision": True})
    client.patch(f"/api/llm/models/{model['id']}", json={"vision": False}, headers=headers)  # 分配后再改标注
    with pytest.raises(AppError) as caught:
        service.resolve_target(user_id, "vision")
    assert caught.value.code == "llm_model_lacks_vision"


def test_complete_maps_adapter_bad_request_for_bad_messages(client):
    user_id, *_rest = _setup(client)
    fake = FakeOpenAI()
    with pytest.raises(AppError) as caught:
        service.complete(user_id, "chat", [ChatMessage("tool", "{}", tool_name="get_weather")], factory=fake.factory)
    assert caught.value.code == "llm_bad_request"
    assert fake.requests == []
