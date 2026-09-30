from datetime import UTC, datetime

from sqlalchemy import func, select, text

from app.auth.service import register_user
from app.db import Base, get_engine, get_sessionmaker
from app.profile.models import Profile, ProfileChange
from app.profile.service import get_or_create_profile, list_profile_changes
from app.security.crypto import decrypt_value
from tests.helpers import accept_disclaimer, register_and_login


def _ready_user(client, username: str) -> dict[str, str]:
    headers = register_and_login(client, username)
    accept_disclaimer(client, headers)
    return headers


def test_profile_requires_disclaimer(client):
    headers = register_and_login(client, "alice")
    for method, path in [("get", "/api/profile"), ("patch", "/api/profile"),
                         ("get", "/api/profile/changes"), ("get", "/api/me/capabilities")]:
        kwargs = {"json": {"goal": "maintain"}} if method == "patch" else {}
        response = getattr(client, method)(path, headers=headers, **kwargs)
        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "disclaimer_not_accepted"


def test_profile_requires_login(client):
    assert client.get("/api/profile").status_code == 401


def test_new_user_gets_empty_profile(client):
    headers = _ready_user(client, "alice")
    body = client.get("/api/profile", headers=headers).json()
    assert body["gender"] is None
    assert body["height_cm"] is None
    assert body["diet_preferences"] == []
    assert body["cycle_tracking_opt_out"] is False


def test_update_then_read_returns_new_values(client):
    headers = _ready_user(client, "alice")
    patch = {"gender": "female", "birth_year": 1998, "height_cm": 162.5, "weight_kg": 52,
             "activity_level": "light", "goal": "lose_fat", "diet_preferences": ["清淡"],
             "food_avoidances": ["香菜"], "health_conditions": "轻度贫血", "notes": "胃不太好"}
    response = client.patch("/api/profile", json=patch, headers=headers)
    assert response.status_code == 200
    body = client.get("/api/profile", headers=headers).json()
    for key, value in patch.items():
        assert body[key] == value, key


def test_update_writes_change_record_only_when_values_change(client):
    headers = _ready_user(client, "alice")
    client.patch("/api/profile", json={"weight_kg": 60}, headers=headers)
    client.patch("/api/profile", json={"weight_kg": 58.5}, headers=headers)
    client.patch("/api/profile", json={"weight_kg": 58.5}, headers=headers)
    changes = client.get("/api/profile/changes", headers=headers).json()
    assert len(changes) == 2
    assert changes[0]["changes"] == {"weight_kg": {"old": 60, "new": 58.5}}
    assert changes[1]["changes"] == {"weight_kg": {"old": None, "new": 60}}


def test_null_clears_field(client):
    headers = _ready_user(client, "alice")
    client.patch("/api/profile", json={"notes": "临时备注", "diet_preferences": ["素食"]}, headers=headers)
    client.patch("/api/profile", json={"notes": None, "diet_preferences": None}, headers=headers)
    body = client.get("/api/profile", headers=headers).json()
    assert body["notes"] is None
    assert body["diet_preferences"] == []


def test_invalid_values_and_unknown_fields_are_rejected(client):
    headers = _ready_user(client, "alice")
    assert client.patch("/api/profile", json={"height_cm": 999}, headers=headers).status_code == 422
    assert client.patch("/api/profile", json={"gender": "robot"}, headers=headers).status_code == 422
    assert client.patch("/api/profile", json={"birth_year": 3000}, headers=headers).status_code == 422
    response = client.patch("/api/profile", json={"user_id": "00000000-0000-0000-0000-000000000000"},
                            headers=headers)
    assert response.status_code == 422


def test_users_cannot_see_each_others_profile(client):
    alice = _ready_user(client, "alice")
    bob = _ready_user(client, "bob")
    client.patch("/api/profile", json={"health_conditions": "高血压", "weight_kg": 70}, headers=alice)
    bob_profile = client.get("/api/profile", headers=bob).json()
    assert bob_profile["health_conditions"] is None
    assert bob_profile["weight_kg"] is None
    assert client.get("/api/profile/changes", headers=bob).json() == []
    assert client.get("/api/profile", headers=alice).json()["health_conditions"] == "高血压"


def test_capabilities_follow_gender_and_opt_out(client):
    headers = _ready_user(client, "alice")
    assert client.get("/api/me/capabilities", headers=headers).json()["cycle"] is False
    client.patch("/api/profile", json={"gender": "female"}, headers=headers)
    caps = client.get("/api/me/capabilities", headers=headers).json()
    assert caps == {"cycle": True, "medical": True, "nutrition": True, "fitness": True}
    client.patch("/api/profile", json={"cycle_tracking_opt_out": True}, headers=headers)
    assert client.get("/api/me/capabilities", headers=headers).json()["cycle"] is False
    client.patch("/api/profile", json={"gender": "male", "cycle_tracking_opt_out": False}, headers=headers)
    assert client.get("/api/me/capabilities", headers=headers).json()["cycle"] is False


def test_sensitive_columns_are_encrypted_at_rest(client):
    headers = _ready_user(client, "alice")
    client.patch("/api/profile", json={"height_cm": 172.5, "weight_kg": 65.25,
                                       "health_conditions": "轻度高血压", "notes": "少盐"}, headers=headers)
    with get_engine().connect() as conn:
        row = conn.execute(text(
            "SELECT height_cm, weight_kg, health_conditions, notes FROM profiles"
        )).one()
        change = conn.execute(text("SELECT changes FROM profile_changes")).scalar_one()
        password_hash = conn.execute(text("SELECT password_hash FROM users")).scalar_one()
    raw = " ".join(row) + change
    for plaintext in ["172.5", "65.25", "高血压", "少盐"]:
        assert plaintext not in raw
    assert decrypt_value(row[0]) == 172.5
    assert decrypt_value(row[2]) == "轻度高血压"
    assert password_hash.startswith("$argon2id$")
    assert "secret-pass-1" not in password_hash


def test_every_business_table_has_user_id():
    for name, table in Base.metadata.tables.items():
        if name == "users":
            continue
        assert "user_id" in table.columns, f"{name} 缺少 user_id 列"


def test_profile_creation_survives_concurrent_first_request(monkeypatch):
    with get_sessionmaker()() as db:
        user_id = register_user(db, "alice", "secret-pass-1").id
    with get_sessionmaker()() as first, get_sessionmaker()() as second:
        real_scalar = second.scalar
        calls = []

        def stale_first_select(statement, *args, **kwargs):
            # 模拟并发：second 的首次查询发生在 first 插入并提交之前，所以看不到这一行。
            calls.append(statement)
            return None if len(calls) == 1 else real_scalar(statement, *args, **kwargs)

        monkeypatch.setattr(second, "scalar", stale_first_select)
        get_or_create_profile(first, user_id)
        profile = get_or_create_profile(second, user_id)
        assert profile.user_id == user_id
        assert second.scalar(select(func.count()).select_from(Profile)) == 1


def test_changes_with_same_timestamp_are_listed_newest_insert_first():
    with get_sessionmaker()() as db:
        user_id = register_user(db, "alice", "secret-pass-1").id
        same_moment = datetime(2026, 1, 1, tzinfo=UTC)
        for n in range(5):
            db.add(ProfileChange(user_id=user_id, changed_at=same_moment, changes={"n": n}))
            db.commit()
        listed = [change.changes["n"] for change in list_profile_changes(db, user_id)]
    assert listed == [4, 3, 2, 1, 0]
