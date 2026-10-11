import json
import re

import pytest

from app.errors import AppError
from app.nutrition.catalog import Nutrients, load_catalog
from app.nutrition.engine import EvaluationContext, HardConstraint
from app.nutrition.needs import Needs
from app.restaurants import needs as needs_module
from app.restaurants.amap import Poi
from app.restaurants.needs import MODEL_PROMPT, load_needs, match_rules, parse_model_needs, resolve
from app.restaurants.ranking import CONCLUSION_RANK, MAX_RESULTS, Ranked, rank
from app.restaurants.types import GENERIC_TYPECODES, TypeAdvice, advise, classify, load_types

CATALOG = load_catalog()
TYPES = {rtype.key: rtype for rtype in load_types()}
NO_SPICY = EvaluationContext(constraints=(HardConstraint("m1", "diet_avoid", "忌辛辣", ("辛辣",)),))


def _poi(poi_id="p1", name="某某餐厅", typecode="050000", distance=100, rating=None):
    return Poi(poi_id, name, 116.4, 39.9, typecode, "餐饮服务", "某路 1 号", distance, rating)


def _type_key(poi):
    rtype = classify(poi)
    return rtype.key if rtype else None


# 数据校验

def test_type_table_is_valid():
    types = load_types()
    keys = [rtype.key for rtype in types]
    assert len(keys) == len(set(keys))
    assert 15 <= len(types) <= 22
    names = {rtype.name for rtype in types}
    for required in ("家常菜", "川菜", "湘菜", "粤菜", "火锅", "烧烤", "麻辣烫与串串", "粥铺", "轻食沙拉", "面馆",
                     "饺子馄饨包子", "素食", "清真与西北菜", "海鲜", "西餐", "日料", "快餐炸鸡汉堡", "甜品饮品"):
        assert required in names
    for rtype in types:
        assert 3 <= len(rtype.dishes) <= 5, rtype.key
        assert len(set(rtype.dishes)) == len(rtype.dishes)
        for food_id in rtype.dishes:
            assert CATALOG.get(food_id) is not None, food_id
        for code in rtype.typecodes:
            assert re.fullmatch(r"\d{6}", code), code
            assert code not in GENERIC_TYPECODES
        assert rtype.typecodes or rtype.name_keywords
        assert all(keyword.strip() for keyword in rtype.name_keywords)


def test_typecodes_are_not_shared_between_types():
    codes = [code for rtype in load_types() for code in rtype.typecodes]
    assert len(codes) == len(set(codes))


def test_need_vocabulary_is_valid():
    needs = load_needs()
    keys = [need.key for need in needs]
    assert len(keys) == len(set(keys))
    assert 10 <= len(needs) <= 15
    names = {need.name for need in needs}
    for required in ("清淡", "粥", "汤", "轻食", "高蛋白", "素食", "面食", "不辣", "少油", "饺子包子", "清真", "甜品"):
        assert required in names
    for need in needs:
        assert need.description and need.synonyms
        assert 1 <= len(need.keywords) <= 3
        assert need.prefer_types and set(need.prefer_types) <= set(TYPES)


def test_data_files_are_lists_of_objects_with_expected_fields():
    from app.restaurants.types import DATA_DIR

    types = json.loads((DATA_DIR / "restaurant_types.json").read_text("utf-8"))
    needs = json.loads((DATA_DIR / "needs.json").read_text("utf-8"))
    assert all(set(item) == {"key", "name", "typecodes", "name_keywords", "dishes"} for item in types)
    assert all(set(item) == {"key", "name", "description", "synonyms", "keywords", "prefer_types"} for item in needs)


# 分类

def test_name_keyword_beats_generic_code():
    assert _type_key(_poi(name="老成都川菜馆", typecode="050100")) == "sichuan"


def test_name_keywords():
    assert _type_key(_poi(name="张记麻辣烫")) == "malatang"
    assert _type_key(_poi(name="XX 粥铺")) == "porridge"
    assert _type_key(_poi(name="潮汕牛肉火锅")) == "hotpot"  # 较长的关键词优先
    assert _type_key(_poi(name="兰州拉面")) == "noodles"


def test_specific_typecode_when_name_has_no_keyword():
    assert _type_key(_poi(name="好味道", typecode="050102")) == "sichuan"
    assert _type_key(_poi(name="好味道", typecode="050100|050102")) == "sichuan"


def test_name_keyword_beats_specific_code():
    assert _type_key(_poi(name="阿婆粥铺", typecode="050102")) == "porridge"


def test_generic_or_unknown_code_is_unclassified():
    assert classify(_poi(name="好味道", typecode="050000")) is None
    assert classify(_poi(name="好味道", typecode="050100")) is None
    assert classify(_poi(name="好味道", typecode="")) is None


# 整类结论

def test_no_spicy_order_avoids_sichuan_and_malatang():
    for key in ("sichuan", "malatang"):
        advice = advise(TYPES[key], NO_SPICY, CATALOG)
        assert isinstance(advice, TypeAdvice)
        assert advice.type_key == key and advice.type_name == TYPES[key].name
        assert advice.conclusion == "not_recommended"
        assert advice.reasons and all(reason.source == "medical" for reason in advice.reasons)
        assert all(reason.effect in ("block", "unverifiable", "caution") for reason in advice.reasons)
    sichuan = advise(TYPES["sichuan"], NO_SPICY, CATALOG)
    assert "麻婆豆腐" in sichuan.avoid
    # 同一条医嘱在几道菜上的原因按 code 与 ref 去重
    pairs = [(reason.code, reason.ref) for reason in sichuan.reasons]
    assert len(pairs) == len(set(pairs))


def test_porridge_is_fine_with_no_spicy_order():
    advice = advise(TYPES["porridge"], NO_SPICY, CATALOG)
    assert advice.conclusion in ("suitable", "caution")
    assert not advice.avoid


def test_partial_hit_is_caution():
    advice = advise(TYPES["home"], NO_SPICY, CATALOG)
    assert advice.conclusion == "caution"
    assert advice.avoid and advice.order
    assert set(advice.order) | set(advice.moderate) | set(advice.avoid) == {
        CATALOG.get(food_id).name for food_id in TYPES["home"].dishes
    }


@pytest.mark.parametrize("context", [
    EvaluationContext(),
    EvaluationContext(needs=Needs(status="ok", energy_kcal=2000, energy_kcal_low=1800, energy_kcal_high=2200,
                                  protein_g=60, sodium_mg_max=2000),
                      day_totals=Nutrients(energy_kcal=0, sodium_mg=0)),
])
def test_unconstrained_user_has_no_avoided_types(context):
    for rtype in load_types():
        advice = advise(rtype, context, CATALOG)
        assert advice.conclusion != "not_recommended", rtype.key
        assert not advice.avoid


def test_unconstrained_user_without_needs_gets_suitable():
    advice = advise(TYPES["porridge"], EvaluationContext(), CATALOG)
    assert advice.conclusion == "suitable"
    assert advice.reasons == () and advice.moderate == () and advice.avoid == ()
    assert advice.order == tuple(CATALOG.get(food_id).name for food_id in TYPES["porridge"].dishes)


# 需求

def test_rules_match_colloquial_text():
    assert match_rules("胃不舒服想吃点软的") == ("light", "porridge")
    assert match_rules("健身后想吃肉") == ("high_protein",)
    assert match_rules("想减脂") == ("light_meal",)
    assert match_rules("随便看看附近有什么") == ()
    assert match_rules("") == ()


def test_rules_are_capped_at_three_in_vocabulary_order():
    order = [need.key for need in load_needs()]
    hits = match_rules("清淡一点，喝粥喝汤，不辣，少油")
    assert len(hits) == 3
    assert list(hits) == sorted(hits, key=order.index)


def test_resolve_merges_direct_keys_with_rules():
    assert resolve("胃不舒服想吃点软的", ["light", "dessert"]) == (("light", "dessert", "porridge"), "rules")
    assert resolve("胃不舒服", ["dessert", "halal", "noodles"]) == (("dessert", "halal", "noodles"), "rules")
    assert resolve(None, ["dessert", "dessert"]) == (("dessert",), "none")
    assert resolve("随便看看", []) == ((), "none")
    assert resolve(None, []) == ((), "none")


def test_resolve_rejects_unknown_key():
    with pytest.raises(AppError) as error:
        resolve("清淡", ["light", "pizza"])
    assert (error.value.status_code, error.value.code) == (422, "restaurant_unknown_need")
    assert "pizza" in error.value.message


def test_model_prompt_lists_vocabulary():
    for need in load_needs():
        assert need.key in MODEL_PROMPT and need.name in MODEL_PROMPT
    assert '{"needs"' in MODEL_PROMPT
    assert "3" in MODEL_PROMPT


def test_parse_model_needs():
    assert parse_model_needs('{"needs": ["light", "porridge"]}') == ("light", "porridge")
    assert parse_model_needs('好的。\n```json\n{"needs": ["soup", "burger", "soup"]}\n```\n以上。') == ("soup",)
    assert parse_model_needs('{"needs": ["light", "soup", "porridge", "dessert"]}') == ("light", "soup", "porridge")
    assert parse_model_needs('{"needs": "light"}') == ()
    assert parse_model_needs('{"needs": [1, null, "light"]}') == ("light",)
    assert parse_model_needs('{"other": []}') == ()
    assert parse_model_needs("我觉得清淡就好") == ()
    assert parse_model_needs("{不是 JSON}") == ()
    assert parse_model_needs("") == ()


def test_needs_module_exports_need_type():
    need = load_needs()[0]
    assert isinstance(need, needs_module.Need)
    with pytest.raises(AttributeError):
        need.key = "x"


# 排序

def _advice(key, conclusion):
    return TypeAdvice(key, TYPES[key].name, conclusion, (), (), (), ())


ADVICE = {
    "sichuan": _advice("sichuan", "not_recommended"),
    "porridge": _advice("porridge", "suitable"),
    "salad": _advice("salad", "suitable"),
    "noodles": _advice("noodles", "caution"),
    "malatang": _advice("malatang", "not_recommended"),
}


def _ids(ranked):
    return [item.poi.id for item in ranked]


def test_conclusion_beats_distance():
    pois = [
        _poi("near-unknown", "好味道", distance=10),
        _poi("near-noodle", "牛肉面馆", distance=20),
        _poi("far-porridge", "阿婆粥铺", distance=900),
    ]
    ranked, _ = rank(pois, ADVICE, set())
    assert _ids(ranked) == ["far-porridge", "near-noodle", "near-unknown"]
    assert [item.conclusion for item in ranked] == ["suitable", "caution", "unchecked"]
    assert ranked[0].rtype.key == "porridge" and ranked[2].rtype is None
    assert isinstance(ranked[0], Ranked)
    assert CONCLUSION_RANK == {"suitable": 0, "caution": 1, "unchecked": 2}


def test_preferred_type_first_within_same_conclusion():
    pois = [_poi("salad", "轻食沙拉", distance=10), _poi("porridge", "粥铺", distance=500)]
    assert _ids(rank(pois, ADVICE, {"porridge"})[0]) == ["porridge", "salad"]
    assert _ids(rank(pois, ADVICE, set())[0]) == ["salad", "porridge"]


def test_missing_distance_last_and_rating_secondary():
    pois = [
        _poi("a", "粥铺", distance=None, rating=5.0),
        _poi("b", "粥铺", distance=300, rating=3.0),
        _poi("c", "粥铺", distance=300, rating=4.5),
        _poi("d", "粥铺", distance=300, rating=None),
        _poi("e", "粥铺", distance=100, rating=None),
    ]
    assert _ids(rank(pois, ADVICE, set())[0]) == ["e", "c", "b", "d", "a"]


def test_avoided_shops_are_grouped_and_excluded():
    pois = [
        _poi("s1", "川菜馆", distance=10),
        _poi("m1", "麻辣烫", distance=20),
        _poi("s2", "好味道", typecode="050102", distance=30),
        _poi("p1", "粥铺", distance=40),
    ]
    ranked, avoided = rank(pois, ADVICE, set())
    assert _ids(ranked) == ["p1"]
    assert {key: [poi.id for poi in shops] for key, shops in avoided.items()} == {
        "sichuan": ["s1", "s2"], "malatang": ["m1"],
    }


def test_truncated_and_deterministic():
    pois = [_poi(f"p{i:02d}", "粥铺", distance=100, rating=4.0) for i in range(30)]
    ranked, avoided = rank(list(reversed(pois)), ADVICE, set())
    assert len(ranked) == MAX_RESULTS == 20
    assert _ids(ranked) == [f"p{i:02d}" for i in range(20)]
    assert _ids(rank(pois, ADVICE, set())[0]) == _ids(ranked)
    assert avoided == {}
