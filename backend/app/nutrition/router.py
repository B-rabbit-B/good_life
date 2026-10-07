import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.clock import get_today
from app.db import get_db
from app.nutrition import meals
from app.nutrition.context import build_context, needs_for_day
from app.nutrition.engine import Evaluation, evaluate_food, evaluate_meal
from app.nutrition.catalog import EXACT_MATCH_TYPES, Food, TagDefinition, load_catalog, round_one
from app.nutrition.deps import require_nutrition_user
from app.nutrition.models import MealEntry
from app.nutrition.schemas import (
    SUMMARY_DISCLAIMER,
    FoodDetailOut,
    EvaluateIn,
    EvaluateMealIn,
    EvaluationOut,
    FoodSummaryOut,
    MealCreate,
    MealEvaluationOut,
    MealItemIn,
    MealOut,
    MealUpdate,
    NeedsOut,
    PortionOut,
    ReasonOut,
    SearchOut,
    SourceOut,
    SummaryOut,
    TagOut,
    nutrients_out,
)

router = APIRouter(prefix="/api/nutrition", tags=["nutrition"])

NutritionUser = Annotated[User, Depends(require_nutrition_user)]
DbSession = Annotated[Session, Depends(get_db)]
Today = Annotated[date, Depends(get_today)]
DayQuery = Annotated[date | None, Query(alias="date")]
PARTIAL_MATCH_MESSAGE = "没有完全一致的食物，下面是名称相近的候选，请确认是否是你要找的"


def _tag_out(tag: TagDefinition) -> TagOut:
    return TagOut(id=tag.id, name=tag.name, kind=tag.kind, basis=tag.basis, review_status=tag.review_status)


def _food_detail(food: Food) -> FoodDetailOut:
    catalog = load_catalog()
    tags = sorted((catalog.tags[tag_id] for tag_id in food.tags), key=lambda tag: (tag.kind, tag.id))
    return FoodDetailOut(
        id=food.id,
        name=food.name,
        aliases=list(food.aliases),
        category=food.category,
        kind=food.kind,
        nutrients_per_100g=nutrients_out(food.nutrients),
        tags=[_tag_out(tag) for tag in tags],
        portions=[PortionOut(unit=unit, grams=grams) for unit, grams in food.portions],
        default_grams=food.default_grams,
        source=SourceOut(
            dataset=food.source.dataset,
            reference=food.source.reference,
            license_status=food.source.license_status,
            note=food.source.note,
        ),
    )


def _meal_out(entry: MealEntry) -> MealOut:
    return MealOut(
        id=entry.id,
        eaten_on=entry.eaten_on,
        meal_type=entry.meal_type,
        food_id=entry.food_id,
        food_name=entry.food_name,
        grams=entry.grams,
        nutrients=nutrients_out(meals.entry_nutrients(entry)),
        note=entry.note,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.get("/foods/search", response_model=SearchOut)
def search_foods(user: NutritionUser, q: Annotated[str, Query(min_length=1, max_length=50)]) -> SearchOut:
    hits = load_catalog().search(q)
    results = [
        FoodSummaryOut(
            id=hit.food.id,
            name=hit.food.name,
            aliases=list(hit.food.aliases),
            category=hit.food.category,
            kind=hit.food.kind,
            match=hit.match,
        )
        for hit in hits
    ]
    exact = bool(results) and results[0].match in EXACT_MATCH_TYPES
    if not results:
        message = f"未找到与“{q}”匹配的食物，请换个说法或检查错别字"
    elif not exact:
        message = PARTIAL_MATCH_MESSAGE
    else:
        message = ""
    return SearchOut(query=q, found=bool(results), exact=exact, results=results, message=message)


@router.get("/foods/{food_id}", response_model=FoodDetailOut)
def get_food(food_id: str, user: NutritionUser) -> FoodDetailOut:
    return _food_detail(meals.get_food(food_id))


@router.get("/tags", response_model=list[TagOut])
def list_tags(user: NutritionUser) -> list[TagOut]:
    tags = sorted(load_catalog().tags.values(), key=lambda tag: (tag.kind, tag.id))
    return [_tag_out(tag) for tag in tags]


@router.post("/meals", status_code=201, response_model=MealOut)
def create_meal(body: MealCreate, user: NutritionUser, db: DbSession, today: Today) -> MealOut:
    entry = meals.log_meal(
        db,
        user.id,
        eaten_on=body.eaten_on,
        meal_type=body.meal_type,
        food_id=body.food_id,
        grams=body.grams,
        portion=body.portion.model_dump() if body.portion else None,
        note=body.note,
        today=today,
    )
    return _meal_out(entry)


@router.get("/meals", response_model=list[MealOut])
def list_meals(user: NutritionUser, db: DbSession, today: Today, day: DayQuery = None) -> list[MealOut]:
    return [_meal_out(entry) for entry in meals.list_meals(db, user.id, day or today)]


@router.patch("/meals/{entry_id}", response_model=MealOut)
def update_meal(entry_id: uuid.UUID, body: MealUpdate, user: NutritionUser, db: DbSession, today: Today) -> MealOut:
    return _meal_out(meals.update_meal(db, user.id, entry_id, body.model_dump(exclude_unset=True), today))


@router.delete("/meals/{entry_id}", status_code=204)
def delete_meal(entry_id: uuid.UUID, user: NutritionUser, db: DbSession) -> Response:
    meals.delete_meal(db, user.id, entry_id)
    return Response(status_code=204)


@router.get("/summary", response_model=SummaryOut)
def get_summary(user: NutritionUser, db: DbSession, today: Today, day: DayQuery = None) -> SummaryOut:
    target = day or today
    needs = needs_for_day(db, user.id, target, today)
    summary = meals.daily_summary(db, user.id, target, needs)
    return SummaryOut(
        date=target,
        meals={meal_type: nutrients_out(nutrients) for meal_type, nutrients in summary.meals.items()},
        total=nutrients_out(summary.total),
        incomplete_fields=list(summary.incomplete_fields),
        needs=NeedsOut.model_validate(summary.needs),
        remaining=None
        if summary.remaining is None
        else {name: round_one(value) for name, value in summary.remaining.items()},
        disclaimer=SUMMARY_DISCLAIMER,
    )


@router.get("/needs", response_model=NeedsOut)
def get_needs(user: NutritionUser, db: DbSession, today: Today) -> NeedsOut:
    return NeedsOut.model_validate(needs_for_day(db, user.id, today, today))


def _resolve_item(item: MealItemIn) -> tuple[Food, float]:
    food = meals.get_food(item.food_id)
    if item.grams is None and item.portion is None:
        return food, food.default_grams
    return food, meals.resolve_grams(food, item.grams, item.portion.model_dump() if item.portion else None)


def _evaluation_out(evaluation: Evaluation) -> EvaluationOut:
    return EvaluationOut(
        food_id=evaluation.food_id,
        food_name=evaluation.food_name,
        grams=evaluation.grams,
        nutrients=nutrients_out(evaluation.nutrients),
        conclusion=evaluation.conclusion,
        reasons=[ReasonOut(**vars(reason)) for reason in evaluation.reasons],
        tradeoff=evaluation.tradeoff,
        data_source=evaluation.data_source,
        disclaimer=evaluation.disclaimer,
    )


@router.post("/evaluate", response_model=EvaluationOut)
def evaluate(body: EvaluateIn, user: NutritionUser, db: DbSession, today: Today) -> EvaluationOut:
    food, grams = _resolve_item(body)
    context = build_context(db, user.id, today)
    return _evaluation_out(evaluate_food(food, grams, context, load_catalog()))


@router.post("/evaluate-meal", response_model=MealEvaluationOut)
def evaluate_meal_items(body: EvaluateMealIn, user: NutritionUser, db: DbSession, today: Today) -> MealEvaluationOut:
    items = [_resolve_item(item) for item in body.items]
    context = build_context(db, user.id, today)
    result = evaluate_meal(items, context, load_catalog())
    return MealEvaluationOut(
        items=[_evaluation_out(evaluation) for evaluation in result.items],
        conclusion=result.conclusion,
        total=nutrients_out(result.total),
        disclaimer=result.disclaimer,
    )
