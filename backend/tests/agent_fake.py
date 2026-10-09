"""智能体测试用的模拟模型服务：基于 MockTransport，按脚本依次回复，绝不访问真实网络。

支持 OpenAI 兼容格式（/chat/completions）与 Claude 格式（/v1/messages）。脚本的每一步是：
- say(text)：一段文字回答；
- call(name, args, ...)：一次回复里的一个或多个工具调用（可附带文字）；
- echo(header)：回显系统指令里以 header 开头的那一段；
- fail(status)：返回错误状态码。
脚本用完后一律回答 DEFAULT_TEXT。每次请求都记录模型名、系统指令、消息与工具声明。
"""

import json
from dataclasses import dataclass, field
from typing import Any

import httpx2
import pytest

from app.llm import service
from app.llm.adapters import make_adapter

SECRET = "sk-test-0123456789abcdef"
BASE_URLS = {"openai_compatible": "http://127.0.0.1:9/v1", "anthropic": "http://127.0.0.1:9"}
MODEL_IDS = {"openai_compatible": "deepseek-chat", "anthropic": "claude-sonnet-4-5"}
DEFAULT_TEXT = "好的。"


@dataclass(frozen=True)
class Step:
    text: str = ""
    calls: tuple[tuple[str, dict], ...] = ()
    echo: str | None = None
    status: int = 200
    reasoning: str | None = None  # OpenAI 兼容格式的 reasoning_content（DeepSeek 思考模式）


def say(text: str) -> Step:
    return Step(text=text)


def call(name: str, args: dict | None = None, *more: tuple[str, dict], text: str = "",
         reasoning: str | None = None) -> Step:
    return Step(text=text, calls=((name, args or {}), *more), reasoning=reasoning)


def echo(header: str) -> Step:
    return Step(echo=header)


def fail(status: int = 500) -> Step:
    return Step(status=status)


@dataclass
class Recorded:
    kind: str
    model: str
    system: str
    messages: list[dict]
    tools: list[dict]  # 统一成 {"name", "description", "parameters"}
    body: dict = field(repr=False)

    @property
    def tool_names(self) -> list[str]:
        return [tool["name"] for tool in self.tools]

    def text(self) -> str:
        """整个请求体的文字（含系统指令、消息与工具结果），供包含关系断言。"""
        return json.dumps(self.body, ensure_ascii=False)


class ScriptedModel:
    def __init__(self):
        self.script: list[Step] = []
        self.requests: list[Recorded] = []
        self.sessions: list = []  # 测试登记的数据库会话；每次请求时记下它们是否开着事务
        self.in_transaction: list[bool] = []

    def add(self, *steps: Step) -> None:
        self.script.extend(steps)

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.in_transaction.append(any(session.in_transaction() for session in self.sessions))
        path = request.url.path
        body = json.loads(request.content)
        if path.endswith("/chat/completions"):
            kind = "openai_compatible"
            messages = body["messages"]
            system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
            tools = [{"name": t["function"]["name"], "description": t["function"]["description"],
                      "parameters": t["function"]["parameters"]} for t in body.get("tools", [])]
        elif path.endswith("/v1/messages"):
            kind = "anthropic"
            messages = body["messages"]
            system = body.get("system", "")
            tools = [{"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}
                     for t in body.get("tools", [])]
        else:
            return httpx2.Response(404, text=f"Cannot {request.method} {path}")
        self.requests.append(Recorded(kind, body["model"], system, messages, tools, body))
        step = self.script.pop(0) if self.script else say(DEFAULT_TEXT)
        if step.status != 200:
            return httpx2.Response(step.status, json={"error": {"message": "scripted failure", "type": "server_error"}})
        text = step.text
        if step.echo is not None:
            text = next(section for section in system.split("\n\n") if section.startswith(step.echo))
        step_number = len(self.requests)
        if kind == "openai_compatible":
            return httpx2.Response(200, json=_openai_reply(body["model"], text, step, step_number))
        return httpx2.Response(200, json=_claude_reply(body["model"], text, step, step_number))


def _openai_reply(model: str, text: str, step: Step, number: int) -> dict:
    message: dict[str, Any] = {"role": "assistant", "content": text or None}
    if step.calls:
        message["tool_calls"] = [
            {"id": f"call-{number}-{i}", "type": "function",
             "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}
            for i, (name, args) in enumerate(step.calls, start=1)
        ]
    if step.reasoning is not None:
        message["reasoning_content"] = step.reasoning
    return {"model": model, "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "choices": [{"message": message, "finish_reason": "tool_calls" if step.calls else "stop"}]}


def _claude_reply(model: str, text: str, step: Step, number: int) -> dict:
    content: list[dict] = [{"type": "text", "text": text}] if text else []
    content += [{"type": "tool_use", "id": f"toolu_{number}_{i}", "name": name, "input": args}
                for i, (name, args) in enumerate(step.calls, start=1)]
    return {"model": model, "usage": {"input_tokens": 10, "output_tokens": 5}, "content": content,
            "stop_reason": "tool_use" if step.calls else "end_turn"}


def connect(client, headers: dict[str, str], kind: str = "openai_compatible", model_id: str | None = None) -> None:
    """为用户建立模型服务与模型，并把它设为“日常对话”用途的模型。"""
    provider = client.post("/api/llm/providers", headers=headers, json={
        "name": f"模拟{kind}{model_id or ''}", "kind": kind, "base_url": BASE_URLS[kind], "api_key": SECRET})
    assert provider.status_code == 201, provider.text
    model = client.post(f"/api/llm/providers/{provider.json()['id']}/models", headers=headers,
                        json={"model_id": model_id or MODEL_IDS[kind]})
    assert model.status_code == 201, model.text
    assigned = client.put("/api/llm/assignments/chat", json={"model_id": model.json()["id"]}, headers=headers)
    assert assigned.status_code == 200, assigned.text


@pytest.fixture
def scripted(client):
    """覆盖 get_adapter_factory：所有用户的模型请求都由同一个 ScriptedModel 回答。"""
    model = ScriptedModel()

    def factory(kind, base_url, api_key):
        return make_adapter(kind, base_url, api_key, transport=httpx2.MockTransport(model))

    client.app.dependency_overrides[service.get_adapter_factory] = lambda: factory
    yield model
    client.app.dependency_overrides.pop(service.get_adapter_factory, None)
