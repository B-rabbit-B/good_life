import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.nutrition.catalog import NUTRIENT_FIELDS, Nutrients, round_one

MealType = Literal["breakfast", "lunch", "dinner", "snack"]
MatchType = Literal["exact_name", "common_name", "exact_alias", "prefix", "contains", "query_contains"]
Conclusion = Literal["suitable", "caution", "not_recommended"]
ReasonSource = Literal["medical", "cycle", "goal", "training", "intake", "preference"]
ReasonEffect = Literal["block", "unverifiable", "caution", "prefer", "info"]
SUMMARY_DISCLAIMER = "以上汇总与需求都是估算，仅供参考，不构成医疗建议；有医嘱时以医嘱为准。"


class NutrientsOut(BaseModel):
    energy_kcal: float | None = None
    protein_g: float | None = None
    fat_g: float | None = None
    carbohydrate_g: float | None = None
    fiber_g: float | None = None
    sodium_mg: float | None = None
    iron_mg: float | None = None
    calcium_mg: float | None = None


def nutrients_out(nutrients: Nutrients) -> NutrientsOut:
    return NutrientsOut(**{name: round_one(getattr(nutrients, name)) for name in NUTRIENT_FIELDS})


class TagOut(BaseModel):
    id: str
    name: str
    kind: str
    basis: str
    review_status: str


class SourceOut(BaseModel):
    dataset: str
    reference: str
    license_status: str
    note: str


class PortionOut(BaseModel):
    unit: str
    grams: float


class FoodSummaryOut(BaseModel):
    id: str
    name: str
    aliases: list[str]
    category: str
    kind: str
    match: MatchType


class SearchOut(BaseModel):
    query: str
    found: bool
    exact: bool
    results: list[FoodSummaryOut]
    message: str


class FoodDetailOut(BaseModel):
    id: str
    name: str
    aliases: list[str]
    category: str
    kind: str
    nutrients_per_100g: NutrientsOut
    tags: list[TagOut]
    portions: list[PortionOut]
    default_grams: float
    source: SourceOut


class PortionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit: Annotated[str, Field(min_length=1, max_length=8)]
    count: Annotated[float, Field(allow_inf_nan=False)]


class MealCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eaten_on: dt.date
    meal_type: MealType
    food_id: Annotated[str, Field(min_length=1, max_length=64)]
    grams: Annotated[float, Field(allow_inf_nan=False)] | None = None
    portion: PortionIn | None = None
    note: Annotated[str, Field(max_length=200)] | None = None


class MealUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eaten_on: dt.date | None = None
    meal_type: MealType | None = None
    food_id: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    grams: Annotated[float, Field(allow_inf_nan=False)] | None = None
    portion: PortionIn | None = None
    note: Annotated[str, Field(max_length=200)] | None = None

    @field_validator("eaten_on", "meal_type", "food_id")
    @classmethod
    def not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("这个字段不能为空")
        return value


class MealOut(BaseModel):
    id: uuid.UUID
    eaten_on: dt.date
    meal_type: MealType
    food_id: str
    food_name: str
    grams: float
    nutrients: NutrientsOut
    note: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


class NeedsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: Literal["ok", "insufficient_profile"]
    missing_fields: list[str]
    energy_kcal: int | None
    energy_kcal_low: int | None
    energy_kcal_high: int | None
    protein_g: int | None
    fat_g_low: int | None
    fat_g_high: int | None
    carbohydrate_g_low: int | None
    carbohydrate_g_high: int | None
    fiber_g_low: int | None
    fiber_g_high: int | None
    sodium_mg_max: int | None
    notes: list[str]


class SummaryOut(BaseModel):
    date: dt.date
    meals: dict[str, NutrientsOut]
    total: NutrientsOut
    incomplete_fields: list[str]
    needs: NeedsOut
    remaining: dict[str, float] | None
    disclaimer: str


class MealItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    food_id: Annotated[str, Field(min_length=1, max_length=64)]
    grams: Annotated[float, Field(allow_inf_nan=False)] | None = None
    portion: PortionIn | None = None

    @model_validator(mode="after")
    def at_most_one_amount(self) -> "MealItemIn":
        if self.grams is not None and self.portion is not None:
            raise ValueError("克数和份量最多填写一项")
        return self


class EvaluateIn(MealItemIn):
    pass


class EvaluateMealIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: Annotated[list[MealItemIn], Field(min_length=1, max_length=20)]


class ReasonOut(BaseModel):
    source: ReasonSource
    effect: ReasonEffect
    code: str
    message: str
    ref: str


class EvaluationOut(BaseModel):
    food_id: str
    food_name: str
    grams: float
    nutrients: NutrientsOut
    conclusion: Conclusion
    reasons: list[ReasonOut]
    tradeoff: str
    data_source: str
    disclaimer: str


class MealEvaluationOut(BaseModel):
    items: list[EvaluationOut]
    conclusion: Conclusion
    total: NutrientsOut
    disclaimer: str
