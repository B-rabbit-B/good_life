from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.common.clock import get_today
from app.main import create_app
from tests.helpers import ready_user

TODAY = date(2026, 10, 6)


@pytest.fixture
def medical_today():
    state = {"today": TODAY}
    app = create_app()
    app.dependency_overrides[get_today] = lambda: state["today"]
    with TestClient(app) as client:
        yield client, state


def _id(client, headers, name):
    return client.get("/api/nutrition/foods/search", params={"q": name}, headers=headers).json()["results"][0]["id"]


def _evaluate(client, headers, name, **amount):
    body = {"food_id": _id(client, headers, name), **amount}
    response = client.post("/api/nutrition/evaluate", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _confirmed_order(client, headers, text):
    order = client.post("/api/medical/orders", json={"text": text}, headers=headers).json()
    for item in order["items"]:
        assert client.post(f"/api/medical/items/{item['id']}/confirm", headers=headers).status_code == 200
    return order["items"]


def test_user_with_medical_avoidance(medical_today):
    client, _ = medical_today
    headers = ready_user(client, "alice")
    [item] = _confirmed_order(client, headers, "一周内忌食辛辣、油腻食物，禁酒。")
    for name in ("麻婆豆腐", "啤酒", "炸鸡"):
        result = _evaluate(client, headers, name)
        assert result["conclusion"] == "not_recommended", name
        assert any(r["source"] == "medical" and r["ref"] == item["id"] for r in result["reasons"]), name
    assert _evaluate(client, headers, "清炒西兰花")["conclusion"] == "suitable"


def test_pending_review_still_blocks_and_resolution_releases(medical_today):
    client, state = medical_today
    headers = ready_user(client, "alice")
    [item] = _confirmed_order(client, headers, "三天内禁酒。")
    state["today"] = date(2026, 10, 8)
    result = _evaluate(client, headers, "啤酒")
    assert result["conclusion"] == "not_recommended"
    assert any("待复核" in r["message"] for r in result["reasons"])
    client.post(f"/api/medical/items/{item['id']}/resolve", headers=headers)
    assert _evaluate(client, headers, "啤酒")["conclusion"] != "not_recommended"


def test_menstrual_user_gets_cycle_caution_for_cold_food(medical_today):
    client, _ = medical_today
    headers = ready_user(client, "bella", {"gender": "female"})
    for start, end in [("2026-07-13", "2026-07-17"), ("2026-08-10", "2026-08-14"), ("2026-09-07", "2026-09-11"),
                       ("2026-10-05", None)]:
        assert client.post("/api/cycle/periods", json={"start_date": start, "end_date": end},
                           headers=headers).status_code == 201
    result = _evaluate(client, headers, "西瓜")
    assert result["conclusion"] == "caution"
    cycle = [r for r in result["reasons"] if r["source"] == "cycle"]
    assert cycle and all("不是医嘱" in r["message"] for r in cycle)
    assert not any(r["source"] == "medical" for r in result["reasons"])


def test_gain_muscle_user_prefers_protein(medical_today):
    client, _ = medical_today
    headers = ready_user(client, "carl", {"gender": "male", "goal": "gain_muscle", "birth_year": 1990,
                                          "height_cm": 175, "weight_kg": 70, "activity_level": "moderate"})
    result = _evaluate(client, headers, "鸡胸肉", grams=150)
    assert result["conclusion"] == "suitable"
    assert any(r["source"] == "goal" and r["effect"] == "prefer" for r in result["reasons"])


def test_healthy_user_and_determinism(medical_today):
    client, _ = medical_today
    headers = ready_user(client, "dora", {"birth_year": 1995, "height_cm": 165, "weight_kg": 55,
                                          "activity_level": "light"})
    first = _evaluate(client, headers, "番茄炒蛋")
    assert first["conclusion"] == "suitable"
    assert "不构成医疗建议" in first["disclaimer"]
    for _ in range(3):
        assert _evaluate(client, headers, "番茄炒蛋") == first


def test_hard_beats_soft_end_to_end(medical_today):
    client, _ = medical_today
    headers = ready_user(client, "erin", {"gender": "male", "goal": "gain_muscle"})
    _confirmed_order(client, headers, "一个月内忌动物内脏。")
    result = _evaluate(client, headers, "猪肝")
    assert result["conclusion"] == "not_recommended"
    assert "医嘱优先" in (result["tradeoff"] or "")


def test_meal_evaluation_and_validation(medical_today):
    client, _ = medical_today
    headers = ready_user(client, "fay")
    _confirmed_order(client, headers, "禁酒。")
    items = [{"food_id": _id(client, headers, n), "grams": 200} for n in ("米饭", "番茄炒蛋", "啤酒")]
    body = client.post("/api/nutrition/evaluate-meal", json={"items": items}, headers=headers).json()
    assert [i["conclusion"] for i in body["items"]][-1] == "not_recommended"
    assert body["conclusion"] == "not_recommended"
    assert body["total"]["energy_kcal"] > 0
    assert client.post("/api/nutrition/evaluate-meal", json={"items": []}, headers=headers).status_code == 422
    bad = client.post("/api/nutrition/evaluate", json={"food_id": "cfcd:nope"}, headers=headers)
    assert bad.json()["error"]["code"] == "food_not_found"
    assert client.post("/api/nutrition/evaluate", json={"food_id": items[0]["food_id"], "date": "2026-10-07"},
                       headers=headers).status_code == 422


def test_unrecognised_order_caps_at_caution(medical_today):
    client, _ = medical_today
    headers = ready_user(client, "gina")
    order = client.post("/api/medical/orders", json={"text": "忌食发物。"}, headers=headers).json()
    client.post(f"/api/medical/items/{order['items'][0]['id']}/confirm", headers=headers)
    result = _evaluate(client, headers, "清炒西兰花")
    assert result["conclusion"] == "caution"
    assert any(r["effect"] == "unverifiable" and "发物" in r["message"] for r in result["reasons"])


def test_amount_defaults_portion_and_conflicts(medical_today):
    client, _ = medical_today
    headers = ready_user(client, "hana")
    food_id = _id(client, headers, "米饭")
    detail = client.get(f"/api/nutrition/foods/{food_id}", headers=headers).json()
    default = client.post("/api/nutrition/evaluate", json={"food_id": food_id}, headers=headers).json()
    assert default["grams"] == detail["default_grams"]
    unit = detail["portions"][0]
    by_portion = client.post("/api/nutrition/evaluate", headers=headers,
                             json={"food_id": food_id, "portion": {"unit": unit["unit"], "count": 2}}).json()
    assert by_portion["grams"] == unit["grams"] * 2
    both = client.post("/api/nutrition/evaluate", headers=headers,
                       json={"food_id": food_id, "grams": 100, "portion": {"unit": unit["unit"], "count": 1}})
    assert both.status_code == 422
    bad_unit = client.post("/api/nutrition/evaluate", headers=headers,
                           json={"food_id": food_id, "portion": {"unit": "不存在", "count": 1}})
    assert bad_unit.json()["error"]["code"] == "invalid_portion"
    assert client.post("/api/nutrition/evaluate", json={"food_id": food_id, "grams": 0},
                       headers=headers).json()["error"]["code"] == "invalid_portion"
    too_many = {"items": [{"food_id": food_id}] * 21}
    assert client.post("/api/nutrition/evaluate-meal", json=too_many, headers=headers).status_code == 422
