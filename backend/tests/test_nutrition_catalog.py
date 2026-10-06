import hashlib

from app.nutrition.catalog import (
    CFCD_FILE,
    CFCD_SHA256,
    LICENSE_PERSONAL_STUDY,
    Nutrients,
    base_name,
    load_catalog,
    match_names,
    normalize_query,
    parse_value,
    round_half_up,
    round_one,
    split_name,
)


def test_data_file_is_the_pinned_version():
    assert hashlib.sha256(CFCD_FILE.read_bytes()).hexdigest() == CFCD_SHA256


def test_parse_value():
    assert parse_value("116") == 116.0
    assert parse_value("2.50") == 2.5
    assert parse_value("899*") == 899.0
    assert parse_value("Tr") == 0.0
    for missing in ("—", "", "un", None):
        assert parse_value(missing) is None


def test_split_name():
    assert split_name("马铃薯［土豆、洋芋］") == ("马铃薯", ("土豆", "洋芋"))
    assert split_name("番茄［西红柿］") == ("番茄", ("西红柿",))
    assert split_name("米饭（蒸，代表值）") == ("米饭（蒸，代表值）", ())


def test_rounding_helpers():
    assert round_half_up(2.5) == 3
    assert round_half_up(2.49) == 2
    assert round_one(5.25) == 5.3
    assert round_one(None) is None
    assert normalize_query(" 一碗　米饭 ") == "一碗米饭"


def test_nutrients_scale_and_add():
    rice = Nutrients(energy_kcal=116, protein_g=2.6, fat_g=0.3, carbohydrate_g=25.9, sodium_mg=None)
    serving = rice.scaled(150)
    assert serving.energy_kcal == 174.0
    assert serving.sodium_mg is None
    total = serving.plus(Nutrients(energy_kcal=10, sodium_mg=5))
    assert total.energy_kcal == 184.0
    assert total.sodium_mg == 5


def test_catalog_loads_every_cfcd_row_with_source():
    catalog = load_catalog()
    cfcd = [food for food in catalog.foods.values() if food.id.startswith("cfcd:")]
    assert len(cfcd) == 1677
    rice = catalog.get("cfcd:012401x")
    assert rice.name == "米饭（蒸，代表值）"
    assert (rice.nutrients.energy_kcal, rice.nutrients.protein_g, rice.nutrients.carbohydrate_g) == (116, 2.6, 25.9)
    assert rice.source.reference == "012401x"
    assert rice.source.license_status == LICENSE_PERSONAL_STUDY
    assert "仅供个人学习" in rice.source.note
    assert all(food.source.dataset and food.source.license_status for food in catalog.foods.values())


def test_bracket_aliases_are_searchable():
    catalog = load_catalog()
    hits = catalog.search("土豆")
    assert hits[0].food.id == "cfcd:021101"
    assert hits[0].match in ("exact_name", "common_name", "exact_alias")
    assert catalog.search("西红柿")[0].food.name == "番茄"


def test_common_aliases_rank_first():
    catalog = load_catalog()
    first = catalog.search("米饭")[0]
    assert (first.food.id, first.match) == ("cfcd:012401x", "common_name")
    assert catalog.search("一碗米饭")[0].food.id == "cfcd:012401x"
    assert catalog.search("一碗米饭")[0].match == "query_contains"


def test_not_found_returns_empty_and_search_is_deterministic():
    catalog = load_catalog()
    assert catalog.search("完全不存在的食物名称") == []
    assert catalog.search("   ") == []
    assert [h.food.id for h in catalog.search("鸡")] == [h.food.id for h in catalog.search("鸡")]
    assert len(catalog.search("鸡")) == 20


def test_nutrition_tags_are_computed_from_values():
    catalog = load_catalog()
    breast = catalog.search("鸡胸脯肉")[0].food
    assert "high_protein" in breast.tags
    assert "high_protein" not in catalog.get("cfcd:012401x").tags
    assert catalog.tag_name("high_protein") == "高蛋白"
    assert catalog.tags["high_protein"].kind == "nutrition"


def test_name_matches_helper_is_gone():
    assert not hasattr(load_catalog(), "name_matches")


def test_base_name_drops_parenthetical_qualifiers():
    assert base_name("菠菜（鲜）") == "菠菜"
    assert base_name("米饭（蒸，代表值）") == "米饭"
    assert base_name("牛肉(代表值)") == "牛肉"
    assert base_name("番茄") == "番茄"


def test_match_names_include_base_name_without_duplicates():
    catalog = load_catalog()
    assert match_names(catalog.get("cfcd:045301")) == ("菠菜（鲜）", "赤根菜", "菠菜")
    assert match_names(catalog.get("cfcd:021101")) == ("马铃薯", "土豆", "洋芋")


def test_base_name_is_searchable_as_alias_but_real_names_win():
    catalog = load_catalog()
    first = catalog.search("菠菜")[0]
    assert (first.food.id, first.match) == ("cfcd:045301", "exact_alias")
    assert catalog.search("新鲜菠菜")[0].food.id == "cfcd:045301"
    assert catalog.search("新鲜菠菜")[0].match == "query_contains"
    # 真正的名称（香蕉［甘蕉］）排在只靠去括号得到的"香蕉"（香蕉（红皮））前面
    hits = catalog.search("香蕉")
    assert (hits[0].food.id, hits[0].match) == ("cfcd:065033", "exact_name")
    assert {h.food.id for h in hits if h.match == "exact_alias"} >= {"cfcd:065031", "cfcd:065032"}


# ---- 最终修复：常用名单独的匹配类型，部分匹配一眼可辨 ----

def test_common_name_has_its_own_match_type_ranked_like_exact_name():
    from app.nutrition.catalog import EXACT_MATCH_TYPES, MATCH_RANKS, MATCH_TYPES

    assert MATCH_TYPES == ("exact_name", "common_name", "exact_alias", "prefix", "contains", "query_contains")
    assert MATCH_RANKS["common_name"] == MATCH_RANKS["exact_name"] == 0
    assert EXACT_MATCH_TYPES == ("exact_name", "common_name", "exact_alias")
    catalog = load_catalog()
    assert catalog.search("花生")[0].match == "common_name"
    assert catalog.search("番茄炒蛋")[0].match == "exact_name"


def test_partial_matches_are_labelled_as_partial():
    catalog = load_catalog()
    for query, name in [("酸菜鱼", "酸白菜"), ("螺蛳粉", "螺蛳"), ("皮蛋瘦肉粥", "松花蛋（鸭蛋）"), ("小龙虾", "龙虾")]:
        first = catalog.search(query)[0]
        assert (first.food.name, first.match) == (name, "query_contains"), query
