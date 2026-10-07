from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.common.clock import get_today
from app.main import create_app
from tests.helpers import ready_user

TODAY = date(2026, 10, 7)


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as test_client:
        yield test_client


def _ex(client, headers, name):
    return client.get("/api/fitness/exercises/search", params={"q": name}, headers=headers).json()["results"][0]["id"]


def _bench_body(client, headers, **extra):
    return {
        "performed_on": "2026-10-07", **extra,
        "strength": [{"exercise_id": _ex(client, headers, "卧推"), "sets": [{"weight_kg": 60, "reps": 8}]}],
    }


def _confirmed_limit(client, headers, text):
    order = client.post("/api/medical/orders", json={"text": text}, headers=headers)
    assert order.status_code == 201, order.text
    item = order.json()["items"][0]
    assert item["category"] == "exercise_limit"
    assert client.post(f"/api/medical/items/{item['id']}/confirm", headers=headers).status_code == 200
    return item["id"]


def test_rest_day_signal(client):
    headers = ready_user(client, "alice", {"weight_kg": 70})
    body = client.get("/api/fitness/signal", headers=headers).json()
    assert (body["day"], body["trained"], body["kinds"], body["intensity"]) == ("2026-10-07", False, [], "none")
    assert (body["energy_low"], body["energy_high"]) == (None, None)
    assert (body["muscles"], body["workout_count"], body["conflicts"]) == ([], 0, [])
    assert "仅为估算" in body["disclaimer"]


def test_training_day_signal(client):
    headers = ready_user(client, "alice", {"weight_kg": 70})
    posted = client.post(
        "/api/fitness/workouts", json=_bench_body(client, headers, duration_minutes=60, rpe=7), headers=headers
    )
    assert posted.status_code == 201, posted.text
    body = client.get("/api/fitness/signal", headers=headers).json()
    assert (body["trained"], body["kinds"], body["intensity"], body["workout_count"]) == (
        True, ["strength"], "moderate", 1)
    # 5.0 × 70 × 1 小时 = 350 千卡，区间 280 至 420
    assert (body["energy_low"], body["energy_high"], body["energy_status"]) == (280, 420, "ok")
    assert "chest" in body["muscles"]
    assert body["muscles"] == sorted(body["muscles"])
    assert "仅为估算" in body["disclaimer"]


def test_signal_without_body_weight_explains_why(client):
    headers = ready_user(client, "alice")
    client.post("/api/fitness/workouts", json=_bench_body(client, headers, rpe=7), headers=headers)
    body = client.get("/api/fitness/signal", headers=headers).json()
    assert (body["trained"], body["energy_low"], body["energy_high"], body["energy_status"]) == (
        True, None, None, "missing_body_weight")
    assert "体重" in "".join(body["notes"])


def test_signal_only_counts_today_and_kinds_are_sorted(client):
    headers = ready_user(client, "alice", {"weight_kg": 70})
    client.post(
        "/api/fitness/workouts", json=_bench_body(client, headers, rpe=6, performed_on="2026-10-06"), headers=headers
    )
    cardio = {"performed_on": "2026-10-07", "rpe": 9,
              "cardio": [{"exercise_id": _ex(client, headers, "跑步"), "duration_minutes": 20}]}
    client.post("/api/fitness/workouts", json=cardio, headers=headers)
    client.post("/api/fitness/workouts", json=_bench_body(client, headers, rpe=5), headers=headers)
    body = client.get("/api/fitness/signal", headers=headers).json()
    assert (body["workout_count"], body["kinds"], body["intensity"]) == (2, ["cardio", "strength"], "vigorous")


def test_conflicts_reach_workout_responses_and_signal(client):
    headers = ready_user(client, "alice", {"weight_kg": 70})
    item_id = _confirmed_limit(client, headers, "两周内避免提重物及剧烈运动。")
    posted = client.post("/api/fitness/workouts", json=_bench_body(client, headers, rpe=6), headers=headers)
    assert posted.status_code == 201
    workout = posted.json()
    assert [(c["item_id"], c["subject"], c["level"], c["workout_ids"]) for c in workout["conflicts"]] == [
        (item_id, "提重物", "conflict", [workout["id"]])]
    assert "两周内避免提重物及剧烈运动" in workout["conflicts"][0]["message"]
    assert client.get(f"/api/fitness/workouts/{workout['id']}", headers=headers).json() == workout
    assert client.get("/api/fitness/workouts", headers=headers).json() == [workout]
    signal = client.get("/api/fitness/signal", headers=headers).json()
    assert [(c["item_id"], c["subject"]) for c in signal["conflicts"]] == [(item_id, "提重物")]


def test_put_recomputes_conflicts_and_saving_is_never_blocked(client):
    headers = ready_user(client, "alice", {"weight_kg": 70})
    _confirmed_limit(client, headers, "两周内避免提重物及剧烈运动。")
    workout = client.post("/api/fitness/workouts", json=_bench_body(client, headers, rpe=6), headers=headers).json()
    assert workout["conflicts"]
    walk = {"performed_on": "2026-10-07", "rpe": 3,
            "cardio": [{"exercise_id": _ex(client, headers, "快走"), "duration_minutes": 30}]}
    replaced = client.put(f"/api/fitness/workouts/{workout['id']}", json=walk, headers=headers)
    assert replaced.status_code == 200
    assert replaced.json()["conflicts"] == []
    assert client.get("/api/fitness/signal", headers=headers).json()["conflicts"] == []


def test_workouts_without_limits_have_empty_conflicts(client):
    headers = ready_user(client, "alice")
    workout = client.post("/api/fitness/workouts", json=_bench_body(client, headers), headers=headers).json()
    assert workout["conflicts"] == []


def test_signal_requires_login(client):
    assert client.get("/api/fitness/signal").status_code == 401
