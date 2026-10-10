import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.nutrition.schemas import Conclusion, MealType, NutrientsOut, ReasonEffect, ReasonSource
from app.photos.recognition import MAX_ITEMS, MAX_NAME_LENGTH

RecognitionStatus = Literal["draft", "confirmed", "discarded"]
ItemStatus = Literal["matched", "needs_confirmation"]
MIN_USER_GRAMS = 1
MAX_USER_GRAMS = 3000


class ItemIn(BaseModel):
    """修正后的一个识别项。带 id 表示修改原有的项，不带表示新增。"""

    model_config = ConfigDict(extra="forbid")

    id: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_NAME_LENGTH)]
    portion_text: Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_NAME_LENGTH)] | None = None
    grams: Annotated[float, Field(ge=MIN_USER_GRAMS, le=MAX_USER_GRAMS, allow_inf_nan=False)] | None = None
    food_id: Annotated[str, Field(min_length=1, max_length=64)] | None = None


class ItemsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: Annotated[list[ItemIn], Field(max_length=MAX_ITEMS)]


class ConfirmIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eaten_on: dt.date
    meal_type: MealType


class CandidateOut(BaseModel):
    food_id: str
    name: str


class ItemSourceOut(BaseModel):
    dataset: str
    license_status: str
    note: str


class ItemOut(BaseModel):
    id: str
    name: str
    portion_text: str
    grams: float
    grams_source: str
    confidence: float
    status: ItemStatus
    food_id: str | None
    food_name: str | None
    match_type: str | None
    candidates: list[CandidateOut]
    nutrients: NutrientsOut | None
    source: ItemSourceOut | None
    review_reasons: list[str]


class ReasonOut(BaseModel):
    source: ReasonSource
    effect: ReasonEffect
    code: str
    message: str
    ref: str


class ItemEvaluationOut(BaseModel):
    item_id: str
    food_name: str
    conclusion: Conclusion
    reasons: list[ReasonOut]
    tradeoff: str


class EvaluationOut(BaseModel):
    conclusion: Conclusion
    items: list[ItemEvaluationOut]
    disclaimer: str


class RecognitionSummaryOut(BaseModel):
    id: uuid.UUID
    status: RecognitionStatus
    items: list[ItemOut]
    totals: NutrientsOut
    needs_review: bool
    disclaimer: str
    note: str | None
    image_kept: bool
    model_id: str
    eaten_on: dt.date | None
    meal_type: MealType | None
    meal_entry_ids: list[uuid.UUID] | None
    created_at: dt.datetime
    updated_at: dt.datetime


class RecognitionOut(RecognitionSummaryOut):
    evaluation: EvaluationOut | None
