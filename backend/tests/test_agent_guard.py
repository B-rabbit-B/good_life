import dataclasses
import time

import pytest

from app.agent.guard import (
    EXCLUDED_NAMES,
    NEGATIVE_CUES,
    REWRITE_INSTRUCTION,
    SAFE_FALLBACK,
    FoodMention,
    GuardVerdict,
    check_answer,
    evidence_section,
    find_foods,
    is_negative,
    rewrite_instruction,
)
from app.agent import guard
from app.nutrition.catalog import load_catalog
from app.nutrition.engine import SOURCE_NAMES, EvaluationContext, HardConstraint, TrainingContext, evaluate_food

CATALOG = load_catalog()
MAPO = "dish:mapo_tofu"
TOMATO_EGG = "dish:tomato_egg"
STEAMED_FISH = "dish:steamed_fish"
KUNG_PAO = "dish:kung_pao_chicken"
NO_SPICY = HardConstraint("m1", "diet_avoid", "忌辛辣", ("辛辣",))
NO_SEAFOOD = HardConstraint("m2", "diet_avoid", "忌海鲜", ("海鲜",))
STRENGTH = TrainingContext(True, ("strength",), "vigorous", 200)


def _evaluate(food_id, **context):
    food = CATALOG.get(food_id)
    evaluation = evaluate_food(food, food.default_grams, EvaluationContext(**context), CATALOG)
    return dataclasses.asdict(evaluation)  # 与 nutrition.evaluate_food 返回的 data 同形


def _ids(text):
    return [m.food_id for m in find_foods(text, CATALOG)]


def _mention(text, food_id):
    return next(m for m in find_foods(text, CATALOG) if m.food_id == food_id)


# ---------- 识别食物 ----------

def test_longest_match_keeps_dishes_whole():
    assert _ids("今晚可以吃番茄炒蛋") == [TOMATO_EGG]
    assert _ids("来一份麻婆豆腐") == [MAPO]
    mention = find_foods("来一份麻婆豆腐", CATALOG)[0]
    assert mention == FoodMention(MAPO, "麻婆豆腐", 3, 7)


def test_alias_and_first_occurrence_only():
    text = "西红柿炒鸡蛋很下饭。番茄炒蛋也行，麻婆豆腐和西红柿炒蛋都可以"
    mentions = find_foods(text, CATALOG)
    assert [m.food_id for m in mentions] == [TOMATO_EGG, MAPO]
    first = mentions[0]
    assert (first.name, first.start, first.end) == ("西红柿炒鸡蛋", 0, 6)
    assert all(text[m.start:m.end] == m.name for m in mentions)


def test_mentions_sorted_by_position():
    mentions = find_foods("先喝一杯牛奶，再吃清蒸鱼和米饭，最后来点苹果", CATALOG)
    assert [m.name for m in mentions] == ["牛奶", "清蒸鱼", "米饭", "苹果"]
    assert [m.start for m in mentions] == sorted(m.start for m in mentions)


def test_shared_name_resolves_like_food_search():
    # “豆腐”是多个食物共有的名称，取搜索食物排第一的那个，与智能体搜索到的一致
    assert _ids("豆腐可以吃") == [CATALOG.search("豆腐", 1)[0].food.id]
    assert _ids("米饭") == [CATALOG.common_aliases["米饭"]]


def test_single_character_names_are_ignored():
    assert _ids("鱼和虾都行，姜少放点，喝点水") == []


@pytest.mark.parametrize("text", [
    "你不是胖子，不用节食",
    "可以把计划写在白板上",
    "很多成人乳糖不耐受",
    "一碗面蛋白质不够",
])
def test_excluded_generic_words_do_not_match(text):
    assert _ids(text) == []


def test_excluded_names_are_real_catalog_names():
    known = {name for food in CATALOG.foods.values() for name in CATALOG.match_names_of(food)}
    assert EXCLUDED_NAMES <= known
    assert _ids("珍珠奶茶") == ["supplement:milk_tea"]


def test_index_is_built_once_and_matching_is_fast():
    find_foods("米饭", CATALOG)
    assert guard._index(CATALOG) is guard._index(CATALOG)
    text = ("今天练了腿，晚饭可以吃清蒸鱼、米饭和西兰花，再来一杯牛奶。如果想吃辣，麻婆豆腐少放辣椒；"
            "明早可以喝燕麦粥配鸡蛋和苹果。") * 6
    started = time.perf_counter()
    for _ in range(50):
        find_foods(text, CATALOG)
    assert time.perf_counter() - started < 2.0


# ---------- 否定语气 ----------

@pytest.mark.parametrize("text", [
    "今晚别吃麻婆豆腐",
    "不建议吃麻婆豆腐和回锅肉",
    "最好避免辛辣的菜，比如麻婆豆腐",
    "医嘱要求忌辛辣，麻婆豆腐不宜",
    "麻婆豆腐不要吃",
    "麻婆豆腐属于你医嘱要求避免的辛辣菜",
    "麻婆豆腐、宫保鸡丁这几天都别碰",
    "别吃麻婆豆腐",                      # 否定词在全文开头
    "麻婆豆腐这几天千万别",              # 否定词在全文结尾
])
def test_negative_tone(text):
    assert is_negative(text, _mention(text, MAPO))


@pytest.mark.parametrize("text", [
    "推荐麻婆豆腐",
    "可以来一份麻婆豆腐",
    "别吃太多。推荐麻婆豆腐",            # 跨句的否定不算
    "不要空腹！麻婆豆腐配米饭正好",
    "特别推荐麻婆豆腐",                  # “特别”里的“别”不是否定
    "区别不大，麻婆豆腐也行",
    "不建议吃回锅肉，可以换成麻婆豆腐",  # 否定之后转为推荐
    "少吃油炸的，多吃麻婆豆腐",
    "不要错过麻婆豆腐",
    "现在不用忌口了，麻婆豆腐也能吃",
    "推荐麻婆豆腐，不要犹豫",            # 食物之后的否定只看同一小句
])
def test_recommending_tone(text):
    assert not is_negative(text, _mention(text, MAPO))


def test_negative_cues_are_the_agreed_list():
    assert NEGATIVE_CUES == ("不要", "别", "避免", "不建议", "不能", "不宜", "忌", "少吃", "不推荐", "停止", "不适合")


# ---------- 输出检查 ----------

def _spicy_blocked():
    return {
        MAPO: _evaluate(MAPO, constraints=(NO_SPICY,)),
        KUNG_PAO: _evaluate(KUNG_PAO, constraints=(NO_SPICY,)),
        STEAMED_FISH: _evaluate(STEAMED_FISH, constraints=(NO_SPICY,), goal="gain_muscle", training=STRENGTH),
    }


def test_medical_block_in_recommending_tone_is_a_violation():
    evaluations = _spicy_blocked()
    assert evaluations[MAPO]["conclusion"] == "not_recommended"
    assert check_answer("今晚推荐麻婆豆腐", evaluations) == GuardVerdict(False, ("麻婆豆腐",))
    assert check_answer("可以来一份麻婆豆腐，再加宫保鸡丁", evaluations) == GuardVerdict(False, ("麻婆豆腐", "宫保鸡丁"))


def test_negative_tone_passes():
    evaluations = _spicy_blocked()
    verdict = check_answer("今晚别吃麻婆豆腐，推荐清蒸鱼", evaluations)
    assert verdict == GuardVerdict(True, ())


def test_any_recommending_occurrence_counts():
    evaluations = _spicy_blocked()
    verdict = check_answer("别吃麻婆豆腐。不过实在想吃的话，麻婆豆腐少来点也行", evaluations)
    assert verdict == GuardVerdict(False, ("麻婆豆腐",))


def test_only_medical_blocks_count():
    evaluations = {
        "cfcd:066201x": _evaluate("cfcd:066201x", cycle_phase="menstrual"),  # 西瓜：经期提示的谨慎
        STEAMED_FISH: _evaluate(STEAMED_FISH, goal="gain_muscle", training=STRENGTH),  # 训练与目标的推荐
    }
    assert evaluations["cfcd:066201x"]["conclusion"] == "caution"
    assert check_answer("推荐西瓜和清蒸鱼", evaluations).passed
    # 即使结论是不建议，没有医嘱阻断也不算违反
    fake = {MAPO: {**_evaluate(MAPO), "conclusion": "not_recommended",
                   "reasons": [{"source": "cycle", "effect": "block", "code": "x", "message": "m", "ref": "r"}]}}
    assert check_answer("推荐麻婆豆腐", fake).passed


def test_foods_without_evaluation_are_skipped():
    assert check_answer("推荐麻婆豆腐", {}).passed


def test_fallback_and_rewrite_texts():
    assert SAFE_FALLBACK.format(foods="麻婆豆腐、宫保鸡丁").startswith("根据你当前生效的医嘱，下面这些食物不建议吃：麻婆豆腐、宫保鸡丁。")
    evaluations = _spicy_blocked()
    instruction = rewrite_instruction("推荐麻婆豆腐和清蒸鱼", evaluations)
    block = evaluations[MAPO]["reasons"][0]["message"]
    assert block in instruction and "麻婆豆腐" in instruction and "清蒸鱼" not in instruction
    assert instruction == REWRITE_INSTRUCTION.format(details=f"麻婆豆腐：{block}")


# ---------- 依据 ----------

def _messages(evaluations):
    return {r["message"] for ev in evaluations.values() for r in ev["reasons"]} | {
        ev["tradeoff"] for ev in evaluations.values() if ev["tradeoff"]}


def test_evidence_quotes_engine_reasons_verbatim():
    evaluations = _spicy_blocked()
    evaluations[STEAMED_FISH] = _evaluate(STEAMED_FISH, constraints=(NO_SEAFOOD,), goal="gain_muscle")
    text = "别吃麻婆豆腐，清蒸鱼也不行，宫保鸡丁同样要避免"
    section = evidence_section(find_foods(text, CATALOG), evaluations)
    lines = section.split("\n")
    assert [line.split("：", 1)[0] for line in lines] == ["麻婆豆腐", "清蒸鱼", "宫保鸡丁"]
    assert lines[0].startswith("麻婆豆腐：不建议。依据：【医嘱】")
    known = _messages(evaluations)
    labels = {*SOURCE_NAMES.values(), "权衡"}
    for line, food_id in zip(lines, [MAPO, STEAMED_FISH, KUNG_PAO]):
        evaluation = evaluations[food_id]
        body = line.split("依据：", 1)[1]
        pieces = [p for p in body.split("【") if p]
        assert len(pieces) == len(evaluation["reasons"]) + bool(evaluation["tradeoff"])
        given = {SOURCE_NAMES[r["source"]] for r in evaluation["reasons"]} | ({"权衡"} if evaluation["tradeoff"] else set())
        for piece in pieces:
            label, message = piece.split("】", 1)
            assert label in labels and label in given
            assert message in known
    assert "【权衡】虽然有健身目标方面的好处，但医嘱优先，结论为不建议。" in lines[1]


def test_evidence_lists_no_source_the_engine_did_not_give():
    evaluations = {"cfcd:066201x": _evaluate("cfcd:066201x", cycle_phase="menstrual")}
    section = evidence_section(find_foods("西瓜", CATALOG), evaluations)
    assert section.startswith("西瓜（代表值）：谨慎。依据：【经期提示】")
    for source, name in SOURCE_NAMES.items():
        given = any(r["source"] == source for r in evaluations["cfcd:066201x"]["reasons"])
        assert (f"【{name}】" in section) == given


def test_evidence_conclusion_names_and_empty():
    suitable = {"cfcd:091112": _evaluate("cfcd:091112", goal="gain_muscle")}
    name = suitable["cfcd:091112"]["food_name"]  # 依据里用引擎判断的食物名
    assert evidence_section(find_foods("鸡胸肉", CATALOG), suitable).startswith(f"{name}：适合。依据：【健身目标】")
    assert evidence_section([], suitable) == ""
    assert evidence_section(find_foods("今天天气不错", CATALOG), suitable) == ""
    assert evidence_section(find_foods("麻婆豆腐", CATALOG), {}) == ""
