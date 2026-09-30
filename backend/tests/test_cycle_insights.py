from datetime import date

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text

from app.common.clock import get_today
from app.cycle.schemas import PhaseOut, PredictionOut, TipOut
from app.db import get_engine
from app.main import create_app
from tests.helpers import ready_user

TODAY = date(2026, 9, 1)
FEMALE = {"gender": "female"}
REGULAR = [
    ("2026-05-01", "2026-05-05"),
    ("2026-05-29", "2026-06-02"),
    ("2026-06-26", "2026-06-30"),
    ("2026-07-25", "2026-07-29"),
    ("2026-08-22", "2026-08-26"),
]
IRREGULAR = [
    ("2026-03-01", "2026-03-05"),
    ("2026-03-25", "2026-03-29"),
    ("2026-04-27", "2026-05-01"),
    ("2026-05-24", "2026-05-28"),
    ("2026-06-29", "2026-07-03"),
    ("2026-07-30", "2026-08-03"),
]
SPARSE = [("2026-08-01", "2026-08-05"), ("2026-08-29", "2026-08-31")]


@pytest.fixture
def cycle_client():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as test_client:
        yield test_client


def _user_with(client, username, periods):
    headers = ready_user(client, username, FEMALE)
    for start, end in periods:
        response = client.post("/api/cycle/periods", json={"start_date": start, "end_date": end}, headers=headers)
        assert response.status_code == 201, response.text
    return headers


def test_stats_for_regular_user(cycle_client):
    headers = _user_with(cycle_client, "regular", REGULAR)
    stats = cycle_client.get("/api/cycle/stats", headers=headers).json()
    assert stats["cycle_count"] == 4
    assert stats["period_count"] == 5
    assert stats["avg_cycle_length"] == 28.3
    assert stats["cycle_length_std"] == 0.5
    assert (stats["shortest_cycle"], stats["longest_cycle"]) == (28, 29)
    assert stats["avg_period_length"] == 5.0
    assert stats["recent_cycle_lengths"] == [28, 28, 29, 28]


def test_regular_prediction(cycle_client):
    headers = _user_with(cycle_client, "regular", REGULAR)
    body = cycle_client.get("/api/cycle/prediction", headers=headers).json()
    assert body["status"] == "ok"
    assert body["next_period_start"] == "2026-09-19"
    assert body["next_period_range"] == {"earliest": "2026-09-17", "latest": "2026-09-21"}
    assert body["ovulation_day"] == "2026-09-05"
    assert body["fertile_window"] == {"earliest": "2026-08-31", "latest": "2026-09-06"}
    assert body["flags"] == []
    assert "不能用于避孕" in body["disclaimer"]


def test_irregular_prediction_is_wider(cycle_client):
    headers = _user_with(cycle_client, "wavy", IRREGULAR)
    body = cycle_client.get("/api/cycle/prediction", headers=headers).json()
    assert body["next_period_range"] == {"earliest": "2026-08-24", "latest": "2026-09-05"}
    assert "irregular" in body["flags"] and "cycle_out_of_range" in body["flags"]


def test_sparse_prediction_is_marked_insufficient(cycle_client):
    headers = _user_with(cycle_client, "sparse", SPARSE)
    body = cycle_client.get("/api/cycle/prediction", headers=headers).json()
    assert body["status"] == "insufficient_data"
    assert body["next_period_start"] is None
    assert body["next_period_range"] is None
    assert body["notes"]
    assert "不能用于避孕" in body["disclaimer"]


def test_phase_endpoint(cycle_client):
    headers = _user_with(cycle_client, "regular", REGULAR)
    ovulation = cycle_client.get("/api/cycle/phase", params={"date": "2026-09-04"}, headers=headers).json()
    assert (ovulation["phase"], ovulation["cycle_day"]) == ("ovulation", 14)
    today = cycle_client.get("/api/cycle/phase", headers=headers).json()
    assert (today["day"], today["phase"], today["cycle_day"]) == ("2026-09-01", "follicular", 11)
    early = cycle_client.get("/api/cycle/phase", params={"date": "2026-04-01"}, headers=headers).json()
    assert (early["phase"], early["reason"]) == ("unknown", "before_first_record")
    for body in (ovulation, today, early):
        assert "不能用于避孕" in body["disclaimer"]
        assert body["flags"] == []


def test_phase_endpoint_reports_overdue():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: date(2026, 9, 22)
    with TestClient(app) as client:
        headers = _user_with(client, "late", REGULAR)
        body = client.get("/api/cycle/phase", headers=headers).json()
    assert (body["day"], body["phase"], body["reason"]) == ("2026-09-22", "unknown", "overdue")
    assert "overdue" in body["flags"]
    assert "不能用于避孕" in body["disclaimer"]


def test_tips_follow_phase(cycle_client):
    headers = _user_with(cycle_client, "regular", REGULAR)
    body = cycle_client.get("/api/cycle/tips", params={"date": "2026-08-23"}, headers=headers).json()
    assert body["phase"]["phase"] == "menstrual"
    ids = [tip["id"] for tip in body["tips"]]
    assert "menstrual-iron" in ids and "menstrual-warm" in ids and "any-follow-medical-advice" in ids
    assert not any(tip_id.startswith("luteal-") for tip_id in ids)
    assert "不构成医疗建议" in body["disclaimer"]
    assert "不能用于避孕" in body["disclaimer"]
    assert "不能用于避孕" in body["phase"]["disclaimer"]
    tradition = next(tip for tip in body["tips"] if tip["id"] == "menstrual-warm")
    assert tradition["category"] == "tradition"


def test_pregnant_or_paused_stops_prediction(cycle_client):
    headers = _user_with(cycle_client, "regular", REGULAR)
    for status in ("pregnant", "paused"):
        cycle_client.put("/api/cycle/settings", json={"status": status}, headers=headers)
        prediction = cycle_client.get("/api/cycle/prediction", headers=headers).json()
        assert prediction["status"] == "paused"
        assert prediction["next_period_start"] is None and prediction["ovulation_day"] is None
        assert prediction["notes"]
        assert "不能用于避孕" in prediction["disclaimer"]
        phase = cycle_client.get("/api/cycle/phase", params={"date": "2026-09-04"}, headers=headers).json()
        assert (phase["phase"], phase["reason"]) == ("unknown", status)
        assert "不能用于避孕" in phase["disclaimer"]
        tips = cycle_client.get("/api/cycle/tips", params={"date": "2026-09-04"}, headers=headers).json()
        assert {tip["phase"] for tip in tips["tips"]} == {"any"}
    cycle_client.put("/api/cycle/settings", json={"status": "pregnant"}, headers=headers)
    assert "孕期" in cycle_client.get("/api/cycle/prediction", headers=headers).json()["notes"][0]
    cycle_client.put("/api/cycle/settings", json={"status": "tracking"}, headers=headers)
    assert cycle_client.get("/api/cycle/prediction", headers=headers).json()["status"] == "ok"


def test_day_logs_crud_and_symptom_stats(cycle_client):
    headers = _user_with(cycle_client, "regular", REGULAR)
    logs = {
        "2026-08-22": {"flow": "heavy", "pain": 3, "mood": "low", "symptoms": ["腹痛", "腰酸"], "note": "第一天"},
        "2026-08-23": {"flow": "medium", "pain": 1, "mood": None, "symptoms": ["腹痛"], "note": None},
        "2026-08-28": {"flow": "none", "pain": 2, "mood": "good", "symptoms": [], "note": None},
    }
    for day, details in logs.items():
        response = cycle_client.put(f"/api/cycle/day-logs/{day}", json=details, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["log_date"] == day
    replaced = cycle_client.put("/api/cycle/day-logs/2026-08-28", json={"flow": "none", "pain": 2}, headers=headers)
    assert replaced.json()["mood"] is None and replaced.json()["symptoms"] == []
    listed = cycle_client.get(
        "/api/cycle/day-logs", params={"start": "2026-08-22", "end": "2026-08-23"}, headers=headers
    ).json()
    assert [item["log_date"] for item in listed] == ["2026-08-22", "2026-08-23"]
    assert len(cycle_client.get("/api/cycle/day-logs", headers=headers).json()) == 3
    stats = cycle_client.get("/api/cycle/stats", headers=headers).json()
    assert stats["logged_days"] == 3
    assert stats["top_symptoms"] == [{"symptom": "腹痛", "days": 2}, {"symptom": "腰酸", "days": 1}]
    assert stats["average_pain_on_bleeding_days"] == 2.0
    assert cycle_client.delete("/api/cycle/day-logs/2026-08-28", headers=headers).status_code == 204
    assert cycle_client.delete("/api/cycle/day-logs/2026-08-28", headers=headers).status_code == 404


def test_day_log_validation(cycle_client):
    headers = _user_with(cycle_client, "regular", REGULAR)
    future = cycle_client.put("/api/cycle/day-logs/2026-09-02", json={"flow": "light"}, headers=headers)
    assert future.status_code == 422
    assert future.json()["error"]["code"] == "log_in_future"
    for bad in ({"pain": 4}, {"flow": "flood"}, {"mood": "happy"}, {"symptoms": ["x"] * 21}, {"user_id": "x"}):
        assert cycle_client.put("/api/cycle/day-logs/2026-08-22", json=bad, headers=headers).status_code == 422


def test_day_log_details_are_encrypted_at_rest(cycle_client):
    headers = _user_with(cycle_client, "regular", REGULAR)
    cycle_client.put(
        "/api/cycle/day-logs/2026-08-22",
        json={"flow": "heavy", "pain": 3, "symptoms": ["偏头痛"], "note": "私密备注"},
        headers=headers,
    )
    with get_engine().connect() as conn:
        raw = conn.execute(text("SELECT details FROM cycle_day_logs")).scalar_one()
    for plaintext in ("heavy", "偏头痛", "私密备注"):
        assert plaintext not in raw


def test_other_users_cannot_see_cycle_data(cycle_client):
    alice = _user_with(cycle_client, "alice", REGULAR)
    cycle_client.put("/api/cycle/day-logs/2026-08-22", json={"flow": "heavy"}, headers=alice)
    bella = ready_user(cycle_client, "bella", FEMALE)
    assert cycle_client.get("/api/cycle/day-logs", headers=bella).json() == []
    assert cycle_client.get("/api/cycle/stats", headers=bella).json()["period_count"] == 0
    assert cycle_client.get("/api/cycle/prediction", headers=bella).json()["status"] == "insufficient_data"
    assert cycle_client.get("/api/cycle/phase", headers=bella).json()["reason"] == "no_data"
    assert cycle_client.delete("/api/cycle/day-logs/2026-08-22", headers=bella).status_code == 404


def test_male_user_cannot_use_insight_endpoints(cycle_client):
    headers = ready_user(cycle_client, "bob", {"gender": "male"})
    for path in ("/api/cycle/stats", "/api/cycle/prediction", "/api/cycle/phase", "/api/cycle/tips",
                 "/api/cycle/day-logs"):
        response = cycle_client.get(path, headers=headers)
        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "cycle_not_available"


def test_response_models_only_accept_known_codes():
    phase = {
        "day": "2026-09-01",
        "phase": "unknown",
        "cycle_day": None,
        "days_until_next_period": None,
        "is_predicted": False,
        "reason": "overdue",
        "flags": ["overdue", "long_gap"],
        "disclaimer": "x",
    }
    PhaseOut.model_validate(phase)
    for field, bad in (("reason", "bogus"), ("flags", ["bogus"])):
        with pytest.raises(ValidationError):
            PhaseOut.model_validate({**phase, field: bad})
    prediction = {
        "status": "ok",
        "next_period_start": None,
        "next_period_range": None,
        "ovulation_day": None,
        "ovulation_range": None,
        "fertile_window": None,
        "flags": ["few_cycles", "irregular", "cycle_out_of_range", "overdue", "long_gap"],
        "notes": [],
        "disclaimer": "x",
    }
    PredictionOut.model_validate(prediction)
    with pytest.raises(ValidationError):
        PredictionOut.model_validate({**prediction, "flags": ["bogus"]})
    tip = {"id": "t", "phase": "any", "category": "tradition", "severity": "caution",
           "title": "t", "content": "c", "basis": "b"}
    TipOut.model_validate(tip)
    for field in ("phase", "category", "severity"):
        with pytest.raises(ValidationError):
            TipOut.model_validate({**tip, field: "bogus"})
