import json
from datetime import date
from pathlib import Path

import pytest

from app.common.clock import get_today
from app.main import create_app
from app.medical.items import USER_ONLY_OPERATIONS
from app.sdk import AgentGrantToken, GoodLife, SdkError, UserAccessToken
from app.sdk.manifest import build_manifest
from app.sdk.registry import REGISTRY
from fastapi.testclient import TestClient
from tests.helpers import ready_user

TODAY = date(2026, 10, 7)
PROFILE = {"gender": "female", "birth_year": 1995, "height_cm": 163, "weight_kg": 55,
           "activity_level": "light", "goal": "maintain"}
MANIFEST = Path(__file__).resolve().parents[1] / "app" / "sdk" / "manifest.json"


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sdk():
    return GoodLife(today=lambda: TODAY)


def _token(client, headers, access="read_write"):
    return AgentGrantToken(client.post("/api/agent-grants", json={"name": "t", "access": access},
                                       headers=headers).json()["token"])


def test_capability_counts_and_levels():
    levels = {}
    for cap in REGISTRY.values():
        levels.setdefault(cap.level, set()).add(cap.name)
    assert (len(REGISTRY), len(levels["read"]), len(levels["write"]), len(levels["user_confirmed"])) == (32, 21, 5, 6)
    assert levels["write"] == {"cycle.record_period", "medical.submit_order", "medical.propose_resolution",
                               "nutrition.log_meal", "fitness.log_workout"}
    assert {name.removeprefix("medical.") for name in levels["user_confirmed"]} == set(USER_ONLY_OPERATIONS)
    for cap in REGISTRY.values():
        assert "user_id" not in cap.input_model.model_json_schema().get("properties", {}), cap.name
        assert cap.summary


def test_sdk_matches_rest_for_the_six_core_actions(client, sdk):
    headers = ready_user(client, "alice", PROFILE)
    token = _token(client, headers)
    period = sdk.call(token, "cycle.record_period", {"start_date": "2026-09-10", "end_date": "2026-09-14"}).data
    assert client.get("/api/cycle/periods", headers=headers).json() == [period]
    assert sdk.call(token, "cycle.get_prediction").data == client.get("/api/cycle/prediction", headers=headers).json()
    order = sdk.call(token, "medical.submit_order", {"text": "一周内忌食辛辣。"}).data
    assert [i["status"] for i in order["items"]] == ["pending_confirmation"]
    assert client.get(f"/api/medical/orders/{order['id']}", headers=headers).json() == order
    rice = sdk.call(token, "nutrition.search_foods", {"query": "米饭"}).data["results"][0]["id"]
    meal = sdk.call(token, "nutrition.log_meal", {"eaten_on": "2026-10-07", "meal_type": "lunch",
                                                   "food_id": rice, "grams": 150}).data
    assert client.get("/api/nutrition/meals", headers=headers).json() == [meal]
    evaluated = sdk.call(token, "nutrition.evaluate_food", {"food_id": rice, "grams": 150}).data
    assert evaluated == client.post("/api/nutrition/evaluate", json={"food_id": rice, "grams": 150},
                                    headers=headers).json()
    bench = sdk.call(token, "fitness.search_exercises", {"query": "卧推"}).data["results"][0]["id"]
    workout = sdk.call(token, "fitness.log_workout", {"performed_on": "2026-10-07", "rpe": 7, "strength": [
        {"exercise_id": bench, "sets": [{"weight_kg": 40, "reps": 10}]}]}).data
    assert client.get(f"/api/fitness/workouts/{workout['id']}", headers=headers).json() == workout


def test_medical_confirmation_only_with_user_token(client, sdk):
    headers = ready_user(client, "alice")
    token = _token(client, headers)
    [item] = sdk.call(token, "medical.submit_order", {"text": "一周内忌食辛辣。"}).data["items"]
    for name, params in (("medical.confirm_item", {"item_id": item["id"]}),
                         ("medical.resolve_item", {"item_id": item["id"]})):
        with pytest.raises(SdkError) as caught:
            sdk.call(token, name, params)
        assert caught.value.kind == "needs_user_confirmation"
    confirmed = sdk.call(UserAccessToken(headers["Authorization"].removeprefix("Bearer ")), "medical.confirm_item",
                         {"item_id": item["id"]}).data
    assert confirmed["status"] == "active"
    proposed = sdk.call(token, "medical.propose_resolution", {"item_id": item["id"], "reason": "医生说可以恢复"}).data
    assert proposed["resolution_proposed_at"] is not None and proposed["status"] == "active"


def test_isolation_and_read_only(client, sdk):
    alice = ready_user(client, "alice", PROFILE)
    order = sdk.call(_token(client, alice), "medical.submit_order", {"text": "一周内忌食辛辣。"}).data
    bella = ready_user(client, "bella", PROFILE)
    bella_token = _token(client, bella)
    with pytest.raises(SdkError) as caught:
        sdk.call(bella_token, "medical.get_item", {"item_id": order["items"][0]["id"]})
    assert caught.value.kind == "not_found"
    assert sdk.call(bella_token, "medical.list_items").data == []
    read_only = _token(client, bella, "read")
    for name, params in (("cycle.record_period", {"start_date": "2026-09-10"}),
                         ("medical.submit_order", {"text": "禁酒。"})):
        with pytest.raises(SdkError) as caught:
            sdk.call(read_only, name, params)
        assert caught.value.code == "write_not_granted"


def test_module_gate_and_notices(client, sdk):
    male = ready_user(client, "carl", {"gender": "male"})
    with pytest.raises(SdkError) as caught:
        sdk.call(_token(client, male), "cycle.get_prediction")
    assert (caught.value.kind, caught.value.code) == ("module_unavailable", "cycle_not_available")
    female = _token(client, ready_user(client, "dana", {"gender": "female"}))
    result = sdk.call(female, "cycle.get_prediction")
    assert [n.kind for n in result.notices] == ["insufficient_data"]
    summary = sdk.call(female, "nutrition.get_daily_summary")
    assert [n.kind for n in summary.notices] == ["insufficient_data"] and "体重" in summary.notices[0].message


def test_manifest_snapshot_is_current():
    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert build_manifest(REGISTRY) == expected, "能力清单有变化：确认向后兼容后运行 python -m app.sdk.manifest 更新快照"
