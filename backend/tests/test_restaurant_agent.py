"""步骤 10：附近餐厅作为只读 SDK 能力 nutrition.nearby_restaurants，经 SDK、MCP 与站内智能体使用。

高德一律由 tests/test_restaurant_flow.py 的模拟服务（MockTransport）回答，模型一律用 tests/agent_fake.py 的模拟服务，
绝不访问真实网络。
"""

import json
from datetime import date

import httpx2
import pytest
from fastapi.testclient import TestClient
from mcp.client import Client
from sqlalchemy import text

from app.agent.assembly import RESTAURANT_NOTE
from app.agent.guard import NOTICE_HEADER
from app.common.clock import get_today
from app.db import get_engine
from app.main import create_app
from app.mcp_server.server import build_server
from app.restaurants import amap
from app.restaurants import service as restaurant_service
from app.restaurants.amap import use_transport
from app.restaurants.needs import load_needs
from app.sdk import AgentGrantToken, GoodLife, SdkError
from app.sdk.client import SDK_VERSION
from app.sdk.manifest import MANIFEST_PATH, build_manifest
from app.sdk.registry import REGISTRY
from app.sdk.tooling import TOOL_USAGE, exposed_capabilities
from tests.agent_fake import call, connect, say, scripted  # noqa: F401
from tests.helpers import ready_user
from tests.test_restaurant_flow import BASE, KEY, FakeAmap, _poi, _settings, ok

TODAY = date(2026, 10, 7)
CAPABILITY = "nutrition.nearby_restaurants"
TOOL = "nutrition_nearby_restaurants"
NO_SPICY = "一周内忌食辛辣。"
OUT_KEYS = {"center_name", "restaurants", "avoided_type_names", "notice"}
SHOP_KEYS = {"name", "type_name", "distance_m", "conclusion", "order"}


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sdk():
    return GoodLife(today=lambda: TODAY)


@pytest.fixture
def fake(client, monkeypatch):
    monkeypatch.setattr(amap, "get_settings", lambda: _settings(amap_key=KEY, amap_base_url=BASE))
    restaurant_service.reset_rate_limit()
    model = FakeAmap()
    with use_transport(httpx2.MockTransport(model)):
        yield model
    restaurant_service.reset_rate_limit()


@pytest.fixture
def unconfigured(client, monkeypatch):
    """服务端没有配置高德密钥；若真的发出请求，模拟服务会记下来。"""
    monkeypatch.setattr(amap, "get_settings", lambda: _settings())
    restaurant_service.reset_rate_limit()
    model = FakeAmap()
    with use_transport(httpx2.MockTransport(model)):
        yield model
    restaurant_service.reset_rate_limit()


def _token(client, headers, access="read"):
    response = client.post("/api/agent-grants", json={"name": "t", "access": access}, headers=headers)
    assert response.status_code == 201, response.text
    return AgentGrantToken(response.json()["token"])


def _rest(client, headers, **body) -> dict:
    response = client.post("/api/restaurants/search", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _spicy_order(client, headers) -> None:
    order = client.post("/api/medical/orders", json={"text": NO_SPICY}, headers=headers)
    assert order.status_code == 201, order.text
    for item in order.json()["items"]:
        assert client.post(f"/api/medical/items/{item['id']}/confirm", headers=headers).status_code == 200


def _expected_shops(body: dict) -> list[dict]:
    """接口结果里排在前面的 8 家，按 SDK 的输出格式整理：可点菜名取所属类型的整类建议。"""
    order = {item["type_key"]: item["order"] for item in body["type_advice"]}
    return [{"name": shop["name"], "type_name": shop["type_name"], "distance_m": shop["distance_m"],
             "conclusion": shop["conclusion"], "order": order.get(shop["type_key"], [])}
            for shop in body["restaurants"][:8]]


def _audits() -> list[tuple]:
    with get_engine().connect() as conn:
        return conn.execute(text(
            "SELECT capability, outcome, error_code, client_name FROM sdk_call_audits ORDER BY created_at")).all()


# ---------- SDK ----------


def test_sdk_with_a_place_returns_the_top_shops_like_the_rest_api(client, sdk, fake):
    headers = ready_user(client, "ann")
    expected = _rest(client, headers, place="国贸")
    data = sdk.call(_token(client, headers), CAPABILITY, {"place": "国贸"}, client_name="pytest").data

    assert set(data) == OUT_KEYS
    assert data["center_name"] == expected["center"]["name"] == "北京市朝阳区国贸"
    assert data["restaurants"] == _expected_shops(expected)
    assert all(set(shop) == SHOP_KEYS for shop in data["restaurants"])
    assert data["avoided_type_names"] == []
    assert data["notice"] == restaurant_service.NOTICE
    unchecked = next(shop for shop in data["restaurants"] if shop["name"] == "某某餐厅")
    assert unchecked == {"name": "某某餐厅", "type_name": None, "distance_m": 80, "conclusion": "unchecked",
                         "order": []}
    assert fake.calls("/v3/geocode/geo")[-1]["address"] == "国贸"
    assert _audits()[-1] == (CAPABILITY, "ok", None, "pytest")


def test_sdk_passes_city_needs_and_radius(client, sdk, fake):
    headers = ready_user(client, "ben")
    sdk.call(_token(client, headers), CAPABILITY,
             {"place": "国贸", "city": "北京", "needs": ["porridge"], "radius": 800})
    [geo] = fake.calls("/v3/geocode/geo")
    assert (geo["address"], geo["city"]) == ("国贸", "北京")
    porridge = next(need for need in load_needs() if need.key == "porridge")
    around = fake.calls("/v5/place/around")
    assert [call["keywords"] for call in around] == list(porridge.keywords)
    assert {call["radius"] for call in around} == {"800"}


def test_sdk_without_a_place_uses_the_saved_area_and_returns_at_most_eight(client, sdk, fake):
    headers = ready_user(client, "cid")
    _rest(client, headers, place="国贸", remember_area=True)
    many = [_poi(f"C{i:03d}", f"张记粥铺{i}号店", "050100", str(100 + i), "4.0", 116.46, 39.91, "建国路")
            for i in range(12)]
    fake.override = ok({"count": str(len(many)), "pois": many})
    before = len(fake.requests)

    data = sdk.call(_token(client, headers), CAPABILITY, {}).data
    assert data["center_name"] == "朝阳区"
    assert len(data["restaurants"]) == 8
    assert [shop["name"] for shop in data["restaurants"]] == [f"张记粥铺{i}号店" for i in range(8)]
    assert [path for path, _ in fake.requests[before:]] == ["/v5/place/around"]  # 不做地址解析


def test_sdk_without_place_or_saved_area_asks_for_a_place(client, sdk, fake):
    headers = ready_user(client, "dan")
    token = _token(client, headers)
    with pytest.raises(SdkError) as caught:
        sdk.call(token, CAPABILITY, {}, client_name="pytest")
    err = caught.value
    assert (err.kind, err.code) == ("invalid_input", "restaurant_no_location")
    assert "在哪里" in err.message and "地名或地标" in err.message
    assert "授权" not in err.message and "定位" not in err.message
    assert fake.requests == []
    assert _audits()[-1] == (CAPABILITY, "error", "restaurant_no_location", "pytest")

    # 清除保存的区域之后也一样
    _rest(client, headers, place="国贸", remember_area=True)
    assert client.delete("/api/restaurants/settings/area", headers=headers).status_code == 204
    with pytest.raises(SdkError) as caught:
        sdk.call(token, CAPABILITY, {})
    assert caught.value.code == "restaurant_no_location"


def test_sdk_without_amap_key_is_not_configured(client, sdk, unconfigured):
    headers = ready_user(client, "eve")
    with pytest.raises(SdkError) as caught:
        sdk.call(_token(client, headers), CAPABILITY, {"place": "国贸"}, client_name="pytest")
    assert caught.value.code == "restaurant_not_configured"
    assert unconfigured.requests == []
    assert _audits()[-1] == (CAPABILITY, "error", "restaurant_not_configured", "pytest")


def test_sdk_output_has_avoided_type_names_but_no_avoid_dishes_or_reasons(client, sdk, fake):
    headers = ready_user(client, "fay")
    _spicy_order(client, headers)
    expected = _rest(client, headers, place="国贸")
    data = sdk.call(_token(client, headers), CAPABILITY, {"place": "国贸"}).data

    assert data["avoided_type_names"] == [group["type_name"] for group in expected["avoided_types"]]
    assert len(data["avoided_type_names"]) == 2  # 川菜与麻辣烫两类
    assert data["restaurants"] == _expected_shops(expected)
    names = {shop["name"] for shop in data["restaurants"]}
    assert "老川菜馆" not in names and "杨记麻辣烫" not in names
    hotpot = next(shop for shop in data["restaurants"] if shop["name"] == "老码头火锅")
    assert hotpot["conclusion"] == "caution"
    serialized = json.dumps(data, ensure_ascii=False)
    for word in ("avoid\"", "moderate", "reasons", "medical", "type_key", "nav_url", "disclaimer", "116.", "39.9"):
        assert word not in serialized, word
    avoid = {dish for item in expected["type_advice"] for dish in item["avoid"]}
    reasons = {r["message"] for item in expected["type_advice"] for r in item["reasons"]}
    assert avoid and reasons
    shown = names | set(data["avoided_type_names"]) | {shop["type_name"] for shop in data["restaurants"]}
    for dish in avoid:
        if not any(dish in name for name in shown if name):  # 店名、类型名里本来就带的字（如“火锅”）除外
            assert dish not in serialized, dish
    for message in reasons:
        assert message not in serialized, message


@pytest.mark.parametrize("params", [
    {"place": "国贸", "needs": ["no_such_need"]},
    {"place": "国贸", "needs": ["light", "soup", "porridge", "light_meal"]},
    {"place": "国贸", "radius": 100},
    {"place": "国贸", "radius": 6000},
    {"place": ""},
    {"place": "国" * 51},
    {"city": "北京"},
    {"place": "国贸", "location": {"lng": 116.4, "lat": 39.9}},
    {"place": "国贸", "user_id": "x"},
])
def test_sdk_rejects_bad_params_before_any_network_call(client, sdk, fake, params):
    headers = ready_user(client, "gus")
    with pytest.raises(SdkError) as caught:
        sdk.call(_token(client, headers), CAPABILITY, params)
    assert (caught.value.kind, caught.value.code) == ("invalid_input", "validation_error")
    assert fake.requests == []


def test_params_schema_lists_the_need_keys_and_has_no_coordinates():
    cap = REGISTRY[CAPABILITY]
    assert cap.level == "read" and cap.module == "nutrition"
    schema = cap.input_model.model_json_schema()
    assert set(schema["properties"]) == {"place", "city", "needs", "radius"}
    assert schema.get("required", []) == [] and schema["additionalProperties"] is False
    items = schema["properties"]["needs"]["items"]
    enum = items.get("enum") or schema["$defs"][items["$ref"].split("/")[-1]]["enum"]
    assert enum == [need.key for need in load_needs()]
    assert schema["properties"]["needs"]["maxItems"] == 3
    radius = schema["properties"]["radius"]
    assert (radius["minimum"], radius["maximum"], radius["default"]) == (500, 5000, 2000)


def test_counts_version_and_manifest():
    levels: dict[str, int] = {}
    for cap in REGISTRY.values():
        levels[cap.level] = levels.get(cap.level, 0) + 1
    assert (len(REGISTRY), levels["read"], levels["write"], levels["user_confirmed"]) == (34, 23, 5, 6)
    assert SDK_VERSION == "1.2"
    snapshot = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert build_manifest(REGISTRY) == snapshot and snapshot["sdk_version"] == "1.2"
    assert CAPABILITY in {cap["name"] for cap in snapshot["capabilities"]}
    when, when_not = TOOL_USAGE[CAPABILITY]
    for word in ("不想做饭", "出去吃", "附近", "地名或地标", "保存"):
        assert word in when, word
    for word in ("菜谱", "外卖", "下单", "真实菜单"):
        assert word in when_not, word


# ---------- MCP ----------


@pytest.mark.anyio
async def test_mcp_lists_28_tools_including_nearby_and_calls_it(client, fake):
    headers = ready_user(client, "hal")
    token = _token(client, headers).token
    server = build_server(GoodLife(today=lambda: TODAY), lambda: AgentGrantToken(token), "pytest")
    async with Client(server) as mcp:
        tools = (await mcp.list_tools()).tools
        result = await mcp.call_tool(TOOL, {"place": "国贸"})
    assert len(tools) == 28 == len(exposed_capabilities(REGISTRY))
    tool = next(tool for tool in tools if tool.name == TOOL)
    assert "什么时候用" in tool.description and "什么时候不要用" in tool.description
    assert not result.is_error
    assert result.structured_content["sdk_version"] == "1.2"
    assert set(result.structured_content["data"]) == OUT_KEYS


# ---------- 智能体 ----------


def _conversation(client, headers) -> str:
    response = client.post("/api/agent/conversations", json={}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _send(client, headers, words) -> dict:
    response = client.post(f"/api/agent/conversations/{_conversation(client, headers)}/messages",
                           json={"text": words, "stream": False}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_agent_gets_the_tool_and_the_prompt_sentence_only_with_an_amap_key(client, scripted, monkeypatch):
    assert RESTAURANT_NOTE == ("附近餐厅推荐只是按餐厅类别给出的一般性建议，不代表该店真实菜单；"
                               "不要向用户索要定位授权，需要地点时请用户说出地名或地标。")
    headers = ready_user(client, "ivy")
    connect(client, headers)

    monkeypatch.setattr(amap, "get_settings", lambda: _settings(amap_key=KEY, amap_base_url=BASE))
    _send(client, headers, "不想做饭，附近有什么吃的")
    with_key = scripted.requests[-1]
    assert TOOL in with_key.tool_names and RESTAURANT_NOTE in with_key.system

    monkeypatch.setattr(amap, "get_settings", lambda: _settings())
    _send(client, headers, "不想做饭，附近有什么吃的")
    without_key = scripted.requests[-1]
    assert TOOL not in without_key.tool_names and RESTAURANT_NOTE not in without_key.system
    assert len(with_key.tool_names) == len(without_key.tool_names) + 1


def test_agent_calls_the_tool_and_the_answer_goes_through_the_output_check(client, scripted, fake):
    headers = ready_user(client, "jay", {"gender": "male"})
    _spicy_order(client, headers)
    connect(client, headers)
    scripted.add(call(TOOL, {"place": "国贸"}), say("国贸附近可以去杨记麻辣烫。"), say("国贸附近可以去张记粥铺喝粥。"))
    body = _send(client, headers, "不想做饭，我在国贸，附近吃点什么")

    assert len(scripted.requests) == 3
    result = scripted.requests[1].messages[-1]
    assert result["role"] == "tool"
    envelope = json.loads(result["content"])
    assert envelope["ok"] is True and set(envelope["data"]) == OUT_KEYS
    assert "张记粥铺" in result["content"] and "杨记麻辣烫" not in result["content"]
    assert len(envelope["data"]["avoided_type_names"]) == 2
    assert body["flags"] == ["guard_rewritten"]
    assert "麻辣烫" in scripted.requests[2].messages[-1]["content"]  # 重写要求里点名了麻辣烫
    assert body["text"].split("\n\n")[0] == "国贸附近可以去张记粥铺喝粥。"
    assert NOTICE_HEADER.format(foods="麻辣烫") in body["text"]
    assert TOOL in body["tools_used"]
    assert (CAPABILITY, "ok", None, "agent") in _audits()


def test_agent_tool_error_without_a_place_reaches_the_model_as_a_structured_error(client, scripted, fake):
    headers = ready_user(client, "kim")
    connect(client, headers)
    scripted.add(call(TOOL, {}), say("你现在在哪里？说个地名或地标就行。"))
    body = _send(client, headers, "附近吃什么")
    envelope = json.loads(scripted.requests[1].messages[-1]["content"])
    assert envelope["ok"] is False and envelope["error"]["code"] == "restaurant_no_location"
    assert body["text"].startswith("你现在在哪里")
    assert fake.requests == []
