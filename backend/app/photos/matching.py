"""把识别出的菜名匹配到营养库、换算克数、算出营养并给出“建议修正”的原因。

热量与营养只由营养库每 100 克数值乘克数得出，与记录一餐时保存的数字用同一套计算与取整。
"""

import uuid
from typing import Any

from app.errors import AppError
from app.nutrition.catalog import EXACT_MATCH_TYPES, NUTRIENT_FIELDS, Catalog, Nutrients, load_catalog
from app.nutrition.schemas import nutrients_out
from app.photos.portions import GRAMS_FROM_GROUP, GRAMS_FROM_MODEL, portion_grams

REVIEW_CONFIDENCE = 0.6
MIN_ITEM_GRAMS = 10
MAX_ITEM_GRAMS = 1500
MAX_CANDIDATES = 5
REVIEW_REASONS = ("low_confidence", "needs_confirmation", "grams_out_of_range", "estimated_grams")
MATCH_USER_SELECTED = "user_selected"
GRAMS_FROM_USER = "user"
_ESTIMATED_SOURCES = (GRAMS_FROM_MODEL, GRAMS_FROM_GROUP)


def build_item(
    name: str,
    portion_text: str,
    grams: float | None,
    grams_source: str | None,
    confidence: float,
    *,
    food_id: str | None = None,
    catalog: Catalog | None = None,
    item_id: str | None = None,
    grams_estimate: float | None = None,
) -> dict[str, Any]:
    """生成一个识别项。grams 为空时按份量换算（grams_estimate 是模型估计的克数，换算表认不出份量时才用）；
    给了 food_id（用户从候选里选的）就直接用它，否则按菜名检索，只有精确、常用名或别名命中才算已匹配。"""
    catalog = catalog or load_catalog()
    food, match_type, candidates = None, None, []
    if food_id is not None:
        food = catalog.get(food_id)
        if food is None:
            raise AppError(422, "photo_unknown_food", "营养库里没有你选的这个食物，请重新从候选里选择或改一个名字")
        match_type = MATCH_USER_SELECTED
    else:
        hits = catalog.search(name)
        if hits and hits[0].match in EXACT_MATCH_TYPES:
            food, match_type = hits[0].food, hits[0].match
        candidates = [{"food_id": hit.food.id, "name": hit.food.name} for hit in hits[:MAX_CANDIDATES]]
    if grams is None:
        grams, grams_source = portion_grams(food, portion_text, grams_estimate)
    elif grams_source is None:
        grams_source = GRAMS_FROM_USER
    nutrients = source = None
    if food is not None:
        nutrients = nutrients_out(food.nutrients.scaled(grams)).model_dump()
        source = {"dataset": food.source.dataset, "license_status": food.source.license_status, "note": food.source.note}
    reasons = [
        reason for reason, applies in (
            ("low_confidence", confidence < REVIEW_CONFIDENCE),
            ("needs_confirmation", food is None),
            ("grams_out_of_range", not MIN_ITEM_GRAMS <= grams <= MAX_ITEM_GRAMS),
            ("estimated_grams", grams_source in _ESTIMATED_SOURCES),
        ) if applies
    ]
    return {
        "id": item_id or str(uuid.uuid4()),
        "name": name,
        "portion_text": portion_text,
        "grams": grams,
        "grams_source": grams_source,
        "confidence": confidence,
        "status": "matched" if food is not None else "needs_confirmation",
        "food_id": food.id if food else None,
        "food_name": food.name if food else None,
        "match_type": match_type,
        "candidates": candidates,
        "nutrients": nutrients,
        "source": source,
        "review_reasons": reasons,
    }


def totals(items: list[dict[str, Any]], catalog: Catalog | None = None) -> dict[str, float | None]:
    """只合计已匹配的菜品；待确认的没有营养数字，不计入。
    按食物与克数重新计算、不取整地相加、最后只取整一次，与饮食日汇总（相加未取整的记录快照）一致。"""
    catalog = catalog or load_catalog()
    total = Nutrients(**{name: 0.0 for name in NUTRIENT_FIELDS})
    for item in items:
        if item["status"] == "matched":
            total = total.plus(catalog.foods[item["food_id"]].nutrients.scaled(item["grams"]))
    return nutrients_out(total).model_dump()


def needs_review(items: list[dict[str, Any]]) -> bool:
    return any(item["review_reasons"] for item in items)
