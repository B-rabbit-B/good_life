"""拉取模型、连通性测试与统一调用入口：用真实适配器加 MockTransport 假服务走通完整链路，绝不访问真实网络。"""

import base64
import json
import uuid

import httpx2
import pytest
from sqlalchemy import event, inspect, select

from app.auth.models import User
from app.config import get_settings
from app.db import get_db, get_engine, get_sessionmaker
from app.errors import AppError
from app.llm import service
from app.llm.adapters import make_adapter
from app.llm.adapters.base import ADAPTER_ERROR_CODES, ChatMessage, ToolSpec
from app.llm.models import LlmProvider
from tests.helpers import ready_user

SECRET = "sk-test-0123456789abcdef"
BASE = "http://127.0.0.1:9/v1"
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32).decode()


def _echo_key(status):
    """把收到的密钥原样写进错误正文，检验密钥不会经由错误信息泄露。"""

    def reply(request):
        key = request.headers.get("authorization", "").removeprefix("Bearer ") or request.headers.get("x-api-key")
        return status, {"error": {"message": f"Incorrect API key provided: {key}", "type": "invalid_request_error"}}

    return reply


class FakeLlm:
    """可编程的假模型服务：按路径给出预设响应（状态码与正文、可调用对象或异常），并记下收到的每个请求。"""

    def __init__(self):
        self.models = ["deepseek-chat", "qwen-vl-max"]
        self.list_reply = None
        self.chat_reply = None
        self.requests: list[httpx2.Request] = []
        self.sessions: list = []  # 接口用到的数据库会话，用来检查调用服务时没有占着事务
        self.in_transaction: list[bool] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        self.in_transaction.append(any(session.in_transaction() for session in self.sessions))
        path = request.url.path
        if request.method == "GET" and path.endswith("/models"):
            reply = self.list_reply or (200, {"object": "list", "data": [{"id": m} for m in self.models]})
        elif request.method == "POST" and path.endswith(("/chat/completions", "/v1/messages")):
            model = json.loads(request.content)["model"]
            reply = self.chat_reply or (200, {"model": model, "usage": {"prompt_tokens": 9, "completion_tokens": 1},
                                              "choices": [{"message": {"role": "assistant", "content": "好"}}]})
        else:
            reply = (404, f"Cannot {request.method} {path}")
        if callable(reply):
            reply = reply(request)
        if isinstance(reply, Exception):
            raise reply
        status, body = reply
        if isinstance(body, dict):
            return httpx2.Response(status, json=body)
        return httpx2.Response(status, text=body)

    @property
    def chat_bodies(self) -> list[dict]:
        return [json.loads(r.content) for r in self.requests if r.method == "POST"]


@pytest.fixture
def fake(client):
    fake = FakeLlm()

    def factory(kind, base_url, api_key):
        return make_adapter(kind, base_url, api_key, transport=httpx2.MockTransport(fake))

    def tracked_db():
        session = get_sessionmaker()()
        fake.sessions.append(session)
        try:
            yield session
        finally:
            session.close()

    client.app.dependency_overrides[service.get_adapter_factory] = lambda: factory
    client.app.dependency_overrides[get_db] = tracked_db
    yield fake
    # 每个用例结束时都检查：假服务收到请求的那一刻，没有任何数据库会话开着事务
    assert fake.in_transaction == [False] * len(fake.requests)


def _provider(client, headers, name="我的DeepSeek", kind="openai_compatible", url=BASE):
    response = client.post("/api/llm/providers", headers=headers,
                           json={"name": name, "kind": kind, "base_url": url, "api_key": SECRET})
    assert response.status_code == 201, response.text
    return response.json()


def _add_model(client, headers, provider, model_id):
    response = client.post(f"/api/llm/providers/{provider['id']}/models", json={"model_id": model_id},
                           headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _assign(client, headers, purpose, model):
    response = client.put(f"/api/llm/assignments/{purpose}", json={"model_id": model["id"]}, headers=headers)
    assert response.status_code == 200, response.text


def _chat(client, headers, purpose="chat", text="你好", images=(), **extra):
    message = {"role": "user", "text": text}
    if images:
        message["images"] = [{"mime_type": "image/png", "data_base64": data} for data in images]
    return client.post("/api/llm/chat", json={"purpose": purpose, "messages": [message], **extra}, headers=headers)


def _test_unsaved(client, headers, model_id=None, kind="openai_compatible", url=BASE):
    body = {"kind": kind, "base_url": url, "api_key": SECRET}
    if model_id is not None:
        body["model_id"] = model_id
    response = client.post("/api/llm/providers/test", json=body, headers=headers)
    assert response.status_code == 200, response.text
    assert SECRET not in response.text
    return response.json()


# ---------- 验收第 1 条：获取模型 ----------

def test_fetch_models_adds_new_and_keeps_manual(client, fake):
    headers = ready_user(client, "alice")
    provider = _provider(client, headers)
    manual = _add_model(client, headers, provider, "deepseek-chat")
    client.patch(f"/api/llm/models/{manual['id']}", json={"vision": True}, headers=headers)
    fake.models = ["qwen-vl-max", "deepseek-chat", "qwen-plus"]

    fetched = client.post(f"/api/llm/providers/{provider['id']}/fetch-models", headers=headers)
    assert fetched.status_code == 200, fetched.text
    body = fetched.json()
    assert (body["added"], body["total"], body["skipped"]) == (2, 3, 0)
    assert [m["model_id"] for m in body["models"]] == ["deepseek-chat", "qwen-plus", "qwen-vl-max"]
    kept = body["models"][0]
    assert (kept["id"], kept["source"], kept["overrides"]["vision"]) == (manual["id"], "manual", True)
    assert {m["source"] for m in body["models"][1:]} == {"fetched"}

    again = client.post(f"/api/llm/providers/{provider['id']}/fetch-models", headers=headers).json()
    assert (again["added"], again["total"]) == (0, 3)
    assert again["models"] == body["models"]

    fake.models = ["qwen-plus"]  # 列表里消失的模型不删除
    shrunk = client.post(f"/api/llm/providers/{provider['id']}/fetch-models", headers=headers).json()
    assert (shrunk["added"], shrunk["total"]) == (0, 1)
    listed = client.get(f"/api/llm/providers/{provider['id']}/models", headers=headers).json()
    assert [m["model_id"] for m in listed] == ["deepseek-chat", "qwen-plus", "qwen-vl-max"]
    assert listed[0]["overrides"]["vision"] is True


def test_fetch_models_failure_is_readable(client, fake):
    headers = ready_user(client, "alice")
    provider = _provider(client, headers)
    fake.list_reply = (404, "Cannot GET /v1/models")
    failed = client.post(f"/api/llm/providers/{provider['id']}/fetch-models", headers=headers)
    assert (failed.status_code, failed.json()["error"]["code"]) == (400, "llm_listing_unsupported_or_bad_url")
    assert "手动添加" in failed.json()["error"]["message"]
    assert client.get(f"/api/llm/providers/{provider['id']}/models", headers=headers).json() == []


# ---------- 验收第 4 条：连通性测试 ----------

_ANTHROPIC_404 = (404, {"type": "error", "error": {"type": "not_found_error", "message": "Not Found"}})


@pytest.mark.parametrize("name, kind, list_reply, chat_reply, conclusion", [
    ("密钥错误", "openai_compatible", _echo_key(401), _echo_key(401), "invalid_key"),
    ("地址不可达", "openai_compatible", httpx2.ConnectError("refused"), None, "bad_url"),
    ("地址错误", "openai_compatible", (404, "Cannot GET /v1/models"), (404, "Cannot POST /v1/chat/completions"),
     "bad_url"),
    ("地址错误（Claude）", "anthropic", _ANTHROPIC_404, _ANTHROPIC_404, "bad_url"),
    ("模型不可用", "openai_compatible", None,
     (404, {"error": {"message": "The model `nope` does not exist", "code": "model_not_found"}}), "model_unavailable"),
    ("余额不足", "openai_compatible", None, (402, {"error": {"message": "Insufficient Balance"}}), "quota_exceeded"),
    ("超时", "openai_compatible", httpx2.ReadTimeout("slow"), None, "timeout"),
])
def test_connection_test_conclusions(client, fake, name, kind, list_reply, chat_reply, conclusion):
    headers = ready_user(client, "alice")
    fake.list_reply, fake.chat_reply = list_reply, chat_reply
    report = _test_unsaved(client, headers, model_id="nope", kind=kind)
    assert report["conclusion"] == conclusion, (name, report)
    assert report["ok"] is False
    assert report["listing"]["ok"] is False or report["chat"]["ok"] is False
    if report["chat"] is not None:  # 对话一步决定结论时，对话步骤的 code 与说明都与结论一致
        assert report["chat"]["code"] == f"llm_{conclusion}"
        assert report["chat"]["message"] == report["message"]
    assert report["message"] and any("一" <= ch <= "鿿" for ch in report["message"])


def test_connection_test_six_failures_are_distinct(client, fake):
    headers = ready_user(client, "alice")
    scenarios = [
        (_echo_key(401), _echo_key(401)),
        (httpx2.ConnectError("refused"), None),
        ((404, "Cannot GET /v1/models"), (404, "Cannot POST /v1/chat/completions")),
        (None, (404, {"error": {"message": "The model `nope` does not exist", "code": "model_not_found"}})),
        (None, (402, {"error": {"message": "Insufficient Balance"}})),
        (httpx2.ReadTimeout("slow"), None),
    ]
    reports = []
    for list_reply, chat_reply in scenarios:
        fake.list_reply, fake.chat_reply = list_reply, chat_reply
        reports.append(_test_unsaved(client, headers, model_id="nope"))
    # 结论只有任务约定的十个取值，“不可达”与“两步都 404”都归为 bad_url，靠拉取步骤的错误码与说明区分
    conclusions = [(r["conclusion"], r["listing"]["code"]) for r in reports]
    assert conclusions == [
        ("invalid_key", "llm_invalid_key"),
        ("bad_url", "llm_bad_url"),
        ("bad_url", "llm_listing_unsupported_or_bad_url"),
        ("model_unavailable", None),
        ("quota_exceeded", None),
        ("timeout", "llm_timeout"),
    ]
    assert len({r["message"] for r in reports}) == 6
    assert "密钥" in reports[0]["message"] and "地址" in reports[1]["message"]
    assert "404" in reports[2]["message"] and "nope" in reports[3]["message"]
    assert "额度" in reports[4]["message"] and "超时" in reports[5]["message"]
    # 拉取失败且不是 404（密钥、不可达、超时）时结论跟随拉取，不再白等一次对话
    assert [r["chat"] is None for r in reports] == [True, True, False, False, False, True]


@pytest.mark.parametrize("list_reply, conclusion", [
    ((401, {"error": {"message": "Invalid API key"}}), "invalid_key"),
    ((402, {"error": {"message": "Insufficient Balance"}}), "quota_exceeded"),
    ((429, {"error": {"message": "Rate limit reached"}}), "rate_limited"),
    (httpx2.ReadTimeout("slow"), "timeout"),
    ((500, "boom"), "provider_error"),
])
def test_connection_test_follows_listing_error_unless_404(client, fake, list_reply, conclusion):
    headers = ready_user(client, "alice")
    fake.list_reply = list_reply
    fake.chat_reply = (404, {"error": {"message": "The model `nope` does not exist"}})
    report = _test_unsaved(client, headers, model_id="nope")
    assert (report["conclusion"], report["chat"]) == (conclusion, None)
    assert report["listing"]["code"] == f"llm_{conclusion}" and report["message"] == report["listing"]["message"]
    assert fake.chat_bodies == []


def test_connection_test_step_codes_match_conclusion(client, fake):
    headers = ready_user(client, "alice")
    fake.chat_reply = (404, "Cannot POST /v1/chat/completions")  # 列表正常、对话路径 404 → 模型不可用
    report = _test_unsaved(client, headers, model_id="nope")
    assert report["conclusion"] == "model_unavailable"
    assert report["chat"] == {"ok": False, "code": "llm_model_unavailable", "message": report["message"]}

    fake.list_reply = (404, "Cannot GET /v1/models")
    fake.chat_reply = (404, {"error": {"message": "The model `nope` does not exist"}})  # 两步都 404 → 地址错误
    report = _test_unsaved(client, headers, model_id="nope")
    assert report["conclusion"] == "bad_url"
    assert report["chat"] == {"ok": False, "code": "llm_bad_url", "message": report["message"]}
    assert report["listing"]["code"] == "llm_listing_unsupported_or_bad_url"

    fake.chat_reply = (400, {"error": {"message": "The model `nope` does not exist"}})  # 列表 404、对话 400 → 模型不可用
    report = _test_unsaved(client, headers, model_id="nope")
    assert report["conclusion"] == "model_unavailable" and report["chat"]["code"] == "llm_model_unavailable"

    fake.chat_reply = (401, {"error": {"message": "Invalid API key"}})  # 列表 404、对话密钥错误 → 跟随对话
    report = _test_unsaved(client, headers, model_id="nope")
    assert report["conclusion"] == "invalid_key" and report["chat"]["code"] == "llm_invalid_key"


def test_connection_test_listing_unsupported_but_chat_ok(client, fake):
    headers = ready_user(client, "alice")
    fake.list_reply = (404, "Cannot GET /v1/models")
    report = _test_unsaved(client, headers, model_id="doubao-pro")
    assert (report["conclusion"], report["ok"]) == ("ok_listing_unsupported", True)
    assert "手动添加模型编号" in report["message"]
    assert report["listing"]["code"] == "llm_listing_unsupported_or_bad_url"
    assert report["chat"] == {"ok": True, "code": None, "message": report["chat"]["message"]}
    body = fake.chat_bodies[0]
    assert body["model"] == "doubao-pro" and body["max_tokens"] == 16
    assert body["messages"] == [{"role": "user", "content": "请只回复：好"}]


def test_connection_test_without_model_suggests_chat(client, fake):
    headers = ready_user(client, "alice")
    fake.models = [f"model-{index:02d}" for index in range(12)]
    report = _test_unsaved(client, headers)
    assert (report["conclusion"], report["ok"], report["chat"]) == ("ok", True, None)
    assert "建议再选一个模型测试对话" in report["message"]
    assert report["models_found"] == 12
    assert report["sample_models"] == [f"model-{index:02d}" for index in range(10)]
    assert fake.chat_bodies == []

    full = _test_unsaved(client, headers, model_id="model-03")
    assert (full["conclusion"], full["listing"]["ok"], full["chat"]["ok"]) == ("ok", True, True)


def test_connection_test_validation_error_does_not_echo_key(client, fake):
    headers = ready_user(client, "alice")
    long_url = f"https://api.example.com/{SECRET}" + "x" * 300
    response = client.post("/api/llm/providers/test", headers=headers,
                           json={"kind": "openai_compatible", "base_url": long_url, "api_key": SECRET})
    assert (response.status_code, response.json()["error"]["code"]) == (422, "validation_error")
    assert SECRET not in response.text and fake.requests == []


def test_connection_test_rejects_bad_url_before_calling(client, fake):
    headers = ready_user(client, "alice")
    response = client.post("/api/llm/providers/test", headers=headers,
                           json={"kind": "openai_compatible", "base_url": f"http://{SECRET}@127.0.0.1:9/v1",
                                 "api_key": SECRET})
    assert (response.status_code, response.json()["error"]["code"]) == (422, "llm_invalid_url")
    assert SECRET not in response.text and fake.requests == []


def test_saved_provider_test_and_privacy(client, fake):
    alice = ready_user(client, "alice")
    provider = _provider(client, alice)
    tested = client.post(f"/api/llm/providers/{provider['id']}/test", json={"model_id": "deepseek-chat"},
                         headers=alice)
    assert tested.status_code == 200, tested.text
    assert tested.json()["conclusion"] == "ok" and SECRET not in tested.text
    assert fake.requests[0].headers["authorization"] == f"Bearer {SECRET}"
    no_model = client.post(f"/api/llm/providers/{provider['id']}/test", json={}, headers=alice).json()
    assert no_model["conclusion"] == "ok" and no_model["chat"] is None

    bella = ready_user(client, "bella")
    count = len(fake.requests)
    assert client.post(f"/api/llm/providers/{provider['id']}/test", json={}, headers=bella).status_code == 404
    assert client.post(f"/api/llm/providers/{provider['id']}/fetch-models", headers=bella).status_code == 404
    assert len(fake.requests) == count


# ---------- 验收第 6、7 条：统一调用入口 ----------

def _two_purposes(client, headers):
    provider = _provider(client, headers)
    chat_model = _add_model(client, headers, provider, "deepseek-chat")
    vision_model = _add_model(client, headers, provider, "qwen-vl-max")
    _assign(client, headers, "chat", chat_model)
    _assign(client, headers, "vision", vision_model)
    return provider, chat_model, vision_model


def test_chat_routes_each_purpose_to_its_model(client, fake):
    headers = ready_user(client, "alice")
    provider, chat_model, vision_model = _two_purposes(client, headers)

    chatted = _chat(client, headers, "chat", "今天吃什么")
    assert chatted.status_code == 200, chatted.text
    assert chatted.json() == {"text": "好", "tool_calls": [], "model_id": "deepseek-chat",
                              "provider_name": provider["name"], "usage": {"input_tokens": 9, "output_tokens": 1}}
    seen = _chat(client, headers, "vision", "这是什么", images=[PNG], max_tokens=200)
    assert seen.status_code == 200, seen.text
    assert seen.json()["model_id"] == "qwen-vl-max"

    first, second = fake.chat_bodies
    assert (first["model"], second["model"]) == ("deepseek-chat", "qwen-vl-max")
    assert first["max_tokens"] == 1024 and second["max_tokens"] == 200
    assert second["messages"][0]["content"][1]["image_url"]["url"] == f"data:image/png;base64,{PNG}"


def test_chat_refuses_images_without_vision(client, fake):
    headers = ready_user(client, "alice")
    _, _, vision_model = _two_purposes(client, headers)
    client.patch(f"/api/llm/models/{vision_model['id']}", json={"vision": False}, headers=headers)

    refused = _chat(client, headers, "vision", "这是什么", images=[PNG])
    assert (refused.status_code, refused.json()["error"]["code"]) == (422, "llm_model_lacks_vision")
    assert "看图" in refused.json()["error"]["message"] and "qwen-vl-max" in refused.json()["error"]["message"]
    no_image = _chat(client, headers, "vision", "没有图片也不行")
    assert no_image.json()["error"]["code"] == "llm_model_lacks_vision"

    with_image = _chat(client, headers, "chat", "看看这张图", images=[PNG])
    assert (with_image.status_code, with_image.json()["error"]["code"]) == (422, "llm_model_lacks_vision")
    assert "手动" in with_image.json()["error"]["message"]
    assert fake.requests == []


def test_chat_not_configured_and_not_chat(client, fake):
    headers = ready_user(client, "alice")
    missing = _chat(client, headers, "chat")
    assert (missing.status_code, missing.json()["error"]["code"]) == (409, "llm_not_configured")
    assert "设置" in missing.json()["error"]["message"]
    assert _chat(client, headers, "vision").json()["error"]["code"] == "llm_not_configured"

    provider = _provider(client, headers)
    model = _add_model(client, headers, provider, "deepseek-chat")
    _assign(client, headers, "chat", model)
    client.patch(f"/api/llm/models/{model['id']}", json={"chat": False}, headers=headers)
    refused = _chat(client, headers, "chat")
    assert (refused.status_code, refused.json()["error"]["code"]) == (422, "llm_model_not_chat")
    client.delete(f"/api/llm/models/{model['id']}", headers=headers)
    assert _chat(client, headers, "chat").json()["error"]["code"] == "llm_not_configured"
    assert fake.requests == []


def test_complete_refuses_tools_when_model_lacks_them(client, fake):
    headers = ready_user(client, "alice")
    provider = _provider(client, headers)
    model = _add_model(client, headers, provider, "deepseek-chat")
    _assign(client, headers, "chat", model)
    client.patch(f"/api/llm/models/{model['id']}", json={"tools": False}, headers=headers)
    factory = lambda kind, url, key: make_adapter(kind, url, key, transport=httpx2.MockTransport(fake))
    tool = ToolSpec("lookup", "查一下", {"type": "object", "properties": {}})
    with get_sessionmaker()() as db:
        fake.sessions.append(db)
        user_id = db.scalar(select(User.id).where(User.username == "alice"))
        with pytest.raises(AppError) as caught:
            service.complete(db, user_id, "chat", [ChatMessage("user", "你好")], tools=(tool,), factory=factory)
        assert caught.value.code == "llm_model_lacks_tools"
        client.patch(f"/api/llm/models/{model['id']}", json={"tools": None}, headers=headers)
        db.expire_all()
        done = service.complete(db, user_id, "chat", [ChatMessage("user", "你好")], tools=(tool,), factory=factory)
    assert (done.result.text, done.model_id, done.model_pk, done.provider_name) == (
        "好", "deepseek-chat", uuid.UUID(model["id"]), provider["name"])
    assert fake.chat_bodies[0]["tools"][0]["function"]["name"] == "lookup"


@pytest.mark.parametrize("reply, status, code", [
    ((429, {"error": {"message": "Rate limit reached"}}), 429, "llm_rate_limited"),
    (httpx2.ReadTimeout("slow"), 504, "llm_timeout"),
    ((500, "boom"), 502, "llm_provider_error"),
    ((402, {"error": {"message": "Insufficient Balance"}}), 402, "llm_quota_exceeded"),
    ((404, {"error": {"message": "The model `x` does not exist"}}), 400, "llm_model_unavailable"),
    ((404, "Cannot POST /v1/chat/completions"), 400, "llm_bad_url"),
    ((400, {"error": {"message": "messages too long"}}), 400, "llm_bad_request"),
    (_echo_key(401), 400, "llm_invalid_key"),
])
def test_chat_maps_provider_errors(client, fake, reply, status, code):
    headers = ready_user(client, "alice")
    model = _add_model(client, headers, _provider(client, headers), "deepseek-chat")
    _assign(client, headers, "chat", model)
    fake.chat_reply = reply
    response = _chat(client, headers)
    assert (response.status_code, response.json()["error"]["code"]) == (status, code)
    assert "请" in response.json()["error"]["message"] and SECRET not in response.text


def test_llm_error_table_covers_every_adapter_code():
    assert set(service.LLM_ERRORS) == set(ADAPTER_ERROR_CODES)
    assert set(service._NEXT_STEPS) == set(ADAPTER_ERROR_CODES)
    assert all("请" in step for step in service._NEXT_STEPS.values())
    assert SECRET not in repr(service._Target("openai_compatible", BASE, SECRET))
    assert service.LLM_ERRORS["invalid_key"] == (400, "llm_invalid_key")
    assert service.LLM_ERRORS["quota_exceeded"] == (402, "llm_quota_exceeded")
    assert all(code.startswith("llm_") for _status, code in service.LLM_ERRORS.values())


def test_chat_request_validation(client, fake):
    headers = ready_user(client, "alice")
    model = _add_model(client, headers, _provider(client, headers), "qwen-vl-max")
    _assign(client, headers, "vision", model)
    too_big = base64.b64encode(b"\x00" * (5 * 1024 * 1024 + 1)).decode()
    just_right = base64.b64encode(b"\x00" * (5 * 1024 * 1024)).decode()
    bad_requests = [
        {"purpose": "vision", "messages": [{"role": "user", "text": "x", "images": [
            {"mime_type": "image/png", "data_base64": too_big}]}]},
        {"purpose": "vision", "messages": [{"role": "user", "text": "x", "images": [
            {"mime_type": "image/png", "data_base64": "不是base64!!"}]}]},
        {"purpose": "vision", "messages": [{"role": "user", "text": "x", "images": [
            {"mime_type": "image/png", "data_base64": "abc"}]}]},
        {"purpose": "vision", "messages": [{"role": "user", "text": "x", "images": [
            {"mime_type": "image/bmp", "data_base64": PNG}]}]},
        {"purpose": "vision", "messages": [{"role": "user", "text": "x", "images": [
            {"mime_type": "image/png", "data_base64": PNG}] * 5}]},
        {"purpose": "chat", "messages": []},
        {"purpose": "chat", "messages": [{"role": "user", "text": "x"}] * 51},
        {"purpose": "chat", "messages": [{"role": "user", "text": "x" * 20001}]},
        {"purpose": "chat", "messages": [{"role": "user", "text": "x"}], "max_tokens": 4097},
        {"purpose": "chat", "messages": [{"role": "user", "text": "x"}], "max_tokens": 0},
        {"purpose": "other", "messages": [{"role": "user", "text": "x"}]},
        {"purpose": "chat", "messages": [{"role": "tool", "text": "x"}]},
        {"purpose": "chat", "messages": [{"role": "user", "text": "x"}], "user_id": "someone"},
    ]
    for body in bad_requests:
        response = client.post("/api/llm/chat", json=body, headers=headers)
        assert response.status_code == 422, (str(body)[:200], response.text[:300])
    assert fake.requests == []
    ok = _chat(client, headers, "vision", "", images=[just_right] * 1)
    assert ok.status_code == 200, ok.text[:300]


def test_chat_image_totals_and_roles(client, fake):
    headers = ready_user(client, "alice")
    model = _add_model(client, headers, _provider(client, headers), "qwen-vl-max")
    _assign(client, headers, "vision", model)
    image = lambda data: {"mime_type": "image/png", "data_base64": data}
    user = lambda *datas: {"role": "user", "text": "看图", "images": [image(d) for d in datas]}
    post = lambda messages: client.post("/api/llm/chat", json={"purpose": "vision", "messages": messages},
                                        headers=headers)

    nine = post([user(PNG, PNG, PNG), user(PNG, PNG, PNG), user(PNG, PNG, PNG)])
    assert (nine.status_code, nine.json()["error"]["code"]) == (422, "llm_invalid_images")
    assert "8 张" in nine.json()["error"]["message"]
    big = base64.b64encode(b"\x00" * (4 * 1024 * 1024 + 512 * 1024)).decode()  # 4.5 MB，单张合格
    heavy = post([user(big, big, big), user(big, big)])
    assert (heavy.status_code, heavy.json()["error"]["code"]) == (422, "llm_invalid_images")
    assert "20 MB" in heavy.json()["error"]["message"]
    for role in ("assistant", "system"):
        wrong = post([{"role": role, "text": "", "images": [image(PNG)]}, user()])
        assert (wrong.status_code, wrong.json()["error"]["code"]) == (422, "llm_invalid_images")
        assert "用户消息" in wrong.json()["error"]["message"]
    assert fake.requests == []

    eight = post([user(PNG, PNG, PNG, PNG), user(PNG, PNG, PNG, PNG)])
    assert eight.status_code == 200, eight.text[:300]
    assert post([user(big, big, big, big)]).status_code == 200  # 合计 18 MB，未超


def test_fetch_models_caps_at_500(client, fake):
    headers = ready_user(client, "alice")
    provider = _provider(client, headers)
    fake.models = [f"m-{index:03d}" for index in range(600)] + ["a" * 201]
    body = client.post(f"/api/llm/providers/{provider['id']}/fetch-models", headers=headers).json()
    assert (body["added"], body["total"], body["skipped"]) == (500, 601, 101)
    assert [m["model_id"] for m in body["models"]] == [f"m-{index:03d}" for index in range(500)]


# ---------- 验收第 5 条：密钥不外泄 ----------

def test_key_never_leaks_from_test_fetch_or_chat(client, fake):
    headers = ready_user(client, "alice")
    provider = _provider(client, headers)
    model = _add_model(client, headers, provider, "deepseek-chat")
    _assign(client, headers, "chat", model)
    fake.list_reply = _echo_key(401)
    fake.chat_reply = _echo_key(401)
    responses = [
        client.post("/api/llm/providers/test", headers=headers,
                    json={"kind": "openai_compatible", "base_url": BASE, "api_key": SECRET, "model_id": "x"}),
        client.post(f"/api/llm/providers/{provider['id']}/test", json={"model_id": "x"}, headers=headers),
        client.post(f"/api/llm/providers/{provider['id']}/fetch-models", headers=headers),
        _chat(client, headers),
    ]
    assert len(fake.requests) == 4  # 两次测试各拉取一次（密钥错误时不再做对话）；获取模型一次；调用一次
    for response in responses:
        assert SECRET not in response.text and SECRET[3:] not in response.text
    assert [r.status_code for r in responses] == [200, 200, 400, 400]
    assert responses[0].json()["conclusion"] == "invalid_key"


# ---------- 出站前再次检查地址 ----------

def test_base_url_is_rechecked_before_every_call(client, fake, monkeypatch):
    headers = ready_user(client, "alice")
    provider = _provider(client, headers)
    model = _add_model(client, headers, provider, "deepseek-chat")
    _assign(client, headers, "chat", model)
    monkeypatch.setattr(get_settings(), "llm_allow_private_hosts", False)
    for response in (
        client.post(f"/api/llm/providers/{provider['id']}/fetch-models", headers=headers),
        client.post(f"/api/llm/providers/{provider['id']}/test", json={"model_id": "deepseek-chat"}, headers=headers),
        _chat(client, headers),
    ):
        assert (response.status_code, response.json()["error"]["code"]) == (422, "llm_invalid_url")
    assert fake.requests == []


# ---------- 密钥延迟加载 ----------

def test_api_key_is_loaded_only_when_calling_the_provider(client, fake):
    headers = ready_user(client, "alice")
    statements: list[str] = []
    capture = lambda conn, cursor, statement, *args: statements.append(statement)
    engine = get_engine()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        provider = _provider(client, headers)
        model = _add_model(client, headers, provider, "deepseek-chat")
        client.get("/api/llm/providers", headers=headers)
        client.get(f"/api/llm/providers/{provider['id']}", headers=headers)
        client.patch(f"/api/llm/providers/{provider['id']}", json={"name": "改名"}, headers=headers)
        client.get(f"/api/llm/providers/{provider['id']}/models", headers=headers)
        client.patch(f"/api/llm/models/{model['id']}", json={"tools": True}, headers=headers)
        _assign(client, headers, "chat", model)
        client.get("/api/llm/assignments", headers=headers)
        quiet = [s for s in statements if "llm_providers.api_key" in s]
        statements.clear()
        assert _chat(client, headers).status_code == 200
        loaded = [s for s in statements if "llm_providers.api_key" in s]
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert quiet == []
    assert len(loaded) == 1

    with get_sessionmaker()() as db:
        user_id = db.scalar(select(User.id).where(User.username == "alice"))
        (listed,) = service.list_providers(db, user_id)
        assert "api_key" in inspect(listed).unloaded
        service.list_models(db, user_id, listed.id)
        service.assign(db, user_id, "chat", uuid.UUID(model["id"]))
        service.list_assignments(db, user_id)
        for instance in db.identity_map.values():
            if isinstance(instance, LlmProvider):
                assert "api_key" in inspect(instance).unloaded
