"""步骤 12：“全部日志”金丝雀测试。

起真实的 uvicorn 服务器（tests/live_server.py），根记录器、uvicorn 各记录器、app.access、httpx2、httpcore2 全部调到
DEBUG，抓取格式化后的完整文本（含堆栈）；用带唯一标记的值走正常、出错、校验失败、唯一约束冲突四种路径，
断言这些值一个都不出现在日志里。模型用 tests/agent_fake.py 的 ScriptedModel，高德用 tests/amap_fake.py 的 FakeAmap，
绝不访问真实网络。
"""

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from urllib.parse import quote

import httpx2
import pytest

from app.common.clock import get_today
from app.llm import service as llm_service
from app.llm.adapters import make_adapter
from app.main import create_app
from app.restaurants import amap
from app.restaurants import service as restaurant_service
from app.restaurants.amap import use_transport
from app.sdk import AgentGrantToken, GoodLife
from tests.agent_fake import MODEL_IDS, ScriptedModel, call, say
from tests.amap_fake import BASE, GUOMAO, KEY, FakeAmap, _settings
from tests.live_server import LiveServer, prepare_user, request

TODAY = date(2026, 10, 7)
ORDER_TEXT = "金丝雀医嘱：每日忌食榴莲酥，复查前停用鱼油 canary-order-5d1c"
PERIOD_START = "2023-03-11"
AGENT_PERIOD = "2023-05-23"
LOG_DATE = "2023-02-17"
MODEL_KEY = "sk-canary-model-9b2e4f7a1c"
PASSWORD = "canary-pass-6a3d9e"
LNG, LAT = "116.471357", "39.918264"
PLACE_MARK = "canary-place-3c8a"
PLACE = f"金丝雀胡同七号院 {PLACE_MARK}"
FIXED_CANARIES = (ORDER_TEXT, "榴莲酥", "canary-order-5d1c", PERIOD_START, AGENT_PERIOD, LOG_DATE, MODEL_KEY,
                  PASSWORD, LNG, LAT, PLACE, PLACE_MARK, quote(PLACE), KEY)
PATHS = ("normal", "error", "validation", "conflict")


@dataclass
class Live:
    server: LiveServer
    model: ScriptedModel
    amap: FakeAmap
    tokens: dict[str, str] = field(default_factory=dict)  # 令牌 → 唯一允许出现它的接口（签发它的那个）
    responses: list[tuple[str, int, str]] = field(default_factory=list)

    def send(self, method: str, path: str, body: Any = None, headers: dict[str, str] | None = None,
             expect: int | None = None) -> Any:
        status, data = request(self.server.url, method, path, body, headers)
        self.responses.append((f"{method} {path}", status, json.dumps(data, ensure_ascii=False)))
        if expect is not None:
            assert status == expect, (method, path, status, data)
        return data

    def user(self) -> dict[str, str]:
        headers = prepare_user(self.server.url, "canary_user", PASSWORD)
        self.tokens[headers["Authorization"].removeprefix("Bearer ")] = "POST /api/auth/login"
        self.send("PATCH", "/api/profile", {"gender": "female"}, headers, expect=200)
        return headers

    def canaries(self) -> list[str]:
        return [*FIXED_CANARIES, *self.tokens]


@pytest.fixture
def live(monkeypatch):
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    model = ScriptedModel()

    def factory(kind, base_url, api_key):
        return make_adapter(kind, base_url, api_key, transport=httpx2.MockTransport(model))
    app.dependency_overrides[llm_service.get_adapter_factory] = lambda: factory
    monkeypatch.setattr(amap, "get_settings", lambda: _settings(amap_key=KEY, amap_base_url=BASE))
    restaurant_service.reset_rate_limit()
    fake = FakeAmap()
    fake.geocodes[PLACE] = [GUOMAO]
    with use_transport(httpx2.MockTransport(fake)), LiveServer(app) as server:
        yield Live(server, model, fake)
    restaurant_service.reset_rate_limit()


def _boom(*args, **kwargs):
    raise RuntimeError(f"{ORDER_TEXT} {PERIOD_START} {MODEL_KEY} {PASSWORD} {LNG},{LAT} {PLACE}")


def _normal(live: Live, monkeypatch) -> None:
    headers = live.user()
    live.send("POST", "/api/medical/orders", {"text": ORDER_TEXT}, headers, expect=201)
    orders = live.send("GET", "/api/medical/orders", headers=headers, expect=200)
    assert orders[0]["source_text"] == ORDER_TEXT
    live.send("POST", "/api/cycle/periods", {"start_date": PERIOD_START, "end_date": "2023-03-15"}, headers,
              expect=201)
    live.send("PUT", f"/api/cycle/day-logs/{LOG_DATE}", {"flow": "light", "pain": 2}, headers, expect=200)
    logs = live.send("GET", f"/api/cycle/day-logs?start={LOG_DATE}&end={LOG_DATE}", headers=headers, expect=200)
    assert [log["log_date"] for log in logs] == [LOG_DATE]

    provider = live.send("POST", "/api/llm/providers", {"name": "模拟模型", "kind": "openai_compatible",
                                                        "base_url": "http://127.0.0.1:9/v1", "api_key": MODEL_KEY},
                         headers, expect=201)
    model = live.send("POST", f"/api/llm/providers/{provider['id']}/models",
                      {"model_id": MODEL_IDS["openai_compatible"]}, headers, expect=201)
    live.send("PUT", "/api/llm/assignments/chat", {"model_id": model["id"]}, headers, expect=200)
    live.model.add(call("cycle_record_period", {"start_date": AGENT_PERIOD, "end_date": "2023-05-27"}),
                   say("已经记下了。"))
    conversation = live.send("POST", "/api/agent/conversations", {}, headers, expect=201)
    live.send("POST", f"/api/agent/conversations/{conversation['id']}/messages",
              {"text": f"帮我记一下经期，{AGENT_PERIOD} 开始", "stream": False}, headers, expect=200)
    periods = live.send("GET", "/api/cycle/periods", headers=headers, expect=200)
    assert {period["start_date"] for period in periods} == {PERIOD_START, AGENT_PERIOD}

    live.send("PUT", "/api/restaurants/settings/consent", {"consent": "granted"}, headers, expect=200)
    live.send("POST", "/api/restaurants/search", {"location": {"lng": float(LNG), "lat": float(LAT),
                                                               "coord_type": "gcj02"}}, headers, expect=200)
    live.send("POST", "/api/restaurants/search", {"place": PLACE}, headers, expect=200)
    assert live.amap.calls("/v5/place/around")[0]["location"] == f"{LNG},{LAT}"
    assert live.amap.calls("/v3/geocode/geo")[0]["address"] == PLACE

    grant = live.send("POST", "/api/agent-grants", {"name": "canary", "access": "read_write"}, headers, expect=201)
    live.tokens[grant["token"]] = "POST /api/agent-grants"
    result = GoodLife(today=lambda: TODAY).call(AgentGrantToken(grant["token"]), "cycle.list_periods",
                                                client_name="canary")
    assert {period["start_date"] for period in result.data} == {PERIOD_START, AGENT_PERIOD}


def _error(live: Live, monkeypatch) -> None:
    headers = live.user()
    live.send("POST", "/api/medical/orders", {"text": ORDER_TEXT}, headers, expect=201)
    monkeypatch.setattr("app.medical.orders.list_orders", _boom)
    live.send("GET", "/api/medical/orders", headers=headers, expect=500)


def _validation(live: Live, monkeypatch) -> None:
    headers = live.user()
    live.send("POST", "/api/medical/orders", {"text": ORDER_TEXT * 200}, headers, expect=422)
    live.send("POST", "/api/cycle/periods", {"start_date": [PERIOD_START], "end_date": {"day": PERIOD_START}},
              headers, expect=422)


def _conflict(live: Live, monkeypatch) -> None:
    headers = live.user()
    monkeypatch.setattr("app.cycle.records.list_periods", lambda db, user_id: [])  # 跳过重叠检查，直接撞唯一约束
    period = {"start_date": PERIOD_START, "end_date": "2023-03-15"}
    live.send("POST", "/api/cycle/periods", period, headers, expect=201)
    live.send("POST", "/api/cycle/periods", period, headers, expect=409)


RUNS = {"normal": _normal, "error": _error, "validation": _validation, "conflict": _conflict}


def test_capture_sees_server_and_application_logs(live, monkeypatch):
    headers = live.user()
    live.send("PUT", "/api/restaurants/settings/consent", {"consent": "granted"}, headers, expect=200)
    live.send("POST", "/api/restaurants/search", {"place": "国贸"}, headers, expect=200)
    monkeypatch.setattr("app.medical.orders.list_orders", _boom)
    live.send("GET", "/api/medical/orders", headers=headers, expect=500)
    text = live.server.text()
    assert "uvicorn.error INFO Uvicorn running on http://127.0.0.1:" in text
    assert "app.access INFO POST /api/auth/register 201" in text
    assert "app.access INFO PUT /api/cycle/day-logs" not in text  # 没请求过的不会凭空出现
    assert "httpx2 INFO HTTP Request: GET https://amap.example.com/v3/geocode/geo?<redacted>" in text
    assert "app.common.request_log ERROR 未处理的异常：RuntimeError GET /api/medical/orders" in text
    assert "app.access INFO GET /api/medical/orders 500" in text


@pytest.mark.parametrize("path", PATHS, ids=PATHS)
def test_every_log_output_at_debug_stays_free_of_canaries(live, monkeypatch, path):
    RUNS[path](live, monkeypatch)
    text = live.server.text()
    assert "app.access INFO" in text  # 确实抓到了这一组请求的日志
    leaked = [canary for canary in live.canaries() if canary in text]
    assert leaked == []


@pytest.mark.parametrize("path", PATHS, ids=PATHS)
def test_error_responses_never_echo_keys_passwords_or_tokens(live, monkeypatch, path):
    RUNS[path](live, monkeypatch)
    if path != "normal":
        assert any(status >= 400 for _, status, _ in live.responses)
    for endpoint, status, body in live.responses:
        assert MODEL_KEY not in body and PASSWORD not in body, (endpoint, status)
        for token, issuer in live.tokens.items():
            if endpoint != issuer:
                assert token not in body, (endpoint, status)
