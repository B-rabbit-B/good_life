from typing import Annotated

from fastapi import Depends
from fastapi.testclient import TestClient

from app.auth.models import User
from app.disclaimer.deps import require_disclaimer_user
from app.main import create_app
from tests.helpers import accept_disclaimer, register_and_login


def test_disclaimer_is_public_and_says_not_medical_advice(client):
    response = client.get("/api/disclaimer")
    assert response.status_code == 200
    body = response.json()
    assert body["version"]
    assert "不构成医疗诊断" in body["text"]


def test_status_before_and_after_accept(client):
    headers = register_and_login(client, "alice")
    before = client.get("/api/disclaimer/status", headers=headers).json()
    assert before["accepted"] is False and before["accepted_at"] is None
    accept_disclaimer(client, headers)
    after = client.get("/api/disclaimer/status", headers=headers).json()
    assert after["accepted"] is True and after["accepted_at"] is not None


def test_accept_is_idempotent(client):
    headers = register_and_login(client, "alice")
    accept_disclaimer(client, headers)
    accept_disclaimer(client, headers)
    assert client.get("/api/disclaimer/status", headers=headers).json()["accepted"] is True


def test_accepting_wrong_version_is_rejected(client):
    headers = register_and_login(client, "alice")
    response = client.post("/api/disclaimer/accept", json={"version": "old-version"}, headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "disclaimer_outdated"


def test_business_routes_are_blocked_until_disclaimer_accepted():
    app = create_app()

    @app.get("/api/_test/business")
    def business(user: Annotated[User, Depends(require_disclaimer_user)]) -> dict[str, str]:
        return {"username": user.username}

    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        blocked = client.get("/api/_test/business", headers=headers)
        assert blocked.status_code == 403
        assert blocked.json()["error"]["code"] == "disclaimer_not_accepted"
        accept_disclaimer(client, headers)
        assert client.get("/api/_test/business", headers=headers).status_code == 200


def test_acceptance_is_per_user(client):
    alice = register_and_login(client, "alice")
    bob = register_and_login(client, "bob")
    accept_disclaimer(client, alice)
    assert client.get("/api/disclaimer/status", headers=bob).json()["accepted"] is False
