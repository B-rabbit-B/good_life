import uuid

import pytest
from sqlalchemy import select

from app.auth.models import User
from app.db import get_sessionmaker
from app.sdk import AgentCredential, GoodLife, SdkError
from app.sdk.tooling import agent_registry, capability_for_tool
from tests.helpers import ready_user


def _user_id(username):
    with get_sessionmaker()() as db:
        return db.scalar(select(User.id).where(User.username == username))


def test_agent_registry_excludes_every_user_confirmed_capability():
    agent = agent_registry()
    assert len(agent) == 28
    assert all(cap.level != "user_confirmed" for cap in agent.values())
    for name in ("medical_confirm_item", "medical_resolve_item", "medical.confirm_item", "medical_void_item"):
        assert capability_for_tool(name) is None
    assert capability_for_tool("medical_get_constraints").name == "medical.get_constraints"


def test_agent_credential_reads_and_writes_but_never_confirms(client):
    headers = ready_user(client, "alice")
    user_id = _user_id("alice")
    sdk = GoodLife(registry=agent_registry())
    order = sdk.call(AgentCredential(user_id), "medical.submit_order", {"text": "一周内忌食辛辣。"},
                     client_name="agent").data
    with pytest.raises(SdkError) as caught:
        sdk.call(AgentCredential(user_id), "medical.confirm_item", {"item_id": order["items"][0]["id"]})
    assert caught.value.code == "unknown_capability"
    with pytest.raises(SdkError) as caught:
        GoodLife().call(AgentCredential(user_id), "medical.confirm_item", {"item_id": order["items"][0]["id"]})
    assert caught.value.kind == "needs_user_confirmation"
    audit = client.get("/api/agent-grants/audit", headers=headers).json()
    assert {(a["capability"], a["client_name"]) for a in audit} >= {("medical.submit_order", "agent")}
    assert {a["credential_kind"] for a in audit if a["client_name"] == "agent"} == {"agent"}


def test_agent_credential_for_a_missing_user_is_unauthenticated(client):
    with pytest.raises(SdkError) as caught:
        GoodLife(registry=agent_registry()).call(AgentCredential(uuid.uuid4()), "profile.get_capabilities")
    assert caught.value.kind == "unauthenticated"
