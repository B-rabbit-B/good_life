"""未成年人规则：不满 14 周岁不能建档、注册要确认年满 14 周岁、14 至 17 岁不估算能量也不按减脂目标给建议，
未成年用户问减重与热量时直接给固定回复。年份边界一律按今天现算。"""

import json
import uuid
from datetime import date

import pytest
from sqlalchemy import update

from app.agent import assembly
from app.agent.assembly import MINOR_INSTRUCTION, MINOR_INTAKE_LINE, UNAVAILABLE
from app.agent.loop import RISK_USER_PLACEHOLDER
from app.agent.safety import SAFE_REPLIES, classify_risk
from app.auth.schemas import AGE_CONFIRM_MESSAGE
from app.db import get_sessionmaker
from app.nutrition.engine import NEEDS_MINOR_MESSAGE
from app.nutrition.needs import MINOR_NOTE, estimate_needs
from app.profile.models import Profile
from app.profile.schemas import UNDER_AGE_MESSAGE
from tests.agent_fake import connect, say, scripted  # noqa: F401
from tests.helpers import ready_user

THIS_YEAR = date.today().year
FRIED_CHICKEN = "dish:fried_chicken"
WEIGHT_LOSS_QUESTION = "我想减肥，一天吃多少热量"
# app.agent.safety._MINOR_DIET 的词表（逐个核对，词表改了这里要一起改）
MINOR_DIET_WORDS = ("减肥", "减脂", "减重", "瘦身", "节食", "热量", "卡路里", "大卡", "千卡", "掉秤", "变瘦", "瘦下来", "控制体重",
                    "kcal", "想瘦", "怎么瘦")
# 未成年用户的常见说法：前一组由固定回复命中；后一组太常见、容易误伤（“少吃点辣”），只靠系统指令里的未成年一句
MINOR_CAUGHT = ("我想瘦十斤", "怎么瘦得快", "想瘦腿", "一碗饭多少kcal", "这个多少 KCAL")
MINOR_LEFT_TO_PROMPT = ("少吃点行不行", "晚饭少吃点", "想变苗条", "怎么让腿细一点")
# “瘦肉”不是减重：未成年与成年用户都不命中
LEAN_MEAT = ("怎么瘦肉炒更好吃", "想瘦肉粥了", "瘦肉怎么做")
NUMBER_FIELDS = (
    "energy_kcal", "energy_kcal_low", "energy_kcal_high", "protein_g", "fat_g_low", "fat_g_high", "carbohydrate_g_low",
    "carbohydrate_g_high", "fiber_g_low", "fiber_g_high", "sodium_mg_max",
)


def _profile(age: int, goal: str = "lose_fat") -> dict:
    return {"gender": "female", "birth_year": THIS_YEAR - age, "height_cm": 150, "weight_kg": 45,
            "activity_level": "light", "goal": goal}


def _details(response) -> dict[str, str]:
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    return {detail["field"]: detail["message"] for detail in error["details"]}


def _send(client, headers, text) -> dict:
    cid = client.post("/api/agent/conversations", json={}, headers=headers).json()["id"]
    return _send_to(client, headers, cid, text)


def _send_to(client, headers, cid, text) -> dict:
    response = client.post(f"/api/agent/conversations/{cid}/messages", json={"text": text, "stream": False},
                           headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_birth_year_under_14_is_refused_with_a_clear_message(client):
    headers = ready_user(client, "teen")
    refused = client.patch("/api/profile", json={"birth_year": THIS_YEAR - 13}, headers=headers)
    assert _details(refused) == {"birth_year": UNDER_AGE_MESSAGE}
    assert client.get("/api/profile", headers=headers).json()["birth_year"] is None
    accepted = client.patch("/api/profile", json={"birth_year": THIS_YEAR - 14}, headers=headers)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["birth_year"] == THIS_YEAR - 14


def test_birth_year_this_year_gets_the_under_age_message_not_the_future_one(client):
    headers = ready_user(client, "baby")
    refused = client.patch("/api/profile", json={"birth_year": THIS_YEAR}, headers=headers)
    assert _details(refused) == {"birth_year": UNDER_AGE_MESSAGE}
    future = client.patch("/api/profile", json={"birth_year": THIS_YEAR + 1}, headers=headers)
    assert _details(future) == {"birth_year": "出生年份不能晚于今年"}


def test_an_old_under_14_profile_can_still_change_other_fields_and_stays_minor(client):
    headers = ready_user(client, "old", _profile(30))
    user_id = uuid.UUID(client.get("/api/auth/me", headers=headers).json()["id"])
    with get_sessionmaker()() as db:  # 规则上线之前存下的旧档案：不满 14 周岁
        db.execute(update(Profile).where(Profile.user_id == user_id).values(birth_year=THIS_YEAR - 10))
        db.commit()
    changed = client.patch("/api/profile", json={"weight_kg": 46}, headers=headers)
    assert changed.status_code == 200, changed.text
    assert changed.json()["birth_year"] == THIS_YEAR - 10
    needs = client.get("/api/nutrition/summary", headers=headers).json()["needs"]
    assert needs["status"] == "minor" and needs["energy_kcal"] is None


def test_registration_requires_the_age_confirmation(client):
    missing = client.post("/api/auth/register", json={"username": "amy", "password": "secret-pass-1"})
    assert _details(missing) == {"age_confirmed": "这一项必须填写"}
    declined = client.post("/api/auth/register",
                           json={"username": "amy", "password": "secret-pass-1", "age_confirmed": False})
    assert _details(declined) == {"age_confirmed": AGE_CONFIRM_MESSAGE}
    confirmed = client.post("/api/auth/register",
                            json={"username": "amy", "password": "secret-pass-1", "age_confirmed": True})
    assert confirmed.status_code == 201, confirmed.text
    assert "age_confirmed" not in confirmed.json()


def test_needs_for_a_minor_have_no_energy_numbers():
    today = date.today()
    for age in (15, 17):
        needs = estimate_needs(gender="female", birth_year=THIS_YEAR - age, height_cm=150, weight_kg=45,
                               activity_level="light", goal="lose_fat", today=today)
        assert needs.status == "minor", age
        assert all(getattr(needs, name) is None for name in NUMBER_FIELDS), age
        assert needs.notes == (MINOR_NOTE,) and needs.missing_fields == ()
    adult = estimate_needs(gender="female", birth_year=THIS_YEAR - 18, height_cm=150, weight_kg=45,
                           activity_level="light", goal="lose_fat", today=today)
    assert adult.status == "ok" and adult.energy_kcal is not None
    assert MINOR_NOTE not in adult.notes


def test_minor_summary_and_evaluation_ignore_the_fat_loss_goal(client):
    headers = ready_user(client, "teen", _profile(15))
    summary = client.get("/api/nutrition/summary", headers=headers).json()
    assert summary["needs"]["status"] == "minor" and summary["remaining"] is None
    assert summary["needs"]["energy_kcal"] is None and summary["needs"]["notes"] == [MINOR_NOTE]
    minor = client.post("/api/nutrition/evaluate", json={"food_id": FRIED_CHICKEN}, headers=headers).json()
    assert [r for r in minor["reasons"] if r["source"] == "goal"] == []
    [intake] = [r for r in minor["reasons"] if r["source"] == "intake"]
    assert (intake["effect"], intake["code"], intake["message"], intake["ref"]) == (
        "info", "needs_minor", NEEDS_MINOR_MESSAGE, "needs")
    assert "不完整" not in intake["message"]

    adult_year = client.patch("/api/profile", json={"birth_year": THIS_YEAR - 30}, headers=headers)
    assert adult_year.status_code == 200, adult_year.text
    adult = client.post("/api/nutrition/evaluate", json={"food_id": FRIED_CHICKEN}, headers=headers).json()
    assert any(r["source"] == "goal" for r in adult["reasons"])
    assert client.get("/api/nutrition/summary", headers=headers).json()["needs"]["status"] == "ok"


def test_system_prompt_for_a_minor_has_the_minor_line_and_no_daily_needs(client, scripted):
    teen = ready_user(client, "teen", _profile(16))
    connect(client, teen)
    scripted.add(say("清蒸鱼配米饭。"))
    _send(client, teen, "晚饭吃什么")
    [request] = scripted.requests
    assert MINOR_INSTRUCTION in request.system and MINOR_INTAKE_LINE in request.system
    assert "估算的每日需求" not in request.system and "目标减脂" not in request.system
    safety = next(section for section in request.system.split("\n\n") if section.startswith("【安全边界】"))
    assert safety.splitlines()[-1] == f"- {MINOR_INSTRUCTION}"

    adult = ready_user(client, "adult", _profile(30))
    connect(client, adult)
    scripted.add(say("清蒸鱼配米饭。"))
    _send(client, adult, "晚饭吃什么")
    system = scripted.requests[-1].system
    assert "估算的每日需求" in system and "目标减脂" in system
    assert MINOR_INSTRUCTION not in system and MINOR_INTAKE_LINE not in system


def test_minor_line_falls_back_to_the_summary_when_the_profile_cannot_be_read(client, scripted, monkeypatch):
    teen = ready_user(client, "teen", _profile(16))
    connect(client, teen)

    def unreadable(data, today):
        raise RuntimeError("档案读取失败")

    monkeypatch.setattr(assembly, "_profile", unreadable)
    scripted.add(say("清蒸鱼配米饭。"))
    _send(client, teen, "晚饭吃什么")
    [request] = scripted.requests
    assert f"档案{UNAVAILABLE}" in request.system  # 档案确实没读到
    assert MINOR_INSTRUCTION in request.system and MINOR_INTAKE_LINE in request.system
    assert "估算的每日需求" not in request.system


@pytest.mark.parametrize("word", MINOR_DIET_WORDS)
def test_every_minor_diet_word_is_caught_only_for_minors(word):
    hit = classify_risk(word, minor=True)
    assert hit is not None and hit.category == "minor_weight_loss", word
    assert classify_risk(word, minor=False) is None, word


def test_common_minor_phrases_split_between_the_fixed_reply_and_the_system_prompt(client, scripted):
    for text in MINOR_CAUGHT:
        hit = classify_risk(text, minor=True)
        assert hit is not None and hit.category == "minor_weight_loss", text
        assert classify_risk(text, minor=False) is None, text
    for text in (*MINOR_LEFT_TO_PROMPT, *LEAN_MEAT):
        assert classify_risk(text, minor=True) is None, text
        assert classify_risk(text, minor=False) is None, text

    teen = ready_user(client, "teen", _profile(15))
    connect(client, teen)
    scripted.add(say("正在长身体，三餐吃好更重要。"))
    body = _send(client, teen, MINOR_LEFT_TO_PROMPT[0])
    [request] = scripted.requests  # 没命中固定回复的说法交给模型，靠系统指令里的未成年一句兜底
    assert MINOR_INSTRUCTION in request.system and body["flags"] == []


def test_minor_weight_loss_gets_the_fixed_reply_without_calling_the_model(client, scripted):
    teen = ready_user(client, "teen", _profile(15))
    connect(client, teen)
    body = _send(client, teen, WEIGHT_LOSS_QUESTION)
    assert body["text"] == SAFE_REPLIES["minor_weight_loss"]
    assert body["flags"] == ["risk_minor_weight_loss"] and body["tools_used"] == [] and body["evidence"] == ""
    assert scripted.requests == []

    unconfigured = ready_user(client, "teen2", _profile(17))  # 没有配置对话模型
    body = _send(client, unconfigured, WEIGHT_LOSS_QUESTION)
    assert body["text"] == SAFE_REPLIES["minor_weight_loss"] and body["flags"] == ["risk_minor_weight_loss"]
    assert scripted.requests == []


def test_adult_weight_loss_question_still_reaches_the_model(client, scripted):
    adult = ready_user(client, "adult", _profile(18))
    connect(client, adult)
    scripted.add(say("可以先记录几天饮食。"))
    body = _send(client, adult, WEIGHT_LOSS_QUESTION)
    assert len(scripted.requests) == 1
    assert body["flags"] == [] and body["text"].startswith("可以先记录几天饮食。")


def test_minor_rules_keep_the_other_categories_first(client, scripted):
    teen = ready_user(client, "teen", _profile(15))
    body = _send(client, teen, "想催吐减肥")
    assert body["flags"] == ["risk_extreme_diet"] and body["text"] == SAFE_REPLIES["extreme_diet"]
    assert scripted.requests == []


def test_minor_risk_turn_is_replayed_as_the_fixed_reply(client, scripted):
    teen = ready_user(client, "teen", _profile(15))
    connect(client, teen)
    cid = client.post("/api/agent/conversations", json={}, headers=teen).json()["id"]
    assert _send_to(client, teen, cid, WEIGHT_LOSS_QUESTION)["flags"] == ["risk_minor_weight_loss"]
    scripted.add(say("清蒸鱼配米饭。"))
    _send_to(client, teen, cid, "晚饭吃什么")
    [request] = scripted.requests
    assert [m["role"] for m in request.messages] == ["system", "user", "assistant", "user"]
    assert request.messages[1]["content"] == RISK_USER_PLACEHOLDER
    assert request.messages[2]["content"] == SAFE_REPLIES["minor_weight_loss"]
    assert "我想减肥" not in json.dumps(request.messages[1:], ensure_ascii=False)  # 上一轮的原话不回放
