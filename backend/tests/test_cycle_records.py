from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.common.clock import get_today
from app.db import get_engine
from app.main import create_app
from tests.helpers import ready_user, register_and_login

TODAY = date(2026, 9, 1)
FEMALE = {"gender": "female"}


@pytest.fixture
def cycle_client():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as test_client:
        yield test_client


def _post(client, headers, start, end=None):
    return client.post("/api/cycle/periods", json={"start_date": start, "end_date": end}, headers=headers)


def test_cycle_is_only_for_female_users_who_did_not_opt_out(cycle_client):
    cases = {
        "nogender": None,
        "male": {"gender": "male"},
        "optout": {"gender": "female", "cycle_tracking_opt_out": True},
    }
    for username, profile in cases.items():
        headers = ready_user(cycle_client, username, profile)
        for method, path in [("get", "/api/cycle/periods"), ("get", "/api/cycle/settings")]:
            response = getattr(cycle_client, method)(path, headers=headers)
            assert response.status_code == 403, (username, path)
            assert response.json()["error"]["code"] == "cycle_not_available"
    female = ready_user(cycle_client, "alice", FEMALE)
    assert cycle_client.get("/api/cycle/periods", headers=female).json() == []


def test_cycle_requires_disclaimer_and_login(cycle_client):
    assert cycle_client.get("/api/cycle/periods").status_code == 401
    headers = register_and_login(cycle_client, "alice")
    response = cycle_client.get("/api/cycle/periods", headers=headers)
    assert response.json()["error"]["code"] == "disclaimer_not_accepted"


def test_create_and_list_periods_newest_first(cycle_client):
    headers = ready_user(cycle_client, "alice", FEMALE)
    assert _post(cycle_client, headers, "2026-06-26", "2026-06-30").status_code == 201
    assert _post(cycle_client, headers, "2026-07-25", "2026-07-29").status_code == 201
    created = _post(cycle_client, headers, "2026-08-22")
    assert created.status_code == 201
    assert created.json()["end_date"] is None
    starts = [item["start_date"] for item in cycle_client.get("/api/cycle/periods", headers=headers).json()]
    assert starts == ["2026-08-22", "2026-07-25", "2026-06-26"]


def test_period_date_validation(cycle_client):
    headers = ready_user(cycle_client, "alice", FEMALE)
    cases = [
        (("2026-09-02", None), 422, "period_in_future"),
        (("2026-08-30", "2026-09-02"), 422, "period_in_future"),
        (("2026-08-10", "2026-08-09"), 422, "invalid_period_range"),
        (("2026-08-01", "2026-08-16"), 422, "period_too_long"),
    ]
    for (start, end), status, code in cases:
        response = _post(cycle_client, headers, start, end)
        assert response.status_code == status, (start, end)
        assert response.json()["error"]["code"] == code
    assert _post(cycle_client, headers, "2026-08-01", "2026-08-15").status_code == 201


def test_overlapping_periods_are_rejected(cycle_client):
    headers = ready_user(cycle_client, "alice", FEMALE)
    assert _post(cycle_client, headers, "2026-08-01", "2026-08-05").status_code == 201
    overlap = _post(cycle_client, headers, "2026-08-04", "2026-08-08")
    assert overlap.status_code == 409
    assert overlap.json()["error"]["code"] == "period_overlap"
    assert _post(cycle_client, headers, "2026-08-06", "2026-08-07").status_code == 201


def test_open_period_counts_as_ongoing(cycle_client):
    headers = ready_user(cycle_client, "alice", FEMALE)
    assert _post(cycle_client, headers, "2026-08-20").status_code == 201
    later = _post(cycle_client, headers, "2026-08-25", "2026-08-26")
    assert later.status_code == 409
    assert "结束日期" in later.json()["error"]["message"]
    assert _post(cycle_client, headers, "2026-07-20", "2026-07-24").status_code == 201


def test_update_and_delete_period(cycle_client):
    headers = ready_user(cycle_client, "alice", FEMALE)
    period_id = _post(cycle_client, headers, "2026-08-20").json()["id"]
    closed = cycle_client.patch(f"/api/cycle/periods/{period_id}", json={"end_date": "2026-08-24"}, headers=headers)
    assert closed.status_code == 200
    assert closed.json()["end_date"] == "2026-08-24"
    bad = cycle_client.patch(f"/api/cycle/periods/{period_id}", json={"start_date": None}, headers=headers)
    assert bad.status_code == 422
    future = cycle_client.patch(f"/api/cycle/periods/{period_id}", json={"end_date": "2026-09-05"}, headers=headers)
    assert future.json()["error"]["code"] == "period_in_future"
    assert cycle_client.delete(f"/api/cycle/periods/{period_id}", headers=headers).status_code == 204
    assert cycle_client.get("/api/cycle/periods", headers=headers).json() == []
    missing = cycle_client.delete(f"/api/cycle/periods/{period_id}", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_update_rechecks_overlap_but_not_against_itself(cycle_client):
    headers = ready_user(cycle_client, "alice", FEMALE)
    first = _post(cycle_client, headers, "2026-08-01", "2026-08-05").json()["id"]
    _post(cycle_client, headers, "2026-08-20", "2026-08-24")
    shifted = cycle_client.patch(f"/api/cycle/periods/{first}", json={"end_date": "2026-08-06"}, headers=headers)
    assert shifted.status_code == 200
    clash = cycle_client.patch(
        f"/api/cycle/periods/{first}", json={"start_date": "2026-08-18", "end_date": "2026-08-21"}, headers=headers
    )
    assert clash.status_code == 409
    assert clash.json()["error"]["code"] == "period_overlap"


def test_other_users_periods_are_invisible(cycle_client):
    alice = ready_user(cycle_client, "alice", FEMALE)
    bob = ready_user(cycle_client, "bella", FEMALE)
    period_id = _post(cycle_client, alice, "2026-08-01", "2026-08-05").json()["id"]
    assert cycle_client.get("/api/cycle/periods", headers=bob).json() == []
    for method, kwargs in [("patch", {"json": {"end_date": "2026-08-04"}}), ("delete", {})]:
        response = getattr(cycle_client, method)(f"/api/cycle/periods/{period_id}", headers=bob, **kwargs)
        assert response.status_code == 404
    assert len(cycle_client.get("/api/cycle/periods", headers=alice).json()) == 1
    assert _post(cycle_client, bob, "2026-08-01", "2026-08-05").status_code == 201


def test_unknown_fields_are_rejected(cycle_client):
    headers = ready_user(cycle_client, "alice", FEMALE)
    response = cycle_client.post(
        "/api/cycle/periods",
        json={"start_date": "2026-08-01", "user_id": "00000000-0000-0000-0000-000000000000"},
        headers=headers,
    )
    assert response.status_code == 422


def test_cycle_settings(cycle_client):
    headers = ready_user(cycle_client, "alice", FEMALE)
    assert cycle_client.get("/api/cycle/settings", headers=headers).json()["status"] == "tracking"
    updated = cycle_client.put("/api/cycle/settings", json={"status": "pregnant"}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["status"] == "pregnant"
    assert cycle_client.get("/api/cycle/settings", headers=headers).json()["status"] == "pregnant"
    assert cycle_client.put("/api/cycle/settings", json={"status": "robot"}, headers=headers).status_code == 422


def test_cycle_status_is_encrypted_at_rest(cycle_client):
    headers = ready_user(cycle_client, "alice", FEMALE)
    assert cycle_client.put("/api/cycle/settings", json={"status": "pregnant"}, headers=headers).status_code == 200
    with get_engine().connect() as conn:
        raw = conn.execute(text("SELECT status FROM cycle_settings")).scalar_one()
    assert "pregnant" not in raw


def test_open_period_older_than_max_length_is_rejected(cycle_client):
    headers = ready_user(cycle_client, "alice", FEMALE)
    too_long = _post(cycle_client, headers, "2026-08-17")
    assert too_long.status_code == 422
    assert too_long.json()["error"]["code"] == "period_too_long"
    assert "结束日期" in too_long.json()["error"]["message"]
    assert _post(cycle_client, headers, "2026-08-18").status_code == 201
