"""对话循环与聊天接口：全部经接口、固定今天、模型由 ScriptedModel 模拟，绝不访问真实网络。"""

import json
import re

import pytest
from sqlalchemy import select

from app.agent.assembly import RISK_FOLLOW_UP
from app.agent.guard import FALLBACK_UNCHECKED, NOTICE_HEADER, REWRITE_INSTRUCTION, safe_fallback
from app.agent.loop import (
    CHINESE_ONLY,
    LATIN_INSTRUCTION,
    MAX_EVALUATED_FOODS,
    MAX_MODEL_CALLS,
    RISK_USER_PLACEHOLDER,
    UNKNOWN_FOODS_INSTRUCTION,
    UNKNOWN_TOOL_MESSAGE,
    strip_self_evidence,
)
from app.agent import assembly
from app.agent.guard import mentioned_food_ids
from app.sdk import GoodLife, SdkError
from app.agent.safety import HEALTH_DISCLAIMER, SAFE_REPLIES
from app.agent_grants.models import SdkCallAudit
from app.db import get_sessionmaker
from app.llm.adapters.base import sanitize_schema_for_gemini
from app.nutrition.catalog import load_catalog
from app.sdk.tooling import agent_registry

from tests.agent_fake import call, connect, echo, say, scripted  # noqa: F401
from tests.helpers import ready_user
from tests.agent_loop_support import (
    CLUE_HINT,
    FULL_PROFILE,
    MAPO,
    RICE,
    STEAMED_FISH,
    _answer,
    _assert_evidence_from_engine,
    _conversation,
    _cycle_user,
    _engine,
    _messages,
    _no_spicy_user,
    _object_nodes_without_properties,
    _send,
    _tool_results,
    client,
)  # noqa: F401


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


def test_tool_declarations_are_agent_tools_and_safe_for_gemini(client, scripted, monkeypatch):
    monkeypatch.setattr(assembly, "amap_configured", lambda: True)  # 配置了高德密钥时附近餐厅也在内
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
