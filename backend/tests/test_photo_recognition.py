import json

import pytest

from app.errors import AppError
from app.nutrition.catalog import NUTRIENT_FIELDS, load_catalog, round_one
from app.photos.matching import (
    MAX_CANDIDATES,
    REVIEW_REASONS,
    build_item,
    needs_review,
    totals,
)
from app.photos.portions import Portion, load_units, parse_portion, portion_grams
from app.photos.recognition import (
    MAX_ITEMS,
    RECOGNITION_PROMPT,
    RETRY_PROMPT,
    RecognitionFormatError,
    parse_output,
)

CATALOG = load_catalog()
TOMATO_EGG = CATALOG.get("dish:tomato_egg")
RICE = CATALOG.get("cfcd:012401x")
OK_JSON = json.dumps({
    "status": "ok",
    "items": [{"name": "番茄炒蛋", "portion": "一盘", "grams": 250, "confidence": 0.8}],
    "note": "",
}, ensure_ascii=False)


# ---------- 输出解析 ----------

def test_parse_plain_json():
    out = parse_output(OK_JSON)
    assert out.status == "ok"
    assert out.items[0].name == "番茄炒蛋"
    assert out.items[0].portion_text == "一盘"
    assert out.items[0].grams_estimate == 250.0
    assert out.items[0].confidence == 0.8


def test_parse_fenced_json():
    assert parse_output(f"```json\n{OK_JSON}\n```").items[0].name == "番茄炒蛋"


def test_parse_json_surrounded_by_text():
    out = parse_output(f"好的，识别结果如下：\n{OK_JSON}\n希望有帮助 {{不是 JSON}}")
    assert out.items[0].name == "番茄炒蛋"


def test_parse_skips_a_broken_brace_before_the_object():
    assert parse_output(f"{{oops {OK_JSON}").status == "ok"


@pytest.mark.parametrize("status", ["maybe", "", None, 3])
def test_parse_rejects_bad_status(status):
    with pytest.raises(RecognitionFormatError):
        parse_output(json.dumps({"status": status, "items": []}))


@pytest.mark.parametrize("text", ["", "没有 JSON", "[1, 2]", '{"items": []}', "{broken"])
def test_parse_rejects_missing_json(text):
    with pytest.raises(RecognitionFormatError):
        parse_output(text)


def test_parse_not_food_and_unclear_have_no_items():
    assert parse_output('{"status": "not_food", "items": [], "note": "是一只猫"}').note == "是一只猫"
    assert parse_output('{"status": "unclear"}').items == ()


def test_parse_keeps_at_most_twelve_items():
    items = [{"name": f"菜{i}", "portion": "一份", "grams": 100, "confidence": 0.9} for i in range(20)]
    out = parse_output(json.dumps({"status": "ok", "items": items}, ensure_ascii=False))
    assert len(out.items) == MAX_ITEMS == 12
    assert out.items[-1].name == "菜11"


def test_parse_drops_empty_names_before_capping():
    items = [{"name": "  "}, {"portion": "一碗"}, {"name": None}, "字符串"] + [{"name": f"菜{i}"} for i in range(12)]
    out = parse_output(json.dumps({"status": "ok", "items": items}, ensure_ascii=False))
    assert [item.name for item in out.items] == [f"菜{i}" for i in range(12)]


def test_parse_trims_and_limits_names():
    items = [{"name": "  米饭  "}, {"name": "长" * 50}]
    out = parse_output(json.dumps({"status": "ok", "items": items}, ensure_ascii=False))
    assert out.items[0].name == "米饭"
    assert out.items[1].name == "长" * 30


@pytest.mark.parametrize("grams", ["-50", -50, 0, "多", None, True, [1], "1e999"])
def test_parse_bad_grams_become_none(grams):
    text = json.dumps({"status": "ok", "items": [{"name": "米饭", "grams": grams}]}, ensure_ascii=False)
    assert parse_output(text).items[0].grams_estimate is None


def test_parse_infinite_grams_become_none():
    assert parse_output('{"status": "ok", "items": [{"name": "米饭", "grams": 1e999}]}').items[0].grams_estimate is None


def test_parse_numeric_string_grams():
    out = parse_output('{"status": "ok", "items": [{"name": "米饭", "grams": "150"}]}')
    assert out.items[0].grams_estimate == 150.0


def test_parse_clamps_and_defaults_confidence():
    items = [
        {"name": "甲", "confidence": 1.7}, {"name": "乙", "confidence": -0.2},
        {"name": "丙"}, {"name": "丁", "confidence": "高"}, {"name": "戊", "confidence": 0.3},
    ]
    out = parse_output(json.dumps({"status": "ok", "items": items}, ensure_ascii=False))
    assert [item.confidence for item in out.items] == [1.0, 0.0, 0.5, 0.5, 0.3]


def test_parse_ignores_calorie_and_nutrient_fields():
    raw = {
        "status": "ok", "calories": 999, "energy_kcal": 999,
        "items": [{"name": "米饭", "portion": "一碗", "grams": 150, "confidence": 0.9,
                   "calories": 500, "kcal": 500, "protein": 20, "nutrients": {"fat_g": 9}}],
    }
    out = parse_output(json.dumps(raw))
    assert set(vars(out.items[0])) == {"name", "portion_text", "grams_estimate", "confidence"}
    assert "500" not in repr(out) and "999" not in repr(out)


def test_prompts_forbid_nutrition_numbers_and_ask_for_json_only():
    assert "只输出一段 JSON" in RECOGNITION_PROMPT
    assert "不要给出热量或任何营养数字" in RECOGNITION_PROMPT
    for word in ("status", "items", "name", "portion", "grams", "confidence", "note", "not_food", "unclear"):
        assert word in RECOGNITION_PROMPT
    assert "只输出一段 JSON" in RETRY_PROMPT


# ---------- 份量说法 ----------

@pytest.mark.parametrize(("text", "quantity", "unit"), [
    ("一碗", 1, "碗"), ("两个", 2, "个"), ("半盘", 0.5, "盘"), ("1.5 碗", 1.5, "碗"),
    ("大半碗", 0.7, "碗"), ("一小碗", 1, "小碗"), ("半个手掌", 1, "半个手掌"), ("三块", 3, "块"),
    ("十二串", 12, "串"), ("二十五根", 25, "根"), ("十片", 10, "片"), ("2个", 2, "个"),
    ("大碗", 1, "大碗"), ("半大碗", 0.5, "大碗"), ("小半碗", 0.35, "碗"), ("一碗半", 1.5, "碗"),
    ("一个手掌", 1, "手掌"), ("一拳头", 1, "拳头"), ("约一份", 1, "份"), ("一小盘", 0.7, "盘"),
    ("两勺", 2, "勺"), ("一杯", 1, "杯"), ("一把", 1, "把"), ("一条", 1, "条"), ("一只", 1, "只"),
    ("一碟", 1, "碟"),
])
def test_parse_portion(text, quantity, unit):
    portion = parse_portion(text)
    assert portion is not None
    assert portion.unit == unit
    assert portion.quantity == pytest.approx(quantity)


@pytest.mark.parametrize("text", ["", "   ", "一些", "适量", "很多", "一箱", "碗2", "0碗", "一"])
def test_parse_portion_unknown(text):
    assert parse_portion(text) is None


def test_bowl_of_rice_uses_the_foods_own_portion():
    assert portion_grams(RICE, "一碗", 999) == (150.0, "food_portion")
    assert portion_grams(RICE, "两碗", None) == (300.0, "food_portion")
    assert portion_grams(RICE, "半碗", None) == (75.0, "food_portion")


def test_dish_plate_uses_the_unit_table_dish_group():
    grams, source = portion_grams(TOMATO_EGG, "一盘", None)
    assert source == "unit_table"
    assert grams == load_units()["units"]["盘"]["groups"]["菜肴"]
    assert portion_grams(TOMATO_EGG, "半盘", None)[0] == grams / 2


def test_unit_table_scales_by_quantity_and_rounds_to_whole_grams():
    assert portion_grams(TOMATO_EGG, "大半碗", None) == (140.0, "unit_table")  # 菜肴 碗 200 × 0.7
    assert portion_grams(None, "一盘", None) == (250.0, "unit_table")  # 没有食物时用单位默认值


def test_model_estimate_when_no_portion_text():
    assert portion_grams(TOMATO_EGG, "", 183.4) == (183.0, "model_estimate")
    assert portion_grams(TOMATO_EGG, "一些", 120) == (120.0, "model_estimate")


def test_group_default_when_nothing_else():
    assert portion_grams(TOMATO_EGG, "", None) == (200.0, "group_default")
    assert portion_grams(TOMATO_EGG, "", -5) == (200.0, "group_default")
    assert portion_grams(None, "", None) == (150.0, "group_default")
    assert portion_grams(CATALOG.get("cfcd:061101x"), "", 0) == (150.0, "group_default")


# ---------- 匹配 ----------

def test_matched_dish_has_nutrients_equal_to_hand_calculation():
    item = build_item("番茄炒蛋", "一盘", 250, "model_estimate", 0.9, catalog=CATALOG)
    assert item["status"] == "matched"
    assert item["food_id"] == "dish:tomato_egg"
    assert item["food_name"] == "番茄炒蛋"
    assert item["match_type"] == "exact_name"
    assert item["grams"] == 250
    for field in NUTRIENT_FIELDS:
        per_100 = getattr(TOMATO_EGG.nutrients, field)
        assert item["nutrients"][field] == (None if per_100 is None else round_one(per_100 * 250 / 100))
    assert item["source"] == {
        "dataset": TOMATO_EGG.source.dataset,
        "license_status": TOMATO_EGG.source.license_status,
        "note": TOMATO_EGG.source.note,
    }
    assert item["nutrients"]["energy_kcal"] > 0


def test_rice_is_matched_and_converted_from_its_own_portion():
    item = build_item("米饭", "一碗", None, None, 0.9, catalog=CATALOG)
    assert item["status"] == "matched"
    assert item["food_id"] == "cfcd:012401x"
    assert (item["grams"], item["grams_source"]) == (150.0, "food_portion")
    assert item["nutrients"]["energy_kcal"] == round_one(RICE.nutrients.energy_kcal * 150 / 100)
    assert item["review_reasons"] == []


def test_grams_estimate_is_used_when_portion_is_not_understood():
    item = build_item("番茄炒蛋", "", None, None, 0.9, grams_estimate=180)
    assert (item["grams"], item["grams_source"]) == (180.0, "model_estimate")
    assert item["review_reasons"] == ["estimated_grams"]


def test_similar_only_name_needs_confirmation_without_numbers():
    item = build_item("酸菜鱼", "一份", None, None, 0.9, catalog=CATALOG)
    assert item["status"] == "needs_confirmation"
    assert item["food_id"] is None and item["food_name"] is None and item["match_type"] is None
    assert item["nutrients"] is None and item["source"] is None
    assert item["candidates"] and len(item["candidates"]) <= MAX_CANDIDATES
    assert all(set(candidate) == {"food_id", "name"} for candidate in item["candidates"])
    assert item["grams"] > 0
    assert "needs_confirmation" in item["review_reasons"]


def test_unknown_name_needs_confirmation_with_no_candidates():
    item = build_item("zzqx不存在", "一份", 200, "model_estimate", 0.9, catalog=CATALOG)
    assert item["status"] == "needs_confirmation"
    assert item["candidates"] == []
    assert item["nutrients"] is None


def test_candidates_are_capped():
    item = build_item("鱼", "", None, None, 0.9, catalog=CATALOG)
    assert len(item["candidates"]) <= MAX_CANDIDATES


def test_user_chosen_food_id_is_used_directly():
    item = build_item("酸菜鱼", "一份", 300, "user", 1.0, food_id="dish:boiled_fish", catalog=CATALOG)
    assert item["status"] == "matched"
    assert item["food_id"] == "dish:boiled_fish"
    assert item["food_name"] == "水煮鱼"
    assert item["nutrients"]["energy_kcal"] == round_one(CATALOG.get("dish:boiled_fish").nutrients.energy_kcal * 3)
    assert item["review_reasons"] == []


def test_unknown_food_id_is_a_422():
    with pytest.raises(AppError) as error:
        build_item("酸菜鱼", "", 100, "user", 1.0, food_id="dish:nope")
    assert (error.value.status_code, error.value.code) == (422, "photo_unknown_food")


def test_item_id_is_kept_or_generated():
    assert build_item("米饭", "", 100, "user", 1.0, item_id="abc")["id"] == "abc"
    first, second = build_item("米饭", "", 100, "user", 1.0), build_item("米饭", "", 100, "user", 1.0)
    assert first["id"] and first["id"] != second["id"]


# ---------- 提醒修正 ----------

def test_each_review_reason_triggers_alone():
    assert REVIEW_REASONS == ("low_confidence", "needs_confirmation", "grams_out_of_range", "estimated_grams")

    def reasons(name, grams, source, confidence):
        return build_item(name, "", grams, source, confidence, catalog=CATALOG)["review_reasons"]

    assert reasons("番茄炒蛋", 250, "user", 0.9) == []
    assert reasons("番茄炒蛋", 250, "user", 0.59) == ["low_confidence"]
    assert reasons("番茄炒蛋", 250, "user", 0.6) == []
    assert reasons("酸菜鱼", 250, "user", 0.9) == ["needs_confirmation"]
    assert reasons("番茄炒蛋", 9, "user", 0.9) == ["grams_out_of_range"]
    assert reasons("番茄炒蛋", 10, "user", 0.9) == []
    assert reasons("番茄炒蛋", 1500, "user", 0.9) == []
    assert reasons("番茄炒蛋", 1501, "user", 0.9) == ["grams_out_of_range"]
    assert reasons("番茄炒蛋", 250, "model_estimate", 0.9) == ["estimated_grams"]
    assert reasons("番茄炒蛋", 250, "group_default", 0.9) == ["estimated_grams"]
    assert reasons("番茄炒蛋", 250, "unit_table", 0.9) == []
    assert reasons("番茄炒蛋", 250, "food_portion", 0.9) == []


def test_review_reasons_combine_in_a_fixed_order():
    item = build_item("zzqx不存在", "", 5, "model_estimate", 0.1, catalog=CATALOG)
    assert item["review_reasons"] == list(REVIEW_REASONS)


def test_needs_review_and_totals_only_count_matched():
    good = build_item("米饭", "一碗", None, None, 0.9, catalog=CATALOG)
    other = build_item("番茄炒蛋", "一盘", 250, "user", 0.9, catalog=CATALOG)
    unknown = build_item("酸菜鱼", "一份", None, None, 0.9, catalog=CATALOG)
    assert not needs_review([good, other])
    assert needs_review([good, unknown])
    assert not needs_review([])
    total = totals([good, other, unknown])
    assert total["energy_kcal"] == round_one(good["nutrients"]["energy_kcal"] + other["nutrients"]["energy_kcal"])
    assert total["protein_g"] == round_one(good["nutrients"]["protein_g"] + other["nutrients"]["protein_g"])
    assert totals([unknown])["energy_kcal"] == 0
    assert totals([]) == {field: 0.0 for field in NUTRIENT_FIELDS}


# ---------- 换算表数据 ----------

def test_units_file_covers_required_units_and_groups():
    data = load_units()
    required = "碗 小碗 大碗 份 盘 碟 个 只 块 片 勺 杯 根 条 串 把 手掌 半个手掌 拳头".split()
    assert set(required) <= set(data["units"])
    assert {"主食", "汤粥", "菜肴", "肉蛋", "水果", "饮品", "零食"} <= set(data["category_groups"])
    assert set(data["modifiers"]) >= {"小", "大", "半"}
    assert data["fallback_grams"] > 0


def test_every_unit_has_a_default_and_known_groups():
    data = load_units()
    for unit, entry in data["units"].items():
        assert entry["default"] > 0, unit
        assert set(entry["groups"]) <= set(data["category_groups"]), unit
        assert all(grams > 0 for grams in entry["groups"].values()), unit


def test_every_group_has_a_default_amount():
    data = load_units()
    assert set(data["group_defaults"]) == set(data["category_groups"])
    assert all(grams > 0 for grams in data["group_defaults"].values())


def test_every_category_prefix_hits_a_catalog_food():
    categories = {food.category for food in CATALOG.foods.values()}
    for group, prefixes in load_units()["category_groups"].items():
        assert prefixes, group
        for prefix in prefixes:
            assert any(category.startswith(prefix) for category in categories), f"{group}：{prefix}"


def test_every_unit_is_parseable_as_a_portion():
    for unit in load_units()["units"]:
        assert parse_portion(unit) == Portion(1.0, unit)
