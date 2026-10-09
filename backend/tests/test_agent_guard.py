import dataclasses
import time

import pytest

from app.agent.guard import (
    EXCLUDED_NAMES,
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
HOT_POT = "dish:hot_pot"
TWICE_COOKED = "dish:twice_cooked_pork"
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


# ---------- 归一 ----------

def test_zero_width_and_spaces_between_chinese_are_ignored():
    text = "推荐 麻\u200b婆 豆腐，再来\u3000火锅"
    mentions = find_foods(text, CATALOG)
    assert [m.food_id for m in mentions] == [MAPO, HOT_POT]
    assert all(text[m.start:m.end] == m.name for m in mentions)
    assert mentions[0].name == "麻\u200b婆 豆腐"


def test_traditional_characters_are_mapped():
    text = "宮保雞丁和回鍋肉都好吃，火鍋也行"
    assert _ids(text) == [KUNG_PAO, TWICE_COOKED, HOT_POT]
    assert find_foods(text, CATALOG)[0].name == "宮保雞丁"


def test_food_traditional_table_maps_to_catalog_characters():
    used = {ch for food in CATALOG.foods.values() for name in CATALOG.match_names_of(food) for ch in name}
    assert all(len(src) == 1 and dst in used for src, dst in guard.FOOD_TRADITIONAL_TO_SIMPLIFIED.items())
    assert set("鍋雞豬魚腸麵餅湯醬燒涼蝦飯") <= guard.FOOD_TRADITIONAL_TO_SIMPLIFIED.keys()


def test_newlines_still_split_names():
    assert _ids("麻婆\n豆腐") != [MAPO]


def test_mostly_latin():
    assert guard.mostly_latin("Mapo tofu is great tonight")
    assert guard.mostly_latin("Try the mapo tofu 麻婆豆腐 tonight")
    assert not guard.mostly_latin("麻婆豆腐YYDS")  # 本身就会因为麻婆豆腐被拦下
    assert not guard.mostly_latin("12345")


@pytest.mark.parametrize("text", [
    "早餐：燕麦50g，鸡蛋1个，牛奶250ml，约400kcal",
    "今晚 BMI 23.5，TDEE 2200kcal，蛋白质120g",
    "推荐清蒸鱼（约200g，含DHA、EPA）",
    "今晚推荐清蒸鱼，配 1 碗米饭（约 150g）",
])
def test_units_and_acronyms_do_not_make_an_answer_latin(text):
    assert not guard.mostly_latin(text)


# ---------- 输出检查：默认拦截 ----------

def _spicy_blocked():
    blocked = (MAPO, KUNG_PAO, HOT_POT, TWICE_COOKED)
    evaluations = {food_id: _evaluate(food_id, constraints=(NO_SPICY,)) for food_id in blocked}
    evaluations[STEAMED_FISH] = _evaluate(STEAMED_FISH, constraints=(NO_SPICY,), goal="gain_muscle", training=STRENGTH)
    return evaluations


# 推荐、放宽或只是提到：一律违反（评审给出的探测句）
RECOMMENDING = [
    "推荐麻婆豆腐配米饭不要太多", "麻婆豆腐可以吃，别吃太多", "麻婆豆腐可以吃，但别吃太多", "不要犹豫，来份麻婆豆腐",
    "别担心，麻婆豆腐没问题", "别担心麻婆豆腐没问题", "不建议你错过麻婆豆腐", "少吃点麻婆豆腐就行", "少吃麻婆豆腐就行",
    "麻婆豆腐不辣的话可以吃", "火锅别点太辣的就行", "火锅别太辣就好", "不忌口的话推荐宫保鸡丁", "不忌口的话宫保鸡丁很好",
    "别犹豫，麻婆豆腐走起", "别客气，点个麻婆豆腐吧", "不要怕，麻婆豆腐吃了没事", "不要怕麻婆豆腐吃了没事",
    "不能错过的川菜：麻婆豆腐", "不能不吃的川菜是麻婆豆腐", "停止纠结，直接点火锅", "避免饿肚子，晚上来顿火锅",
    "避免浪费，把麻婆豆腐吃完", "忌口期间也能吃麻婆豆腐", "少吃多餐，麻婆豆腐分两次吃", "别饿着，宫保鸡丁加米饭",
    "不适合你的菜很多，但麻婆豆腐例外", "麻婆豆腐别有一番风味，推荐", "麻婆豆腐是个不错的选择，不要太辣",
    "宫保鸡丁很下饭，别放太多油就好", "火锅不能天天吃，偶尔吃一次没问题", "火锅不宜太烫，记得晾一下再吃",
    "麻婆豆腐吃完别忘了喝水", "吃麻婆豆腐的时候别配啤酒", "晚饭就麻婆豆腐吧，不要再犹豫了", "晚饭就吃麻婆豆腐吧",
    "麻婆豆腐YYDS", "今晚麻婆豆腐安排上", "没有医嘱限制的话，麻婆豆腐很好", "你的医嘱不禁止麻婆豆腐",
    "虽然忌辛辣，但麻婆豆腐可以少量吃", "虽然要避免辛辣，麻婆豆腐少量也行", "避免辛辣？麻婆豆腐其实问题不大",
    "不要只吃米饭，配点麻婆豆腐", "别只吃米饭，加个麻婆豆腐", "别光吃菜，火锅里的肉也要吃",
    "不建议空腹，先吃点宫保鸡丁垫垫", "少吃零食，正餐吃麻婆豆腐", "宮保雞丁很好吃", "回鍋肉推荐", "火鍋推荐",
    "别人都说麻婆豆腐好吃，你也试试",
    # 结构成立但同一小句里有放宽说法
    "不要吃太多麻婆豆腐", "火锅不要吃太多", "麻婆豆腐别吃太多", "麻婆豆腐不能天天吃", "能不能吃麻婆豆腐？可以",
    "要不要来点麻婆豆腐", "可以分别吃麻婆豆腐和米饭", "现在不用忌麻婆豆腐了",
    # 列表：空行、非禁止标题、推荐标题、条目里放宽
    "这几天不要吃：\n- 清蒸鱼\n\n- 麻婆豆腐", "这几天不要吃：\n- 回锅肉\n晚饭推荐：\n- 麻婆豆腐",
    "推荐这些，别太辣：\n- 麻婆豆腐", "这几天不要吃：\n- 麻婆豆腐（少量可以）", "- 麻婆豆腐",
]

# 明确的禁止结构：不算违反
PROHIBITING = [
    "今晚别吃麻婆豆腐，推荐清蒸鱼", "不要吃麻婆豆腐", "先别吃麻婆豆腐", "不能吃麻婆豆腐", "不建议吃麻婆豆腐",
    "避免麻婆豆腐", "避开麻婆豆腐", "忌麻婆豆腐", "远离麻婆豆腐和火锅。", "戒掉火锅一段时间", "最好不吃火锅", "不碰火锅",
    "暂停火锅", "火锅暂停一段时间", "建议避开麻婆豆腐", "建议不要吃麻婆豆腐", "推荐你避开火锅",
    "千万不要碰火锅、麻婆豆腐和宫保鸡丁。",
    "麻婆豆腐不要吃", "麻婆豆腐别吃", "麻婆豆腐先别吃", "麻婆豆腐不能吃", "麻婆豆腐不建议吃", "麻婆豆腐要避免",
    "麻婆豆腐要避开", "麻婆豆腐不行", "麻婆豆腐就算了", "麻婆豆腐先不吃", "火锅等医嘱解除后再吃。", "麻婆豆腐这几天先别碰",
    "按医嘱，麻婆豆腐暂时不能吃。", "麻婆豆腐我不推荐，换成清蒸鱼更好。", "不建议吃火锅，建议改天再说，改吃清蒸鱼。",
    "不建议吃火锅，建议你吃清蒸鱼。", "医嘱要求忌辛辣，因此麻婆豆腐不在推荐范围内。", "你可以吃清蒸鱼，但麻婆豆腐不行。",
    "可以吃清蒸鱼，麻婆豆腐就算了。", "不要吃麻婆豆腐，也不要吃火锅。", "宫保鸡丁？不行，医嘱忌辛辣。", "忌：麻婆豆腐、火锅",
    "你的医嘱要求忌辛辣，所以麻婆豆腐、火锅和宫保鸡丁这几天都先别碰。", "麻婆豆腐、火锅这类辛辣菜，按医嘱要先避开。",
    "麻婆豆腐、火锅这类辛辣菜要先避开", "不要吃麻婆豆腐、火锅这类辛辣菜", "麻婆豆腐这几天千万别",
    "这几天不要吃：\n- 麻婆豆腐\n- 火锅", "下面这些要避免：\n1. 麻婆豆腐\n2. 宫保鸡丁\n\n晚饭推荐清蒸鱼。",
    "避免以下食物：\n- 麻婆豆腐", "別吃麻婆豆腐", "不要吃麻 婆豆腐",
    "火锅 不要吃", "不要 吃 火锅", "不 要吃火锅", "推荐清蒸鱼，不要吃火锅", "麻婆豆腐 不要吃。", "這幾天別吃火鍋",
    "火鍋這幾天先別碰", "不要吃火锅，可以吃清蒸鱼", "火锅等医生说好了后再吃", "火锅等复查后再吃", "不要吃火锅等辛辣菜",
    "这几天不要吃：\n- 麻婆豆腐（含辣）\n- 火锅。",
]

# 复审的静默放行：后文反悔、禁止后面还有别的内容、列表标题或条目不明确、“等……后再吃”不是等医嘱
SILENT_PASSES = [
    "不要吃火锅？其实可以", "别吃清蒸鱼和麻婆豆腐以外的东西", "避免火锅？没必要", "火锅不要吃？才怪", "火锅别吃了？想吃就吃",
    "千万别吃麻婆豆腐以外的菜", "不要吃火锅和宫保鸡丁以外的", "不要吃火锅和麻婆豆腐吧，开玩笑的", "不要吃火锅，开玩笑，吃吧",
    "不要吃清蒸鱼和麻婆豆腐，开玩笑",
    "火锅等下班后再吃", "火锅等你回来后再吃", "麻婆豆腐等周末后再吃",
    "避免吃火锅太晚", "不要吃火锅的时候喝冰水", "不要吃火锅后马上运动", "别吃火锅吃到撑", "不要吃火锅太快",
    "这几天要避免：\n- 冰饮，可以多吃麻婆豆腐", "这几天不要吃：\n- 清蒸鱼，推荐火锅",
    "不要犹豫，试试这些：\n- 麻婆豆腐", "别错过这些：\n- 火锅", "不能错过的川菜：\n- 麻婆豆腐",
    "避免饿肚子，晚上吃这些：\n- 火锅\n- 宫保鸡丁", "不要只吃米饭，加上这些：\n1. 麻婆豆腐", "别光吃菜：\n- 火锅",
    "不要吃火锅？可以的", "火锅不要吃？不存在的", "火锅不行？那是以前", "不建议吃火锅，骗你的", "别吃麻婆豆腐，除非你很想吃",
    "不要吃麻婆豆腐，除非不辣", "麻婆豆腐不能吃？能吃", "麻婆豆腐别吃！才怪", "不要吃火锅；当然吃也没关系",
    "不要吃火锅\n开玩笑，可以吃", "忌麻婆豆腐？早就解除了", "远离火锅？不需要", "不要吃麻婆豆腐以外的辣菜",
    "忌麻婆豆腐偶爾吃", "麻婆豆腐不要吃，偶爾", "不要吃火鍋偶爾來點", "這幾天別吃火鍋，其實可以",
    "这几天不要吃：\n- 麻婆豆腐也能吃", "这几天不要吃：\n- 麻婆豆腐。今晚就吃它",
]

# 自然的提醒但不在禁止结构里：仍会拦下，交给重写或固定安全回答（可以接受）
STILL_BLOCKED = [
    "火锅含辣，医嘱期间不吃为好。", "我知道你很想吃火锅，但医嘱期间还是不行。", "不建议吃火锅，可以理解你想吃火锅的心情。",
    "麻婆豆腐属于辛辣菜，与你的医嘱冲突。", "不宜：辛辣菜（如麻婆豆腐）", "不要吃辣，麻婆豆腐这种换季时更要注意",
]


@pytest.mark.parametrize("text", RECOMMENDING + SILENT_PASSES + STILL_BLOCKED)
def test_blocked_food_outside_prohibition_is_a_violation(text):
    verdict = check_answer(text, _spicy_blocked())
    assert not verdict.passed and verdict.violations


@pytest.mark.parametrize("text", PROHIBITING)
def test_blocked_food_inside_prohibition_passes(text):
    verdict = check_answer(text, _spicy_blocked())
    assert verdict == GuardVerdict(True, ()), verdict
    assert all(is_negative(text, m) for m in find_foods(text, CATALOG) if m.food_id != STEAMED_FISH)


def test_latin_answer_has_no_mentions_but_is_flagged():
    text = "Mapo tofu is great tonight"
    assert check_answer(text, _spicy_blocked()).passed  # 识别不了食物，由调用方按 mostly_latin 要求重写
    assert guard.mostly_latin(text)


def test_violation_names_and_order():
    evaluations = _spicy_blocked()
    assert check_answer("今晚推荐麻婆豆腐", evaluations) == GuardVerdict(False, ("麻婆豆腐",))
    assert check_answer("可以来一份麻婆豆腐，再加宮保雞丁", evaluations) == GuardVerdict(False, ("麻婆豆腐", "宫保鸡丁"))


def test_any_unprohibited_occurrence_counts():
    verdict = check_answer("别吃麻婆豆腐。不过实在想吃的话，麻婆豆腐少来点也行", _spicy_blocked())
    assert verdict == GuardVerdict(False, ("麻婆豆腐",))


def test_unblocked_foods_never_violate():
    assert check_answer("推荐清蒸鱼，可以多吃点", _spicy_blocked()).passed


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


def test_catalog_parameter_is_used():
    evaluations = _spicy_blocked()
    assert check_answer("推荐麻婆豆腐", evaluations, CATALOG) == check_answer("推荐麻婆豆腐", evaluations)
    assert rewrite_instruction("推荐麻婆豆腐", evaluations, CATALOG) == rewrite_instruction("推荐麻婆豆腐", evaluations)


def test_fallback_and_rewrite_texts():
    assert SAFE_FALLBACK.format(foods="麻婆豆腐、宫保鸡丁").startswith("根据你当前生效的医嘱，下面这些食物不建议吃：麻婆豆腐、宫保鸡丁。")
    evaluations = _spicy_blocked()
    instruction = rewrite_instruction("推荐麻婆豆腐和清蒸鱼", evaluations)
    block = evaluations[MAPO]["reasons"][0]["message"]
    assert block in instruction and "麻婆豆腐" in instruction and "清蒸鱼" not in instruction
    assert instruction == REWRITE_INSTRUCTION.format(details=f"麻婆豆腐：{block}")
    assert "简体中文" in REWRITE_INSTRUCTION and "这几天先别吃" in REWRITE_INSTRUCTION


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
        given = {SOURCE_NAMES[r["source"]] for r in evaluation["reasons"]}
        given |= {"权衡"} if evaluation["tradeoff"] else set()
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
