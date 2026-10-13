"""步骤 11 前端需要的后端小改动：消息编号、审计按客户端筛选、全部医嘱事件列表。"""

import json
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agent import conversations
from app.agent_grants.models import SdkCallAudit
from app.auth.models import User
from app.common.clock import get_today
from app.db import get_sessionmaker
from app.main import create_app
from tests.agent_fake import connect, say, scripted  # noqa: F401
from tests.helpers import ready_user

TODAY = date(2026, 9, 30)


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    with get_sessionmaker()() as session:
        yield session


def _user_id(db, username):
    return db.scalar(select(User.id).where(User.username == username))


# ---------- 消息编号 ----------


def test_conversation_messages_carry_their_ids(client, db):
    headers = ready_user(client, "alice")
    cid = client.post("/api/agent/conversations", json={}, headers=headers).json()["id"]
    uid = _user_id(db, "alice")
    first = conversations.append_message(db, uid, uuid.UUID(cid), "user", {"text": "晚饭吃什么"})
    second = conversations.append_message(db, uid, uuid.UUID(cid), "assistant", {"text": "清蒸鱼"})
    messages = client.get(f"/api/agent/conversations/{cid}", headers=headers).json()["messages"]
    assert [m["id"] for m in messages] == [str(first.id), str(second.id)]
    assert messages[0]["id"] != messages[1]["id"]


def test_streamed_done_message_id_matches_the_saved_assistant_message(client, scripted):
    headers = ready_user(client, "alice")
    connect(client, headers)
    cid = client.post("/api/agent/conversations", json={}, headers=headers).json()["id"]
    scripted.add(say("晚饭可以吃清蒸鱼和米饭，再配一份清炒时蔬，整体清淡又有足够的蛋白质。"))
    response = client.post(
        f"/api/agent/conversations/{cid}/messages", json={"text": "晚饭吃什么", "stream": True}, headers=headers
    )
    assert response.status_code == 200
    blocks = [b for b in response.text.split("\n\n") if b.strip()]
    event, data = blocks[-1].split("\n", 1)
    assert event == "event: done"
    done = json.loads(data.removeprefix("data: "))
    messages = client.get(f"/api/agent/conversations/{cid}", headers=headers).json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[-1]["id"] == done["message_id"]


# ---------- 审计按客户端名筛选 ----------


def test_audit_can_be_filtered_by_client_name(client, db):
    alice = ready_user(client, "alice")
    ready_user(client, "bella")
    alice_id, bella_id = _user_id(db, "alice"), _user_id(db, "bella")
    for user_id, name in ((alice_id, "agent"), (alice_id, "agent"), (alice_id, "inspector"), (bella_id, "agent")):
        db.add(SdkCallAudit(user_id=user_id, credential_kind="session", client_name=name,
                            capability="medical_list_items", outcome="ok", duration_ms=3))
    db.commit()

    def names(**params):
        response = client.get("/api/agent-grants/audit", params=params, headers=alice)
        assert response.status_code == 200, response.text
        return sorted(a["client_name"] for a in response.json())

    assert names() == ["agent", "agent", "inspector"]
    assert names(client_name="agent") == ["agent", "agent"]
    assert names(client_name="inspector") == ["inspector"]
    assert names(client_name="nobody") == []
    for bad in ("", "x" * 65):
        response = client.get("/api/agent-grants/audit", params={"client_name": bad}, headers=alice)
        assert response.status_code == 422, bad


# ---------- 全部医嘱事件 ----------


def _two_items(client, headers, **second):
    order = client.post("/api/medical/orders", json={"text": "下周一上午十点复诊。"}, headers=headers).json()
    assert order["items"] == []  # 条目全部是手动加的
    base = {"category": "diet_avoid", "subjects": ["辛辣"]}
    first = client.post(f"/api/medical/orders/{order['id']}/items", headers=headers,
                        json={**base, "content": "每天晚饭后服用药物期间不吃辛辣食物，含 0.5 克与 3 次的数值"}).json()
    other = client.post(f"/api/medical/orders/{order['id']}/items", headers=headers,
                        json={"category": "other", "content": "多喝水", **second}).json()
    return first, other


def test_medical_events_list_every_item_newest_first(client):
    headers = ready_user(client, "alice")
    first, other = _two_items(client, headers)
    assert client.post(f"/api/medical/items/{first['id']}/confirm", headers=headers).status_code == 200
    assert client.post(f"/api/medical/items/{other['id']}/void", headers=headers).status_code == 200
    response = client.get("/api/medical/events", headers=headers)
    assert response.status_code == 200, response.text
    events = response.json()
    assert sorted((e["action"], e["item_id"]) for e in events) == sorted([
        ("created", first["id"]), ("confirmed", first["id"]), ("created", other["id"]), ("voided", other["id"])])
    stamps = [e["occurred_at"] for e in events]
    assert stamps == sorted(stamps, reverse=True)
    for event in events:
        item = first if event["item_id"] == first["id"] else other
        assert event["item_category"] == item["category"]
        assert event["item_content"] == item["content"]
    assert any(len(e["item_content"]) > 20 and "…" not in e["item_content"] for e in events)
    assert set(events[0]) == {"id", "seq", "occurred_at", "action", "from_status", "to_status", "source", "detail",
                              "item_id", "item_category", "item_content"}


def test_medical_events_limit_bounds_and_ownership(client):
    alice = ready_user(client, "alice")
    first, other = _two_items(client, alice)
    client.post(f"/api/medical/items/{first['id']}/confirm", headers=alice)
    assert len(client.get("/api/medical/events", params={"limit": 1}, headers=alice).json()) == 1
    for bad in (0, 201):
        assert client.get("/api/medical/events", params={"limit": bad}, headers=alice).status_code == 422
    bella = ready_user(client, "bella")
    assert client.get("/api/medical/events", headers=bella).json() == []


def test_medical_events_include_system_review_events(client):
    headers = ready_user(client, "alice")
    order = client.post("/api/medical/orders", json={"text": "少吃辛辣。"}, headers=headers).json()
    item = client.post(
        f"/api/medical/orders/{order['id']}/items", headers=headers,
        json={"category": "diet_avoid", "content": "不吃辛辣", "subjects": ["辛辣"],
              "start_date": "2026-09-01", "review_date": TODAY.isoformat()},
    ).json()
    assert client.post(f"/api/medical/items/{item['id']}/confirm", headers=headers).status_code == 200
    assert client.get("/api/medical/constraints", headers=headers).status_code == 200  # 触发状态刷新
    events = client.get("/api/medical/events", headers=headers).json()
    due = [e for e in events if e["action"] == "review_due"]
    assert len(due) == 1
    assert due[0]["source"] == "system" and due[0]["item_id"] == item["id"]
    assert due[0]["detail"]["reason"] == "已到复查日期，请确认是否还需要继续遵守"
