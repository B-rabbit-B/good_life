from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.common.clock import get_today
from app.main import create_app
from app.nutrition.catalog import load_catalog, round_one
from tests.helpers import ready_user, register_and_login

TODAY = date(2026, 10, 6)
RICE = "cfcd:012401x"
EGG = "cfcd:111101x"
PROFILE = {
    "gender": "female", "birth_year": 1998, "height_cm": 162.5, "weight_kg": 52,
    "activity_level": "light", "goal": "lose_fat",
}


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as test_client:
        yield test_client


def _log(client, headers, food_id, meal_type="lunch", **amount):
    body = {"eaten_on": "2026-10-06", "meal_type": meal_type, "food_id": food_id, **amount}
    response = client.post("/api/nutrition/meals", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_search_and_food_detail(client):
    headers = ready_user(client, "alice")
    body = client.get("/api/nutrition/foods/search", params={"q": "米饭"}, headers=headers).json()
    assert body["found"] is True
    assert body["results"][0]["id"] == RICE
    assert body["results"][0]["match"] == "exact_name"
    missing = client.get("/api/nutrition/foods/search", params={"q": "完全不存在的食物名称"}, headers=headers).json()
    assert (missing["found"], missing["results"]) == (False, [])
    assert "未找到" in missing["message"]
    detail = client.get(f"/api/nutrition/foods/{RICE}", headers=headers).json()
    assert detail["nutrients_per_100g"]["energy_kcal"] == 116
    assert detail["source"]["license_status"] == "personal_study_only"
    assert isinstance(detail["tags"], list)
    assert all({"id", "name", "kind", "basis"} <= set(tag) for tag in detail["tags"])
    assert client.get("/api/nutrition/foods/cfcd:nope", headers=headers).json()["error"]["code"] == "food_not_found"
    tags = client.get("/api/nutrition/tags", headers=headers).json()
    assert any(tag["kind"] == "tradition" and "传统" in tag["basis"] for tag in tags)


def test_daily_summary_matches_hand_calculation(client):
    headers = ready_user(client, "alice", PROFILE)
    catalog = load_catalog()
    plan = [("breakfast", EGG, 50), ("breakfast", RICE, 100), ("lunch", RICE, 150), ("dinner", RICE, 200)]
    for meal_type, food_id, grams in plan:
        _log(client, headers, food_id, meal_type, grams=grams)
    summary = client.get("/api/nutrition/summary", params={"date": "2026-10-06"}, headers=headers).json()
    expected_energy = sum(catalog.get(f).nutrients.energy_kcal * g / 100 for _, f, g in plan)
    assert summary["total"]["energy_kcal"] == round_one(expected_energy)
    assert summary["meals"]["lunch"]["energy_kcal"] == 174.0
    assert summary["meals"]["snack"]["energy_kcal"] == 0
    expected_protein = sum(catalog.get(f).nutrients.protein_g * g / 100 for _, f, g in plan)
    assert summary["total"]["protein_g"] == round_one(expected_protein)
    assert summary["needs"]["energy_kcal"] == 1443
    assert summary["remaining"]["energy_kcal"] == round_one(1443 - expected_energy)


def test_portion_units_and_validation(client):
    headers = ready_user(client, "alice")
    food = load_catalog().get(RICE)
    bowl = dict(food.portions)["碗"]
    entry = _log(client, headers, RICE, portion={"unit": "碗", "count": 2})
    assert entry["grams"] == bowl * 2
    bad = [
        {"food_id": RICE},
        {"food_id": RICE, "grams": 100, "portion": {"unit": "碗", "count": 1}},
        {"food_id": RICE, "portion": {"unit": "桶", "count": 1}},
        {"food_id": RICE, "grams": 0},
    ]
    for extra in bad:
        body = {"eaten_on": "2026-10-06", "meal_type": "lunch", **extra}
        assert client.post("/api/nutrition/meals", json=body, headers=headers).status_code == 422, extra
    future = {"eaten_on": "2026-10-07", "meal_type": "lunch", "food_id": RICE, "grams": 100}
    assert client.post("/api/nutrition/meals", json=future, headers=headers).json()["error"]["code"] == "meal_in_future"
    unknown = {"eaten_on": "2026-10-06", "meal_type": "lunch", "food_id": "cfcd:nope", "grams": 100}
    assert client.post("/api/nutrition/meals", json=unknown, headers=headers).json()["error"]["code"] == "food_not_found"


def test_update_and_delete_meal(client):
    headers = ready_user(client, "alice")
    entry = _log(client, headers, RICE, grams=100)
    updated = client.patch(f"/api/nutrition/meals/{entry['id']}", json={"grams": 200}, headers=headers).json()
    assert updated["nutrients"]["energy_kcal"] == 232.0
    switched = client.patch(f"/api/nutrition/meals/{entry['id']}", json={"food_id": EGG}, headers=headers).json()
    assert switched["food_id"] == EGG
    assert client.delete(f"/api/nutrition/meals/{entry['id']}", headers=headers).status_code == 204
    assert client.get("/api/nutrition/meals", params={"date": "2026-10-06"}, headers=headers).json() == []


def test_meals_are_private(client):
    alice = ready_user(client, "alice")
    entry = _log(client, alice, RICE, grams=100, note="私密备注")
    bella = ready_user(client, "bella")
    assert client.get("/api/nutrition/meals", params={"date": "2026-10-06"}, headers=bella).json() == []
    assert client.patch(f"/api/nutrition/meals/{entry['id']}", json={"grams": 1}, headers=bella).status_code == 404
    assert client.delete(f"/api/nutrition/meals/{entry['id']}", headers=bella).status_code == 404
    summary = client.get("/api/nutrition/summary", params={"date": "2026-10-06"}, headers=bella).json()
    assert summary["total"]["energy_kcal"] == 0


def test_needs_endpoint(client):
    complete = ready_user(client, "alice", PROFILE)
    assert client.get("/api/nutrition/needs", headers=complete).json()["energy_kcal"] == 1443
    incomplete = ready_user(client, "bella")
    body = client.get("/api/nutrition/needs", headers=incomplete).json()
    assert body["status"] == "insufficient_profile"


def test_nutrition_requires_login_and_disclaimer(client):
    assert client.get("/api/nutrition/tags").status_code == 401
    headers = register_and_login(client, "carl")
    assert client.get("/api/nutrition/tags", headers=headers).json()["error"]["code"] == "disclaimer_not_accepted"


def test_note_only_edit_keeps_snapshot_and_does_not_touch_catalog(client, monkeypatch):
    from app.nutrition import meals

    headers = ready_user(client, "alice")
    entry = _log(client, headers, RICE, grams=100, note="旧备注")

    def unavailable(*args, **kwargs):
        raise AssertionError("note-only edit must not read the catalog")

    monkeypatch.setattr(meals, "load_catalog", unavailable)
    monkeypatch.setattr(meals, "get_food", unavailable)
    for change in ({"note": "新备注"}, {"meal_type": "dinner"}, {"eaten_on": "2026-10-05"}):
        updated = client.patch(f"/api/nutrition/meals/{entry['id']}", json=change, headers=headers)
        assert updated.status_code == 200, updated.text
        body = updated.json()
        assert body["nutrients"] == entry["nutrients"] and body["grams"] == 100
        assert body["food_name"] == entry["food_name"]
    assert body["note"] == "新备注" and body["meal_type"] == "dinner" and body["eaten_on"] == "2026-10-05"
