"""经期与医嘱的单独同意：未同意前两个模块的接口与 SDK 一律拒绝，同意记录时间与文案版本，
撤回即清除该模块的数据并关闭模块；站内智能体把未同意的模块当作未开放。"""

import json
import re
import uuid
from datetime import date, timedelta

import pytest
from fastapi.routing import APIRoute, iter_route_contexts
from sqlalchemy import text

from app.agent.assembly import MEDICAL_NOT_CONSENTED
from app.agent.loop import FLAG_FALLBACK, FLAG_REWRITTEN
from app.consents.content import CONSENT_KINDS, CONSENT_TEXTS, CONSENT_VERSION
from app.db import get_engine
from app.disclaimer.content import DISCLAIMER_TEXT
from app.medical.samples import SAMPLE_ORDERS
from app.sdk import GoodLife, SdkError, UserAccessToken
from app.sdk.errors import CONSENT_HINT
from tests.agent_fake import call, connect, say, scripted  # noqa: F401
from tests.helpers import grant_consents, ready_user

FEMALE = {"gender": "female"}
CYCLE_TABLES = ("cycle_periods", "cycle_day_logs", "cycle_settings")
MEDICAL_TABLES = ("medical_orders", "medical_evidence", "medical_items", "medical_item_events")
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _code(response) -> str:
    return response.json()["error"]["code"]


def _user_id(username: str) -> uuid.UUID:
    with get_engine().connect() as conn:
        return conn.execute(text("SELECT id FROM users WHERE username = :name"), {"name": username}).scalar_one()


def _rows(table: str, username: str) -> int:
    with get_engine().connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table} WHERE user_id = :id"),  # noqa: S608 表名是常量
                            {"id": _user_id(username)}).scalar_one()


def _status(client, headers, kind: str) -> dict:
    listed = client.get("/api/consents", headers=headers)
    assert listed.status_code == 200, listed.text
    return next(item for item in listed.json() if item["kind"] == kind)


def _withdraw(client, headers, kind: str):
    return client.post(f"/api/account/consents/{kind}/withdraw", headers=headers)


def _fill_cycle(client, headers) -> None:
    start = date.today() - timedelta(days=20)
    period = client.post("/api/cycle/periods", headers=headers,
                         json={"start_date": start.isoformat(), "end_date": (start + timedelta(days=4)).isoformat()})
    assert period.status_code == 201, period.text
    log = client.put(f"/api/cycle/day-logs/{start.isoformat()}", json={"flow": "medium", "pain": 2}, headers=headers)
    assert log.status_code == 200, log.text
    settings = client.put("/api/cycle/settings", json={"status": "tracking"}, headers=headers)
    assert settings.status_code == 200, settings.text


def _fill_medical(client, headers) -> None:
    order = client.post("/api/medical/orders", json={"text": SAMPLE_ORDERS["short_term"]}, headers=headers)
    assert order.status_code == 201, order.text
    evidence = client.post(f"/api/medical/orders/{order.json()['id']}/evidence",
                           files={"file": ("order.png", PNG, "image/png")}, headers=headers)
    assert evidence.status_code == 201, evidence.text
    require = order.json()["items"][1]
    assert client.post(f"/api/medical/items/{require['id']}/confirm", headers=headers).status_code == 200


def _sentences(value: str) -> set[str]:
    return {part.strip() for part in re.split(r"[。！？\n]", value) if part.strip()}


def test_cycle_and_medical_refuse_until_consented(client):
    headers = ready_user(client, "alice", FEMALE, consents=False)
    for path in ("/api/cycle/periods", "/api/medical/items"):
        response = client.get(path, headers=headers)
        assert response.status_code == 403, response.text
        assert _code(response) == "consent_required"
    assert client.get("/api/nutrition/summary", headers=headers).status_code == 200
    assert client.get("/api/fitness/workouts", headers=headers).status_code == 200

    grant_consents(client, headers)
    assert client.get("/api/cycle/periods", headers=headers).status_code == 200
    assert client.get("/api/medical/items", headers=headers).status_code == 200


def test_sdk_reports_missing_consent_as_needing_the_user(client):
    headers = ready_user(client, "alice", FEMALE, consents=False)
    token = UserAccessToken(headers["Authorization"].removeprefix("Bearer "))
    sdk = GoodLife()
    for capability in ("cycle.list_periods", "medical.list_items"):
        with pytest.raises(SdkError) as caught:
            sdk.call(token, capability)
        assert (caught.value.kind, caught.value.code, caught.value.hint) == (
            "needs_user_confirmation", "consent_required", CONSENT_HINT), capability


def test_every_cycle_and_medical_route_refuses_without_consent(client):
    headers = ready_user(client, "alice", FEMALE, consents=False)
    today = date.today().isoformat()
    checked = []
    for ctx in iter_route_contexts(client.app.routes):
        if not isinstance(ctx.original_route, APIRoute):
            continue
        if not ctx.path.startswith(("/api/cycle/", "/api/medical/")):
            continue
        path = re.sub(r"\{(\w+)\}", lambda m: today if m.group(1) == "log_date" else str(uuid.uuid4()), ctx.path)
        for method in ctx.methods:
            response = client.request(method, path, json={}, headers=headers)
            assert (response.status_code, _code(response)) == (403, "consent_required"), f"{method} {ctx.path}"
            checked.append(f"{method} {ctx.path}")
    assert len(checked) >= 30


def test_consent_records_time_and_text_version(client):
    headers = ready_user(client, "alice", FEMALE, consents=False)
    listed = client.get("/api/consents", headers=headers).json()
    assert [item["kind"] for item in listed] == list(CONSENT_KINDS)
    assert all(not item["granted"] and item["granted_at"] is None for item in listed)
    assert {item["current_version"] for item in listed} == {CONSENT_VERSION}

    outdated = client.post("/api/consents/cycle", json={"version": "2000-01-01"}, headers=headers)
    assert (outdated.status_code, _code(outdated)) == (409, "consent_outdated")
    assert not _status(client, headers, "cycle")["granted"]

    first = client.post("/api/consents/cycle", json={"version": CONSENT_VERSION}, headers=headers)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["granted"] and body["granted_version"] == CONSENT_VERSION and body["granted_at"]
    assert body["withdrawn_at"] is None
    assert _status(client, headers, "cycle") == body
    again = client.post("/api/consents/cycle", json={"version": CONSENT_VERSION}, headers=headers)
    assert again.status_code == 200 and again.json() == body
    assert _rows("sensitive_consents", "alice") == 1
    assert not _status(client, headers, "medical")["granted"]

    extra = client.post("/api/consents/medical", json={"version": CONSENT_VERSION, "x": 1}, headers=headers)
    assert extra.status_code == 422
    assert client.post("/api/consents/photos", json={"version": CONSENT_VERSION}, headers=headers).status_code == 422


def test_consent_text_states_necessity_and_impact_and_is_not_the_disclaimer():
    assert set(CONSENT_TEXTS) == set(CONSENT_KINDS)
    disclaimer = _sentences(DISCLAIMER_TEXT)
    for kind, body in CONSENT_TEXTS.items():
        for word in ("必要", "影响", "撤回", "参照"):
            assert word in body, (kind, word)
        assert _sentences(body) & disclaimer == set(), kind


def test_withdraw_clears_module_data_and_closes_the_module(client):
    headers = ready_user(client, "alice", FEMALE)
    _fill_cycle(client, headers)
    _fill_medical(client, headers)
    assert all(_rows(table, "alice") > 0 for table in CYCLE_TABLES + MEDICAL_TABLES)

    response = _withdraw(client, headers, "cycle")
    assert response.status_code == 204, response.text
    assert [_rows(table, "alice") for table in CYCLE_TABLES] == [0, 0, 0]
    assert _code(client.get("/api/cycle/periods", headers=headers)) == "consent_required"
    status = _status(client, headers, "cycle")
    assert not status["granted"] and status["withdrawn_at"]

    response = _withdraw(client, headers, "medical")
    assert response.status_code == 204, response.text
    assert [_rows(table, "alice") for table in MEDICAL_TABLES] == [0, 0, 0, 0]
    assert _code(client.get("/api/medical/items", headers=headers)) == "consent_required"

    again = _withdraw(client, headers, "medical")
    assert (again.status_code, _code(again)) == (404, "not_found")


def test_withdrawing_one_module_keeps_the_other_and_other_users(client):
    alice = ready_user(client, "alice", FEMALE)
    bella = ready_user(client, "bella", FEMALE)
    for headers in (alice, bella):
        _fill_cycle(client, headers)
        _fill_medical(client, headers)
    before = {table: _rows(table, "alice") for table in MEDICAL_TABLES}
    others = {table: _rows(table, "bella") for table in CYCLE_TABLES + MEDICAL_TABLES}

    assert _withdraw(client, alice, "cycle").status_code == 204
    assert {table: _rows(table, "alice") for table in MEDICAL_TABLES} == before
    assert {table: _rows(table, "bella") for table in CYCLE_TABLES + MEDICAL_TABLES} == others
    assert client.get("/api/medical/items", headers=alice).status_code == 200
    assert _status(client, alice, "medical")["granted"]
    assert client.get("/api/cycle/periods", headers=bella).status_code == 200
    assert _status(client, bella, "cycle")["granted"]


def test_regrant_after_withdraw_reopens_an_empty_module(client):
    headers = ready_user(client, "alice", FEMALE)
    _fill_cycle(client, headers)
    assert _withdraw(client, headers, "cycle").status_code == 204

    response = client.post("/api/consents/cycle", json={"version": CONSENT_VERSION}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["granted"] and response.json()["withdrawn_at"] is None
    periods = client.get("/api/cycle/periods", headers=headers)
    assert periods.status_code == 200 and periods.json() == []
    assert _rows("sensitive_consents", "alice") == 2  # 经期一行、医嘱一行，重新同意不新增行


def test_withdraw_needs_only_login(client):
    headers = ready_user(client, "alice", FEMALE)
    with get_engine().begin() as conn:
        conn.execute(text("UPDATE disclaimer_acceptances SET version = '2000-01-01' WHERE user_id = :id"),
                     {"id": _user_id("alice")})
    assert _code(client.get("/api/cycle/periods", headers=headers)) == "disclaimer_not_accepted"
    assert _withdraw(client, headers, "cycle").status_code == 204
    assert client.post("/api/account/consents/medical/withdraw").status_code == 401


def test_agent_treats_missing_consent_as_a_closed_module(client, scripted):
    headers = ready_user(client, "alice", FEMALE, consents=False)
    connect(client, headers)
    scripted.add(say("Fried chicken tonight is fine, and 炸鸡 with a salad works well for dinner."))
    cid = client.post("/api/agent/conversations", json={}, headers=headers).json()["id"]
    response = client.post(f"/api/agent/conversations/{cid}/messages", json={"text": "晚饭吃炸鸡可以吗", "stream": False},
                           headers=headers)
    assert response.status_code == 200, response.text
    [request] = scripted.requests  # 只调了一次模型：没有触发重写
    assert not [name for name in request.tool_names if name.startswith(("cycle_", "medical_"))]
    assert "经期" not in request.system
    constraints = next(s for s in request.system.split("\n\n") if s.startswith("【当前硬约束"))
    assert MEDICAL_NOT_CONSENTED in constraints and "暂时读不到" not in constraints
    flags = response.json()["flags"]
    assert FLAG_REWRITTEN not in flags and FLAG_FALLBACK not in flags


OPENING_SENTENCE = "开场问候记录里可能含相关内容，撤回时同样不会自动删除，可在清空对话历史时一并清掉。"


def test_consent_text_says_openings_are_cleared_with_the_conversation_history():
    for kind, body in CONSENT_TEXTS.items():
        assert OPENING_SENTENCE in body, kind
    assert CONSENT_VERSION == "2026-10-15"


def _turn(client, headers, cid: str, text_: str) -> dict:
    response = client.post(f"/api/agent/conversations/{cid}/messages", json={"text": text_, "stream": False},
                           headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _replayed(request) -> str:
    """发给模型的对话消息（不含系统指令与工具声明）。"""
    return json.dumps(request.messages, ensure_ascii=False)


def test_withdrawn_module_tool_results_are_not_replayed_to_the_model(client, scripted):
    canary = "金丝雀医嘱条目甲乙丙"
    headers = ready_user(client, "alice", FEMALE)
    connect(client, headers)
    order = client.post("/api/medical/orders", json={"text": "饮食清淡。"}, headers=headers).json()
    item = client.post(f"/api/medical/orders/{order['id']}/items", headers=headers,
                       json={"category": "other", "content": canary})
    assert item.status_code == 201, item.text
    cid = client.post("/api/agent/conversations", json={}, headers=headers).json()["id"]
    start = (date.today() - timedelta(days=30)).isoformat()
    scripted.add(call("medical_list_items", {}), call("cycle_record_period", {"start_date": start}), say("都看过了。"))
    assert _turn(client, headers, cid, "看看我的条目，再记一下经期")["tools_used"] == [
        "medical_list_items", "cycle_record_period"]
    assert canary in _replayed(scripted.requests[-1])  # 同一轮里模型确实拿到过这份工具结果

    assert _withdraw(client, headers, "medical").status_code == 204
    _turn(client, headers, cid, "今天吃什么好")
    replay = scripted.requests[-1]
    assert canary not in replay.text()
    assert "medical_list_items" not in replay.text()
    assert "cycle_record_period" in _replayed(replay)  # 仍然同意的模块照常回放

    assert _withdraw(client, headers, "cycle").status_code == 204
    _turn(client, headers, cid, "明天呢")
    assert "cycle_record_period" not in scripted.requests[-1].text()
