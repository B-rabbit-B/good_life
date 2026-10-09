"""智能体的存储与接口：会话与消息、偏好记忆（含过滤）、开场记录、设置。没有任何模型调用。"""

import threading
import uuid
from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.agent import conversations, preferences
from app.agent.models import AgentConversation, AgentMessage, AgentOpening, AgentPreference, AgentSettings
from app.auth.models import User
from app.db import get_engine, get_sessionmaker
from app.errors import AppError
from app.security.crypto import decrypt_value
from tests.helpers import ready_user


@pytest.fixture
def db():
    with get_sessionmaker()() as session:
        yield session


def _make_user(db, name: str) -> uuid.UUID:
    user = User(username=name, password_hash="x")
    db.add(user)
    db.commit()
    return user.id


def _raw(sql: str, **params) -> list:
    with get_engine().connect() as conn:
        return list(conn.execute(text(sql), params).scalars())


# ---------- 会话与消息 ----------


def test_conversation_crud_and_order(db):
    uid = _make_user(db, "alice")
    first = conversations.create_conversation(db, uid, "晚饭吃什么")
    second = conversations.create_conversation(db, uid)
    assert second.title is None
    assert [c.id for c in conversations.list_conversations(db, uid)] == [second.id, first.id]
    conversations.append_message(db, uid, first.id, "user", {"text": "你好"})  # 追加消息会把会话顶到最前
    assert [c.id for c in conversations.list_conversations(db, uid)] == [first.id, second.id]
    assert conversations.get_conversation(db, uid, first.id).title == "晚饭吃什么"
    conversations.delete_conversation(db, uid, first.id)
    assert [c.id for c in conversations.list_conversations(db, uid)] == [second.id]


def test_messages_get_increasing_positions_in_order(db):
    uid = _make_user(db, "alice")
    conversation = conversations.create_conversation(db, uid)
    other = conversations.create_conversation(db, uid)
    roles = ["user", "assistant", "tool", "assistant"]
    for index, role in enumerate(roles):
        message = conversations.append_message(db, uid, conversation.id, role, {"text": f"m{index}"})
        assert message.position == index + 1
    assert conversations.append_message(db, uid, other.id, "user", {"text": "x"}).position == 1  # 各会话独立计数
    stored = conversations.history(db, uid, conversation.id)
    assert [m.position for m in stored] == [1, 2, 3, 4]
    assert [m.role for m in stored] == roles
    assert [m.content["text"] for m in stored] == ["m0", "m1", "m2", "m3"]


def test_history_returns_the_latest_messages_oldest_first(db):
    uid = _make_user(db, "alice")
    conversation = conversations.create_conversation(db, uid)
    for index in range(1, 46):
        conversations.append_message(db, uid, conversation.id, "user", {"text": str(index)})
    default = conversations.history(db, uid, conversation.id)
    assert [m.position for m in default] == list(range(6, 46))
    assert [m.position for m in conversations.history(db, uid, conversation.id, limit=3)] == [43, 44, 45]


def test_append_message_rejects_bad_role_and_content(db):
    uid = _make_user(db, "alice")
    conversation = conversations.create_conversation(db, uid)
    with pytest.raises(ValueError):
        conversations.append_message(db, uid, conversation.id, "system", {"text": "x"})
    with pytest.raises(ValueError):
        conversations.append_message(db, uid, conversation.id, "user", "纯文本")  # type: ignore[arg-type]
    assert conversations.history(db, uid, conversation.id) == []


def test_duplicate_position_is_rejected_by_the_database(db):
    uid = _make_user(db, "alice")
    conversation = conversations.create_conversation(db, uid)
    conversations.append_message(db, uid, conversation.id, "user", {"text": "a"})
    db.add(AgentMessage(user_id=uid, conversation_id=conversation.id, position=1, role="user", content={"text": "b"}))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_append_waits_for_the_conversation_row_lock(db):
    """另一个事务锁着会话行时，追加会排队等待；放锁后序号照常从 1 开始。"""
    uid = _make_user(db, "alice")
    conversation = conversations.create_conversation(db, uid)
    results: list[int] = []

    def append() -> None:
        with get_sessionmaker()() as session:
            results.append(conversations.append_message(session, uid, conversation.id, "user", {"text": "a"}).position)

    with get_sessionmaker()() as holder:
        holder.execute(select(AgentConversation).where(AgentConversation.id == conversation.id).with_for_update())
        thread = threading.Thread(target=append)
        thread.start()
        thread.join(timeout=0.5)
        assert thread.is_alive() and results == []
        holder.rollback()
    thread.join(timeout=10)
    assert results == [1]


def test_concurrent_appends_get_distinct_consecutive_positions(db):
    uid = _make_user(db, "alice")
    conversation = conversations.create_conversation(db, uid)
    errors: list[Exception] = []

    def worker(name: int) -> None:
        try:
            with get_sessionmaker()() as session:
                for index in range(5):
                    conversations.append_message(session, uid, conversation.id, "user", {"text": f"{name}-{index}"})
        except Exception as exc:  # noqa: BLE001 - 收集后在主线程断言
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert errors == []
    stored = conversations.history(db, uid, conversation.id, limit=100)
    assert [m.position for m in stored] == list(range(1, 31))


def test_content_and_title_are_encrypted_at_rest(db):
    uid = _make_user(db, "alice")
    conversation = conversations.create_conversation(db, uid, "秘密标题XYZ")
    message = conversations.append_message(
        db, uid, conversation.id, "assistant",
        {"text": "秘密正文XYZ", "provider_state": {"sig": "秘密状态XYZ"}, "evidence": [], "flags": []},
    )
    preferences.add_preference(db, uid, "我不吃香菜XYZ", "user")
    db.add(AgentOpening(user_id=uid, day=date(2026, 10, 9), kind="review", status="asked", question="秘密问题XYZ"))
    db.commit()
    [title] = _raw("SELECT title FROM agent_conversations")
    [content] = _raw("SELECT content FROM agent_messages")
    [pref] = _raw("SELECT content FROM agent_preferences")
    [question] = _raw("SELECT question FROM agent_openings")
    for raw in (title, content, pref, question):
        assert "XYZ" not in raw
    assert decrypt_value(title) == "秘密标题XYZ"
    assert decrypt_value(content)["text"] == "秘密正文XYZ"
    assert decrypt_value(pref) == "我不吃香菜XYZ"
    assert decrypt_value(question) == "秘密问题XYZ"
    assert message.content["provider_state"] == {"sig": "秘密状态XYZ"}


def test_other_users_conversations_are_not_found(db):
    alice, bob = _make_user(db, "alice"), _make_user(db, "bob")
    conversation = conversations.create_conversation(db, alice)
    assert conversations.list_conversations(db, bob) == []
    for call in (
        lambda: conversations.get_conversation(db, bob, conversation.id),
        lambda: conversations.delete_conversation(db, bob, conversation.id),
        lambda: conversations.append_message(db, bob, conversation.id, "user", {"text": "x"}),
        lambda: conversations.history(db, bob, conversation.id),
    ):
        with pytest.raises(AppError) as error:
            call()
        assert error.value.status_code == 404
    assert conversations.history(db, alice, conversation.id) == []


def test_deleting_a_conversation_deletes_its_messages(db):
    uid = _make_user(db, "alice")
    conversation = conversations.create_conversation(db, uid)
    conversations.append_message(db, uid, conversation.id, "user", {"text": "a"})
    conversations.delete_conversation(db, uid, conversation.id)
    assert db.scalars(select(AgentMessage)).all() == []


# ---------- 偏好 ----------

REJECTED = [
    "我对花生过敏",
    "医生让我少吃盐",
    "我在吃降压药",
    "忌口（因医嘱）",
    "忌口(因医嘱)",
    "遵医嘱忌口辛辣",
    "我有糖尿病",
    "最近血糖偏高，少吃甜",
    "血 压高不吃咸",
    "我怀孕了不吃生食",
    "备孕期间不喝咖啡",
    "术后要吃清淡",
    "每天服药后不吃柚子",
    "药剂量按说明来",
    "我痛风，不吃海鲜",
    "I am allergic to peanuts",
    "my Doctor said no salt",
    "   ",
]
ACCEPTED = ["我喜欢吃辣", "早餐习惯喝豆浆", "我不吃香菜", "晚饭想清淡一点", "不爱吃内脏", "周末喜欢做饭", "忌口：不吃折耳根"]


@pytest.mark.parametrize("text_value", REJECTED)
def test_check_preference_rejects_medical_information(text_value):
    reason = preferences.check_preference(text_value)
    assert reason is not None
    if text_value.strip():
        assert reason == preferences.REJECT_REASON


@pytest.mark.parametrize("text_value", ACCEPTED)
def test_check_preference_accepts_taste_preferences(text_value):
    assert preferences.check_preference(text_value) is None


def test_check_preference_rejects_overlong_text():
    assert preferences.check_preference("辣" * preferences.MAX_PREFERENCE_CHARS) is None
    assert preferences.check_preference("辣" * (preferences.MAX_PREFERENCE_CHARS + 1)) is not None


def test_hard_info_words_cover_the_required_terms():
    required = {"医嘱", "医生", "处方", "用药", "服药", "药", "剂量", "过敏", "病", "确诊", "术后",
                "忌口（因医嘱）", "血糖", "血压", "孕", "怀孕"}
    assert required <= set(preferences.HARD_INFO_WORDS)


def test_add_list_and_delete_preferences(db):
    uid = _make_user(db, "alice")
    first = preferences.add_preference(db, uid, " 我喜欢吃辣 ", "user")
    second = preferences.add_preference(db, uid, "早餐习惯喝豆浆", "agent")
    assert (first.content, first.source, second.source) == ("我喜欢吃辣", "user", "agent")
    assert [p.id for p in preferences.list_preferences(db, uid)] == [first.id, second.id]
    preferences.delete_preference(db, uid, first.id)
    assert [p.id for p in preferences.list_preferences(db, uid)] == [second.id]


def test_duplicate_preference_is_not_added_again(db):
    uid = _make_user(db, "alice")
    first = preferences.add_preference(db, uid, "我喜欢吃辣", "user")
    again = preferences.add_preference(db, uid, "我喜欢 吃辣", "agent")
    assert again.id == first.id
    assert len(preferences.list_preferences(db, uid)) == 1
    other = _make_user(db, "bob")
    assert preferences.add_preference(db, other, "我喜欢吃辣", "user").id != first.id  # 去重只在本人范围内


def test_preference_limit(db):
    uid = _make_user(db, "alice")
    for index in range(preferences.MAX_PREFERENCES):
        preferences.add_preference(db, uid, f"口味偏好{index}", "user")
    with pytest.raises(AppError) as error:
        preferences.add_preference(db, uid, "一条新的口味偏好", "user")
    assert (error.value.status_code, error.value.code) == (409, "agent_too_many_preferences")
    assert preferences.add_preference(db, uid, "口味偏好3", "user").content == "口味偏好3"  # 重复的仍然返回已有的
    assert len(preferences.list_preferences(db, uid)) == preferences.MAX_PREFERENCES


def test_rejected_preference_is_not_stored(db):
    uid = _make_user(db, "alice")
    with pytest.raises(AppError) as error:
        preferences.add_preference(db, uid, "我对花生过敏", "agent")
    assert (error.value.status_code, error.value.code) == (422, "agent_preference_rejected")
    assert preferences.list_preferences(db, uid) == []


def test_preference_isolation(db):
    alice, bob = _make_user(db, "alice"), _make_user(db, "bob")
    pref = preferences.add_preference(db, alice, "我喜欢吃辣", "user")
    assert preferences.list_preferences(db, bob) == []
    with pytest.raises(AppError) as error:
        preferences.delete_preference(db, bob, pref.id)
    assert error.value.status_code == 404
    assert db.scalars(select(AgentPreference)).one().id == pref.id


# ---------- 开场记录与设置（模型层） ----------


def test_opening_is_unique_per_user_day_and_kind(db):
    uid = _make_user(db, "alice")
    day = date(2026, 10, 9)
    db.add(AgentOpening(user_id=uid, day=day, kind="review", status="asked", question="q"))
    db.commit()
    db.add(AgentOpening(user_id=uid, day=day, kind="meal", status="asked", question="q"))
    db.add(AgentOpening(user_id=uid, day=date(2026, 10, 10), kind="review", status="asked", question="q"))
    db.commit()
    db.add(AgentOpening(user_id=uid, day=day, kind="review", status="declined", question="q"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_settings_row_is_unique_per_user_and_defaults_on(db):
    uid = _make_user(db, "alice")
    db.add(AgentSettings(user_id=uid))
    db.commit()
    assert db.scalars(select(AgentSettings)).one().openings_enabled is True
    db.add(AgentSettings(user_id=uid))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# ---------- 接口 ----------


def test_conversation_api_hides_tool_messages_and_provider_state(client, db):
    headers = ready_user(client, "alice")
    created = client.post("/api/agent/conversations", json={"title": "今天吃什么"}, headers=headers)
    assert created.status_code == 201
    cid = created.json()["id"]
    uid = db.scalar(select(User.id).where(User.username == "alice"))
    cuid = uuid.UUID(cid)
    conversations.append_message(db, uid, cuid, "user", {"text": "晚饭吃什么"})
    conversations.append_message(
        db, uid, cuid, "assistant",
        {"text": "", "tool_calls": [{"id": "c1", "name": "list_orders", "arguments": {}}],
         "provider_state": {"thought_signature": "SECRET-STATE"}},
    )
    conversations.append_message(
        db, uid, cuid, "tool", {"tool_call_id": "c1", "tool_name": "list_orders", "text": "SECRET-TOOL-RESULT"}
    )
    conversations.append_message(
        db, uid, cuid, "assistant",
        {"text": "可以吃清蒸鱼", "evidence": [{"source": "医嘱"}], "flags": ["guard_rewritten"],
         "provider_state": {"thought_signature": "SECRET-STATE"}, "tool_calls": []},
    )
    response = client.get(f"/api/agent/conversations/{cid}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "今天吃什么"
    assert [(m["role"], m["text"]) for m in body["messages"]] == [("user", "晚饭吃什么"), ("assistant", "可以吃清蒸鱼")]
    assert body["messages"][0]["evidence"] == [] and body["messages"][0]["flags"] == []
    assert body["messages"][1]["evidence"] == [{"source": "医嘱"}]
    assert body["messages"][1]["flags"] == ["guard_rewritten"]
    assert set(body["messages"][1]) == {"role", "text", "evidence", "flags", "created_at"}
    assert "SECRET" not in response.text and "tool" not in {m["role"] for m in body["messages"]}


def test_conversation_api_list_isolation_and_delete(client):
    alice = ready_user(client, "alice")
    bob = ready_user(client, "bob")
    first = client.post("/api/agent/conversations", json={}, headers=alice).json()
    second = client.post("/api/agent/conversations", json={}, headers=alice).json()
    assert first["title"] is None
    assert [c["id"] for c in client.get("/api/agent/conversations", headers=alice).json()] == [second["id"], first["id"]]
    assert client.get("/api/agent/conversations", headers=bob).json() == []
    assert client.get(f"/api/agent/conversations/{first['id']}", headers=bob).status_code == 404
    assert client.delete(f"/api/agent/conversations/{first['id']}", headers=bob).status_code == 404
    assert client.delete(f"/api/agent/conversations/{first['id']}", headers=alice).status_code == 204
    assert client.get(f"/api/agent/conversations/{first['id']}", headers=alice).status_code == 404
    assert client.get(f"/api/agent/conversations/{uuid.uuid4()}", headers=alice).status_code == 404


def test_conversation_create_rejects_client_supplied_fields(client):
    headers = ready_user(client, "alice")
    assert client.post("/api/agent/conversations", json={"user_id": str(uuid.uuid4())}, headers=headers).status_code == 422
    assert client.post("/api/agent/conversations", json={"title": ""}, headers=headers).status_code == 422
    assert client.post("/api/agent/conversations", json={"title": "x" * 51}, headers=headers).status_code == 422


def test_preference_api(client):
    alice = ready_user(client, "alice")
    bob = ready_user(client, "bob")
    created = client.post("/api/agent/preferences", json={"content": "我喜欢吃辣"}, headers=alice)
    assert created.status_code == 201
    pref = created.json()
    assert (pref["content"], pref["source"]) == ("我喜欢吃辣", "user")
    assert client.post("/api/agent/preferences", json={"content": "我喜欢吃辣"}, headers=alice).json()["id"] == pref["id"]
    assert [p["id"] for p in client.get("/api/agent/preferences", headers=alice).json()] == [pref["id"]]
    assert client.get("/api/agent/preferences", headers=bob).json() == []
    assert client.delete(f"/api/agent/preferences/{pref['id']}", headers=bob).status_code == 404
    assert client.delete(f"/api/agent/preferences/{pref['id']}", headers=alice).status_code == 204
    assert client.get("/api/agent/preferences", headers=alice).json() == []


def test_preference_api_filters_and_validates(client):
    headers = ready_user(client, "alice")
    rejected = client.post("/api/agent/preferences", json={"content": "我对花生过敏"}, headers=headers)
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "agent_preference_rejected"
    assert client.post("/api/agent/preferences", json={"content": "早餐习惯喝豆浆"}, headers=headers).status_code == 201
    assert client.post("/api/agent/preferences", json={"content": "  "}, headers=headers).status_code == 422
    assert client.post("/api/agent/preferences", json={"content": "辣" * 101}, headers=headers).status_code == 422
    assert client.post("/api/agent/preferences", json={"content": "x", "source": "agent"}, headers=headers).status_code == 422
    assert client.post("/api/agent/preferences", json={"content": "x", "user_id": str(uuid.uuid4())}, headers=headers).status_code == 422


def test_preference_api_limit(client):
    headers = ready_user(client, "alice")
    for index in range(preferences.MAX_PREFERENCES):
        assert client.post("/api/agent/preferences", json={"content": f"口味偏好{index}"}, headers=headers).status_code == 201
    response = client.post("/api/agent/preferences", json={"content": "一条新的口味偏好"}, headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "agent_too_many_preferences"


def test_settings_api(client):
    alice = ready_user(client, "alice")
    bob = ready_user(client, "bob")
    assert client.get("/api/agent/settings", headers=alice).json() == {"openings_enabled": True}
    assert client.put("/api/agent/settings", json={"openings_enabled": False}, headers=alice).json() == {
        "openings_enabled": False
    }
    assert client.get("/api/agent/settings", headers=alice).json() == {"openings_enabled": False}
    assert client.get("/api/agent/settings", headers=bob).json() == {"openings_enabled": True}
    assert client.put("/api/agent/settings", json={"openings_enabled": True}, headers=alice).json() == {
        "openings_enabled": True
    }
    assert client.put("/api/agent/settings", json={}, headers=alice).status_code == 422
    assert client.put("/api/agent/settings", json={"openings_enabled": True, "x": 1}, headers=alice).status_code == 422
    assert client.put("/api/agent/settings", json={"openings_enabled": "maybe"}, headers=alice).status_code == 422


def test_agent_api_requires_login_and_disclaimer(client):
    assert client.get("/api/agent/conversations").status_code == 401
    assert client.get("/api/agent/settings").status_code == 401
    from tests.helpers import register_and_login

    headers = register_and_login(client, "nodisclaimer")
    for path in ("/api/agent/conversations", "/api/agent/preferences", "/api/agent/settings"):
        assert client.get(path, headers=headers).status_code == 403, path
