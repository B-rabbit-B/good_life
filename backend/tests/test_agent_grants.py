from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.agent_grants import service
from app.db import get_engine, get_sessionmaker
from tests.helpers import register_and_login, ready_user


def test_create_list_and_revoke_grant(client):
    headers = ready_user(client, "alice")
    created = client.post("/api/agent-grants", json={"name": "Claude Desktop", "access": "read"}, headers=headers)
    assert created.status_code == 201
    assert created.headers["cache-control"] == "no-store"
    body = created.json()
    assert body["token"].startswith("gl_") and len(body["token"]) > 40
    assert "只显示这一次" in body["token_notice"]
    listed = client.get("/api/agent-grants", headers=headers).json()
    assert [(g["id"], g["name"], g["access"], g["status"]) for g in listed] == [
        (body["id"], "Claude Desktop", "read", "active")]
    assert all("token" not in g for g in listed)
    with get_engine().connect() as conn:
        stored = conn.execute(text("SELECT token_hash FROM agent_grants")).scalar_one()
    assert stored == service.hash_token(body["token"]) and body["token"] not in stored
    assert client.delete(f"/api/agent-grants/{body['id']}", headers=headers).status_code == 204
    assert client.get("/api/agent-grants", headers=headers).json()[0]["status"] == "revoked"


def test_grant_validation_and_limits(client):
    headers = ready_user(client, "alice")
    for bad in ({"name": "", "access": "read"}, {"name": "x", "access": "admin"},
                {"name": "x", "access": "read", "expires_in_days": 0},
                {"name": "x", "access": "read", "expires_in_days": 366},
                {"name": "x", "access": "read", "user_id": "someone"}):
        assert client.post("/api/agent-grants", json=bad, headers=headers).status_code == 422, bad
    for i in range(service.MAX_ACTIVE_GRANTS):
        assert client.post("/api/agent-grants", json={"name": f"g{i}", "access": "read"}, headers=headers).status_code == 201
    over = client.post("/api/agent-grants", json={"name": "over", "access": "read"}, headers=headers)
    assert (over.status_code, over.json()["error"]["code"]) == (409, "too_many_grants")


def test_grants_are_private(client):
    alice = ready_user(client, "alice")
    grant_id = client.post("/api/agent-grants", json={"name": "a", "access": "read"}, headers=alice).json()["id"]
    bella = ready_user(client, "bella")
    assert client.get("/api/agent-grants", headers=bella).json() == []
    assert client.delete(f"/api/agent-grants/{grant_id}", headers=bella).status_code == 404


def test_grants_require_login_and_disclaimer(client):
    assert client.get("/api/agent-grants").status_code == 401
    headers = register_and_login(client, "carl")
    response = client.post("/api/agent-grants", json={"name": "a", "access": "read"}, headers=headers)
    assert response.json()["error"]["code"] == "disclaimer_not_accepted"


def test_authenticate_grant(client):
    headers = ready_user(client, "alice")
    token = client.post("/api/agent-grants", json={"name": "a", "access": "read_write", "expires_in_days": 1},
                        headers=headers).json()["token"]
    now = service.now()
    with get_sessionmaker()() as db:
        grant = service.authenticate_grant(db, token, now)
        assert grant is not None and grant.access == "read_write" and grant.last_used_at is not None
        assert service.authenticate_grant(db, token + "x", now) is None
        assert service.authenticate_grant(db, "", now) is None
        assert service.authenticate_grant(db, token, now + timedelta(days=1, seconds=1)) is None
        service.revoke_grant(db, grant.user_id, grant.id, now)
        assert service.authenticate_grant(db, token, now) is None


def test_database_errors_hide_bound_parameters():
    assert get_engine().hide_parameters is True
    with pytest.raises(DBAPIError) as caught, get_engine().connect() as conn:
        conn.execute(text("SELECT token_hash FROM no_such_table WHERE token_hash = :h"), {"h": "secret-hash-value"})
    assert "secret-hash-value" not in str(caught.value)
