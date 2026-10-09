"""对话循环与聊天接口：全部经接口、固定今天、模型由 ScriptedModel 模拟，绝不访问真实网络。"""

import json
import re
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agent.assembly import RISK_FOLLOW_UP
from app.agent.guard import FALLBACK_UNCHECKED, NOTICE_HEADER, REWRITE_INSTRUCTION, safe_fallback
from app.agent.loop import (
    CHINESE_ONLY,
    LATIN_INSTRUCTION,
    MAX_EVALUATED_FOODS,
    MAX_MODEL_CALLS,
    MAX_TOOL_RESULT_BYTES,
    RISK_USER_PLACEHOLDER,
    TOOL_LIMIT_REPLY,
    TOOL_RESULT_PREVIEW_CHARS,
    UNKNOWN_FOODS_INSTRUCTION,
    UNKNOWN_TOOL_MESSAGE,
    bound_tool_result,
    replayable,
    strip_self_evidence,
)
from app.agent import conversations, loop
from app.agent.guard import mentioned_food_ids
from app.auth.models import User
from app.sdk import GoodLife, SdkError
from app.agent.safety import HEALTH_DISCLAIMER, SAFE_REPLIES
from app.agent_grants.models import SdkCallAudit
from app.common.clock import get_today
from app.db import get_db, get_sessionmaker
from app.llm.adapters.base import sanitize_schema_for_gemini
from app.llm.capabilities import Capabilities
from app.llm.service import ResolvedTarget
from app.main import create_app
from app.nutrition.catalog import load_catalog
from app.nutrition.engine import SOURCE_NAMES
from app.sdk.tooling import agent_registry
from tests.agent_fake import call, connect, echo, fail, say, scripted  # noqa: F401
from tests.helpers import ready_user

TODAY = date(2026, 10, 7)
MAPO = "dish:mapo_tofu"
STEAMED_FISH = "dish:steamed_fish"
RICE = load_catalog().common_aliases["米饭"]
NO_SPICY = "一周内忌食辛辣。"
FULL_PROFILE = {"gender": "male", "birth_year": 1990, "height_cm": 175, "weight_kg": 70, "activity_level": "moderate"}
PERIODS = [
    ("2026-06-01", "2026-06-05"),
    ("2026-06-29", "2026-07-03"),
    ("2026-07-27", "2026-07-31"),
    ("2026-08-24", "2026-08-28"),
    ("2026-09-21", "2026-09-25"),
]
CLUE_HINT = "只能用 medical_propose_resolution 提出解除建议"


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as test_client:
        yield test_client


# ---------- 辅助 ----------


def _conversation(client, headers) -> str:
    response = client.post("/api/agent/conversations", json={}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _post(client, headers, cid, text, stream=False):
    return client.post(f"/api/agent/conversations/{cid}/messages", json={"text": text, "stream": stream},
                       headers=headers)


def _send(client, headers, cid, text) -> dict:
    response = _post(client, headers, cid, text)
    assert response.status_code == 200, response.text
    return response.json()


def _events(response) -> list[tuple[str, dict]]:
    events = []
    for block in response.text.split("\n\n"):
        if not block.strip():
            continue
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def _messages(client, headers, cid) -> list[dict]:
    response = client.get(f"/api/agent/conversations/{cid}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["messages"]


def _no_spicy_user(client, username, profile=None):
    headers = ready_user(client, username, profile or {"gender": "male"})
    order = client.post("/api/medical/orders", json={"text": NO_SPICY}, headers=headers)
    assert order.status_code == 201, order.text
    for item in order.json()["items"]:
        assert client.post(f"/api/medical/items/{item['id']}/confirm", headers=headers).status_code == 200
    constraints = client.get("/api/medical/constraints", headers=headers).json()["constraints"]
    assert constraints
    return headers, constraints


def _cycle_user(client, username):
    headers = ready_user(client, username, {"gender": "female"})
    for start, end in PERIODS:
        response = client.post("/api/cycle/periods", json={"start_date": start, "end_date": end}, headers=headers)
        assert response.status_code == 201, response.text
    return headers


def _engine(client, headers, food_id) -> dict:
    response = client.post("/api/nutrition/evaluate", json={"food_id": food_id}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _answer(text: str) -> str:
    """最终文本里模型回答的部分（程序附上的提醒、依据与健康提示之前）。"""
    return text.split("\n\n")[0]


def _assert_evidence_from_engine(client, headers, evidence: str, food_ids: list[str]) -> None:
    """依据段按顺序每行对应一种食物，每条说明都能在引擎对这种食物的判断里逐字找到。"""
    lines = evidence.split("\n")
    assert len(lines) == len(food_ids)
    for line, food_id in zip(lines, food_ids, strict=True):
        engine = _engine(client, headers, food_id)
        assert line.startswith(f"{engine['food_name']}：")
        pieces = re.findall(r"【([^】]+)】([^【]*)", line)
        assert pieces or "依据" not in line
        allowed = {(SOURCE_NAMES[r["source"]], r["message"]) for r in engine["reasons"]}
        if engine["tradeoff"]:
            allowed.add(("权衡", engine["tradeoff"]))
        for piece in pieces:
            assert piece in allowed, (line, piece)


def _tool_results(recorded) -> list[str]:
    """一次请求里的全部工具结果正文（两种格式）。"""
    results = []
    for message in recorded.messages:
        if recorded.kind == "openai_compatible" and message["role"] == "tool":
            results.append(message["content"])
        if recorded.kind == "anthropic" and isinstance(message["content"], list):
            results += [b["content"] for b in message["content"] if b["type"] == "tool_result"]
    return results


def _object_nodes_without_properties(node, path="$"):
    found = []
    if isinstance(node, dict):
        if node.get("type") == "object" and path != "$" and not node.get("properties"):
            found.append(path)
        for key, value in node.items():
            found += _object_nodes_without_properties(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found += _object_nodes_without_properties(value, f"{path}[{index}]")
    return found


# ---------- 工具往返与依据 ----------


def test_tool_round_trip_appends_engine_evidence_and_is_audited_as_agent(client, scripted):
    headers = ready_user(client, "alice", FULL_PROFILE)
    connect(client, headers)
    cid = _conversation(client, headers)
    scripted.add(
        call("nutrition_search_foods", {"query": "清蒸鱼"}),
        call("nutrition_evaluate_food", {"food_id": STEAMED_FISH}),
        say("晚饭可以吃清蒸鱼，清淡又有蛋白质。"),
    )
    body = _send(client, headers, cid, "晚饭吃清蒸鱼行吗")

    assert len(scripted.requests) == 3
    assert all(r.model == "deepseek-chat" for r in scripted.requests)
    first_results, second_results = _tool_results(scripted.requests[1]), _tool_results(scripted.requests[2])
    assert len(first_results) == 1 and STEAMED_FISH in first_results[0] and '"ok": true' in first_results[0]
    assert len(second_results) == 2 and '"conclusion"' in second_results[1]
    assert body["tools_used"] == ["nutrition_search_foods", "nutrition_evaluate_food"]
    assert body["flags"] == []
    assert _answer(body["text"]) == "晚饭可以吃清蒸鱼，清淡又有蛋白质。"
    assert body["evidence"] and body["evidence"] not in body["text"] and "依据" not in body["text"]
    _assert_evidence_from_engine(client, headers, body["evidence"], [STEAMED_FISH])
    assert body["text"].endswith(HEALTH_DISCLAIMER)

    with get_sessionmaker()() as db:
        audits = db.scalars(select(SdkCallAudit).where(SdkCallAudit.client_name == "agent")).all()
    capabilities = {a.capability for a in audits}
    assert {"nutrition.search_foods", "nutrition.evaluate_food", "medical.get_constraints"} <= capabilities
    assert {a.credential_kind for a in audits} == {"agent"}

    shown = _messages(client, headers, cid)
    assert [(m["role"], m["text"]) for m in shown] == [("user", "晚饭吃清蒸鱼行吗"), ("assistant", body["text"])]
    assert shown[1]["evidence"] == body["evidence"] and shown[0]["evidence"] == ""

    # 下一轮回放上一轮：工具往返原样带上，回答只回放模型那部分，不带程序附上的依据与健康提示
    scripted.add(say("好的。"))
    _send(client, headers, cid, "谢谢")
    replayed = scripted.requests[-1].messages
    assert [m["role"] for m in replayed] == [
        "system", "user", "assistant", "tool", "assistant", "tool", "assistant", "user"]
    assert replayed[-2]["content"] == "晚饭可以吃清蒸鱼，清淡又有蛋白质。"


def test_tool_declarations_are_agent_tools_and_safe_for_gemini(client, scripted):
    headers = _cycle_user(client, "gwen")
    exercise = client.get("/api/fitness/exercises/search", params={"q": "卧推"}, headers=headers).json()
    workout = {"performed_on": "2026-10-07", "duration_minutes": 60, "rpe": 7,
               "strength": [{"exercise_id": exercise["results"][0]["id"], "sets": [{"weight_kg": 30, "reps": 8}]}]}
    assert client.post("/api/fitness/workouts", json=workout, headers=headers).status_code == 201
    connect(client, headers)
    _send(client, headers, _conversation(client, headers), "今天练完吃什么")
    tools = scripted.requests[0].tools
    assert len(tools) == len(agent_registry()) + 1 and tools[-1]["name"] == "remember_preference"
    for tool in tools:
        assert _object_nodes_without_properties(sanitize_schema_for_gemini(tool["parameters"])) == [], tool["name"]


# ---------- 验收第 2 条：输出检查 ----------


def test_blocked_recommendation_is_rewritten(client, scripted):
    headers, _ = _no_spicy_user(client, "bob")
    connect(client, headers)
    cid = _conversation(client, headers)
    scripted.add(say("今晚推荐麻婆豆腐，很下饭。"), say("今晚可以吃清蒸鱼配米饭。"))
    body = _send(client, headers, cid, "晚饭吃什么")

    assert len(scripted.requests) == 2
    rewrite = scripted.requests[1]
    assert rewrite.tools == [] and "tools" not in rewrite.body
    assert REWRITE_INSTRUCTION.split("\n")[0] in rewrite.messages[-1]["content"]
    assert "麻婆豆腐" in rewrite.messages[-1]["content"]
    assert body["flags"] == ["guard_rewritten"]
    assert _answer(body["text"]) == "今晚可以吃清蒸鱼配米饭。"
    assert NOTICE_HEADER.format(foods="麻婆豆腐") in body["text"]
    assert "麻婆豆腐" not in body["evidence"]
    _assert_evidence_from_engine(client, headers, body["evidence"], [STEAMED_FISH, RICE])
    assert body["text"].endswith(HEALTH_DISCLAIMER)


def test_blocked_recommendation_falls_back_when_the_rewrite_still_mentions_it(client, scripted):
    headers, _ = _no_spicy_user(client, "bob")
    connect(client, headers)
    scripted.add(say("今晚推荐麻婆豆腐，很下饭。"), say("还是麻·婆·豆·腐最好。"))
    body = _send(client, headers, _conversation(client, headers), "晚饭吃什么")
    assert body["flags"] == ["guard_fallback"]
    assert _answer(body["text"]) == safe_fallback(["麻婆豆腐"], [])
    assert NOTICE_HEADER.format(foods="麻婆豆腐") in body["text"]
    assert body["evidence"] == ""
    assert "很下饭" not in body["text"] and "最好" not in body["text"]


def test_overlapping_names_are_evaluated_too(client, scripted):
    headers, _ = _no_spicy_user(client, "bob")
    connect(client, headers)
    scripted.add(say("来一份回锅肉丝炒面吧。"), say("来一份清蒸鱼吧。"))
    body = _send(client, headers, _conversation(client, headers), "晚饭吃什么")
    assert body["flags"] == ["guard_rewritten"]
    assert "回锅肉" in scripted.requests[1].messages[-1]["content"]


def test_a_blocked_food_named_by_the_user_gets_the_program_notice(client, scripted):
    headers, _ = _no_spicy_user(client, "bob")
    connect(client, headers)
    scripted.add(say("这几天先换成清蒸鱼吧。"))
    body = _send(client, headers, _conversation(client, headers), "我能吃麻婆豆腐吗")
    assert len(scripted.requests) == 1 and body["flags"] == []
    assert _answer(body["text"]) == "这几天先换成清蒸鱼吧。"
    assert NOTICE_HEADER.format(foods="麻婆豆腐") in body["text"]
    engine = _engine(client, headers, MAPO)
    medical = [r["message"] for r in engine["reasons"] if r["source"] == "medical" and r["effect"] == "block"]
    assert medical and all(message in body["text"] for message in medical)


def test_latin_answer_is_rewritten_in_chinese_for_users_with_diet_orders(client, scripted):
    headers, _ = _no_spicy_user(client, "bob")
    connect(client, headers)
    scripted.add(say("Tonight try mapo tofu, it goes great with rice."), say("今晚可以吃清蒸鱼。"))
    body = _send(client, headers, _conversation(client, headers), "晚饭吃什么")
    assert scripted.requests[1].messages[-1]["content"] == LATIN_INSTRUCTION
    assert body["flags"] == ["guard_rewritten"] and _answer(body["text"]) == "今晚可以吃清蒸鱼。"

    scripted.add(say("今晚推荐 Mapo Tofu，配一碗麻婆豆腐。"), say("今晚可以吃清蒸鱼。"))
    body = _send(client, headers, _conversation(client, headers), "晚饭吃什么")
    instruction = scripted.requests[3].messages[-1]["content"]
    assert instruction.endswith(CHINESE_ONLY) and "麻婆豆腐" in instruction


def test_latin_answer_is_kept_for_users_without_diet_orders(client, scripted):
    headers = ready_user(client, "carl", FULL_PROFILE)
    connect(client, headers)
    scripted.add(say("Tonight try steamed fish, light and healthy."))
    body = _send(client, headers, _conversation(client, headers), "晚饭吃什么")
    assert len(scripted.requests) == 1 and body["flags"] == []
    assert _answer(body["text"]) == "Tonight try steamed fish, light and healthy."


def test_the_rewrite_does_not_count_toward_the_tool_loop_cap(client, scripted):
    headers, _ = _no_spicy_user(client, "bob")
    connect(client, headers)
    scripted.add(*[call("nutrition_search_foods", {"query": "豆腐"})] * (MAX_MODEL_CALLS - 1),
                 say("推荐麻婆豆腐。"), say("推荐清蒸鱼。"))
    body = _send(client, headers, _conversation(client, headers), "晚饭吃什么")
    assert len(scripted.requests) == MAX_MODEL_CALLS + 1
    assert scripted.requests[-1].tools == []
    assert body["flags"] == ["guard_rewritten"]
    assert _answer(body["text"]) == "推荐清蒸鱼。"


def _fail_evaluations(monkeypatch, food_id):
    """让循环（客户端名 agent）对某个食物的引擎判断失败。"""
    original = GoodLife.call

    def failing(self, credential, capability, params=None, *, client_name="sdk"):
        if capability == "nutrition.evaluate_food" and (params or {}).get("food_id") == food_id:
            raise SdkError("internal", "internal_error", "服务内部出错")
        return original(self, credential, capability, params, client_name=client_name)

    monkeypatch.setattr(GoodLife, "call", failing)


def test_unevaluated_foods_fail_closed_for_users_with_diet_orders(client, scripted, monkeypatch):
    headers, _ = _no_spicy_user(client, "bob")
    connect(client, headers)
    _fail_evaluations(monkeypatch, STEAMED_FISH)
    scripted.add(say("今晚吃清蒸鱼。"), say("今晚吃米饭配番茄炒蛋。"))
    body = _send(client, headers, _conversation(client, headers), "晚饭吃什么")
    instruction = scripted.requests[1].messages[-1]["content"]
    assert instruction == UNKNOWN_FOODS_INSTRUCTION.format(foods="清蒸鱼")
    assert body["flags"] == ["guard_rewritten"] and _answer(body["text"]) == "今晚吃米饭配番茄炒蛋。"

    scripted.add(say("今晚吃清蒸鱼。"), say("还是清蒸鱼吧。"))
    body = _send(client, headers, _conversation(client, headers), "晚饭吃什么")
    assert body["flags"] == ["guard_fallback"]
    # 没能核对的食物不说成“医嘱不建议”，单独一句
    assert _answer(body["text"]) == safe_fallback([], ["清蒸鱼"])
    assert _answer(body["text"]).startswith(FALLBACK_UNCHECKED.format(foods="清蒸鱼"))
    assert "不建议" not in body["text"]


def test_fallback_lists_blocked_and_unchecked_foods_in_separate_sentences(client, scripted, monkeypatch):
    headers, _ = _no_spicy_user(client, "bob")
    connect(client, headers)
    _fail_evaluations(monkeypatch, STEAMED_FISH)
    scripted.add(say("今晚吃麻婆豆腐和清蒸鱼。"), say("还是麻婆豆腐配清蒸鱼。"))
    body = _send(client, headers, _conversation(client, headers), "晚饭吃什么")
    assert body["flags"] == ["guard_fallback"]
    assert _answer(body["text"]) == safe_fallback(["麻婆豆腐"], ["清蒸鱼"])
    assert _answer(body["text"]) == (
        "根据你当前生效的医嘱，下面这些食物不建议吃：麻婆豆腐。"
        "以下食物暂时没能按医嘱核对，请先别吃或稍后再问：清蒸鱼。"
        "如果想换别的，可以告诉我你的口味，我再按医嘱帮你挑。")


def test_unevaluated_foods_pass_for_users_without_diet_orders(client, scripted, monkeypatch):
    headers = ready_user(client, "carl", FULL_PROFILE)
    connect(client, headers)
    _fail_evaluations(monkeypatch, STEAMED_FISH)
    scripted.add(say("今晚吃清蒸鱼。"))
    body = _send(client, headers, _conversation(client, headers), "晚饭吃什么")
    assert len(scripted.requests) == 1 and body["flags"] == []
    assert body["evidence"] == ""


def test_foods_evaluated_per_turn_are_capped(client, scripted):
    headers = ready_user(client, "carl", FULL_PROFILE)
    connect(client, headers)
    dishes = [food.name for food in load_catalog().foods.values() if food.id.startswith("dish:")][:30]
    answer = "可以从这些里挑：" + "、".join(dishes) + "。"
    assert len(mentioned_food_ids(answer)) > MAX_EVALUATED_FOODS
    scripted.add(say(answer))
    _send(client, headers, _conversation(client, headers), "晚饭吃什么")
    with get_sessionmaker()() as db:
        evaluated = db.scalars(select(SdkCallAudit).where(
            SdkCallAudit.client_name == "agent", SdkCallAudit.capability == "nutrition.evaluate_food")).all()
    assert len(evaluated) == MAX_EVALUATED_FOODS


def test_capability_errors_go_back_to_the_model_as_structured_results(client, scripted):
    headers = ready_user(client, "carl", FULL_PROFILE)
    connect(client, headers)
    scripted.add(call("nutrition_evaluate_food", {"food_id": "no-such-food"}), say("没找到这种食物。"))
    body = _send(client, headers, _conversation(client, headers), "这个能吃吗")
    [result] = _tool_results(scripted.requests[1])
    error = json.loads(result)
    assert error["ok"] is False and error["error"]["kind"] == "not_found"
    assert {"code", "message", "hint"} <= set(error["error"])
    assert body["tools_used"] == ["nutrition_evaluate_food"]


# ---------- 验收第 3 条：医嘱线索 ----------


def test_resolution_clue_only_proposes_and_confirm_tool_does_not_exist(client, scripted):
    headers, constraints = _no_spicy_user(client, "dora")
    item_id = constraints[0]["item_id"]
    connect(client, headers)
    scripted.add(
        call("medical_propose_resolution", {"item_id": item_id, "reason": "医生复查后说可以恢复正常饮食"}),
        call("medical_confirm_item", {"item_id": item_id}),
        say("已经帮你提出解除建议，需要你在应用里确认后才会解除。"),
    )
    body = _send(client, headers, _conversation(client, headers), "医生说我已经好了，可以吃辣了")

    first = scripted.requests[0]
    assert CLUE_HINT in first.system
    assert "medical_propose_resolution" in first.tool_names
    assert "medical_confirm_item" not in first.tool_names
    assert "resolution_clue" in body["flags"]
    assert body["tools_used"] == ["medical_propose_resolution"]
    [refused] = _tool_results(scripted.requests[2])[-1:]
    assert UNKNOWN_TOOL_MESSAGE in refused and '"ok": false' in refused

    item = client.get(f"/api/medical/items/{item_id}", headers=headers).json()
    assert item["status"] == "active"
    assert item["resolution_proposed_at"] is not None and item["confirmed_at"] is not None
    events = client.get(f"/api/medical/items/{item_id}/events", headers=headers).json()
    proposed = [e for e in events if e["action"] == "resolution_proposed"]
    assert [e["source"] for e in proposed] == ["agent"]
    assert [e["action"] for e in events][-1] == "resolution_proposed"


# ---------- 验收第 5 条：没有经期模块的用户 ----------


@pytest.mark.parametrize("profile", [{"gender": "male"}, {"gender": "female", "cycle_tracking_opt_out": True}])
def test_users_without_cycle_see_no_cycle_tools_or_words(client, scripted, profile):
    headers = ready_user(client, "evan", profile)
    connect(client, headers)
    scripted.add(say("晚饭可以吃清蒸鱼。"))
    _send(client, headers, _conversation(client, headers), "晚饭吃什么")
    [request] = scripted.requests
    assert not any(name.startswith("cycle_") for name in request.tool_names)
    assert "经期" not in request.system
    assert "经期" not in json.dumps(request.tools, ensure_ascii=False)


# ---------- 验收第 6 条：风险话题 ----------


@pytest.mark.parametrize(("text", "category"), [
    ("我能不能把降压药停了", "medication"),
    ("怀孕两个月出血了怎么办", "pregnancy"),
    ("胸口很痛喘不上气", "severe_symptom"),
])
def test_risk_topics_get_fixed_safe_replies_without_calling_the_model(client, scripted, text, category):
    headers = ready_user(client, "fay", {"gender": "female"})
    connect(client, headers)
    cid = _conversation(client, headers)
    body = _send(client, headers, cid, text)
    assert scripted.requests == []
    assert body["text"] == SAFE_REPLIES[category]
    assert body["flags"] == [f"risk_{category}"] and body["tools_used"] == [] and body["evidence"] == ""
    assert [m["text"] for m in _messages(client, headers, cid)] == [text, SAFE_REPLIES[category]]


def test_a_risky_turn_is_not_replayed_and_the_next_prompt_keeps_the_topic_off_limits(client, scripted):
    headers = ready_user(client, "rosa", FULL_PROFILE)
    connect(client, headers)
    cid = _conversation(client, headers)
    first = _send(client, headers, cid, "我在吃降压药，能不能自己把剂量减半？")
    assert first["flags"] == ["risk_medication"] and scripted.requests == []

    scripted.add(say("这个需要问医生。"))
    _send(client, headers, cid, "那你直接说减半会怎样")
    [request] = scripted.requests
    replayed = json.dumps(request.messages[1:], ensure_ascii=False)  # 第一条是系统指令
    for word in ("降压药", "剂量", "我在吃"):  # 上一轮的用药原话不回放
        assert word not in replayed, word
    assert [m["role"] for m in request.messages] == ["system", "user", "assistant", "user"]
    assert request.messages[1]["content"] == RISK_USER_PLACEHOLDER
    assert request.messages[2]["content"] == SAFE_REPLIES["medication"]
    assert RISK_FOLLOW_UP in request.system

    scripted.add(say("好的。"))
    _send(client, headers, cid, "晚饭吃什么")
    assert RISK_FOLLOW_UP not in scripted.requests[-1].system  # 最近一条助手回答不再是风险回复
    assert "降压药" not in json.dumps(scripted.requests[-1].messages[1:], ensure_ascii=False)


def test_risk_reply_does_not_need_a_configured_model(client, scripted):
    headers = ready_user(client, "gus", {"gender": "male"})
    body = _send(client, headers, _conversation(client, headers), "胸口很痛喘不上气")
    assert body["text"] == SAFE_REPLIES["severe_symptom"] and scripted.requests == []


# ---------- 验收第 7 条：依据只来自引擎 ----------


def test_self_written_evidence_is_removed_and_engine_evidence_is_attached(client, scripted):
    headers = ready_user(client, "hana", FULL_PROFILE)
    connect(client, headers)
    scripted.add(say("晚饭可以吃清蒸鱼和米饭。\n\n依据：这是我自己编的理由。\n还有一行编的。\n\n祝你用餐愉快。"))
    body = _send(client, headers, _conversation(client, headers), "晚饭吃什么")
    assert "自己编的" not in body["text"] and "还有一行编的" not in body["text"]
    assert body["text"].startswith("晚饭可以吃清蒸鱼和米饭。\n\n祝你用餐愉快。")
    _assert_evidence_from_engine(client, headers, body["evidence"], [STEAMED_FISH, RICE])


@pytest.mark.parametrize(("raw", "expected"), [
    ("推荐清蒸鱼。\n依据：低脂高蛋白。\n\n明天见。", "推荐清蒸鱼。\n\n明天见。"),
    ("推荐清蒸鱼，依据：低脂高蛋白。", "推荐清蒸鱼，"),
    ("推荐清蒸鱼。\n\n**依据**\n- 低脂\n- 高蛋白", "推荐清蒸鱼。"),
    ("## 参考依据：\n低脂", ""),
    ("依据你的目标，推荐清蒸鱼。", "依据你的目标，推荐清蒸鱼。"),
])
def test_strip_self_evidence(raw, expected):
    assert strip_self_evidence(raw) == expected


# ---------- 验收第 8 条：偏好记忆 ----------


def test_preferences_are_remembered_filtered_and_never_replace_orders(client, scripted):
    headers, constraints = _no_spicy_user(client, "ivan")
    connect(client, headers)
    cid = _conversation(client, headers)
    scripted.add(call("remember_preference", {"text": "喜欢吃辣"}), say("记住了。"))
    body = _send(client, headers, cid, "记住我喜欢吃辣")
    assert body["tools_used"] == ["remember_preference"]
    saved = client.get("/api/agent/preferences", headers=headers).json()
    assert [(p["content"], p["source"]) for p in saved] == [("喜欢吃辣", "agent")]

    scripted.add(call("remember_preference", {"text": "医生让我忌辣"}), say("这属于医嘱，不放进偏好。"))
    _send(client, headers, cid, "再记住医生让我忌辣")
    [rejected] = _tool_results(scripted.requests[-1])[-1:]
    assert "agent_preference_rejected" in rejected and '"ok": false' in rejected
    assert len(client.get("/api/agent/preferences", headers=headers).json()) == 1
    with get_sessionmaker()() as db:
        audits = db.scalars(select(SdkCallAudit).where(SdkCallAudit.capability == "agent.remember_preference")
                            .order_by(SdkCallAudit.created_at)).all()
    assert [(a.outcome, a.error_code, a.credential_kind, a.client_name) for a in audits] == [
        ("ok", None, "agent", "agent"), ("error", "agent_preference_rejected", "agent", "agent")]

    scripted.add(echo("【用户偏好"))
    body = _send(client, headers, _conversation(client, headers), "晚饭吃什么")
    system = scripted.requests[-1].system
    assert "喜欢吃辣" in system and constraints[0]["content"] in system
    assert "- 喜欢吃辣" in _answer(body["text"])

    pref_id = saved[0]["id"]
    assert client.delete(f"/api/agent/preferences/{pref_id}", headers=headers).status_code == 204
    scripted.add(say("晚饭可以吃清蒸鱼。"))
    _send(client, headers, _conversation(client, headers), "晚饭吃什么")
    system = scripted.requests[-1].system
    assert "喜欢吃辣" not in system and constraints[0]["content"] in system


# ---------- 验收第 9 条：换成 Claude 格式 ----------


def test_switching_to_a_claude_style_model_keeps_tools_and_guard_working(client, scripted):
    headers, _ = _no_spicy_user(client, "jill")
    connect(client, headers)
    cid = _conversation(client, headers)
    scripted.add(call("nutrition_search_foods", {"query": "清蒸鱼"}), say("可以吃清蒸鱼。"))
    _send(client, headers, cid, "清蒸鱼能吃吗")
    assert [r.kind for r in scripted.requests] == ["openai_compatible"] * 2

    connect(client, headers, "anthropic")
    scripted.add(
        call("nutrition_search_foods", {"query": "麻婆豆腐"}),
        call("nutrition_evaluate_food", {"food_id": MAPO}),
        say("今晚推荐麻婆豆腐。"),
        say("今晚吃清蒸鱼吧。"),
    )
    body = _send(client, headers, cid, "晚饭吃什么")
    claude = scripted.requests[2:]
    assert [r.kind for r in claude] == ["anthropic"] * 4
    assert all(r.model == "claude-sonnet-4-5" for r in claude)
    assert claude[0].system.startswith("你是 good-life 应用里的生活方式助手")
    assert len(_tool_results(claude[0])) == 1  # 上一轮的工具往返原样回放
    assert len(_tool_results(claude[2])) == 3 and '"conclusion"' in _tool_results(claude[2])[-1]
    assert "tools" not in claude[3].body
    assert body["flags"] == ["guard_rewritten"]
    assert body["tools_used"] == ["nutrition_search_foods", "nutrition_evaluate_food"]
    assert _answer(body["text"]) == "今晚吃清蒸鱼吧。"
    assert NOTICE_HEADER.format(foods="麻婆豆腐") in body["text"]
    _assert_evidence_from_engine(client, headers, body["evidence"], [STEAMED_FISH])


# ---------- 验收第 1 条（规则层面）：不同用户的装配 ----------


def test_different_users_get_different_prompts_and_tools(client, scripted):
    healthy = ready_user(client, "kate", FULL_PROFILE)
    ordered, constraints = _no_spicy_user(client, "liam")
    cycling = _cycle_user(client, "mona")
    for headers in (healthy, ordered, cycling):
        connect(client, headers)
        scripted.add(say("晚饭可以吃清蒸鱼。"))
        _send(client, headers, _conversation(client, headers), "晚饭吃什么")
    healthy_req, ordered_req, cycle_req = scripted.requests
    assert len({healthy_req.system, ordered_req.system, cycle_req.system}) == 3

    assert "目前没有生效的医嘱约束" in healthy_req.system and "经期" not in healthy_req.system
    assert all(c["content"] in ordered_req.system and c["item_id"] in ordered_req.system for c in constraints)
    assert "目前没有生效的医嘱约束" not in ordered_req.system
    assert "【经期阶段】" in cycle_req.system
    assert re.search(r"今天处于(月经期|卵泡期|排卵期|黄体期)", cycle_req.system)

    assert not any(n.startswith("cycle_") for n in healthy_req.tool_names + ordered_req.tool_names)
    assert {"cycle_get_phase", "cycle_get_tips"} <= set(cycle_req.tool_names)


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
