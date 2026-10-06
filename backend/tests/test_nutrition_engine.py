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
    assert vocabulary.lookup("低盐饮食").violates == ("high_sodium",)
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
    assert vocabulary.lookup("辛辣刺激性食物").tags == ("spicy",)


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
    assert vocabulary.lookup("红肉").tags == ("meat",)


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
