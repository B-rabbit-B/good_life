"""对话循环与聊天接口（续）：流式与 JSON、错误、历史重放；夹具与辅助函数见 agent_loop_support.py。"""

import json
import re
import uuid

import pytest
from sqlalchemy import select

from app.agent.guard import NOTICE_HEADER
from app.agent.loop import (
    MAX_MODEL_CALLS,
    MAX_TOOL_RESULT_BYTES,
    RISK_USER_PLACEHOLDER,
    TOOL_LIMIT_REPLY,
    TOOL_RESULT_PREVIEW_CHARS,
    bound_tool_result,
    replayable,
)
from app.agent import conversations, loop
from app.auth.models import User
from app.agent.safety import HEALTH_DISCLAIMER, SAFE_REPLIES
from app.db import get_db, get_sessionmaker
from app.llm.capabilities import Capabilities
from app.llm.service import ResolvedTarget

from tests.agent_fake import call, connect, fail, say, scripted  # noqa: F401
from tests.helpers import ready_user
from tests.agent_loop_support import (
    FULL_PROFILE,
    _answer,
    _conversation,
    _events,
    _messages,
    _no_spicy_user,
    _post,
    _send,
    _tool_results,
    client,
)  # noqa: F401


# ---------- 流式与 JSON ----------


def test_streaming_sends_deltas_then_done(client, scripted):
    headers = ready_user(client, "nick", FULL_PROFILE)
    connect(client, headers)
    cid = _conversation(client, headers)
    scripted.add(say("晚饭可以吃清蒸鱼和米饭，再配一份清炒时蔬，整体清淡又有足够的蛋白质。"))
    response = _post(client, headers, cid, "晚饭吃什么", stream=True)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _events(response)
    deltas = [data["text"] for event, data in events if event == "delta"]
    assert len(deltas) >= 2 and [event for event, _ in events[:-1]] == ["delta"] * len(deltas)
    event, done = events[-1]
    assert event == "done"
    assert set(done) == {"message_id", "evidence", "flags", "tools_used"}
    final = _messages(client, headers, cid)[-1]
    assert "".join(deltas) == final["text"] and done["evidence"] == final["evidence"]


def test_streaming_a_rewritten_answer_sends_only_the_guarded_text(client, scripted):
    headers, _ = _no_spicy_user(client, "bob")
    connect(client, headers)
    cid = _conversation(client, headers)
    scripted.add(say("今晚推荐麻婆豆腐，很下饭。"), say("今晚可以吃清蒸鱼配米饭，清淡又有蛋白质。"))
    events = _events(_post(client, headers, cid, "晚饭吃什么", stream=True))
    streamed = "".join(data["text"] for event, data in events if event == "delta")
    event, done = events[-1]
    assert event == "done" and done["flags"] == ["guard_rewritten"]
    assert streamed == _messages(client, headers, cid)[-1]["text"]
    assert _answer(streamed) == "今晚可以吃清蒸鱼配米饭，清淡又有蛋白质。"
    assert "很下饭" not in streamed and done["evidence"] not in streamed
    assert NOTICE_HEADER.format(foods="麻婆豆腐") in streamed


def test_every_non_risk_answer_ends_with_the_health_disclaimer(client, scripted):
    headers = ready_user(client, "hugo", FULL_PROFILE)
    connect(client, headers)
    scripted.add(say("你好呀，有什么可以帮你？"))
    body = _send(client, headers, _conversation(client, headers), "你好")
    assert body["tools_used"] == [] and body["evidence"] == ""
    assert body["text"] == "你好呀，有什么可以帮你？\n\n" + HEALTH_DISCLAIMER


def test_large_tool_results_are_truncated_to_a_valid_json_summary(client, scripted, monkeypatch):
    headers = ready_user(client, "tara", FULL_PROFILE)
    connect(client, headers)
    big = {"ok": True, "data": ["米饭" * 50] * 200}
    monkeypatch.setattr(loop, "_execute", lambda *args: big)
    cid = _conversation(client, headers)
    scripted.add(call("nutrition_list_meals", {"day": "2026-10-07"}), say("今天还没记。"))
    _send(client, headers, cid, "今天吃了什么")
    [result] = _tool_results(scripted.requests[1])
    summary = json.loads(result)
    full = json.dumps(big, ensure_ascii=False)
    assert summary == {"truncated": True, "preview": full[:TOOL_RESULT_PREVIEW_CHARS]}
    scripted.add(say("好的。"))
    _send(client, headers, cid, "谢谢")
    assert _tool_results(scripted.requests[-1]) == [result]  # 保存与回放的也是截断后的


def test_bound_tool_result():
    small = json.dumps({"ok": True, "data": "米饭"}, ensure_ascii=False)
    assert bound_tool_result(small) == small
    edge = "x" * MAX_TOOL_RESULT_BYTES
    assert bound_tool_result(edge) == edge
    over = "饭" * (MAX_TOOL_RESULT_BYTES // 3 + 1)  # 字数不到上限，但按 UTF-8 字节超过
    assert json.loads(bound_tool_result(over)) == {"truncated": True, "preview": over[:TOOL_RESULT_PREVIEW_CHARS]}
    assert MAX_TOOL_RESULT_BYTES == 8 * 1024


def test_non_streaming_returns_json(client, scripted):
    headers = ready_user(client, "olga", FULL_PROFILE)
    connect(client, headers)
    scripted.add(say("晚饭可以吃清蒸鱼。"))
    response = _post(client, headers, _conversation(client, headers), "晚饭吃什么")
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert set(body) == {"message_id", "text", "evidence", "flags", "tools_used"}
    uuid.UUID(body["message_id"])


@pytest.mark.parametrize("text", ["", "   ", "字" * 2001])
def test_message_text_is_validated(client, text):
    headers = ready_user(client, "pete", FULL_PROFILE)
    response = _post(client, headers, _conversation(client, headers), text)
    assert response.status_code == 422


def test_extra_fields_are_rejected(client):
    headers = ready_user(client, "pete", FULL_PROFILE)
    cid = _conversation(client, headers)
    response = client.post(f"/api/agent/conversations/{cid}/messages", json={"text": "你好", "user_id": "x"},
                           headers=headers)
    assert response.status_code == 422


# ---------- 错误 ----------


def test_unconfigured_model_is_reported(client, scripted):
    headers = ready_user(client, "quin", FULL_PROFILE)
    cid = _conversation(client, headers)
    response = _post(client, headers, cid, "晚饭吃什么")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "agent_model_not_configured"
    assert "设置页" in response.json()["error"]["message"]

    response = _post(client, headers, cid, "晚饭吃什么", stream=True)
    assert response.status_code == 409
    [(event, data)] = _events(response)
    assert event == "error" and data["code"] == "agent_model_not_configured"
    assert [m["text"] for m in _messages(client, headers, cid)] == ["晚饭吃什么", "晚饭吃什么"]


def test_someone_elses_conversation_is_404(client, scripted):
    owner = ready_user(client, "rita", FULL_PROFILE)
    other = ready_user(client, "sam", FULL_PROFILE)
    connect(client, other)
    cid = _conversation(client, owner)
    for stream in (False, True):
        response = _post(client, other, cid, "晚饭吃什么", stream=stream)
        assert response.status_code == 404
    assert scripted.requests == []
    assert _messages(client, owner, cid) == []


def test_model_errors_are_readable_and_keep_the_user_message(client, scripted):
    headers = ready_user(client, "tina", FULL_PROFILE)
    connect(client, headers)
    cid = _conversation(client, headers)
    scripted.add(fail(500))
    response = _post(client, headers, cid, "晚饭吃什么")
    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "agent_model_error" and error["message"].startswith("模型调用失败")
    assert [m["role"] for m in _messages(client, headers, cid)] == ["user"]


def _mark_chat_model(client, headers, **overrides):
    assignment = next(a for a in client.get("/api/llm/assignments", headers=headers).json() if a["purpose"] == "chat")
    response = client.patch(f"/api/llm/models/{assignment['model']['id']}", json=overrides, headers=headers)
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(("overrides", "code"), [({"tools": False}, "llm_model_lacks_tools"),
                                                 ({"chat": False}, "llm_model_not_chat")])
def test_model_configuration_errors_keep_their_own_status_and_code(client, scripted, overrides, code):
    headers = ready_user(client, "cora", FULL_PROFILE)
    connect(client, headers)
    _mark_chat_model(client, headers, **overrides)
    cid = _conversation(client, headers)
    response = _post(client, headers, cid, "晚饭吃什么")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
    response = _post(client, headers, cid, "晚饭吃什么", stream=True)
    assert response.status_code == 422
    [(event, data)] = _events(response)
    assert event == "error" and data["code"] == code
    assert scripted.requests == []


def test_tool_limit_stops_the_loop_and_keeps_history_replayable(client, scripted):
    headers = ready_user(client, "uma", FULL_PROFILE)
    connect(client, headers)
    cid = _conversation(client, headers)
    scripted.add(*[call("nutrition_search_foods", {"query": "米饭"})] * MAX_MODEL_CALLS)
    body = _send(client, headers, cid, "晚饭吃什么")
    assert len(scripted.requests) == MAX_MODEL_CALLS
    assert body["flags"] == ["tool_limit"]
    assert _answer(body["text"]) == TOOL_LIMIT_REPLY

    scripted.add(say("好的。"))
    _send(client, headers, cid, "那就算了")
    messages = scripted.requests[-1].messages
    calls = [m for m in messages if m.get("tool_calls")]
    assert len(calls) == MAX_MODEL_CALLS - 1
    for index, message in enumerate(messages):
        if message.get("tool_calls"):
            ids = [c["id"] for c in message["tool_calls"]]
            following = [m["tool_call_id"] for m in messages[index + 1:index + 1 + len(ids)]]
            assert following == ids


def test_router_ends_its_read_transaction_before_the_turn(client, scripted):
    def tracked_db():
        session = get_sessionmaker()()
        scripted.sessions.append(session)
        try:
            yield session
        finally:
            session.close()

    client.app.dependency_overrides[get_db] = tracked_db
    headers = ready_user(client, "vera", FULL_PROFILE)
    connect(client, headers)
    scripted.add(call("nutrition_search_foods", {"query": "米饭"}), say("可以吃米饭。"))
    _send(client, headers, _conversation(client, headers), "晚饭吃什么")
    assert scripted.in_transaction == [False, False]


# ---------- 历史 ----------


def test_provider_state_is_replayed_only_to_the_same_model(client, scripted):
    headers = ready_user(client, "will", FULL_PROFILE)
    connect(client, headers)
    cid = _conversation(client, headers)
    scripted.add(call("nutrition_search_foods", {"query": "米饭"}, reasoning="思考过程A"), say("可以吃米饭。"))
    _send(client, headers, cid, "米饭能吃吗")
    assert "思考过程A" in scripted.requests[1].text()

    scripted.add(say("好的。"))
    _send(client, headers, cid, "谢谢")
    assert "思考过程A" in scripted.requests[-1].text()

    connect(client, headers, model_id="qwen-max")
    scripted.add(say("好的。"))
    _send(client, headers, cid, "再见")
    assert scripted.requests[-1].model == "qwen-max"
    assert "思考过程A" not in scripted.requests[-1].text()
    assert len(_tool_results(scripted.requests[-1])) == 1


def test_gemini_history_replays_to_claude_with_unique_tool_ids(client, scripted):
    headers = ready_user(client, "xena", FULL_PROFILE)
    cid = _conversation(client, headers)
    with get_sessionmaker()() as db:
        uid = db.scalar(select(User.id).where(User.username == "xena"))
        gemini_step = {"text": "", "provider_state": None, "model": "gemini-2.5-flash", "provider_kind": "gemini",
                       "tool_calls": [{"name": "nutrition_search_foods", "arguments": {"query": "米饭"},
                                       "call_id": "gemini-call-1", "provider_state": {"thoughtSignature": "SIG"}}]}
        result = {"text": "{}", "tool_call_id": "gemini-call-1", "tool_name": "nutrition_search_foods"}
        for role, content in [("user", {"text": "米饭能吃吗"}), ("assistant", gemini_step), ("tool", result),
                              ("assistant", gemini_step), ("tool", result),
                              ("assistant", {"text": "可以吃。", "answer": "可以吃。"})]:
            conversations.append_message(db, uid, uuid.UUID(cid), role, content)
    connect(client, headers, "anthropic")
    scripted.add(say("好的。"))
    _send(client, headers, cid, "谢谢")
    [request] = scripted.requests
    assert request.kind == "anthropic" and "SIG" not in request.text()
    uses = [b["id"] for m in request.messages if isinstance(m["content"], list)
            for b in m["content"] if b["type"] == "tool_use"]
    results = [b["tool_use_id"] for m in request.messages if isinstance(m["content"], list)
               for b in m["content"] if b["type"] == "tool_result"]
    assert len(uses) == 2 and len(set(uses)) == 2 and uses == results
    assert all(re.fullmatch(r"[A-Za-z0-9_-]+", call_id) for call_id in uses)


def _target(kind="openai_compatible", model_id="m1"):
    return ResolvedTarget(kind=kind, base_url="http://127.0.0.1:9", api_key="k", model_id=model_id,
                          provider_name="p", model_pk=uuid.uuid4(), capabilities=Capabilities())


def _calls(*ids, model="m1"):
    return ("assistant", {"text": "", "model": model, "provider_kind": "openai_compatible", "provider_state": {"s": 1},
                          "tool_calls": [{"name": "t", "arguments": {}, "call_id": i, "provider_state": None}
                                         for i in ids]})


def _result(call_id):
    return ("tool", {"text": "{}", "tool_call_id": call_id, "tool_name": "t"})


def test_replayable_drops_the_unreplayable_parts():
    saved = [
        _result("a"),  # 窗口从工具结果开始
        _calls("b"), _result("b"),  # 窗口开头的工具往返（在第一条用户消息之前）
        ("assistant", {"text": "上一轮的回答"}),
        ("user", {"text": "第一问"}),
        _calls("c", "d"), _result("c"),  # 没有配齐
        _result("e"),  # 孤立的工具结果
        _calls("f", "f2"), _result("f2"), _result("f"),  # 配齐（顺序不同也算）
        ("assistant", {"text": ""}),
        ("assistant", {"text": "回答"}),
        ("user", {"text": "第二问"}),
    ]
    out = replayable(saved, _target())
    assert [(m.role, m.text, m.tool_call_id) for m in out] == [
        ("user", "第一问", None), ("assistant", "", None), ("tool", "{}", "f2"), ("tool", "{}", "f"),
        ("assistant", "回答", None), ("user", "第二问", None)]
    assert out[1].provider_state == {"s": 1}
    assert [c.call_id for c in out[1].tool_calls] == ["f", "f2"]
    other = replayable(saved, _target(model_id="m2"))
    assert other[1].provider_state is None
    assert [c.call_id for c in other[1].tool_calls] == ["h2_1", "h2_2"]  # 换了模型：重新编号，结果跟着改
    assert [m.tool_call_id for m in other[2:4]] == ["h2_2", "h2_1"]
    assert replayable(saved + [_calls("g", "g"), _result("g"), _result("g")], _target())[-1].role == "user"  # 同一回复里编号重复：整组丢掉
    assert replayable(saved, _target(kind="anthropic"))[1].provider_state is None


def test_replayable_replaces_risky_turns_with_placeholders():
    saved = [
        ("user", {"text": "晚饭吃什么"}),
        ("assistant", {"text": "清蒸鱼。", "answer": "清蒸鱼。", "flags": []}),
        ("user", {"text": "我想把降压药减半"}),
        ("assistant", {"text": SAFE_REPLIES["medication"], "flags": ["risk_medication"]}),
        ("user", {"text": "那减半会怎样"}),
    ]
    out = replayable(saved, _target())
    assert [(m.role, m.text) for m in out] == [
        ("user", "晚饭吃什么"), ("assistant", "清蒸鱼。"), ("user", RISK_USER_PLACEHOLDER),
        ("assistant", SAFE_REPLIES["medication"]), ("user", "那减半会怎样")]
