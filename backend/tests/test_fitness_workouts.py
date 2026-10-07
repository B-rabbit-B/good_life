from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.common.clock import get_today
from app.db import get_engine
from app.main import create_app
from tests.helpers import ready_user, register_and_login

TODAY = date(2026, 10, 7)


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as test_client:
        yield test_client


def _ex(client, headers, name):
    return client.get("/api/fitness/exercises/search", params={"q": name}, headers=headers).json()["results"][0]["id"]


def _bench_workout(client, headers, day="2026-10-07", sets=((60, 10), (60, 8), (65, 6))):
    body = {
        "performed_on": day, "rpe": 7, "note": "胸部日",
        "strength": [{"exercise_id": _ex(client, headers, "卧推"),
                      "sets": [{"weight_kg": w, "reps": r} for w, r in sets]}],
        "cardio": [],
    }
    response = client.post("/api/fitness/workouts", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_record_bench_press_workout(client):
    headers = ready_user(client, "alice")
    workout = _bench_workout(client, headers)
    [block] = workout["strength"]
    assert block["exercise_name"] == "卧推"
    assert [(s["set_index"], s["weight_kg"], s["reps"]) for s in block["sets"]] == [(1, 60, 10), (2, 60, 8), (3, 65, 6)]
    assert workout["note"] == "胸部日"
    fetched = client.get(f"/api/fitness/workouts/{workout['id']}", headers=headers).json()
    assert fetched == workout


def test_workout_validation(client):
    headers = ready_user(client, "alice")
    bench = _ex(client, headers, "卧推")
    run = _ex(client, headers, "跑步")
    cases = [
        ({"performed_on": "2026-10-08", "strength": [{"exercise_id": bench, "sets": [{"weight_kg": 60, "reps": 5}]}]},
         422, "workout_in_future"),
        ({"performed_on": "2026-10-07", "strength": [], "cardio": []}, 422, "empty_workout"),
        ({"performed_on": "2026-10-07", "strength": [{"exercise_id": "ex:nope", "sets": [{"weight_kg": 1, "reps": 1}]}]},
         404, "exercise_not_found"),
        ({"performed_on": "2026-10-07", "strength": [{"exercise_id": run, "sets": [{"weight_kg": 1, "reps": 1}]}]},
         422, "exercise_kind_mismatch"),
    ]
    for body, status, code in cases:
        response = client.post("/api/fitness/workouts", json=body, headers=headers)
        assert (response.status_code, response.json()["error"]["code"]) == (status, code), body
    for bad_set in ({"weight_kg": -1, "reps": 5}, {"weight_kg": 60, "reps": 0}, {"weight_kg": 60, "reps": 5, "x": 1}):
        body = {"performed_on": "2026-10-07", "strength": [{"exercise_id": bench, "sets": [bad_set]}]}
        assert client.post("/api/fitness/workouts", json=body, headers=headers).status_code == 422


def test_replace_and_delete_workout(client):
    headers = ready_user(client, "alice")
    workout = _bench_workout(client, headers)
    body = {"performed_on": "2026-10-06", "rpe": 5, "strength": [],
            "cardio": [{"exercise_id": _ex(client, headers, "跑步"), "duration_minutes": 30, "distance_km": 5}]}
    replaced = client.put(f"/api/fitness/workouts/{workout['id']}", json=body, headers=headers).json()
    assert (replaced["performed_on"], replaced["strength"], replaced["cardio"][0]["duration_minutes"]) == (
        "2026-10-06", [], 30)
    listed = client.get("/api/fitness/workouts", params={"start": "2026-10-01", "end": "2026-10-07"},
                        headers=headers).json()
    assert [w["id"] for w in listed] == [workout["id"]]
    assert client.delete(f"/api/fitness/workouts/{workout['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/fitness/workouts/{workout['id']}", headers=headers).status_code == 404


def test_custom_exercise_is_private(client):
    alice = ready_user(client, "alice")
    created = client.post("/api/fitness/exercises", json={
        "name": "地雷管推举", "aliases": ["单臂地雷推"], "kind": "strength", "primary_muscles": ["shoulders"],
        "equipment": "barbell",
    }, headers=alice)
    assert created.status_code == 201
    custom_id = created.json()["id"]
    assert custom_id.startswith("custom:")
    assert client.get("/api/fitness/exercises/search", params={"q": "地雷管推举"}, headers=alice).json()["results"][0][
        "id"] == custom_id
    dup = client.post("/api/fitness/exercises", json={
        "name": "地雷管推举", "kind": "strength", "primary_muscles": ["shoulders"], "equipment": "barbell"}, headers=alice)
    assert dup.json()["error"]["code"] == "custom_exercise_exists"
    bella = ready_user(client, "bella")
    found = client.get("/api/fitness/exercises/search", params={"q": "地雷管推举"}, headers=bella).json()
    assert found["results"] == []
    assert client.get(f"/api/fitness/exercises/{custom_id}", headers=bella).status_code == 404
    body = {"performed_on": "2026-10-07", "strength": [{"exercise_id": custom_id, "sets": [{"weight_kg": 20, "reps": 10}]}]}
    assert client.post("/api/fitness/workouts", json=body, headers=bella).json()["error"]["code"] == "exercise_not_found"
    assert client.post("/api/fitness/workouts", json=body, headers=alice).status_code == 201
    assert client.get("/api/fitness/exercises/custom", headers=bella).json() == []
    assert client.delete(f"/api/fitness/exercises/custom/{custom_id}", headers=bella).status_code == 404


def test_workouts_are_private_and_note_is_encrypted(client):
    alice = ready_user(client, "alice")
    workout = _bench_workout(client, alice)
    bella = ready_user(client, "bella")
    assert client.get("/api/fitness/workouts", headers=bella).json() == []
    for method, kwargs in [("get", {}), ("delete", {}),
                           ("put", {"json": {"performed_on": "2026-10-07", "strength": [], "cardio": [
                               {"exercise_id": "ex:running", "duration_minutes": 10}]}})]:
        response = getattr(client, method)(f"/api/fitness/workouts/{workout['id']}", headers=bella, **kwargs)
        assert response.status_code == 404, method
    with get_engine().connect() as conn:
        raw = conn.execute(text("SELECT note FROM workouts")).scalar_one()
    assert "胸部日" not in raw


def test_fitness_requires_login_and_disclaimer(client):
    assert client.get("/api/fitness/workouts").status_code == 401
    headers = register_and_login(client, "carl")
    assert client.get("/api/fitness/workouts", headers=headers).json()["error"]["code"] == "disclaimer_not_accepted"


def test_exercise_search_and_detail(client):
    headers = ready_user(client, "alice")
    missing = client.get("/api/fitness/exercises/search", params={"q": "不存在的动作"}, headers=headers).json()
    assert (missing["found"], missing["exact"], missing["results"]) == (False, False, [])
    assert missing["message"] == "未找到与“不存在的动作”匹配的动作，可以新增自定义动作"
    exact = client.get("/api/fitness/exercises/search", params={"q": "卧推"}, headers=headers).json()
    assert (exact["found"], exact["exact"], exact["message"]) == (True, True, "")
    partial = client.get("/api/fitness/exercises/search", params={"q": "推"}, headers=headers).json()
    assert (partial["found"], partial["exact"]) == (True, False) and partial["message"]
    detail = client.get("/api/fitness/exercises/ex:running", headers=headers).json()
    assert detail["kind"] == "cardio" and detail["met"]["light"] < detail["met"]["vigorous"] and detail["met_source_note"]
    strength = client.get(f"/api/fitness/exercises/{_ex(client, headers, '卧推')}", headers=headers).json()
    assert strength["met"] == {"light": 3.5, "moderate": 5.0, "vigorous": 6.0}
    assert client.get("/api/fitness/exercises/ex:nope", headers=headers).json()["error"]["code"] == "exercise_not_found"
    assert client.get("/api/fitness/exercises/custom:not-a-uuid", headers=headers).status_code == 404


def test_custom_cardio_exercise_needs_met(client):
    headers = ready_user(client, "alice")
    base = {"name": "跳绳变式", "kind": "cardio", "primary_muscles": ["full_body"], "equipment": "none"}
    assert client.post("/api/fitness/exercises", json=base, headers=headers).status_code == 422
    bad_order = {**base, "met_light": 8, "met_moderate": 6, "met_vigorous": 10}
    assert client.post("/api/fitness/exercises", json=bad_order, headers=headers).status_code == 422
    strength_with_met = {**base, "kind": "strength", "met_light": 3}
    assert client.post("/api/fitness/exercises", json=strength_with_met, headers=headers).status_code == 422
    ok = client.post("/api/fitness/exercises", json={**base, "met_light": 6, "met_moderate": 8, "met_vigorous": 10},
                     headers=headers)
    assert ok.status_code == 201 and ok.json()["met"] == {"light": 6, "moderate": 8, "vigorous": 10}
    body = {"performed_on": "2026-10-07", "cardio": [{"exercise_id": ok.json()["id"], "duration_minutes": 15}]}
    assert client.post("/api/fitness/workouts", json=body, headers=headers).status_code == 201
    assert client.delete(f"/api/fitness/exercises/custom/{ok.json()['id']}", headers=headers).status_code == 204
    [workout] = client.get("/api/fitness/workouts", headers=headers).json()
    assert workout["cardio"][0]["exercise_name"] == "跳绳变式"  # 删除动作后历史快照保留


def test_list_workouts_range_and_order(client):
    headers = ready_user(client, "alice")
    old = _bench_workout(client, headers, day="2026-09-20")
    recent = _bench_workout(client, headers, day="2026-10-05")
    latest = _bench_workout(client, headers, day="2026-10-07")
    default = client.get("/api/fitness/workouts", headers=headers).json()
    assert [w["id"] for w in default] == [latest["id"], recent["id"]]
    everything = client.get("/api/fitness/workouts", params={"start": "2026-09-01"}, headers=headers).json()
    assert [w["id"] for w in everything] == [latest["id"], recent["id"], old["id"]]
    reversed_range = client.get("/api/fitness/workouts", params={"start": "2026-10-07", "end": "2026-10-01"},
                                headers=headers)
    assert (reversed_range.status_code, reversed_range.json()["error"]["code"]) == (422, "invalid_range")


def test_replace_workout_rules(client):
    headers = ready_user(client, "alice")
    workout = _bench_workout(client, headers)
    bench = _ex(client, headers, "卧推")
    squat = _ex(client, headers, "深蹲")
    body = {"performed_on": "2026-10-07", "strength": [
        {"exercise_id": squat, "sets": [{"weight_kg": 80, "reps": 5}, {"weight_kg": 85, "reps": 5}]},
        {"exercise_id": bench, "sets": [{"weight_kg": 50, "reps": 12}]},
    ]}
    replaced = client.put(f"/api/fitness/workouts/{workout['id']}", json=body, headers=headers).json()
    assert [(b["position"], b["exercise_name"], [s["set_index"] for s in b["sets"]]) for b in replaced["strength"]] == [
        (1, "深蹲", [1, 2]), (2, "卧推", [1])]
    assert replaced["note"] is None
    future = {**body, "performed_on": "2026-10-08"}
    assert client.put(f"/api/fitness/workouts/{workout['id']}", json=future, headers=headers).status_code == 422
    kept = client.get(f"/api/fitness/workouts/{workout['id']}", headers=headers).json()
    assert kept == replaced  # 校验失败不改动原记录
