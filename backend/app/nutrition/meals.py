"""饮食记录与每日汇总。"""

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.common.ownership import get_owned_or_404, owned_by
from app.errors import AppError
from app.nutrition.catalog import NUTRIENT_FIELDS, Food, Nutrients, load_catalog
from app.nutrition.models import MealEntry
from app.nutrition.needs import Needs

MEAL_TYPES = ("breakfast", "lunch", "dinner", "snack")
MAX_GRAMS = 5000
MAX_PORTION_COUNT = 20


@dataclass(frozen=True)
class DailySummary:
    day: date
    meals: dict[str, Nutrients]
    total: Nutrients
    incomplete_fields: tuple[str, ...]
    needs: Needs
    remaining: dict[str, float] | None


def get_food(food_id: str) -> Food:
    food = load_catalog().get(food_id)
    if food is None:
        raise AppError(404, "food_not_found", "营养库里没有这个食物")
    return food


def resolve_grams(food: Food, grams: float | None, portion: dict[str, Any] | None) -> float:
    if (grams is None) == (portion is None):
        raise AppError(422, "invalid_portion", "请填写克数或份量其中一项")
    if grams is not None:
        if not 0 < grams <= MAX_GRAMS:
            raise AppError(422, "invalid_portion", f"克数需要大于 0 且不超过 {MAX_GRAMS}")
        return float(grams)
    units = dict(food.portions)
    unit, count = portion["unit"], portion["count"]
    if unit not in units:
        raise AppError(422, "invalid_portion", f"这个食物没有“{unit}”这个份量单位，可选：{'、'.join(units) or '无'}")
    if not 0 < count <= MAX_PORTION_COUNT:
        raise AppError(422, "invalid_portion", f"份数需要大于 0 且不超过 {MAX_PORTION_COUNT}")
    return units[unit] * count


def _apply_snapshot(entry: MealEntry, food: Food, grams: float) -> None:
    entry.food_id, entry.food_name, entry.grams = food.id, food.name, grams
    serving = food.nutrients.scaled(grams)
    for name in NUTRIENT_FIELDS:
        setattr(entry, name, getattr(serving, name))


def entry_nutrients(entry: MealEntry) -> Nutrients:
    return Nutrients(**{name: getattr(entry, name) for name in NUTRIENT_FIELDS})


def log_meal(
    db: Session,
    user_id: uuid.UUID,
    *,
    eaten_on: date,
    meal_type: str,
    food_id: str,
    grams: float | None,
    portion: dict[str, Any] | None,
    note: str | None,
    today: date,
) -> MealEntry:
    if eaten_on > today:
        raise AppError(422, "meal_in_future", "不能记录未来日期的饮食")
    food = get_food(food_id)
    entry = MealEntry(user_id=user_id, eaten_on=eaten_on, meal_type=meal_type, note=note)
    _apply_snapshot(entry, food, resolve_grams(food, grams, portion))
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def update_meal(
    db: Session, user_id: uuid.UUID, entry_id: uuid.UUID, changes: dict[str, Any], today: date
) -> MealEntry:
    entry = get_owned_or_404(db, MealEntry, user_id, entry_id)
    eaten_on = changes.get("eaten_on", entry.eaten_on)
    if eaten_on > today:
        raise AppError(422, "meal_in_future", "不能记录未来日期的饮食")
    snapshot = None
    if {"food_id", "grams", "portion"} & changes.keys():  # 只有食物或份量变了才重算营养快照
        food = get_food(changes.get("food_id", entry.food_id))
        if "grams" in changes or "portion" in changes:
            grams = resolve_grams(food, changes.get("grams"), changes.get("portion"))
        else:
            grams = entry.grams
        snapshot = (food, grams)
    entry.eaten_on = eaten_on
    entry.meal_type = changes.get("meal_type", entry.meal_type)
    if "note" in changes:
        entry.note = changes["note"]
    if snapshot:
        _apply_snapshot(entry, *snapshot)
    db.commit()
    db.refresh(entry)
    return entry


def delete_meal(db: Session, user_id: uuid.UUID, entry_id: uuid.UUID) -> None:
    db.delete(get_owned_or_404(db, MealEntry, user_id, entry_id))
    db.commit()


def list_meals(db: Session, user_id: uuid.UUID, day: date) -> list[MealEntry]:
    entries = db.scalars(owned_by(MealEntry, user_id).where(MealEntry.eaten_on == day)).all()
    return sorted(entries, key=lambda e: (MEAL_TYPES.index(e.meal_type), e.created_at, str(e.id)))


def day_totals(db: Session, user_id: uuid.UUID, day: date) -> Nutrients:
    total = Nutrients(**{name: 0.0 for name in NUTRIENT_FIELDS})
    for entry in list_meals(db, user_id, day):
        total = total.plus(entry_nutrients(entry))
    return total


def daily_summary(db: Session, user_id: uuid.UUID, day: date, needs: Needs) -> DailySummary:
    zero = Nutrients(**{name: 0.0 for name in NUTRIENT_FIELDS})
    meals = {meal_type: zero for meal_type in MEAL_TYPES}
    incomplete: set[str] = set()
    total = zero
    for entry in list_meals(db, user_id, day):
        nutrients = entry_nutrients(entry)
        incomplete.update(name for name in NUTRIENT_FIELDS if getattr(nutrients, name) is None)
        meals[entry.meal_type] = meals[entry.meal_type].plus(nutrients)
        total = total.plus(nutrients)
    remaining = None
    if needs.status == "ok":
        remaining = {
            "energy_kcal": needs.energy_kcal - total.energy_kcal,
            "protein_g": needs.protein_g - total.protein_g,
            "sodium_mg": needs.sodium_mg_max - total.sodium_mg,
        }
    return DailySummary(day, meals, total, tuple(sorted(incomplete)), needs, remaining)
