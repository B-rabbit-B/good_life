from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.common.clock import get_today
from app.main import create_app
from tests.helpers import ready_user

TODAY = date(2026, 10, 7)  # 星期三
BENCH_MUSCLES = ("chest", "shoulders", "triceps")


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as test_client:
        yield test_client


def _ex(client, headers, name):
    return client.get("/api/fitness/exercises/search", params={"q": name}, headers=headers).json()["results"][0]["id"]


def _post(client, headers, body):
    response = client.post("/api/fitness/workouts", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _bench(client, headers, day, sets, **extra):
    _post(client, headers, {
        "performed_on": day, "rpe": 7, **extra,
        "strength": [{"exercise_id": _ex(client, headers, "卧推"),
                      "sets": [{"weight_kg": w, "reps": r} for w, r in sets]}],
    })


@pytest.fixture
def alice(client):
    headers = ready_user(client, "alice", {"weight_kg": 70})
    _bench(client, headers, "2026-09-30", ((55, 10), (60, 8)))  # 550 + 480 = 1030
    _bench(client, headers, "2026-10-03", ((60, 10), (62.5, 8)))  # 600 + 500 = 1100
    _bench(client, headers, "2026-10-07", ((60, 10), (60, 8), (65, 6)), duration_minutes=60)  # 1470
    _post(client, headers, {
        "performed_on": "2026-10-05", "rpe": 6,
        "cardio": [{"exercise_id": _ex(client, headers, "跑步"), "duration_minutes": 30, "distance_km": 5}],
    })
    return headers


def test_trend_is_ascending_with_hand_calculated_values(client, alice):
    bench = _ex(client, alice, "卧推")
    body = client.get(f"/api/fitness/exercises/{bench}/trend", headers=alice).json()
    assert (body["exercise_id"], body["exercise_name"]) == (bench, "卧推")
    assert [(p["day"], p["max_weight_kg"], p["total_volume"], p["total_reps"], p["sets"]) for p in body["points"]] == [
        ("2026-09-30", 60, 1030, 18, 2), ("2026-10-03", 62.5, 1100, 18, 2), ("2026-10-07", 65, 1470, 24, 3)]


def test_week_summary_matches_hand_calculation(client, alice):
    body = client.get("/api/fitness/summary/week", params={"start": "2026-10-05"}, headers=alice).json()
    assert (body["week_start"], body["week_end"]) == ("2026-10-05", "2026-10-11")
    assert (body["workout_count"], body["training_days"], body["total_volume"], body["cardio_minutes"]) == (
        2, 2, 1470, 30)
    assert body["muscle_volumes"] == {m: 1470 for m in BENCH_MUSCLES}
    assert list(body["muscle_volumes"]) == sorted(body["muscle_volumes"])
    # 跑步 280（224~336）+ 力量 350（280~420）
    assert (body["energy_low_kcal"], body["energy_high_kcal"], body["energy_status"]) == (504, 756, "ok")
    assert "仅为估算" in body["note"]


def test_week_summary_defaults_to_this_monday(client, alice):
    default = client.get("/api/fitness/summary/week", headers=alice).json()
    explicit = client.get("/api/fitness/summary/week", params={"start": "2026-10-05"}, headers=alice).json()
    assert default == explicit


def test_week_start_must_be_a_monday(client, alice):
    response = client.get("/api/fitness/summary/week", params={"start": "2026-10-07"}, headers=alice)
    assert (response.status_code, response.json()["error"]["code"]) == (422, "invalid_week_start")


def test_missing_body_weight_gives_no_energy_range(client):
    headers = ready_user(client, "noweight")
    _bench(client, headers, "2026-10-07", ((60, 10),), duration_minutes=60)
    body = client.get("/api/fitness/summary/week", headers=headers).json()
    assert (body["energy_low_kcal"], body["energy_high_kcal"], body["energy_status"]) == (
        None, None, "missing_body_weight")
    assert "体重" in body["note"]
    assert body["total_volume"] == 600


def test_other_user_sees_empty_summary_and_trend(client, alice):
    bella = ready_user(client, "bella", {"weight_kg": 60})
    week = client.get("/api/fitness/summary/week", params={"start": "2026-10-05"}, headers=bella).json()
    assert (week["workout_count"], week["training_days"], week["total_volume"], week["cardio_minutes"]) == (0, 0, 0, 0)
    assert (week["muscle_volumes"], week["energy_low_kcal"], week["energy_high_kcal"]) == ({}, 0, 0)
    bench = _ex(client, bella, "卧推")
    assert client.get(f"/api/fitness/exercises/{bench}/trend", headers=bella).json()["points"] == []


def test_trend_unknown_and_foreign_custom_exercise_are_404(client, alice):
    created = client.post("/api/fitness/exercises", headers=alice, json={
        "name": "我的划船", "kind": "strength", "primary_muscles": ["back"], "equipment": "machine"})
    custom_id = created.json()["id"]
    bella = ready_user(client, "bella")
    for exercise_id, headers in (("ex:nope", alice), ("nonsense", alice), (custom_id, bella)):
        response = client.get(f"/api/fitness/exercises/{exercise_id}/trend", headers=headers)
        assert (response.status_code, response.json()["error"]["code"]) == (404, "exercise_not_found")
    assert client.get(f"/api/fitness/exercises/{custom_id}/trend", headers=alice).json()["points"] == []


def test_deleted_custom_exercises_do_not_break_summaries(client, alice):
    row = client.post("/api/fitness/exercises", headers=alice, json={
        "name": "我的划船", "kind": "strength", "primary_muscles": ["back"], "equipment": "machine"}).json()["id"]
    swim = client.post("/api/fitness/exercises", headers=alice, json={
        "name": "我的水中走", "kind": "cardio", "primary_muscles": ["full_body"], "equipment": "none",
        "met_light": 3.0, "met_moderate": 4.0, "met_vigorous": 5.0}).json()["id"]
    _post(client, alice, {
        "performed_on": "2026-10-06", "rpe": 6,
        "strength": [{"exercise_id": row, "sets": [{"weight_kg": 40, "reps": 10}]}],
        "cardio": [{"exercise_id": swim, "duration_minutes": 20}],
    })
    for exercise_id in (row, swim):
        assert client.delete(f"/api/fitness/exercises/custom/{exercise_id}", headers=alice).status_code == 204
    week = client.get("/api/fitness/summary/week", params={"start": "2026-10-05"}, headers=alice)
    assert week.status_code == 200, week.text
    body = week.json()
    assert body["workout_count"] == 3
    assert body["muscle_volumes"]["full_body"] == 400
    assert "我的划船" in body["note"] and "我的水中走" in body["note"]
    trend = client.get(f"/api/fitness/exercises/{row}/trend", headers=alice)
    assert trend.status_code == 200
    assert (trend.json()["exercise_name"], [p["total_volume"] for p in trend.json()["points"]]) == ("我的划船", [400])
