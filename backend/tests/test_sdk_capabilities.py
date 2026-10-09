import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.common.clock import get_today
from app.main import create_app
from app.medical.items import USER_ONLY_OPERATIONS
from app.medical.samples import SAMPLE_ORDERS
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
    assert (len(REGISTRY), len(levels["read"]), len(levels["write"]), len(levels["user_confirmed"])) == (33, 22, 5, 6)
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


def _events(client, headers, item_id):
    return client.get(f"/api/medical/items/{item_id}/events", headers=headers).json()


def test_propose_resolution_records_the_actor(client, sdk):
    headers = ready_user(client, "alice")
    token = _token(client, headers)
    user = UserAccessToken(headers["Authorization"].removeprefix("Bearer "))
    [item] = sdk.call(token, "medical.submit_order", {"text": "一周内忌食辛辣。"}).data["items"]
    sdk.call(user, "medical.confirm_item", {"item_id": item["id"]})
    sdk.call(token, "medical.propose_resolution", {"item_id": item["id"], "reason": "医生说可以恢复"})
    assert [e["source"] for e in _events(client, headers, item["id"]) if e["action"] == "resolution_proposed"] == [
        "agent"]
    sdk.call(user, "medical.cancel_resolution_proposal", {"item_id": item["id"]})
    sdk.call(user, "medical.propose_resolution", {"item_id": item["id"], "reason": "复查正常"})
    assert [e["source"] for e in _events(client, headers, item["id"]) if e["action"] == "resolution_proposed"] == [
        "agent", "user"]


def test_phase_notice_without_any_period(client, sdk):
    token = _token(client, ready_user(client, "dana", {"gender": "female"}))
    result = sdk.call(token, "cycle.get_phase")
    assert result.data["reason"] == "no_data"
    assert [n.kind for n in result.notices] == ["insufficient_data"] and "还没有经期记录" in result.notices[0].message


def test_fitness_notices_when_body_weight_is_missing(client, sdk):
    for username, profile, expected in (("erin", {"gender": "female"}, ["insufficient_data"]),
                                        ("fay", PROFILE, [])):
        token = _token(client, ready_user(client, username, profile))
        bench = sdk.call(token, "fitness.search_exercises", {"query": "卧推"}).data["results"][0]["id"]
        sdk.call(token, "fitness.log_workout", {"performed_on": "2026-10-07", "strength": [
            {"exercise_id": bench, "sets": [{"weight_kg": 40, "reps": 10}]}]})
        for name in ("fitness.get_training_signal", "fitness.get_week_summary"):
            result = sdk.call(token, name)
            assert [n.kind for n in result.notices] == expected, (username, name)
            if expected:
                assert result.notices[0].message == "档案里没有体重，无法估算训练消耗"


def test_update_item_with_user_token_changes_only_sent_fields(client, sdk):
    headers = ready_user(client, "alice")
    user = UserAccessToken(headers["Authorization"].removeprefix("Bearer "))
    [item] = sdk.call(user, "medical.submit_order", {"text": "一周内忌食辛辣。"}).data["items"]
    updated = sdk.call(user, "medical.update_item", {"item_id": item["id"], "content": "一周内不吃辣"}).data
    assert updated["content"] == "一周内不吃辣"
    unchanged = ("category", "subjects", "start_date", "end_date", "review_date", "status")
    assert {k: updated[k] for k in unchanged} == {k: item[k] for k in unchanged}
    assert client.get(f"/api/medical/items/{item['id']}", headers=headers).json() == updated


def test_param_models_reject_a_user_id_field(client, sdk):
    for cap in REGISTRY.values():
        with pytest.raises(ValidationError) as caught:
            cap.input_model.model_validate({"user_id": "00000000-0000-0000-0000-000000000000"})
        assert ("user_id",) in [e["loc"] for e in caught.value.errors() if e["type"] == "extra_forbidden"], cap.name
    token = _token(client, ready_user(client, "alice"))
    with pytest.raises(SdkError) as caught:
        sdk.call(token, "medical.list_items", {"user_id": "00000000-0000-0000-0000-000000000000"})
    assert caught.value.kind == "invalid_input"


def test_get_constraints_filters_by_category(client, sdk):
    headers = ready_user(client, "alice")
    user = UserAccessToken(headers["Authorization"].removeprefix("Bearer "))
    avoid, require = sdk.call(user, "medical.submit_order", {"text": SAMPLE_ORDERS["short_term"]}).data["items"]
    for item in (avoid, require):
        sdk.call(user, "medical.confirm_item", {"item_id": item["id"]})
    token = _token(client, headers, "read")
    every = sdk.call(token, "medical.get_constraints").data
    assert [c["item_id"] for c in every["constraints"]] == [avoid["id"], require["id"]]
    only = sdk.call(token, "medical.get_constraints", {"category": "diet_require"}).data
    assert only == client.get("/api/medical/constraints", params={"category": "diet_require"}, headers=headers).json()
    assert [c["item_id"] for c in only["constraints"]] == [require["id"]]
    with pytest.raises(SdkError) as caught:
        sdk.call(token, "medical.get_constraints", {"category": "nope"})
    assert caught.value.kind == "invalid_input"


def test_every_input_field_has_a_description():
    checked, missing = 0, []
    for cap in REGISTRY.values():
        schema = cap.input_model.model_json_schema()
        for owner, model in [(cap.name, schema), *((f"{cap.name}:{n}", d) for n, d in schema.get("$defs", {}).items())]:
            for field, prop in model.get("properties", {}).items():
                checked += 1
                if not str(prop.get("description", "")).strip():
                    missing.append(f"{owner}.{field}")
    assert checked > 50 and missing == []


def test_get_profile_returns_advice_fields_without_free_text(client, sdk):
    headers = ready_user(client, "alice", {**PROFILE, "food_avoidances": ["香菜"], "health_conditions": "秘密病史",
                                            "notes": "秘密备注"})
    profile = sdk.call(_token(client, headers, "read"), "profile.get_profile").data
    rest = client.get("/api/profile", headers=headers).json()
    for field in ("gender", "birth_year", "height_cm", "weight_kg", "activity_level", "goal", "diet_preferences",
                  "food_avoidances", "cycle_tracking_opt_out", "updated_at"):
        assert profile[field] == rest[field], field
    assert "health_conditions" not in profile and "notes" not in profile
    assert "秘密" not in json.dumps(profile, ensure_ascii=False)
