import uuid
from datetime import UTC, datetime, timedelta

from app.security.tokens import create_access_token
from tests.helpers import register_and_login


def test_register_returns_user_without_password(client):
    response = client.post("/api/auth/register", json={"username": "Alice", "password": "secret-pass-1"})
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "alice"
    assert "password" not in body and "password_hash" not in body


def test_duplicate_username_is_rejected_case_insensitively(client):
    client.post("/api/auth/register", json={"username": "alice", "password": "secret-pass-1"})
    response = client.post("/api/auth/register", json={"username": "ALICE", "password": "another-pass-2"})
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "username_taken"
    assert "已被注册" in error["message"]


def test_register_validates_input(client):
    response = client.post("/api/auth/register", json={"username": "a!", "password": "short"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_login_with_wrong_password_or_unknown_user_is_rejected(client):
    client.post("/api/auth/register", json={"username": "alice", "password": "secret-pass-1"})
    wrong = client.post("/api/auth/login", json={"username": "alice", "password": "wrong-pass-9"})
    unknown = client.post("/api/auth/login", json={"username": "nobody", "password": "secret-pass-1"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"] == "invalid_credentials"


def test_me_requires_login(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_me_returns_current_user(client):
    headers = register_and_login(client, "alice")
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["username"] == "alice"


def test_garbage_token_is_rejected(client):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_token_for_unknown_user_is_rejected(client):
    token = create_access_token(uuid.uuid4(), 0)
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_expired_token_is_rejected(client):
    headers = register_and_login(client, "alice")
    user_id = uuid.UUID(client.get("/api/auth/me", headers=headers).json()["id"])
    token = create_access_token(user_id, 0, now=datetime.now(UTC) - timedelta(days=365))
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_logout_invalidates_existing_token(client):
    headers = register_and_login(client, "alice")
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"
    login = client.post("/api/auth/login", json={"username": "alice", "password": "secret-pass-1"})
    new_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/auth/me", headers=new_headers).status_code == 200
