"""第一阶段整体验收的修复：忌生冷时新鲜水果不再被静默放行，冷热不确定的饮品给无法判断。

新鲜水果是单独的 fresh_fruit 标签，只有“生冷”“生冷食物”对应它；raw_cold 的成员与经期提示保持不变。
"""

from datetime import date

import pytest

from app.medical.extraction import RuleBasedExtractor
from app.nutrition.catalog import load_catalog
from app.nutrition.engine import (
    CAUTION,
    NOT_RECOMMENDED,
    SUITABLE,
    EvaluationContext,
    HardConstraint,
    evaluate_food,
)
from app.nutrition.needs import Needs

ORDER_TEXT = "两周内忌食辛辣、生冷食物，避免剧烈运动。"
NEEDS = Needs(status="ok", energy_kcal=1800, energy_kcal_low=1600, energy_kcal_high=2000, protein_g=60,
              sodium_mg_max=2000)
FRUIT_CATEGORY = "水果类及其制品"
DRINK_CATEGORIES = ("补充-饮料", "补充-酒类", "补充-饮品", "乳类及其制品-液态乳", "乳类及其制品-酸奶")
SOY_DRINKS = {"cfcd:031402": "豆奶", "cfcd:031403": "豆汁（生）", "cfcd:031404": "酸豆奶", "cfcd:031405": "豆浆",
              "cfcd:031406": "豆浆（甜）"}  # 归在干豆类大豆小类里的饮品，按编号列为不确定成员；豆浆粉、豆奶粉不算
RAW_COLD_MEMBERS = {"supplement:ice_cream", "dish:cucumber_salad", "dish:century_egg_tofu"}  # 与本次修复前相同
# 按名称里的明确字样（干、罐头、糖水、饼、蜜枣）认定为加工或晒干的水果制品，逐个核对过
PROCESSED_FRUITS = {
    "cfcd:061302": "红果（干）", "cfcd:062206": "杏干", "cfcd:062302": "枣（干）", "cfcd:062303": "枣（干，大）",
    "cfcd:062313": "小枣（干）", "cfcd:063107": "葡萄干", "cfcd:063904": "桑葚（干）", "cfcd:063912": "无花果（干）",
    "cfcd:065007": "桂圆（干）", "cfcd:065021": "桂圆（干）", "cfcd:065024": "荔枝（干）",
    "cfcd:061119": "苹果（罐头）", "cfcd:061228": "冬果梨（罐头）", "cfcd:061229": "梨（糖水罐头）",
    "cfcd:061902": "海棠（罐头）", "cfcd:062116": "桃（糖水罐头）", "cfcd:062205": "杏（罐头）",
    "cfcd:063304": "柿饼", "cfcd:064211": "橘饼", "cfcd:062310": "蜜枣",
}
PROCESSED_MARKERS = ("干", "罐头", "糖水", "脯", "蜜饯", "酱", "饼", "蜜枣")


def _order():
    items = RuleBasedExtractor().extract(ORDER_TEXT, date(2026, 10, 6)).items
    return tuple(HardConstraint(f"m{i}", item.category, item.content, tuple(item.subjects))
                 for i, item in enumerate(items))


def _evaluate(food_id, grams=100, **kwargs):
    catalog = load_catalog()
    context = EvaluationContext(needs=NEEDS, **kwargs)
    return evaluate_food(catalog.get(food_id), grams, context, catalog)


def _medical(result):
    return [r for r in result.reasons if r.source == "medical"]


def _fruits():
    return [food for food in load_catalog().foods.values() if food.category.startswith(FRUIT_CATEGORY)]


def test_order_extracts_raw_cold_subject():
    [avoid] = [c for c in _order() if c.category == "diet_avoid"]
    assert avoid.subjects == ("辛辣", "生冷食物")


@pytest.mark.parametrize("food_id", ["cfcd:066201x", "cfcd:061101x", "cfcd:065033"])  # 西瓜、苹果、香蕉
def test_fresh_fruit_is_blocked_by_raw_cold_order(food_id):
    constraints = _order()
    [avoid] = [c for c in constraints if c.category == "diet_avoid"]
    result = _evaluate(food_id, 200, constraints=constraints)
    assert result.conclusion == NOT_RECOMMENDED
    blocks = [r for r in _medical(result) if r.effect == "block"]
    assert blocks and {r.ref for r in blocks} == {avoid.item_id}
    assert all("生冷食物" in r.message and "新鲜水果" in r.message and avoid.content in r.message for r in blocks)


@pytest.mark.parametrize("food_id", ["cfcd:063107", "cfcd:061119", "cfcd:062206"])  # 葡萄干、苹果罐头、杏干
def test_processed_fruit_is_not_blocked_as_raw_cold(food_id):
    result = _evaluate(food_id, constraints=_order())
    assert _medical(result) == []
    assert not {"raw_cold", "fresh_fruit"} & load_catalog().get(food_id).tags


DRINKS = ["supplement:cola", "supplement:orange_juice", "supplement:milk_tea", "supplement:coffee", "supplement:latte",
          "supplement:tea", "supplement:beer", "supplement:baijiu", "supplement:red_wine", "supplement:water",
          "cfcd:101101x", "cfcd:103001x", *SOY_DRINKS]  # cfcd:101101x、cfcd:103001x 是纯牛奶（代表值）、酸奶（代表值）


@pytest.mark.parametrize("food_id", DRINKS)
def test_drinks_are_unverifiable_under_raw_cold_order(food_id):
    result = _evaluate(food_id, constraints=_order())
    assert result.conclusion == CAUTION
    [reason] = _medical(result)
    assert (reason.effect, reason.code) == ("unverifiable", "avoid_unverifiable")
    assert "生冷食物" in reason.message and "核对" in reason.message


@pytest.mark.parametrize("subject", ["生冷", "冷饮", "冰"])
@pytest.mark.parametrize("food_id", DRINKS)
def test_drinks_are_unverifiable_under_every_raw_cold_term(subject, food_id):
    result = _evaluate(food_id, constraints=(HardConstraint("m1", "diet_avoid", f"忌{subject}", (subject,)),))
    [reason] = _medical(result)
    assert (reason.effect, reason.code) == ("unverifiable", "avoid_unverifiable")
    assert reason.message == f"无法自动判断这个食物是否属于医嘱「忌{subject}」中的「{subject}」，请自行核对或咨询医生。"
    assert result.conclusion == CAUTION


def test_profile_avoidance_of_raw_cold_cautions_fresh_fruit_but_not_uncertain_drinks():
    for food_id in ("cfcd:066201x", "cfcd:061101x", "cfcd:065033"):
        result = _evaluate(food_id, food_avoidances=("生冷",))
        assert result.conclusion == CAUTION
        [reason] = result.reasons
        assert (reason.source, reason.effect, reason.code, reason.ref) == (
            "preference", "caution", "avoidance_match", "生冷")
        assert "新鲜水果" in reason.message
    for food_id in DRINKS:
        assert _evaluate(food_id, food_avoidances=("生冷",)).reasons == (), food_id
    assert _evaluate("cfcd:063107", food_avoidances=("生冷",)).reasons == ()  # 葡萄干


@pytest.mark.parametrize("subject", ["冷饮", "冰"])
def test_cold_drink_and_ice_orders_do_not_block_fresh_fruit(subject):
    order = (HardConstraint("m1", "diet_avoid", f"忌{subject}", (subject,)),)
    for food_id in ("cfcd:066201x", "cfcd:061101x", "cfcd:065033"):
        assert _medical(_evaluate(food_id, constraints=order)) == []
    assert _evaluate("supplement:ice_cream", constraints=order).conclusion == NOT_RECOMMENDED


@pytest.mark.parametrize("food_id", ["supplement:ice_cream", "dish:cucumber_salad"])
def test_existing_raw_cold_foods_stay_blocked(food_id):
    result = _evaluate(food_id, constraints=_order())
    assert result.conclusion == NOT_RECOMMENDED
    assert any(r.effect == "block" and "生冷" in r.message for r in _medical(result))


def test_cooked_dish_with_a_drink_ingredient_is_not_affected():
    assert _medical(_evaluate("dish:cola_wings", constraints=_order())) == []


@pytest.mark.parametrize("food_id", ["cfcd:066201x", "cfcd:061101x", "cfcd:065033", "supplement:cola"])
def test_without_raw_cold_order_fruit_and_drink_have_no_medical_reason(food_id):
    assert _medical(_evaluate(food_id)) == []
    spicy_only = (HardConstraint("m1", "diet_avoid", "忌辛辣", ("辛辣",)),)
    assert _medical(_evaluate(food_id, constraints=spicy_only)) == []


def test_apple_without_any_constraint_is_still_suitable():
    result = _evaluate("cfcd:061101x")
    assert (result.conclusion, result.reasons) == (SUITABLE, ())


def test_fresh_fruit_covers_most_fruit_entries_and_raw_cold_is_unchanged():
    fruits = _fruits()
    tagged = [food for food in fruits if "fresh_fruit" in food.tags]
    assert len(fruits) == 182
    assert len(tagged) >= 160 and len(tagged) / len(fruits) >= 0.85
    foods = load_catalog().foods.values()
    assert {food.id for food in foods if "fresh_fruit" in food.tags} == {food.id for food in tagged}
    assert {food.id for food in foods if "raw_cold" in food.tags} == RAW_COLD_MEMBERS


def test_processed_fruit_exclusions_are_exactly_the_reviewed_list():
    catalog = load_catalog()
    untagged = {food.id: food.name for food in _fruits() if "fresh_fruit" not in food.tags}
    assert untagged == PROCESSED_FRUITS
    for food_id, name in PROCESSED_FRUITS.items():
        assert catalog.get(food_id).name == name
        assert any(marker in name for marker in PROCESSED_MARKERS), name
    # 名称里有这些字样的水果都被排除；“粉”只出现在白粉桃、石榴（红粉皮）这两个新鲜品种里，仍算新鲜水果
    for food in _fruits():
        if any(marker in food.name for marker in PROCESSED_MARKERS):
            assert food.id in PROCESSED_FRUITS, food.name
    assert "fresh_fruit" in catalog.get("cfcd:062102").tags and "fresh_fruit" in catalog.get("cfcd:063202").tags
    # 拿不准的几种枣、桂圆肉、酒枣仍算新鲜水果
    for food_id in ("cfcd:062304", "cfcd:062305", "cfcd:062306", "cfcd:062307", "cfcd:062308", "cfcd:065008",
                    "cfcd:062309"):
        assert "fresh_fruit" in catalog.get(food_id).tags, food_id


def test_only_drink_categories_and_soy_drinks_are_uncertain_raw_cold():
    catalog = load_catalog()
    foods = catalog.foods.values()
    uncertain = {food.id for food in foods if "raw_cold" in food.uncertain_tags}
    drinks = {food.id for food in foods if food.category in DRINK_CATEGORIES}
    assert {food.category for food in foods if food.id in drinks} == set(DRINK_CATEGORIES)
    assert {food_id: catalog.get(food_id).name for food_id in SOY_DRINKS} == SOY_DRINKS
    drinks |= set(SOY_DRINKS)
    assert uncertain == drinks
    assert all("raw_cold" not in load_catalog().get(food_id).tags for food_id in drinks)


def test_menstrual_phase_results_for_fruit_and_drinks_are_unchanged():
    # 与本分支之前的 main 相同：苹果没有任何依据，西瓜只因寒凉得到经期谨慎，饮品不因生冷得到经期提示
    assert _evaluate("cfcd:061101x", cycle_phase="menstrual").reasons == ()
    assert _evaluate("cfcd:061101x", cycle_phase="menstrual").conclusion == SUITABLE
    melon = _evaluate("cfcd:066201x", cycle_phase="menstrual")
    [reason] = melon.reasons
    assert (melon.conclusion, reason.source, reason.ref) == (CAUTION, "cycle", "menstrual-warm")
    assert reason.message.endswith("（这个食物：寒凉（传统经验））。")
    for food_id in ("supplement:cola", "cfcd:101101x", "supplement:water"):
        assert not any(r.ref == "menstrual-warm" for r in _evaluate(food_id, cycle_phase="menstrual").reasons)
