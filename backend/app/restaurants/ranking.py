"""过滤与排序：只由规则决定。

被判为建议避开的类型的店不进推荐列表，按类型键分组另行返回；其余按结论、是否属于偏向类型、距离、评分、
店铺编号排序，截取前 20 家。
"""

from dataclasses import dataclass

from app.nutrition.engine import NOT_RECOMMENDED
from app.restaurants.amap import Poi
from app.restaurants.types import RestaurantType, TypeAdvice, classify

MAX_RESULTS = 20
UNCHECKED = "unchecked"
CONCLUSION_RANK = {"suitable": 0, "caution": 1, UNCHECKED: 2}


@dataclass(frozen=True)
class Ranked:
    poi: Poi
    rtype: RestaurantType | None
    conclusion: str  # suitable / caution / unchecked


def _sort_key(item: Ranked, prefer_types: set[str]) -> tuple:
    poi = item.poi
    preferred = item.rtype is not None and item.rtype.key in prefer_types
    return (
        CONCLUSION_RANK[item.conclusion],
        0 if preferred else 1,
        (1, 0) if poi.distance_m is None else (0, poi.distance_m),
        (1, 0.0) if poi.rating is None else (0, -poi.rating),
        poi.id,
    )


def rank(
    pois: list[Poi], advice_by_type: dict[str, TypeAdvice], prefer_types: set[str]
) -> tuple[list[Ranked], dict[str, list[Poi]]]:
    """advice_by_type 要包含这些店里出现的每个类型；无法判断类型的店结论为未核对。"""
    candidates: list[Ranked] = []
    avoided: dict[str, list[Poi]] = {}
    for poi in pois:
        rtype = classify(poi)
        if rtype is None:
            candidates.append(Ranked(poi, None, UNCHECKED))
            continue
        conclusion = advice_by_type[rtype.key].conclusion
        if conclusion == NOT_RECOMMENDED:
            avoided.setdefault(rtype.key, []).append(poi)
        else:
            candidates.append(Ranked(poi, rtype, conclusion))
    candidates.sort(key=lambda item: _sort_key(item, prefer_types))
    return candidates[:MAX_RESULTS], avoided
