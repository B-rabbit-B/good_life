"""餐厅类型：按店名关键词与高德类别编码判断一家店的类型，用步骤 04 的引擎评价代表菜得出整类结论。

类型表在 data/restaurant_types.json，每类的代表菜都是营养库里的食物编号。
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.nutrition.catalog import Catalog
from app.nutrition.engine import CAUTION, NOT_RECOMMENDED, SUITABLE, EvaluationContext, Reason, evaluate_food
from app.restaurants.amap import Poi

DATA_DIR = Path(__file__).with_name("data")
GENERIC_TYPECODES = frozenset({"050000", "050100"})  # 餐饮服务、中餐厅：太笼统，不据此判断类型
NEGATIVE_EFFECTS = ("block", "unverifiable", "caution")


@dataclass(frozen=True)
class RestaurantType:
    key: str
    name: str
    typecodes: tuple[str, ...]
    name_keywords: tuple[str, ...]
    dishes: tuple[str, ...]  # 营养库食物编号


@dataclass(frozen=True)
class TypeAdvice:
    type_key: str
    type_name: str
    conclusion: str  # suitable / caution / not_recommended
    order: tuple[str, ...]  # 可点（适合的代表菜名）
    moderate: tuple[str, ...]  # 适量（需注意）
    avoid: tuple[str, ...]  # 应避开（不建议）
    reasons: tuple[Reason, ...]


@lru_cache
def load_types() -> tuple[RestaurantType, ...]:
    raw = json.loads((DATA_DIR / "restaurant_types.json").read_text("utf-8"))
    return tuple(
        RestaurantType(item["key"], item["name"], tuple(item["typecodes"]), tuple(item["name_keywords"]),
                       tuple(item["dishes"]))
        for item in raw
    )


@lru_cache
def _keyword_order() -> tuple[tuple[str, RestaurantType], ...]:
    """全部店名关键词，较长的在前；同样长时按类型表与关键词的顺序。"""
    pairs = [(keyword, rtype) for rtype in load_types() for keyword in rtype.name_keywords]
    return tuple(sorted(pairs, key=lambda pair: -len(pair[0])))


@lru_cache
def _by_typecode() -> dict[str, RestaurantType]:
    return {code: rtype for rtype in load_types() for code in rtype.typecodes}


def classify(poi: Poi) -> RestaurantType | None:
    """店名关键词（较长的优先）→ 具体类别编码（高德可能用“|”给出多个，按顺序）→ 笼统编码不判断，返回 None。"""
    for keyword, rtype in _keyword_order():
        if keyword in poi.name:
            return rtype
    for code in poi.typecode.split("|"):
        code = code.strip()
        if code in GENERIC_TYPECODES:
            continue
        rtype = _by_typecode().get(code)
        if rtype is not None:
            return rtype
    return None


def advise(rtype: RestaurantType, context: EvaluationContext, catalog: Catalog) -> TypeAdvice:
    """每道代表菜按默认克数交给引擎评价；一半以上（含一半）不建议 → 整类不建议，否则有不建议或需注意 → 需注意。

    原因取不建议与需注意菜品里的负面原因（不建议、无法判断、需注意），按 code 与 ref 去重，保持引擎给出的顺序。
    """
    order, moderate, avoid = [], [], []
    reasons: dict[tuple[str, str], Reason] = {}
    for food_id in rtype.dishes:
        food = catalog.foods[food_id]
        evaluation = evaluate_food(food, food.default_grams, context, catalog)
        if evaluation.conclusion == SUITABLE:
            order.append(food.name)
            continue
        (avoid if evaluation.conclusion == NOT_RECOMMENDED else moderate).append(food.name)
        for reason in evaluation.reasons:
            if reason.effect in NEGATIVE_EFFECTS:
                reasons.setdefault((reason.code, reason.ref), reason)
    if len(avoid) * 2 >= len(rtype.dishes):
        conclusion = NOT_RECOMMENDED
    elif avoid or moderate:
        conclusion = CAUTION
    else:
        conclusion = SUITABLE
    return TypeAdvice(rtype.key, rtype.name, conclusion, tuple(order), tuple(moderate), tuple(avoid),
                      tuple(reasons.values()))
