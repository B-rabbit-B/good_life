import random

import pytest

from app.nutrition.catalog import Catalog, Food, Nutrients, Source, TagDefinition
from app.nutrition.engine import (
    CAUTION,
    DISCLAIMER,
    NOT_RECOMMENDED,
    SUITABLE,
    EvaluationContext,
    HardConstraint,
    evaluate_food,
    evaluate_meal,
)
from app.nutrition.needs import Needs

SOURCE = Source("测试数据", "t", "personal_study_only", "测试")
TAGS = [
    TagDefinition(tag, name, kind, "传统饮食经验" if kind == "tradition" else "测试", "reviewed")
    for tag, name, kind in [
        ("spicy", "辛辣", "culinary"), ("high_fat", "高脂肪", "nutrition"), ("meat", "含肉", "composition"),
        ("cold_nature", "寒凉", "tradition"), ("raw_cold", "生冷", "culinary"), ("alcohol", "含酒精", "composition"),
        ("high_protein", "高蛋白", "nutrition"), ("organ_meat", "动物内脏", "composition"),
        ("iron_rich", "富含铁", "nutrition"), ("high_sodium", "高钠", "nutrition"), ("sweets", "甜食", "dietary"),
        ("high_sugar", "高糖", "dietary"), ("fast_carb", "快碳", "dietary"), ("fried", "油炸", "culinary"),
        ("slow_carb", "慢碳", "dietary"), ("high_fiber", "高膳食纤维", "nutrition"),
    ]
]


def _food(food_id, name, tags, energy=100.0, sodium=10.0, aliases=()):
    return Food(
        id=food_id, name=name, aliases=aliases, category="测试", kind="ingredient",
        nutrients=Nutrients(energy_kcal=energy, protein_g=5, fat_g=5, carbohydrate_g=10, sodium_mg=sodium),
        tags=frozenset(tags), source=SOURCE,
    )


HOTPOT = _food("t:hotpot", "火锅", {"spicy", "high_fat", "meat"}, energy=150)
WATERMELON = _food("t:melon", "西瓜", {"cold_nature"}, energy=30)
BEER = _food("t:beer", "啤酒", {"alcohol"}, energy=40)
BREAST = _food("t:breast", "鸡胸肉", {"high_protein", "meat"}, energy=130)
LIVER = _food("t:liver", "猪肝", {"organ_meat", "iron_rich", "high_protein", "meat"}, energy=130)
SPINACH = _food("t:spinach", "菠菜", set(), energy=25)
CAKE = _food("t:cake", "蛋糕", {"sweets", "high_sugar"}, energy=350)
BEEF_JERKY = _food("t:jerky", "卤牛肉", {"high_protein", "high_sodium", "meat"}, energy=200, sodium=900)
RICE = _food("t:rice", "米饭", {"fast_carb"}, energy=116)
CATALOG = Catalog([HOTPOT, WATERMELON, BEER, BREAST, LIVER, SPINACH, CAKE, BEEF_JERKY, RICE], TAGS, {})
NEEDS = Needs(status="ok", energy_kcal=1500, energy_kcal_low=1350, energy_kcal_high=1650, protein_g=60,
              sodium_mg_max=2000)
ZERO = Nutrients(energy_kcal=0, sodium_mg=0)


def _avoid(item_id, content, subjects, needs_review=False, category="diet_avoid"):
    return HardConstraint(item_id, category, content, tuple(subjects), needs_review)


def _ctx(**kwargs):
    base = {"needs": NEEDS, "day_totals": ZERO}
    base.update(kwargs)
    return EvaluationContext(**base)


def _evaluate(food, grams=100, **kwargs):
    return evaluate_food(food, grams, _ctx(**kwargs), CATALOG)


def _sources(result):
    return [(r.source, r.effect) for r in result.reasons]


def test_healthy_user_gets_suitable_with_disclaimer():
    result = _evaluate(SPINACH)
    assert result.conclusion == SUITABLE
    assert result.reasons == ()
    assert result.disclaimer == DISCLAIMER
    assert "测试数据" in result.data_source


def test_medical_avoid_blocks_and_names_the_order():
    result = _evaluate(HOTPOT, constraints=(_avoid("m1", "一周内忌食辛辣、油腻", ["辛辣", "油腻"]),))
    assert result.conclusion == NOT_RECOMMENDED
    blocks = [r for r in result.reasons if r.effect == "block"]
    assert {r.ref for r in blocks} == {"m1"}
    assert any("一周内忌食辛辣、油腻" in r.message and "辛辣" in r.message for r in blocks)


def test_name_match_blocks_too():
    result = _evaluate(WATERMELON, constraints=(_avoid("m1", "忌西瓜", ["西瓜"]),))
    assert result.conclusion == NOT_RECOMMENDED


def test_pending_review_order_still_blocks():
    result = _evaluate(BEER, constraints=(_avoid("m2", "禁酒", ["酒"], needs_review=True),))
    assert result.conclusion == NOT_RECOMMENDED
    assert any("待复核" in r.message for r in result.reasons)


def test_non_food_subject_is_ignored_and_known_food_subject_is_verifiable():
    result = _evaluate(RICE, constraints=(_avoid("m3", "戒烟，忌菠菜", ["烟", "菠菜"]),))
    assert result.conclusion == SUITABLE
    assert result.reasons == ()


def test_unrecognised_subject_caps_at_caution():
    result = _evaluate(RICE, constraints=(_avoid("m4", "忌发物", ["发物"]),))
    assert result.conclusion == CAUTION
    assert _sources(result) == [("medical", "unverifiable")]
    assert "发物" in result.reasons[0].message and "核对" in result.reasons[0].message


def test_requirement_styles():
    low_salt = _avoid("m5", "低盐饮食", ["低盐"], category="diet_require")
    assert _evaluate(BEEF_JERKY, constraints=(low_salt,)).conclusion == NOT_RECOMMENDED
    assert _evaluate(SPINACH, constraints=(low_salt,)).conclusion == SUITABLE
    protein = _avoid("m6", "优质蛋白饮食", ["优质蛋白"], category="diet_require")
    result = _evaluate(BREAST, constraints=(protein,))
    assert (result.conclusion, _sources(result)) == (SUITABLE, [("medical", "prefer")])
    liquid = _avoid("m7", "流质饮食", ["流质"], category="diet_require")
    assert _evaluate(SPINACH, constraints=(liquid,)).conclusion == CAUTION
    meals = _avoid("m8", "少量多餐", ["少量多餐"], category="diet_require")
    assert _evaluate(SPINACH, constraints=(meals,)).conclusion == SUITABLE


def test_exercise_and_other_orders_do_not_affect_food():
    orders = (_avoid("m9", "避免剧烈运动", ["剧烈运动"], category="exercise_limit"),
              _avoid("m10", "每天测血压", [], category="other"))
    assert _evaluate(HOTPOT, constraints=orders).conclusion == SUITABLE


def test_menstrual_cold_food_is_caution_from_cycle_not_medical():
    result = _evaluate(WATERMELON, cycle_phase="menstrual")
    assert result.conclusion == CAUTION
    [reason] = result.reasons
    assert (reason.source, reason.effect, reason.ref) == ("cycle", "caution", "menstrual-warm")
    assert "不是医嘱" in reason.message and "传统经验" in reason.message


def test_menstrual_iron_is_preferred():
    result = _evaluate(LIVER, cycle_phase="menstrual")
    assert result.conclusion == SUITABLE
    assert ("cycle", "prefer") in _sources(result)


def test_hard_constraint_beats_soft_preference():
    result = _evaluate(LIVER, cycle_phase="menstrual", goal="gain_muscle",
                       constraints=(_avoid("m11", "忌动物内脏", ["动物内脏"]),))
    assert result.conclusion == NOT_RECOMMENDED
    assert "医嘱优先" in result.tradeoff


def test_soft_conflict_gets_a_tradeoff_note():
    result = _evaluate(BEEF_JERKY, cycle_phase="luteal", goal="lose_fat")
    assert result.conclusion == CAUTION
    assert ("cycle", "caution") in _sources(result) and ("goal", "prefer") in _sources(result)
    assert "权衡" in result.tradeoff


def test_intake_over_energy_upper_bound():
    result = _evaluate(CAKE, grams=100, day_totals=Nutrients(energy_kcal=1400, sodium_mg=0))
    assert result.conclusion == CAUTION
    assert any(r.source == "intake" and "1650" in r.message for r in result.reasons)


def test_unknown_needs_gives_info_only():
    result = _evaluate(SPINACH, needs=Needs(status="insufficient_profile", missing_fields=("weight_kg",)))
    assert result.conclusion == SUITABLE
    assert _sources(result) == [("intake", "info")]


def test_personal_avoidance_and_preference():
    result = _evaluate(HOTPOT, food_avoidances=("辣",))
    assert (result.conclusion, _sources(result)) == (CAUTION, [("preference", "caution")])
    assert _evaluate(BREAST, diet_preferences=("素食",)).conclusion == CAUTION


def test_output_is_deterministic_regardless_of_input_order():
    orders = [
        _avoid("m1", "忌辛辣", ["辛辣"]), _avoid("m2", "忌油腻", ["油腻"]), _avoid("m3", "忌发物", ["发物"]),
    ]
    first = _evaluate(HOTPOT, constraints=tuple(orders), cycle_phase="menstrual", goal="lose_fat")
    for seed in range(5):
        shuffled = orders[:]
        random.Random(seed).shuffle(shuffled)
        again = _evaluate(HOTPOT, constraints=tuple(shuffled), cycle_phase="menstrual", goal="lose_fat")
        assert again == first


def test_meal_takes_the_worst_conclusion_and_running_totals():
    context = _ctx(day_totals=Nutrients(energy_kcal=1300, sodium_mg=0),
                   constraints=(_avoid("m1", "禁酒", ["酒"]),))
    result = evaluate_meal([(RICE, 200), (CAKE, 100), (BEER, 300)], context, CATALOG)
    assert [i.conclusion for i in result.items] == [SUITABLE, CAUTION, NOT_RECOMMENDED]
    assert result.conclusion == NOT_RECOMMENDED
    assert result.total.energy_kcal == pytest.approx(232 + 350 + 120)


def test_vocabulary_lookup_strips_suffixes_and_entries_have_one_kind():
    from app.nutrition.rules import VocabularyEntry, load_vocabulary

    vocabulary = load_vocabulary()
    assert vocabulary.lookup("油腻食物").tags == ("fried", "high_fat")
    assert vocabulary.lookup("低盐饮食").violates == ("high_sodium", "cured")
    assert vocabulary.lookup("海鲜类食物").tags == ("seafood",)
    assert vocabulary.lookup("吸烟").non_food
    assert vocabulary.lookup("发物") is None and vocabulary.lookup("食物") is None
    with pytest.raises(ValueError):
        VocabularyEntry(tags=("spicy",), unverifiable=True)
    with pytest.raises(ValueError):
        VocabularyEntry()


def test_soft_rules_reference_known_phases_goals_and_tips():
    from app.cycle.tips import load_tip_rules
    from app.nutrition.rules import load_soft_rules

    rules = load_soft_rules()
    assert set(rules.cycle) == {"menstrual", "luteal"} and set(rules.goals) == {"lose_fat", "gain_muscle"}
    tip_ids = {tip.id for tip in load_tip_rules()}
    assert all(rule.tip_id in tip_ids for phase_rules in rules.cycle.values() for rule in phase_rules)
    assert next(r for r in rules.cycle["menstrual"] if r.tip_id == "menstrual-warm").tradition


# ---- Fix round 1: real-catalog regressions and loader checks ----


def _real(name):
    from app.nutrition.catalog import load_catalog

    return load_catalog().search(name)[0].food


def _real_conclusion(category, subjects, name):
    from app.nutrition.catalog import load_catalog

    context = EvaluationContext(constraints=(_avoid("m", "医嘱原文", subjects, category=category),))
    return evaluate_food(_real(name), 100, context, load_catalog()).conclusion


@pytest.mark.parametrize(("category", "subjects", "name", "expected"), [
    ("medication_diet", ["低盐"], "咸鸭蛋", NOT_RECOMMENDED),
    ("diet_avoid", ["流质"], "米饭", CAUTION),
    ("diet_avoid", ["盐"], "咸鸭蛋", NOT_RECOMMENDED),
    ("diet_avoid", ["烟酒"], "啤酒", NOT_RECOMMENDED),
    ("diet_avoid", ["烟酒"], "白酒", NOT_RECOMMENDED),
    ("diet_avoid", ["烟酒"], "米饭", SUITABLE),
    ("diet_avoid", ["辛辣刺激性食物"], "麻婆豆腐", NOT_RECOMMENDED),
    ("diet_avoid", ["高盐", "高脂食物"], "咸鸭蛋", NOT_RECOMMENDED),
    ("diet_avoid", ["高盐", "高脂食物"], "红烧肉", NOT_RECOMMENDED),
    ("diet_avoid", ["高糖"], "可乐", NOT_RECOMMENDED),
    ("diet_avoid", ["醋"], "米饭", CAUTION),
    ("diet_avoid", ["糖"], "糖醋排骨", NOT_RECOMMENDED),
])
def test_real_catalog_orders(category, subjects, name, expected):
    assert _real_conclusion(category, subjects, name) == expected


def test_avoid_order_with_requirement_or_unverifiable_wording():
    low_salt = _avoid("m1", "服药期间低盐饮食", ["低盐"], category="medication_diet")
    assert _sources(_evaluate(BEEF_JERKY, constraints=(low_salt,))) == [("medical", "block")]
    protein = _avoid("m2", "忌口期间优质蛋白", ["优质蛋白"])
    assert _sources(_evaluate(BREAST, constraints=(protein,))) == [("medical", "prefer")]
    liquid = _avoid("m3", "流质", ["流质"])
    result = _evaluate(SPINACH, constraints=(liquid,))
    assert _sources(result) == [("medical", "unverifiable")]
    meals = _avoid("m4", "少量多餐", ["少量多餐"], category="medication_diet")
    assert _evaluate(SPINACH, constraints=(meals,)).reasons == ()


def test_unknown_single_character_subject_is_unverifiable():
    from app.nutrition.rules import load_vocabulary

    assert load_vocabulary().lookup("醋") is None
    result = _evaluate(RICE, constraints=(_avoid("m1", "忌醋", ["醋"]),))
    assert _sources(result) == [("medical", "unverifiable")]


def test_single_character_term_ignores_parenthetical_qualifiers():
    from app.nutrition.catalog import load_catalog

    catalog = load_catalog()
    milk = catalog.get("cfcd:101173")
    assert "乳糖" in milk.name
    context = EvaluationContext(constraints=(_avoid("m1", "忌糖", ["糖"]),))
    assert not any(r.effect == "block" for r in evaluate_food(milk, 100, context, catalog).reasons)
    chilled = catalog.get("cfcd:121246")
    context = EvaluationContext(constraints=(_avoid("m2", "忌冰", ["冰"]),))
    assert not any(r.effect == "block" for r in evaluate_food(chilled, 100, context, catalog).reasons)


def test_unverifiable_message_reads_naturally_and_carries_pending_note():
    result = _evaluate(RICE, constraints=(_avoid("m1", "忌食发物", ["发物"], needs_review=True),))
    [reason] = result.reasons
    assert reason.message.startswith("无法自动判断这个食物是否属于医嘱「忌食发物」中的「发物」")
    assert "核对" in reason.message and "待复核" in reason.message


def test_tradeoff_excludes_medical_from_benefits():
    avoid_organ = _avoid("m1", "忌动物内脏", ["动物内脏"])
    protein = _avoid("m2", "优质蛋白饮食", ["优质蛋白"], category="diet_require")
    only_medical = _evaluate(LIVER, constraints=(avoid_organ, protein))
    assert only_medical.tradeoff == "虽然这个食物有符合其他医嘱要求的方面，但它违反了医嘱，结论为不建议。"
    mixed = _evaluate(LIVER, constraints=(avoid_organ, protein), goal="gain_muscle")
    assert mixed.tradeoff == "虽然有健身目标方面的好处，但医嘱优先，结论为不建议。"


def test_vocabulary_strips_trailing_xing():
    from app.nutrition.rules import load_vocabulary

    vocabulary = load_vocabulary()
    assert vocabulary.lookup("寒凉性食物").tags == ("cold_nature",)
    assert vocabulary.lookup("辛辣刺激性食物").tags == ("spicy", "caffeine", "alcohol")


def test_json_parser_rejects_duplicate_keys():
    from app.nutrition.rules import parse_json

    with pytest.raises(ValueError, match="辣"):
        parse_json('{"terms": {"辣": {"tags": ["spicy"]}, "辣": {"non_food": true}}}')


def _soft(cycle=None, goals=None):
    return {"cycle": cycle or {}, "goals": goals or {}}


@pytest.mark.parametrize(("raw", "fragment"), [
    (_soft(cycle={"menstrual": [{"tags": ["nope"], "effect": "caution", "tradition": False,
                                 "tip_id": "menstrual-warm", "message": "m"}]}), "nope"),
    (_soft(cycle={"menstrual": [{"tags": ["spicy"], "effect": "caution", "tradition": False,
                                 "tip_id": "no-such-tip", "message": "m"}]}), "no-such-tip"),
    (_soft(cycle={"winter": [{"tags": ["spicy"], "effect": "caution", "tradition": False,
                              "tip_id": "menstrual-warm", "message": "m"}]}), "winter"),
    (_soft(goals={"bulk": [{"tags": ["spicy"], "effect": "caution", "message": "m"}]}), "bulk"),
])
def test_soft_rules_parser_rejects_unknown_references(raw, fragment):
    from app.nutrition.rules import parse_soft_rules

    with pytest.raises(ValueError, match=fragment):
        parse_soft_rules(raw)


def test_vocabulary_parser_rejects_unknown_tag():
    from app.nutrition.rules import parse_vocabulary

    with pytest.raises(ValueError, match="nope"):
        parse_vocabulary({"terms": {"怪": {"tags": ["nope"]}}})


def test_tag_entry_loader_is_public():
    from app.nutrition.catalog import load_tag_entries

    assert "spicy" in {entry.id for entry in load_tag_entries()}


# ---- Fix round 2: subjects not in the vocabulary ----


def _real_medical(subjects, name):
    from app.nutrition.catalog import load_catalog

    context = EvaluationContext(constraints=(_avoid("m", "医嘱原文", subjects),))
    result = evaluate_food(_real(name), 100, context, load_catalog())
    return result.conclusion, [r.effect for r in result.reasons if r.source == "medical"]


@pytest.mark.parametrize(("subjects", "name", "expected"), [
    (["牛羊肉"], "羊肉", (NOT_RECOMMENDED, ["block"])),
    (["牛羊肉"], "牛肉", (CAUTION, ["unverifiable"])),
    (["猪牛羊肉"], "牛肉", (CAUTION, ["unverifiable"])),
    (["猪牛羊肉"], "猪肉", (CAUTION, ["unverifiable"])),
    (["葡萄柚"], "葡萄", (SUITABLE, [])),
    (["葡萄柚"], "葡萄柚", (NOT_RECOMMENDED, ["block"])),
    (["咖啡因"], "可乐", (NOT_RECOMMENDED, ["block"])),
    (["红肉"], "牛肉", (NOT_RECOMMENDED, ["block"])),
    (["菠菜"], "米饭", (SUITABLE, [])),
    (["菠菜"], "菠菜", (NOT_RECOMMENDED, ["block"])),
    (["白粥"], "白粥", (NOT_RECOMMENDED, ["block"])),
])
def test_real_catalog_unknown_subjects(subjects, name, expected):
    assert _real_medical(subjects, name) == expected


def test_vocabulary_has_caffeine_and_red_meat():
    from app.nutrition.rules import load_vocabulary

    vocabulary = load_vocabulary()
    assert vocabulary.lookup("咖啡因").tags == ("caffeine",)
    assert vocabulary.lookup("红肉").tags == ("red_meat",)


def test_personal_avoidance_of_compound_subject_ignores_unverifiable():
    from app.nutrition.catalog import load_catalog

    catalog = load_catalog()
    context = EvaluationContext(food_avoidances=("牛羊肉",), needs=NEEDS)
    lamb = evaluate_food(_real("羊肉"), 100, context, catalog)
    assert [(r.source, r.effect) for r in lamb.reasons] == [("preference", "caution")]
    beef = evaluate_food(_real("牛肉"), 100, context, catalog)
    assert beef.reasons == () and beef.conclusion == SUITABLE
    grape = evaluate_food(_real("葡萄"), 100, EvaluationContext(food_avoidances=("葡萄柚",), needs=NEEDS), catalog)
    assert grape.reasons == ()


# ---- Final fix wave: dishes are hit through their recipe ingredients ----


def _extracted(text):
    """把医嘱原文交给规则抽取器，再按抽取出的条目组装硬约束（与线上流程一致）。"""
    from datetime import date

    from app.medical.extraction import RuleBasedExtractor

    items = RuleBasedExtractor().extract(text, date(2026, 10, 6)).items
    assert items, text
    return tuple(HardConstraint(f"m{i}", item.category, item.content, tuple(item.subjects))
                 for i, item in enumerate(items))


def _real_food(name_or_id):
    from app.nutrition.catalog import load_catalog

    catalog = load_catalog()
    return catalog.get(name_or_id) if ":" in name_or_id else catalog.search(name_or_id)[0].food


def _order_result(text, name_or_id, **kwargs):
    from app.nutrition.catalog import load_catalog

    context = EvaluationContext(constraints=_extracted(text), **kwargs)
    return evaluate_food(_real_food(name_or_id), 100, context, load_catalog())


DISH_PROBES = [
    ("忌花生。", "宫保鸡丁"),
    *[("忌猪肉。", name) for name in ("红烧肉", "回锅肉", "鱼香肉丝", "青椒肉丝", "糖醋排骨", "冬瓜排骨汤", "馄饨",
                                     "炸酱面", "炒面", "干煸四季豆", "麻辣烫")],
    *[("忌鸡蛋。", name) for name in ("茶叶蛋", "紫菜蛋花汤", "炸鸡")],
    ("忌牛肉。", "麻婆豆腐"), ("忌牛肉。", "火锅"), ("忌羊肉。", "火锅"), ("忌菠菜。", "麻辣烫"),
]


@pytest.mark.parametrize(("text", "name"), DISH_PROBES)
def test_avoid_order_hits_dish_through_recipe_ingredient(text, name):
    result = _order_result(text, name)
    assert result.conclusion == NOT_RECOMMENDED, (text, name, result.reasons)
    assert any(r.effect == "block" and r.code == "avoid_match" and "菜品配方含「" in r.message
               for r in result.reasons), result.reasons


def test_ingredient_hit_message_names_ingredient_order_and_subject():
    [block] = [r for r in _order_result("忌花生。", "宫保鸡丁").reasons if r.effect == "block"]
    assert block.message.startswith("菜品配方含「花生仁（油炸）」，与医嘱「")
    assert "中的「花生」相符" in block.message and block.message.endswith("不建议食用。")


SINGLE_FOOD_ORDERS = ("花生", "猪肉", "牛肉", "羊肉", "鸡蛋", "菠菜", "辣椒", "酒", "咖啡")


@pytest.mark.parametrize("subject", SINGLE_FOOD_ORDERS)
def test_every_dish_with_a_blocked_ingredient_is_blocked(subject):
    """真实营养库矩阵：菜品配方里任何一个食材本身被这条医嘱判为不建议，菜品也必须是不建议。"""
    from app.nutrition.catalog import load_catalog

    catalog = load_catalog()
    context = EvaluationContext(constraints=(_avoid("m", f"忌{subject}", [subject]),))
    dishes = [food for food in catalog.foods.values() if food.kind == "dish"]
    assert len(dishes) >= 40 and all(dish.ingredients for dish in dishes)
    missed, hit = [], 0
    for dish in dishes:
        blocked = [catalog.get(i).name for i in dish.ingredients
                   if evaluate_food(catalog.get(i), 100, context, catalog).conclusion == NOT_RECOMMENDED]
        if blocked:
            hit += 1
            if evaluate_food(dish, 100, context, catalog).conclusion != NOT_RECOMMENDED:
                missed.append((dish.name, blocked))
    assert missed == []
    if subject != "酒":  # 目前没有菜品用到酒
        assert hit > 0


def test_non_inherited_ingredient_tags_do_not_block_dishes():
    """油、糖、盐这些调料自己带的营养类、饮食类标签（高脂肪、高糖、高钠）只描述每 100 克调料，不让菜品命中。"""
    assert _order_result("一周内忌食辛辣、油腻食物。", "清炒西兰花").conclusion == SUITABLE
    assert _order_result("忌甜食。", "番茄炒蛋").conclusion == SUITABLE
    assert _order_result("忌高盐食物。", "清炒西兰花").conclusion == SUITABLE


def test_personal_avoidance_hits_dish_through_ingredient():
    from app.nutrition.catalog import load_catalog

    context = EvaluationContext(food_avoidances=("花生",), needs=NEEDS)
    result = evaluate_food(_real_food("宫保鸡丁"), 100, context, load_catalog())
    [reason] = result.reasons
    assert (reason.source, reason.effect, reason.code) == ("preference", "caution", "avoidance_match")
    assert "菜品配方含「花生仁（油炸）」" in reason.message


@pytest.mark.parametrize(("text", "name_or_id", "expected"), [
    ("忌猪肉。", "cfcd:081131", NOT_RECOMMENDED),  # 名称里没有"猪肉"的猪小排，按含猪肉标签命中
    ("忌猪肉。", "火腿肠", NOT_RECOMMENDED),
    ("忌猪肉。", "牛肉", SUITABLE),
    ("忌牛肉。", "牛肚", NOT_RECOMMENDED),
    ("忌牛肉。", "猪肉", SUITABLE),
    ("忌羊肉。", "羊肝", NOT_RECOMMENDED),
    ("忌羊肉。", "鸡胸肉", SUITABLE),
])
def test_pork_beef_and_mutton_orders_cover_the_whole_subcategory(text, name_or_id, expected):
    assert _order_result(text, name_or_id).conclusion == expected


# ---- Final fix wave: vocabulary, new tags and embedded vocabulary terms ----


VOCABULARY_PROBES = [
    # 红肉只对应畜肉，不再拦禽肉
    ("少吃红肉，多吃白肉。", "鸡腿", SUITABLE),
    ("少吃红肉，多吃白肉。", "炸鸡", SUITABLE),
    ("少吃红肉，多吃白肉。", "宫保鸡丁", SUITABLE),
    ("少吃红肉，多吃白肉。", "牛肉", NOT_RECOMMENDED),
    ("少吃红肉，多吃白肉。", "红烧肉", NOT_RECOMMENDED),
    ("少吃红肉，多吃白肉。", "猪肝", NOT_RECOMMENDED),
    # 葡萄柚汁不再按"葡萄"误拦葡萄
    ("服用他汀期间避免食用葡萄柚或饮用葡萄柚汁。", "葡萄", SUITABLE),
    ("服用他汀期间避免食用葡萄柚或饮用葡萄柚汁。", "cfcd:064303", NOT_RECOMMENDED),
    ("服用他汀期间避免食用葡萄柚或饮用葡萄柚汁。", "cfcd:064304", NOT_RECOMMENDED),
    ("服用他汀期间避免食用葡萄柚或饮用葡萄柚汁。", "cfcd:064301", SUITABLE),  # 柚（文旦）不是葡萄柚
    # 单字说法只按标签与完全相同的名称命中，不再按字面片段误拦
    ("忌鱼。", "鱼香肉丝", SUITABLE),
    ("忌鱼。", "鱼腥草", SUITABLE),
    ("忌鱼。", "红烧鱼", NOT_RECOMMENDED),
    ("忌鱼。", "带鱼", NOT_RECOMMENDED),
    ("忌鱼。", "麻辣烫", NOT_RECOMMENDED),  # 配方里有鱼丸
    ("忌鱼。", "白灼虾", SUITABLE),  # 只对应鱼，不含虾蟹贝
    ("忌奶。", "奶白菜", SUITABLE),
    ("忌奶。", "豆奶", SUITABLE),
    ("忌奶。", "牛奶", NOT_RECOMMENDED),
    ("忌奶。", "奶茶", NOT_RECOMMENDED),
    ("忌茶。", "茶树菇", SUITABLE),
    ("忌茶。", "茶油", SUITABLE),
    ("忌茶。", "茶水", NOT_RECOMMENDED),
    ("忌茶。", "咖啡", NOT_RECOMMENDED),
    ("忌肉。", "桂圆肉", SUITABLE),
    ("忌肉。", "猪肉", NOT_RECOMMENDED),
    ("忌肉。", "宫保鸡丁", NOT_RECOMMENDED),
    ("忌蛋。", "鸡蛋", NOT_RECOMMENDED),
    ("忌蛋。", "蛋糕", NOT_RECOMMENDED),
    ("忌蛋。", "米饭", SUITABLE),
    ("忌水。", "饺子", SUITABLE),
    ("忌水。", "年糕", SUITABLE),
    ("忌水。", "水煮鱼", SUITABLE),
    ("忌酒。", "啤酒", NOT_RECOMMENDED),
    ("忌酒。", "酒枣", NOT_RECOMMENDED),
    # 常见类别说法
    ("忌鸡蛋。", "蛋糕", NOT_RECOMMENDED),
    ("忌鱼类。", "带鱼", NOT_RECOMMENDED),
    ("忌鱼类。", "红烧鱼", NOT_RECOMMENDED),
    ("忌鱼类。", "虾", SUITABLE),
    ("忌海产品。", "白灼虾", NOT_RECOMMENDED),
    ("忌海产品。", "虾", NOT_RECOMMENDED),
    ("忌蛋类。", "鸡蛋", NOT_RECOMMENDED),
    ("忌蛋类。", "番茄炒蛋", NOT_RECOMMENDED),
    ("忌豆类、豆制品。", "豆腐", NOT_RECOMMENDED),
    ("忌豆类、豆制品。", "豆腐干", NOT_RECOMMENDED),
    ("忌豆类、豆制品。", "豆浆", NOT_RECOMMENDED),
    ("忌豆类、豆制品。", "麻婆豆腐", NOT_RECOMMENDED),
    ("忌豆类、豆制品。", "米饭", SUITABLE),
    ("忌乳制品。", "酸奶", NOT_RECOMMENDED),
    ("忌乳制品。", "豆浆", SUITABLE),
    ("忌奶制品。", "酸奶", NOT_RECOMMENDED),
    ("忌牛奶。", "酸奶", NOT_RECOMMENDED),
    ("忌坚果。", "核桃", NOT_RECOMMENDED),
    ("忌坚果。", "宫保鸡丁", NOT_RECOMMENDED),
    ("忌坚果。", "米饭", SUITABLE),
    ("忌腌制品。", "咸鸭蛋", NOT_RECOMMENDED),
    ("忌腌制食品。", "咸鸭蛋", NOT_RECOMMENDED),
    ("忌烧烤。", "米饭", CAUTION),  # 没有对应的标签，仍是无法判断
    # 刺激性不只是辛辣
    ("禁食生冷、刺激性食物。", "咖啡", NOT_RECOMMENDED),
    ("禁食生冷、刺激性食物。", "啤酒", NOT_RECOMMENDED),
    ("禁食生冷、刺激性食物。", "麻婆豆腐", NOT_RECOMMENDED),
    ("禁食生冷、刺激性食物。", "米饭", SUITABLE),
]


@pytest.mark.parametrize(("text", "name_or_id", "expected"), VOCABULARY_PROBES)
def test_vocabulary_probes_from_extractor_text(text, name_or_id, expected):
    result = _order_result(text, name_or_id)
    assert result.conclusion == expected, (text, name_or_id, result.reasons)


def test_grapefruit_order_leaves_grapes_without_any_medical_reason():
    result = _order_result("服用他汀期间避免食用葡萄柚或饮用葡萄柚汁。", "葡萄")
    assert [r for r in result.reasons if r.source == "medical"] == []


def test_embedded_vocabulary_terms_block_their_tags_and_others_are_unverifiable():
    text = "忌高嘌呤食物如动物内脏。"
    assert [c.subjects for c in _extracted(text)] == [("高嘌呤食物如动物内脏",)]
    liver = _order_result(text, "猪肝")
    assert liver.conclusion == NOT_RECOMMENDED
    assert any("高嘌呤" in r.message and "动物内脏" in r.message for r in liver.reasons if r.effect == "block")
    assert _order_result(text, "火锅").conclusion == NOT_RECOMMENDED  # 火锅显式声明高嘌呤
    rice = _order_result(text, "米饭")
    assert (rice.conclusion, [(r.effect, r.code) for r in rice.reasons if r.source == "medical"]) == (
        CAUTION, [("unverifiable", "avoid_unverifiable")])


def test_embedded_scan_ignores_single_character_terms():
    from app.nutrition.rules import load_vocabulary

    vocabulary = load_vocabulary()
    assert vocabulary.embedded("高嘌呤食物如动物内脏") == ("内脏", "动物内脏", "嘌呤", "高嘌呤")
    assert vocabulary.embedded("鱼腥草汁") == ()


def test_diabetes_diet_cautions_staples_and_blocks_sugar():
    text = "糖尿病饮食。"
    rice = _order_result(text, "米饭")
    assert rice.conclusion == CAUTION
    [reason] = [r for r in rice.reasons if r.source == "medical"]
    assert (reason.effect, reason.code) == ("caution", "require_caution")
    assert "糖尿病饮食" in reason.message and "控制" in reason.message and "快消化碳水" in reason.message
    assert _order_result(text, "可乐").conclusion == NOT_RECOMMENDED
    assert _order_result(text, "清炒西兰花").conclusion == SUITABLE


def test_diabetes_diet_preference_still_cautions_fast_carbs():
    from app.nutrition.catalog import load_catalog

    context = EvaluationContext(diet_preferences=("糖尿病饮食",), needs=NEEDS)
    result = evaluate_food(_real_food("米饭"), 100, context, load_catalog())
    assert [(r.source, r.effect) for r in result.reasons] == [("preference", "caution")]


def test_requirement_cautions_are_validated_against_tags():
    from app.nutrition.rules import VocabularyEntry, parse_vocabulary

    assert VocabularyEntry(violates=("high_sugar",), cautions=("fast_carb",)).referenced_tags() == (
        "high_sugar", "fast_carb")
    with pytest.raises(ValueError, match="nope"):
        parse_vocabulary({"terms": {"怪": {"violates": ["high_sugar"], "cautions": ["nope"]}}})
    with pytest.raises(ValueError):
        VocabularyEntry(tags=("spicy",), cautions=("fast_carb",))



# ---- Final fix wave: reason codes and response types ----


def test_unverifiable_codes_follow_the_order_category():
    liquid_avoid = _evaluate(SPINACH, constraints=(_avoid("m1", "忌流质", ["流质"]),))
    [reason] = [r for r in liquid_avoid.reasons if r.source == "medical"]
    assert (reason.effect, reason.code) == ("unverifiable", "avoid_unverifiable")
    assert "是否属于医嘱「忌流质」中的「流质」" in reason.message
    liquid_require = _evaluate(SPINACH, constraints=(_avoid("m2", "流质饮食", ["流质"], category="diet_require"),))
    [reason] = [r for r in liquid_require.reasons if r.source == "medical"]
    assert (reason.effect, reason.code) == ("unverifiable", "require_unverifiable")
    assert "是否符合医嘱「流质饮食」中的「流质」" in reason.message


def test_response_models_use_literal_values():
    from pydantic import ValidationError

    from app.nutrition.schemas import EvaluationOut, MealEvaluationOut, ReasonOut

    ReasonOut(source="medical", effect="block", code="avoid_match", message="m", ref="r")
    for field, value in [("source", "doctor"), ("effect", "warn")]:
        with pytest.raises(ValidationError):
            ReasonOut(**{"source": "medical", "effect": "block", "code": "c", "message": "m", "ref": "r", field: value})
    nutrients = {"energy_kcal": 1}
    base = {"food_id": "f", "food_name": "n", "grams": 1, "nutrients": nutrients, "reasons": [], "tradeoff": "",
            "data_source": "d", "disclaimer": "x"}
    EvaluationOut(conclusion="caution", **base)
    with pytest.raises(ValidationError):
        EvaluationOut(conclusion="ok", **base)
    with pytest.raises(ValidationError):
        MealEvaluationOut(items=[], conclusion="fine", total=nutrients, disclaimer="x")


def test_ranking_every_food_for_a_five_subject_order_is_fast():
    import time

    from app.nutrition.catalog import load_catalog

    load_catalog.cache_clear()
    catalog = load_catalog()  # 新的营养库实例，名称扫描的缓存从空开始
    context = EvaluationContext(constraints=(
        _avoid("m1", "忌牛羊肉、发物、醋、高嘌呤食物如动物内脏、葡萄柚汁",
               ["牛羊肉", "发物", "醋", "高嘌呤食物如动物内脏", "葡萄柚汁"]),
    ), needs=NEEDS)
    started = time.perf_counter()
    results = [evaluate_food(food, 100, context, catalog) for food in catalog.foods.values()]
    elapsed = time.perf_counter() - started
    assert elapsed < 2, elapsed
    assert len(results) == len(catalog.foods)


# ---- Follow-up (Ruling 12): vocabulary subjects never match recipe ingredient names ----


SALTED = ("cfcd:081308", "cfcd:081305", "cfcd:081409")  # 咸肉、腊肉（生）、火腿肠

FOLLOWUP_PROBES = [
    # 1. 词汇表说法只按食物自己的标签与名称、以及配方食材会被菜品继承的标签命中
    *[(text, name, expected) for text in ("少吃盐。", "限盐。") for name, expected in [
        ("食盐", NOT_RECOMMENDED), ("酱油", NOT_RECOMMENDED), ("咸鸭蛋", NOT_RECOMMENDED),
        ("清炒西兰花", SUITABLE), ("凉拌黄瓜", SUITABLE), ("番茄炒蛋", SUITABLE), ("米饭", SUITABLE)]],
    ("忌醋。", "醋溜白菜", NOT_RECOMMENDED),  # 不在词汇表里的说法仍按配方食材名称命中
    ("忌醋。", "米饭", CAUTION),
    ("忌白糖。", "番茄炒蛋", NOT_RECOMMENDED),
    ("忌酱油。", "红烧肉", NOT_RECOMMENDED),
    ("忌牛奶。", "cfcd:011410", NOT_RECOMMENDED),  # 花卷（加牛奶）
    ("忌油炸食物。", "宫保鸡丁", NOT_RECOMMENDED),  # 菜品显式声明油炸（油炸花生仁）
    ("忌油炸食物。", "炸鸡", NOT_RECOMMENDED),
    # 2. 腌腊制品
    *[(text, food_id, NOT_RECOMMENDED) for text in ("忌咸。", "少吃盐。", "低盐饮食。", "忌腌制食品。")
      for food_id in SALTED],
    ("少吃盐。", "麻辣烫", NOT_RECOMMENDED),  # 配方里的火腿肠，继承腌腊制品
    # 3. 具体的禽、鱼、虾蟹贝、菌类
    *[("忌鸡肉。", name, NOT_RECOMMENDED) for name in ("鸡腿", "鸡胸肉", "宫保鸡丁", "炸鸡", "可乐鸡翅")],
    ("忌鸡肉。", "鸡蛋", SUITABLE), ("忌鸡肉。", "番茄炒蛋", SUITABLE),
    *[("忌鸡。", name, NOT_RECOMMENDED) for name in ("鸡腿", "宫保鸡丁", "可乐鸡翅")],
    ("忌鸡。", "鸡蛋", SUITABLE), ("忌鸡。", "番茄炒蛋", SUITABLE),
    ("忌鸭肉。", "烤鸭", NOT_RECOMMENDED), ("忌鸭肉。", "鸭肉", NOT_RECOMMENDED), ("忌鸭肉。", "咸鸭蛋", SUITABLE),
    ("忌禽肉。", "鸭肉", NOT_RECOMMENDED), ("忌禽肉。", "鸡腿", NOT_RECOMMENDED), ("忌禽肉。", "牛肉", SUITABLE),
    *[("忌鱼肉。", name, NOT_RECOMMENDED) for name in ("带鱼", "草鱼", "红烧鱼", "清蒸鱼")],
    ("忌鱼肉。", "cfcd:129013", SUITABLE),  # 章鱼不是鱼
    ("忌虾仁。", "白灼虾", NOT_RECOMMENDED), ("忌虾仁。", "虾", NOT_RECOMMENDED), ("忌虾仁。", "带鱼", SUITABLE),
    ("忌螃蟹。", "螃蟹", NOT_RECOMMENDED), ("忌蟹。", "螃蟹", NOT_RECOMMENDED),
    ("忌贝类。", "扇贝", NOT_RECOMMENDED), ("忌贝类。", "虾", SUITABLE),
    ("忌蘑菇。", "香菇", NOT_RECOMMENDED), ("忌蘑菇。", "金针菇", NOT_RECOMMENDED), ("忌蘑菇。", "麻辣烫", NOT_RECOMMENDED),
    ("忌蘑菇。", "米饭", SUITABLE),
    ("忌鱼虾。", "带鱼", NOT_RECOMMENDED), ("忌鱼虾。", "虾", NOT_RECOMMENDED),
    ("忌豆。", "豆腐", NOT_RECOMMENDED), ("忌豆。", "麻婆豆腐", NOT_RECOMMENDED),
    ("忌豆。", "地三鲜", SUITABLE), ("忌豆。", "酸辣土豆丝", SUITABLE), ("忌豆。", "清炒西兰花", SUITABLE),
    # 4. 数据补漏
    ("忌肉。", "cfcd:011503", NOT_RECOMMENDED),  # 面筋（肉馅）
    ("忌甜食。", "cfcd:011407", NOT_RECOMMENDED),  # 烧饼（加糖）
    # 5. 说法的前缀与"其制品"
    ("忌食花生及其制品。", "宫保鸡丁", NOT_RECOMMENDED), ("忌食花生及其制品。", "花生", NOT_RECOMMENDED),
    ("忌食花生及其制品。", "米饭", SUITABLE),
    ("忌吃鸡肉。", "鸡腿", NOT_RECOMMENDED), ("忌吃鸡肉。", "鸡蛋", SUITABLE),
    ("忌喝酒。", "啤酒", NOT_RECOMMENDED), ("忌喝酒。", "米饭", SUITABLE),
]


@pytest.mark.parametrize(("text", "name_or_id", "expected"), FOLLOWUP_PROBES)
def test_followup_probes_from_extractor_text(text, name_or_id, expected):
    result = _order_result(text, name_or_id)
    assert result.conclusion == expected, (text, name_or_id, result.reasons)


def test_vocabulary_subject_never_matches_recipe_ingredient_names():
    """"盐"在词汇表里：配方里的食盐（名称就是"盐"）不让菜品命中；只有菜品会继承的标签才算。"""
    result = _order_result("少吃盐。", "番茄炒蛋")
    assert [r for r in result.reasons if r.source == "medical"] == []
    eggs = _order_result("忌鸡蛋。", "茶叶蛋")  # 鸡蛋按继承的含蛋标签命中，依据仍列出配方食材
    assert any("菜品配方含「鸡蛋（代表值）」" in r.message for r in eggs.reasons if r.effect == "block")


def test_subject_prefix_is_stripped_but_vocabulary_terms_and_food_names_are_kept():
    from app.nutrition.catalog import load_catalog
    from app.nutrition.engine import subject_term
    from app.nutrition.rules import load_vocabulary

    vocabulary, catalog = load_vocabulary(), load_catalog()
    assert subject_term("吃鸡肉", vocabulary, catalog) == "鸡肉"
    assert subject_term("食用 花生", vocabulary, catalog) == "花生"
    assert subject_term("喝酒", vocabulary, catalog) == "酒"
    assert subject_term("吃素", vocabulary, catalog) == "吃素"  # 词汇表里的要求类说法
    assert subject_term("饮用水", vocabulary, catalog) == "饮用水"  # 营养库里的食物名称
    assert _real_conclusion("diet_require", ["吃素"], "鸡腿") == NOT_RECOMMENDED


def test_personal_avoidance_prefix_is_stripped():
    from app.nutrition.catalog import load_catalog

    context = EvaluationContext(food_avoidances=("吃鸡肉",), needs=NEEDS)
    result = evaluate_food(_real_food("鸡腿"), 100, context, load_catalog())
    assert [(r.source, r.effect) for r in result.reasons] == [("preference", "caution")]


# ---- 第三批跟进：少盐、少油、方腿、腌腊制品、食用菌 ----


def test_shaoyan_diet_order_from_extractor_text():
    text = "清淡少盐饮食。"
    assert _order_result(text, "火腿肠").conclusion == NOT_RECOMMENDED
    assert _order_result(text, "咸鸭蛋").conclusion == NOT_RECOMMENDED
    assert _order_result(text, "清炒西兰花").conclusion == SUITABLE
    assert _order_result("少油饮食。", "炸鸡").conclusion == NOT_RECOMMENDED
    assert _order_result("少油饮食。", "米饭").conclusion == SUITABLE


def test_luncheon_ham_is_cured_and_blocked_by_low_salt():
    assert "cured" in _real_food("方腿").tags
    assert _order_result("低盐饮食。", "方腿").conclusion == NOT_RECOMMENDED


@pytest.mark.parametrize(("subject", "blocked", "name"), [
    ("腌腊制品", "咸肉", "米饭"), ("食用菌", "香菇", "米饭"),
])
def test_cured_and_edible_fungi_subjects_are_vocabulary_terms(subject, blocked, name):
    assert _real_conclusion("diet_avoid", [subject], blocked) == NOT_RECOMMENDED
    assert _real_conclusion("diet_avoid", [subject], name) == SUITABLE
