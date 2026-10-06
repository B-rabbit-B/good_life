import json
import tempfile
from pathlib import Path

import pytest

from app.nutrition import catalog as catalog_module
from app.nutrition.catalog import DATA_DIR, LICENSE_PERSONAL_STUDY, LICENSE_SELF_ESTIMATE, load_catalog

COMMON_FOODS = [
    # 主食 20
    "米饭", "白粥", "小米粥", "馒头", "花卷", "包子", "饺子", "馄饨", "面条", "炒饭",
    "炒面", "油条", "烧饼", "面包", "玉米", "红薯", "土豆", "燕麦", "糙米饭", "年糕",
    # 早餐与饮品 10
    "豆浆", "牛奶", "酸奶", "鸡蛋", "咸鸭蛋", "茶叶蛋", "咖啡", "奶茶", "可乐", "橙汁",
    # 蔬菜 15
    "西红柿", "黄瓜", "大白菜", "菠菜", "生菜", "西兰花", "胡萝卜", "茄子", "青椒", "冬瓜",
    "南瓜", "豆芽", "芹菜", "苦瓜", "蘑菇",
    # 水果 10
    "苹果", "香蕉", "橙子", "梨", "西瓜", "葡萄", "草莓", "桃", "猕猴桃", "柚子",
    # 肉蛋豆 15
    "猪肉", "五花肉", "牛肉", "羊肉", "鸡胸肉", "鸡腿", "鸭肉", "猪肝", "鱼", "带鱼",
    "虾", "螃蟹", "豆腐", "豆腐干", "花生",
    # 菜品 25
    "番茄炒蛋", "宫保鸡丁", "鱼香肉丝", "红烧肉", "麻婆豆腐", "青椒肉丝", "糖醋排骨", "回锅肉", "地三鲜", "清炒西兰花",
    "蒜蓉菠菜", "醋溜白菜", "红烧鱼", "清蒸鱼", "水煮鱼", "酸辣土豆丝", "可乐鸡翅", "炸鸡", "凉拌黄瓜", "紫菜蛋花汤",
    "西红柿鸡蛋汤", "火锅", "麻辣烫", "炸酱面", "牛肉面",
    # 其他 5
    "白酒", "啤酒", "红酒", "蛋糕", "冰淇淋",
]


def _food(name):
    return load_catalog().search(name)[0].food


def test_common_food_list_has_one_hundred_distinct_names():
    assert len(COMMON_FOODS) == 100
    assert len(set(COMMON_FOODS)) == 100


@pytest.mark.parametrize("name", COMMON_FOODS)
def test_common_food_is_found_exactly(name):
    hits = load_catalog().search(name)
    assert hits, f"{name} 未找到"
    assert hits[0].match in ("exact_name", "common_name", "exact_alias"), (name, hits[0].food.name, hits[0].match)


def test_dishes_are_well_formed_and_computed_from_recipe():
    catalog = load_catalog()
    raw = json.loads((DATA_DIR / "dishes.json").read_text("utf-8"))
    assert len(raw) >= 40
    for dish in raw:
        assert dish["serving_grams"] > 0
        total = 0.0
        energy = 0.0
        for ingredient in dish["ingredients"]:
            food = catalog.get(ingredient["food"])
            assert food is not None, (dish["id"], ingredient["food"])
            assert ingredient["grams"] > 0
            total += ingredient["grams"]
            energy += (food.nutrients.energy_kcal or 0) * ingredient["grams"] / 100
        computed = catalog.get(f"dish:{dish['id']}")
        assert computed.kind == "dish"
        assert computed.nutrients.energy_kcal == pytest.approx(energy / total * 100)
        assert computed.source.license_status == LICENSE_PERSONAL_STUDY
        assert computed.source.reference == dish["id"]
        assert computed.default_grams == dish["serving_grams"]


def test_dishes_inherit_composition_tags():
    assert "meat" in _food("宫保鸡丁").tags
    assert "egg" in _food("番茄炒蛋").tags
    assert "seafood" in _food("清蒸鱼").tags


def test_supplements_are_marked_as_unverified_estimates():
    for food in load_catalog().foods.values():
        if food.kind == "supplement":
            assert food.source.license_status == LICENSE_SELF_ESTIMATE
            assert "估算" in food.source.note


def test_every_tag_used_is_defined_and_tradition_is_labelled():
    catalog = load_catalog()
    for food in catalog.foods.values():
        assert food.tags <= set(catalog.tags), food.id
    for tag in catalog.tags.values():
        if tag.kind == "tradition":
            assert "传统" in tag.basis
    expected_kinds = {
        "meat": "composition", "seafood": "composition", "egg": "composition", "dairy": "composition",
        "organ_meat": "composition", "fatty_meat": "composition", "alcohol": "composition",
        "spicy": "culinary", "fried": "culinary", "raw_cold": "culinary",
        "fast_carb": "dietary", "slow_carb": "dietary", "high_sugar": "dietary", "sweets": "dietary",
        "sugary_drink": "dietary", "caffeine": "dietary", "high_purine": "dietary",
        "cold_nature": "tradition", "warm_nature": "tradition",
    }
    assert {tag: catalog.tags[tag].kind for tag in expected_kinds} == expected_kinds


@pytest.mark.parametrize(
    ("name", "tag"),
    [
        ("啤酒", "alcohol"), ("白酒", "alcohol"), ("红酒", "alcohol"),
        ("麻婆豆腐", "spicy"), ("水煮鱼", "spicy"), ("酸辣土豆丝", "spicy"), ("麻辣烫", "spicy"), ("宫保鸡丁", "spicy"),
        ("油条", "fried"), ("炸鸡", "fried"), ("冰淇淋", "raw_cold"), ("凉拌黄瓜", "raw_cold"),
        ("猪肝", "organ_meat"), ("五花肉", "fatty_meat"), ("红烧肉", "fatty_meat"),
        ("蛋糕", "sweets"), ("可乐", "sugary_drink"), ("奶茶", "sugary_drink"), ("咖啡", "caffeine"),
        ("猪肝", "high_purine"), ("西瓜", "cold_nature"), ("梨", "cold_nature"), ("苦瓜", "cold_nature"),
        ("羊肉", "warm_nature"), ("米饭", "fast_carb"), ("燕麦", "slow_carb"), ("鸡胸肉", "meat"),
        ("带鱼", "seafood"), ("牛奶", "dairy"),
    ],
)
def test_expected_tags(name, tag):
    assert tag in _food(name).tags, (name, _food(name).name, sorted(_food(name).tags))


def test_plain_foods_do_not_get_wrong_tags():
    assert "spicy" not in _food("番茄炒蛋").tags
    assert "alcohol" not in _food("米饭").tags
    assert "cold_nature" not in _food("羊肉").tags


def test_portions():
    rice = _food("米饭")
    assert dict(rice.portions)["碗"] > 0
    assert dict(_food("鸡蛋").portions)["个"] > 0
    assert _food("番茄炒蛋").default_grams > 0
    assert dict(_food("番茄炒蛋").portions)["份"] == _food("番茄炒蛋").default_grams


def test_aliases_are_unique_across_foods():
    catalog = load_catalog()
    seen = {}
    for food in catalog.foods.values():
        if food.kind == "ingredient":
            continue
        for name in (food.name, *food.aliases):
            assert name not in seen, (name, seen.get(name), food.id)
            seen[name] = food.id


# ---- 以下为任务 2 实现时补充的检查 ----

@pytest.mark.parametrize(
    ("name", "food_id"),
    [
        ("鱼", "cfcd:121102"), ("虾", "cfcd:122121"), ("螃蟹", "cfcd:123002"), ("牛奶", "cfcd:101101x"),
        ("酸奶", "cfcd:103001x"), ("面条", "cfcd:011317"), ("白粥", "cfcd:012404"), ("五花肉", "cfcd:081108"),
        ("豆腐干", "cfcd:031510x"), ("青椒", "cfcd:043124"), ("菠菜", "cfcd:045301"), ("花生", "cfcd:072003"),
        ("包子", "dish:baozi"), ("炒饭", "dish:egg_fried_rice"), ("可乐", "supplement:cola"),
    ],
)
def test_common_names_point_to_the_intended_food(name, food_id):
    assert _food(name).id == food_id


def test_broad_name_patterns_do_not_over_tag():
    catalog = load_catalog()
    # 名称含"肝""肚""心""肠"但不是动物内脏
    for food_id in ("cfcd:051042", "cfcd:014201", "cfcd:041105", "cfcd:031520", "cfcd:051023", "cfcd:021101"):
        assert "organ_meat" not in catalog.get(food_id).tags, catalog.get(food_id).name
    # 炸酱面的"炸"是炸酱，不是油炸；冰鲜鱼不是生冷
    assert "fried" not in _food("炸酱面").tags
    assert "raw_cold" not in catalog.get("cfcd:121246").tags
    # 牛肉股内肉的别名"黄瓜条"、西瓜子、凤梨不属于寒凉
    for food_id in ("cfcd:082118", "cfcd:072014", "cfcd:065002", "cfcd:061227"):
        assert "cold_nature" not in catalog.get(food_id).tags, catalog.get(food_id).name
    # 菜品里的调料不让菜品带上饮品类标签（含咖啡因按配方继承，见下面的继承测试）
    assert "sugary_drink" not in _food("可乐鸡翅").tags


def test_dish_note_lists_missing_values_and_estimated_ingredients():
    note = _food("青椒肉丝").source.note
    assert "家常" in note
    assert "按 0 计" in note and "甜椒" in note
    assert "估算" in note  # 用到了食盐、酱油等手动补充的估算值


def test_portion_units_merge_and_default_grams():
    catalog = load_catalog()
    milk = _food("牛奶")
    assert set(dict(milk.portions)) >= {"杯", "盒"}
    assert milk.portions == tuple(sorted(milk.portions))
    assert milk.default_grams == milk.portions[0][1]
    bun = _food("包子")
    assert dict(bun.portions)["个"] > 0 and dict(bun.portions)["份"] == bun.default_grams
    assert dict(_food("饺子").portions)["个"] > 0
    assert dict(_food("馒头").portions)["个"] > 0
    assert dict(_food("苹果").portions)["个"] > 0
    assert dict(_food("香蕉").portions)["根"] > 0
    beer = _food("啤酒")
    assert beer.kind == "supplement" and beer.default_grams == dict(beer.portions)["罐"]
    assert catalog.get("cfcd:045217").default_grams == 100  # 没有份量的食材按 100 克


def _load_with(monkeypatch, **files):
    """把数据文件复制到临时目录（可替换其中几个）后重新加载营养库；不用 tmp_path，避免 pytest 清理旧目录时的告警。"""
    with tempfile.TemporaryDirectory() as directory:
        data_dir = Path(directory)
        for name in ("tags.json", "aliases.json", "supplements.json", "dishes.json", "portions.json"):
            content = files.get(name, (DATA_DIR / name).read_text("utf-8"))
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False)
            (data_dir / name).write_text(content, "utf-8")
        monkeypatch.setattr(catalog_module, "DATA_DIR", data_dir)
        return catalog_module.load_catalog.__wrapped__()


DISH = {
    "id": "x", "name": "测试菜", "aliases": [], "category": "菜品-家常菜",
    "ingredients": [{"food": "cfcd:045217", "grams": 100}], "serving_grams": 100, "tags": [], "note": "家常做法估计",
}


@pytest.mark.parametrize(
    ("files", "message"),
    [
        ({"dishes.json": [{**DISH, "ingredients": [{"food": "cfcd:nope", "grams": 10}]}]}, "cfcd:nope"),
        ({"dishes.json": [{**DISH, "tags": ["no_such_tag"]}]}, "no_such_tag"),
        ({"dishes.json": [DISH, DISH]}, "dish:x"),
        ({"portions.json": {"cfcd:nope": {"个": 10}}}, "cfcd:nope"),
        ({"supplements.json": [{
            "id": "s", "name": "测试饮料", "aliases": [], "category": "补充-饮料", "nutrients": {"energy_kcal": 1},
            "serving_grams": 100, "serving_unit": "杯", "tags": [], "note": "来自包装",
        }]}, "估算"),
    ],
)
def test_invalid_data_files_are_rejected(monkeypatch, files, message):
    with pytest.raises(ValueError, match=message):
        _load_with(monkeypatch, **files)


def test_data_entries_reject_unknown_fields(monkeypatch):
    with pytest.raises(ValueError):
        _load_with(monkeypatch, **{"dishes.json": [{**DISH, "colour": "red"}]})


def test_copied_data_files_load(monkeypatch):
    assert _load_with(monkeypatch).get("dish:tomato_egg") is not None


# ---- 修复轮 1 ----

def test_every_high_fat_red_meat_entry_is_fatty_meat():
    """fatty_meat 的依据是"畜肉类中每 100 克脂肪不少于 20 克的条目"，逐条列出时不能漏。"""
    catalog = load_catalog()
    missing = sorted(
        f"{food.id} {food.name}"
        for food in catalog.foods.values()
        if food.id.startswith("cfcd:") and food.category.startswith("畜肉类")
        and food.nutrients.fat_g is not None and food.nutrients.fat_g >= 20 and "fatty_meat" not in food.tags
    )
    assert missing == []


def test_canned_fruit_in_syrup_is_high_sugar():
    catalog = load_catalog()
    syrup = [food for food in catalog.foods.values() if food.id.startswith("cfcd:") and "糖水" in food.name]
    assert {food.id for food in syrup} >= {"cfcd:061229", "cfcd:062116", "cfcd:072010"}
    assert [food.name for food in syrup if "high_sugar" not in food.tags] == []


def test_butter_tea_contains_caffeine():
    assert "caffeine" in load_catalog().get("cfcd:105010").tags


# ---- 最终修复：菜品保留配方食材，并继承辛辣、含酒精、含咖啡因 ----

def test_dishes_keep_recipe_ingredient_ids():
    catalog = load_catalog()
    raw = {dish["id"]: dish for dish in json.loads((DATA_DIR / "dishes.json").read_text("utf-8"))}
    for dish_id, dish in raw.items():
        expected = tuple(dict.fromkeys(item["food"] for item in dish["ingredients"]))
        assert catalog.get(f"dish:{dish_id}").ingredients == expected
    assert catalog.get("cfcd:072022").ingredients == ()
    assert catalog.get("supplement:cola").ingredients == ()


def test_dishes_inherit_spicy_alcohol_and_caffeine():
    assert "spicy" in _food("醋溜白菜").tags  # 配方里有干辣椒
    assert "caffeine" in _food("可乐鸡翅").tags  # 可乐含咖啡因
    catalog = load_catalog()
    for food in catalog.foods.values():
        if food.kind == "dish":
            from_ingredients = {tag for i in food.ingredients for tag in catalog.get(i).tags}
            assert {"spicy", "alcohol", "caffeine"} & from_ingredients <= food.tags, food.name


def test_new_draft_tags_and_members():
    catalog = load_catalog()
    for tag, kind in [("red_meat", "composition"), ("fish", "composition"), ("legume", "composition"),
                      ("nut", "composition"), ("grapefruit", "dietary"), ("pork", "composition"),
                      ("beef", "composition"), ("mutton", "composition")]:
        assert (catalog.tags[tag].kind, catalog.tags[tag].review_status) == (kind, "draft"), tag
    assert "red_meat" in _food("牛肉").tags and "red_meat" in _food("红烧肉").tags
    assert "red_meat" not in _food("鸡腿").tags and "red_meat" not in _food("宫保鸡丁").tags
    assert {food.id for food in catalog.foods.values() if "grapefruit" in food.tags} == {"cfcd:064303", "cfcd:064304"}
    assert "fish" in _food("带鱼").tags and "fish" in _food("红烧鱼").tags and "fish" in catalog.get("cfcd:219043").tags
    assert "fish" in catalog.get("cfcd:129018").tags  # 鱼翅（鲨鱼）
    assert "fish" not in _food("虾").tags and "fish" not in _food("鱼香肉丝").tags
    assert "legume" in _food("豆腐").tags and "legume" in _food("麻婆豆腐").tags
    assert "nut" in _food("核桃").tags and "nut" in _food("宫保鸡丁").tags
    assert "alcohol" in catalog.get("cfcd:062309").tags  # 酒枣


# ---- 跟进修复（裁定 12）：新标签与数据补漏 ----

def test_followup_draft_tags():
    catalog = load_catalog()
    for tag in ("cured", "poultry", "chicken", "duck", "shrimp", "crab", "shellfish", "fungi"):
        assert (catalog.tags[tag].kind, catalog.tags[tag].review_status) == ("composition", "draft"), tag
    for food_id in ("cfcd:081308", "cfcd:081305", "cfcd:081320", "cfcd:081410", "cfcd:081413", "cfcd:081409",
                    "cfcd:081421", "cfcd:112203", "cfcd:121224"):
        assert "cured" in catalog.get(food_id).tags, food_id
    assert "cured" in _food("麻辣烫").tags and "cured" not in _food("猪肉").tags
    assert "chicken" in _food("宫保鸡丁").tags and "poultry" in _food("炸鸡").tags
    assert "chicken" not in _food("鸡蛋").tags and "duck" not in _food("咸鸭蛋").tags
    assert "shrimp" in _food("白灼虾").tags and "crab" in _food("螃蟹").tags and "shellfish" in _food("扇贝").tags
    assert "fungi" in _food("香菇").tags and "fungi" in _food("麻辣烫").tags  # 配方里的金针菇
    assert "fried" in _food("宫保鸡丁").tags


def test_followup_data_gaps():
    catalog = load_catalog()
    assert "dairy" in catalog.get("cfcd:011410").tags  # 花卷（加牛奶）
    assert "meat" in catalog.get("cfcd:011503").tags  # 面筋（肉馅）
    assert "sweets" in catalog.get("cfcd:011407").tags  # 烧饼（加糖）


def test_soybean_and_bean_sprouts_are_legume():
    catalog = load_catalog()
    for food_id in ("cfcd:042109", "cfcd:042202", "cfcd:042205", "cfcd:042206"):
        assert "legume" in catalog.get(food_id).tags, food_id
