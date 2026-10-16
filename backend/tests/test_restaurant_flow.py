"""步骤 10：附近餐厅推荐的设置、检索流程与接口。

高德一律由 MockTransport 驱动的模拟服务回答（固定的一组店：川菜馆、粥铺、轻食店、火锅店、麻辣烫、面馆、
一家判断不出类别的“某某餐厅”），模型一律用 tests/agent_fake.py 的模拟服务，绝不访问真实网络。
"""

import json
import uuid
from datetime import date

import httpx2
import pytest
from sqlalchemy import text

from app.db import Base, get_db, get_engine, get_sessionmaker
from app.errors import AppError
from app.llm import service as llm_service
from app.nutrition.catalog import load_catalog
from app.nutrition.engine import DISCLAIMER
from app.restaurants import amap
from app.restaurants import service as restaurant_service
from app.restaurants.amap import AmapClient, Poi, navigation_url
from app.restaurants.coords import wgs84_to_gcj02
from app.restaurants.needs import MODEL_PROMPT, load_needs, match_rules
from app.restaurants.schemas import SearchIn
from app.security.crypto import decrypt_value
from tests.agent_fake import connect, fail, say, scripted  # noqa: F401
from tests.amap_fake import BASE, CITY_LEVEL, KEY, POIS, fake, settings  # noqa: F401
from tests.helpers import ready_user

URL = "/api/restaurants"
NOTICE = "到店可点与应避开是基于餐厅类别的一般性建议，不代表该店真实菜单，也不保证该店有这些菜。"
UNCHECKED_TIP = "无法判断这家店的类别，请到店自行留意。"
GPS = {"lng": 116.461234, "lat": 39.909876}
CATALOG_NAMES = {food.name for food in load_catalog().foods.values()}
NEED_TEXT_WITHOUT_RULES = "随便来点好吃的"
# 不设区的地级市：没有区县，逆地理的地址名称细到街道
DONGGUAN_REGEO = {"formatted_address": "广东省东莞市南城街道鸿福路 100 号", "addressComponent": {
    "district": [], "adcode": "441900", "city": "东莞市", "province": "广东省"}}


def _search(client, headers, **body):
    return client.post(f"{URL}/search", json=body, headers=headers)


def _ok(client, headers, **body) -> dict:
    response = _search(client, headers, **body)
    assert response.status_code == 200, response.text
    return response.json()


def _grant(client, headers, consent="granted"):
    response = client.put(f"{URL}/settings/consent", json={"consent": consent}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _names(body: dict) -> list[str]:
    return [shop["name"] for shop in body["restaurants"]]


def _shop(body: dict, name: str) -> dict:
    return next(shop for shop in body["restaurants"] if shop["name"] == name)


def _advice(body: dict, key: str) -> dict:
    return next(item for item in body["type_advice"] if item["type_key"] == key)


def _spicy_order(client, headers) -> list[dict]:
    order = client.post("/api/medical/orders", json={"text": "一周内忌食辛辣。"}, headers=headers).json()
    for item in order["items"]:
        assert client.post(f"/api/medical/items/{item['id']}/confirm", headers=headers).status_code == 200
    return order["items"]


def _row(user_headers_name: str) -> dict:
    with get_engine().connect() as conn:
        row = conn.execute(text(
            "SELECT s.location_consent, s.area, s.area_saved_at, s.consent_updated_at FROM restaurant_settings s "
            "JOIN users u ON u.id = s.user_id WHERE u.username = :name"), {"name": user_headers_name}).one()
    return dict(row._mapping)


def _all_rows_text() -> str:
    """整个数据库每张表的原始内容（加密列就是密文）。"""
    parts = []
    with get_engine().connect() as conn:
        for table in Base.metadata.sorted_tables:
            parts += conn.execute(text(f"SELECT t::text FROM {table.name} t")).scalars().all()
    return "\n".join(parts)


# ---------- 验收第 1 条：授权定位后检索 ----------


def test_granted_gps_search_returns_shops_with_distance_type_and_conclusion(client, fake):
    headers = ready_user(client, "ann")
    assert client.get(f"{URL}/settings", headers=headers).json()["should_ask_location"] is True
    _grant(client, headers)
    body = _ok(client, headers, location={**GPS, "coord_type": "gps"})

    [around] = fake.calls("/v5/place/around")
    gcj = wgs84_to_gcj02(GPS["lng"], GPS["lat"])
    assert around["location"] == f"{gcj[0]:.6f},{gcj[1]:.6f}"  # 高德收到的是换算后的坐标
    assert around["types"] == "050000" and around["radius"] == "2000" and "keywords" not in around
    assert body["center"] == {"name": "你的当前位置", "source": "gps"}
    assert body["needs"] == {"keys": [], "names": [], "source": "none"}
    assert set(_names(body)) == {"老川菜馆", "张记粥铺", "绿叶轻食", "老码头火锅", "杨记麻辣烫", "张姐面馆", "某某餐厅"}
    sichuan = _shop(body, "老川菜馆")
    assert sichuan == {"id": "B001", "name": "老川菜馆", "type_key": "sichuan", "type_name": sichuan["type_name"],
                       "distance_m": 120, "rating": 4.6, "address": "建国路 1 号", "conclusion": sichuan["conclusion"],
                       "nav_url": sichuan["nav_url"], "tip": None}
    assert sichuan["type_name"] and sichuan["conclusion"] in ("suitable", "caution")
    unknown = _shop(body, "某某餐厅")
    assert unknown["type_key"] is None and unknown["type_name"] is None
    assert unknown["conclusion"] == "unchecked" and unknown["tip"] == UNCHECKED_TIP
    assert _shop(body, "张姐面馆")["rating"] is None
    assert body["restaurants"][-1]["name"] == "某某餐厅"  # 未核对排在最后
    assert {shop["type_key"] for shop in body["restaurants"]} == {
        "sichuan", "porridge", "salad", "hotpot", "malatang", "noodles", None}


def test_gcj02_coordinates_are_sent_unchanged(client, fake):
    headers = ready_user(client, "abe")
    _grant(client, headers)
    _ok(client, headers, location={**GPS, "coord_type": "gcj02"})
    assert fake.calls("/v5/place/around")[0]["location"] == "116.461234,39.909876"


def test_coordinates_default_to_gps(client, fake):
    headers = ready_user(client, "amy")
    _grant(client, headers)
    _ok(client, headers, location=GPS, radius=800)
    gcj = wgs84_to_gcj02(GPS["lng"], GPS["lat"])
    [around] = fake.calls("/v5/place/around")
    assert around["location"] == f"{gcj[0]:.6f},{gcj[1]:.6f}" and around["radius"] == "800"


# ---------- 验收第 2 条：手动地点 ----------


def test_manual_place_without_consent_works(client, fake):
    headers = ready_user(client, "bob")
    body = _ok(client, headers, place="国贸", city="北京")
    [geo] = fake.calls("/v3/geocode/geo")
    assert geo["address"] == "国贸" and geo["city"] == "北京"
    [around] = fake.calls("/v5/place/around")
    assert around["location"] == "116.458000,39.908000"
    assert body["center"] == {"name": "北京市朝阳区国贸", "source": "place"}
    assert len(body["restaurants"]) == 7
    settings = client.get(f"{URL}/settings", headers=headers).json()
    assert settings["location_consent"] == "not_asked" and settings["area"] is None  # 手动地点不改变授权状态


def test_unknown_place_is_422_with_advice(client, fake):
    headers = ready_user(client, "ben")
    response = _search(client, headers, place="不存在的地方")
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "restaurant_place_not_found"
    assert "换个说法" in error["message"] and "城市" in error["message"]
    assert fake.calls("/v5/place/around") == []


# ---------- 验收第 3 条：忌口医嘱避开命中的类型 ----------


def test_spicy_order_avoids_sichuan_and_malatang_with_medical_reasons(client, fake):
    headers = ready_user(client, "cat")
    [item] = _spicy_order(client, headers)
    body = _ok(client, headers, place="国贸")

    names = _names(body)
    assert "老川菜馆" not in names and "杨记麻辣烫" not in names
    avoided = {group["type_key"]: group for group in body["avoided_types"]}
    assert set(avoided) == {"sichuan", "malatang"}
    assert avoided["sichuan"]["restaurants"] == ["老川菜馆"]
    assert avoided["malatang"]["restaurants"] == ["杨记麻辣烫"]
    for group in avoided.values():
        assert group["type_name"]
        assert group["reasons"]
        assert any(r["source"] == "medical" and r["ref"] == item["id"] for r in group["reasons"])
        for reason in group["reasons"]:
            assert set(reason) == {"food_name", "source", "effect", "code", "message", "ref"}
            assert reason["food_name"] in CATALOG_NAMES
    # 火锅这一类只有代表菜“火锅”不建议，整类是“需要注意”：留在列表里，应避开里列出“火锅”并说明原因
    hotpot = _shop(body, "老码头火锅")
    assert hotpot["conclusion"] == "caution"
    hotpot_advice = _advice(body, "hotpot")
    assert hotpot_advice["conclusion"] == "caution" and "火锅" in hotpot_advice["avoid"]
    assert any(r["food_name"] == "火锅" and r["source"] == "medical" and r["ref"] == item["id"]
               for r in hotpot_advice["reasons"])
    # 避开的类型也给出整类建议，原因与 avoided_types 一致
    assert _advice(body, "sichuan")["reasons"] == avoided["sichuan"]["reasons"]
    assert _advice(body, "sichuan")["conclusion"] == "not_recommended"
    # 适合的排在需要注意的前面
    conclusions = [shop["conclusion"] for shop in body["restaurants"]]
    assert conclusions == sorted(conclusions, key=["suitable", "caution", "unchecked"].index)


def test_ordinary_user_does_not_avoid_sichuan(client, fake):
    headers = ready_user(client, "cid")
    body = _ok(client, headers, place="国贸")
    assert body["avoided_types"] == []
    assert "老川菜馆" in _names(body) and "杨记麻辣烫" in _names(body)


# ---------- 验收第 4 条：一般性建议的固定提示 ----------


def test_every_result_carries_the_notice_and_dish_names_come_from_the_catalog(client, fake):
    headers = ready_user(client, "dan")
    _spicy_order(client, headers)
    body = _ok(client, headers, place="国贸")
    assert body["notice"] == NOTICE == restaurant_service.NOTICE
    assert body["disclaimer"] == DISCLAIMER
    keys = {item["type_key"] for item in body["type_advice"]}
    assert keys == {"sichuan", "porridge", "salad", "hotpot", "malatang", "noodles"}
    for item in body["type_advice"]:
        assert set(item) == {"type_key", "type_name", "conclusion", "order", "moderate", "avoid", "reasons"}
        dishes = item["order"] + item["moderate"] + item["avoid"]
        assert dishes and set(dishes) <= CATALOG_NAMES
    empty = _ok(client, ready_user(client, "dee"), place="国贸", need="想喝粥")
    assert empty["notice"] == NOTICE


# ---------- 验收第 5 条：导航跳转 ----------


def test_every_shop_has_a_navigation_link_to_its_coordinates_and_name(client, fake):
    headers = ready_user(client, "eve")
    body = _ok(client, headers, place="国贸")
    by_id = {poi["id"]: poi for poi in POIS}
    for shop in body["restaurants"]:
        raw = by_id[shop["id"]]
        lng, lat = (float(part) for part in raw["location"].split(","))
        expected = navigation_url(Poi(raw["id"], raw["name"], lng, lat, "", "", "", None, None))
        assert shop["nav_url"] == expected
        assert shop["nav_url"].startswith("https://uri.amap.com/navigation?to=")
        assert f"{lng:.6f},{lat:.6f}," in shop["nav_url"]


# ---------- 验收第 6 条：精确位置不入库，粗略区域可清除 ----------


def test_search_stores_no_coordinates_or_place_text(client, fake):
    headers = ready_user(client, "fay")
    _grant(client, headers)
    _ok(client, headers, location={**GPS, "coord_type": "gps"}, need="想喝粥")
    _ok(client, headers, place="国贸", city="北京")
    gcj = wgs84_to_gcj02(GPS["lng"], GPS["lat"])
    dump = _all_rows_text()
    for secret in ("116.461234", "39.909876", f"{gcj[0]:.6f}", f"{gcj[1]:.6f}", "国贸", "想喝粥"):
        assert secret not in dump
    row = _row("fay")
    assert row["area"] is None and row["area_saved_at"] is None


def test_remember_area_from_gps_saves_encrypted_rough_area_and_can_be_cleared(client, fake):
    headers = ready_user(client, "gus")
    _grant(client, headers)
    _ok(client, headers, location={**GPS, "coord_type": "gps"}, remember_area=True)
    [regeo] = fake.calls("/v3/geocode/regeo")
    gcj = wgs84_to_gcj02(GPS["lng"], GPS["lat"])
    assert regeo["location"] == f"{gcj[0]:.6f},{gcj[1]:.6f}"

    row = _row("gus")
    assert "朝阳区" not in row["area"] and not row["area"].startswith("{")  # 数据库里是密文
    area = decrypt_value(row["area"])
    assert area == {"name": "朝阳区", "adcode": "110105", "lng": round(gcj[0], 2), "lat": round(gcj[1], 2)}
    assert row["area_saved_at"] is not None
    settings = client.get(f"{URL}/settings", headers=headers).json()
    assert settings["area"]["name"] == "朝阳区" and settings["area"]["saved_at"]
    assert set(settings["area"]) == {"name", "saved_at"}

    saved = _ok(client, headers, use_saved_area=True)
    assert saved["center"] == {"name": "朝阳区", "source": "saved_area"}
    assert fake.calls("/v5/place/around")[-1]["location"] == f"{round(gcj[0], 2):.6f},{round(gcj[1], 2):.6f}"

    assert client.delete(f"{URL}/settings/area", headers=headers).status_code == 204
    row = _row("gus")
    assert row["area"] is None and row["area_saved_at"] is None
    assert client.get(f"{URL}/settings", headers=headers).json()["area"] is None
    response = _search(client, headers, use_saved_area=True)
    assert response.status_code == 422 and response.json()["error"]["code"] == "restaurant_no_location"


def test_remember_area_from_place_uses_the_geocoded_district(client, fake):
    headers = ready_user(client, "hal")
    _ok(client, headers, place="国贸", city="北京", remember_area=True)
    assert fake.calls("/v3/geocode/regeo") == []
    area = decrypt_value(_row("hal")["area"])
    assert area == {"name": "朝阳区", "adcode": "110105", "lng": 116.46, "lat": 39.91}


def test_city_level_match_saves_the_province_name_not_an_empty_one(client, fake):
    headers = ready_user(client, "hap")
    _ok(client, headers, place="北京", remember_area=True)
    area = decrypt_value(_row("hap")["area"])
    assert area["name"] == "北京市" and area["adcode"] == "110000"  # 来自 province：district 与 city 都是空数组

    # 连省份也没有时用固定名称，不用解析出的地址名称，也不用用户输入的原文
    fake.geocodes["北京"] = [{**CITY_LEVEL, "province": []}]
    _ok(client, headers, place="北京", remember_area=True)
    assert decrypt_value(_row("hap")["area"])["name"] == "大致区域"


def test_gps_area_without_district_uses_the_city_not_the_street_address(client, fake):
    headers = ready_user(client, "hay")
    _grant(client, headers)
    fake.regeo = DONGGUAN_REGEO
    _ok(client, headers, location={"lng": 113.75, "lat": 23.02}, remember_area=True)
    area = decrypt_value(_row("hay")["area"])
    assert area["name"] == "东莞市" and area["adcode"] == "441900"
    assert client.get(f"{URL}/settings", headers=headers).json()["area"]["name"] == "东莞市"


def test_saved_area_without_saving_is_422(client, fake):
    headers = ready_user(client, "hob")
    response = _search(client, headers, use_saved_area=True)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "restaurant_no_location"
    assert fake.requests == []


# ---------- 验收第 7 条：拒绝授权后不反复索要 ----------


def test_denied_consent_is_never_asked_again_and_coordinates_get_409(client, fake):
    headers = ready_user(client, "ivy")
    denied = _grant(client, headers, "denied")
    assert denied["location_consent"] == "denied" and denied["should_ask_location"] is False
    assert _row("ivy")["consent_updated_at"] is not None

    response = _search(client, headers, location=GPS)
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "restaurant_location_not_granted"
    assert "输入地点" in error["message"]
    for nagging in ("请授权", "开启定位", "打开定位", "允许定位", "去授权", "重新授权"):
        assert nagging not in error["message"]
    assert fake.requests == []

    assert _ok(client, headers, place="国贸")["restaurants"]
    for _ in range(2):
        settings = client.get(f"{URL}/settings", headers=headers).json()
        assert settings["should_ask_location"] is False and settings["location_consent"] == "denied"

    _grant(client, headers, "granted")
    assert _ok(client, headers, location=GPS)["center"]["source"] == "gps"


def test_not_asked_consent_also_rejects_coordinates(client, fake):
    headers = ready_user(client, "ike")
    response = _search(client, headers, location=GPS)
    assert response.status_code == 409
    assert client.get(f"{URL}/settings", headers=headers).json() == {
        "location_consent": "not_asked", "should_ask_location": True, "area": None}


def test_consent_only_accepts_granted_or_denied(client, fake):
    headers = ready_user(client, "ida")
    for body in ({"consent": "not_asked"}, {"consent": "maybe"}, {}, {"consent": "granted", "user_id": "x"}):
        assert client.put(f"{URL}/settings/consent", json=body, headers=headers).status_code == 422


# ---------- 需求 ----------


def test_needs_vocabulary_endpoint(client, fake):
    headers = ready_user(client, "jay")
    body = client.get(f"{URL}/needs", headers=headers).json()
    assert body == [{"key": n.key, "name": n.name, "description": n.description} for n in load_needs()]


def test_rule_matched_need_sends_its_keywords(client, fake):
    headers = ready_user(client, "jon")
    body = _ok(client, headers, place="国贸", need="胃不舒服想喝点粥")
    by_key = {need.key: need for need in load_needs()}
    keys = list(match_rules("胃不舒服想喝点粥"))
    assert body["needs"] == {"keys": keys, "names": [by_key[k].name for k in keys], "source": "rules"}
    expected = list(dict.fromkeys(kw for k in keys for kw in by_key[k].keywords))[:3]
    assert [call["keywords"] for call in fake.calls("/v5/place/around")] == expected
    assert len({shop["id"] for shop in body["restaurants"]}) == len(body["restaurants"]) == 7  # 按编号去重
    assert body["restaurants"][0]["name"] == "张记粥铺"  # 偏向的类型排在同结论的前面


def test_direct_need_keys_are_merged(client, fake):
    headers = ready_user(client, "joy")
    body = _ok(client, headers, place="国贸", needs=["noodles"])
    assert body["needs"]["keys"] == ["noodles"]
    by_key = {need.key: need for need in load_needs()}
    assert [c["keywords"] for c in fake.calls("/v5/place/around")] == list(by_key["noodles"].keywords)[:3]


def test_model_picks_needs_when_rules_miss_and_unknown_words_are_dropped(client, fake, scripted):  # noqa: F811
    assert match_rules(NEED_TEXT_WITHOUT_RULES) == ()
    headers = ready_user(client, "kim")
    connect(client, headers)
    scripted.add(say(json.dumps({"needs": ["soup", "kebab", "porridge"]})))
    body = _ok(client, headers, place="国贸", need=NEED_TEXT_WITHOUT_RULES)

    [request] = scripted.requests
    assert MODEL_PROMPT in request.system
    assert NEED_TEXT_WITHOUT_RULES in request.text()
    assert body["needs"]["keys"] == ["soup", "porridge"] and body["needs"]["source"] == "model"
    by_key = {need.key: need for need in load_needs()}
    expected = list(dict.fromkeys([*by_key["soup"].keywords, *by_key["porridge"].keywords]))[:3]
    assert [c["keywords"] for c in fake.calls("/v5/place/around")] == expected


def test_model_is_not_called_when_rules_match(client, fake, scripted):  # noqa: F811
    headers = ready_user(client, "kit")
    connect(client, headers)
    assert _ok(client, headers, place="国贸", need="想吃面")["needs"]["source"] == "rules"
    assert scripted.requests == []


def test_without_chat_model_the_need_step_is_skipped_silently(client, fake, scripted):  # noqa: F811
    headers = ready_user(client, "lee")
    body = _ok(client, headers, place="国贸", need=NEED_TEXT_WITHOUT_RULES)
    assert body["needs"] == {"keys": [], "names": [], "source": "none"}
    assert scripted.requests == []
    [around] = fake.calls("/v5/place/around")
    assert "keywords" not in around


def test_failing_or_unhelpful_model_falls_back_to_no_need(client, fake, scripted):  # noqa: F811
    headers = ready_user(client, "lou")
    connect(client, headers)
    scripted.add(fail(500), say("我推荐火锅"))
    for _ in range(2):
        body = _ok(client, headers, place="国贸", need=NEED_TEXT_WITHOUT_RULES)
        assert body["needs"] == {"keys": [], "names": [], "source": "none"}
    assert len(scripted.requests) == 2


def test_service_without_factory_skips_the_model(client, fake, scripted):  # noqa: F811
    headers = ready_user(client, "lyn")
    connect(client, headers)
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    amap_client = AmapClient(KEY, BASE, 5.0, transport=httpx2.MockTransport(fake))
    with get_sessionmaker()() as db:
        result = restaurant_service.search(
            db, uuid.UUID(user_id), SearchIn(place="国贸", need=NEED_TEXT_WITHOUT_RULES), date.today(),
            client=amap_client, factory=None)
    assert result["needs"]["source"] == "none" and scripted.requests == []
    assert result["notice"] == NOTICE and len(result["restaurants"]) == 7


# ---------- 请求校验 ----------


@pytest.mark.parametrize("body", [
    {"location": GPS, "place": "国贸"},
    {"place": "国贸", "use_saved_area": True},
    {"location": GPS, "use_saved_area": True},
    {"city": "北京"},
    {"location": GPS, "city": "北京"},
    {"place": "国贸", "needs": ["light", "soup", "porridge", "noodles"]},
    {"place": "国贸", "radius": 499},
    {"place": "国贸", "radius": 5001},
    {"place": ""},
    {"place": "国" * 51},
    {"place": "国贸", "city": "北" * 21},
    {"place": "国贸", "need": "想" * 101},
    {"location": {"lng": 181, "lat": 39.9}},
    {"location": {"lng": 116.4, "lat": -91}},
    {"location": {**GPS, "coord_type": "bd09"}},
    {"place": "国贸", "user_id": "someone"},
])
def test_invalid_requests_are_422(client, fake, body):
    headers = ready_user(client, "max")
    _grant(client, headers)
    response = _search(client, headers, **body)
    assert response.status_code == 422, body
    assert response.json()["error"]["code"] == "validation_error"
    assert fake.requests == []


def test_no_location_at_all_is_restaurant_no_location(client, fake):
    headers = ready_user(client, "meg")
    response = _search(client, headers, need="想喝粥")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "restaurant_no_location"
    assert "地点" in response.json()["error"]["message"]


def test_unknown_need_key_is_rejected_before_any_network_call(client, fake):
    headers = ready_user(client, "mia")
    response = _search(client, headers, place="国贸", needs=["kebab"])
    assert response.status_code == 422 and response.json()["error"]["code"] == "restaurant_unknown_need"
    assert fake.requests == []


# ---------- 错误 ----------


def test_missing_amap_key_is_503(client, fake, monkeypatch):
    monkeypatch.setattr(amap, "get_settings", lambda: settings())
    headers = ready_user(client, "ned")
    response = _search(client, headers, place="国贸")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "restaurant_not_configured"
    assert fake.requests == []
    assert client.get(f"{URL}/settings", headers=headers).status_code == 200  # 设置与词表不依赖密钥
    assert client.get(f"{URL}/needs", headers=headers).status_code == 200


def test_amap_quota_is_503_and_failure_is_502_without_the_key(client, fake):
    headers = ready_user(client, "nia")
    fake.override = httpx2.Response(200, json={"status": "0", "info": f"OVER {KEY}", "infocode": "10003"})
    response = _search(client, headers, place="国贸")
    assert response.status_code == 503 and response.json()["error"]["code"] == "restaurant_service_busy"
    assert KEY not in response.text
    fake.override = httpx2.Response(500, text=f"boom {KEY}")
    response = _search(client, headers, place="国贸")
    assert response.status_code == 502 and response.json()["error"]["code"] == "restaurant_service_failed"
    assert KEY not in response.text


def test_rate_limit_is_per_user_per_hour(client, fake, monkeypatch):
    assert restaurant_service.RATE_LIMIT == 30
    monkeypatch.setattr(restaurant_service, "RATE_LIMIT", 2)
    first, second = ready_user(client, "ozzy"),ready_user(client, "ola")
    for _ in range(2):
        _ok(client, first, place="国贸")
    response = _search(client, first, place="国贸")
    assert response.status_code == 429
    error = response.json()["error"]
    assert error["code"] == "restaurant_rate_limited" and "稍后" in error["message"]
    assert len(fake.calls("/v3/geocode/geo")) == 2
    _ok(client, second, place="国贸")
    restaurant_service.reset_rate_limit()
    _ok(client, first, place="国贸")


def test_rate_limit_window_slides_and_idle_users_are_evicted(monkeypatch):
    restaurant_service.reset_rate_limit()
    monkeypatch.setattr(restaurant_service, "RATE_LIMIT", 2)
    clock = [1000.0]
    monkeypatch.setattr(restaurant_service.time, "monotonic", lambda: clock[0])
    busy, idle = uuid.uuid4(), uuid.uuid4()
    restaurant_service._check_rate(idle)
    clock[0] += 1800
    restaurant_service._check_rate(busy)
    restaurant_service._check_rate(busy)
    with pytest.raises(AppError) as exc:
        restaurant_service._check_rate(busy)
    assert exc.value.status_code == 429
    assert set(restaurant_service._recent_searches) == {idle, busy}

    clock[0] += 1800  # idle 的那次已满一小时
    with pytest.raises(AppError):
        restaurant_service._check_rate(busy)  # busy 的两次还在窗口里
    assert set(restaurant_service._recent_searches) == {busy}  # 窗口里没有记录的用户被移出

    clock[0] += 1800
    restaurant_service._check_rate(busy)  # 窗口滑过之后重新建立计数
    assert len(restaurant_service._recent_searches[busy]) == 1
    restaurant_service.reset_rate_limit()


# ---------- 事务 ----------


def test_no_database_transaction_is_open_during_amap_or_model_calls(client, fake, scripted, monkeypatch):  # noqa: F811
    make_session = get_sessionmaker()
    sessions: list = []
    fake.sessions = scripted.sessions = sessions

    def tracked_db():
        session = make_session()
        sessions.append(session)
        try:
            yield session
        finally:
            session.close()

    def tracked_sessionmaker():
        def make():
            session = make_session()
            sessions.append(session)
            return session

        return make

    headers = ready_user(client, "pam")
    connect(client, headers)
    _grant(client, headers)
    _spicy_order(client, headers)
    client.app.dependency_overrides[get_db] = tracked_db
    monkeypatch.setattr(llm_service, "get_sessionmaker", tracked_sessionmaker)
    scripted.add(say(json.dumps({"needs": ["soup"]})))
    try:
        _ok(client, headers, location=GPS, need=NEED_TEXT_WITHOUT_RULES, remember_area=True)
        _ok(client, headers, place="国贸", remember_area=True)
    finally:
        client.app.dependency_overrides.pop(get_db)
    assert len(scripted.in_transaction) == 1
    assert len(fake.in_transaction) == 3 + 1 + 1 + 1  # 三次周边、一次逆地理；一次地址解析、一次周边
    assert scripted.in_transaction == [False]
    assert fake.in_transaction == [False] * 6


# ---------- 归属与准入 ----------


def test_settings_only_affect_their_owner(client, fake):
    owner, other = ready_user(client, "quinn"), ready_user(client, "quill")
    _grant(client, owner)
    _ok(client, owner, place="国贸", remember_area=True)
    assert client.get(f"{URL}/settings", headers=other).json() == {
        "location_consent": "not_asked", "should_ask_location": True, "area": None}
    assert _search(client, other, location=GPS).status_code == 409
    assert _search(client, other, use_saved_area=True).status_code == 422
    _grant(client, other, "denied")
    assert client.delete(f"{URL}/settings/area", headers=other).status_code == 204
    owner_settings = client.get(f"{URL}/settings", headers=owner).json()
    assert owner_settings["location_consent"] == "granted" and owner_settings["area"]["name"] == "朝阳区"


def test_restaurant_routes_need_login_and_nutrition_access(client, fake):
    assert client.get(f"{URL}/settings").status_code == 401
    from tests.helpers import register_and_login

    headers = register_and_login(client, "ray")  # 没有确认免责声明
    assert client.get(f"{URL}/needs", headers=headers).status_code == 403
    assert _search(client, headers, place="国贸").status_code == 403
    assert fake.requests == []
