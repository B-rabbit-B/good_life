"""SDK 自己定义的参数模型（REST 里来自路径或查询参数的部分）；全部拒绝多余字段，都不含用户编号。"""

from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.medical.schemas import Category, ContinueBody, ItemStatus, ItemUpdate, Reason, ReasonBody


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DayParams(_Params):
    day: date | None = None


class QueryParams(_Params):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class FoodIdParams(_Params):
    food_id: Annotated[str, Field(min_length=1, max_length=64)]


class ItemIdParams(_Params):
    item_id: UUID


class ItemFilterParams(_Params):
    status: ItemStatus | None = None
    category: Category | None = None


class ProposalParams(_Params):
    item_id: UUID
    reason: Reason


class RangeParams(_Params):
    start: date | None = None
    end: date | None = None


class WeekParams(_Params):
    start: date | None = None


class ExerciseIdParams(_Params):
    exercise_id: Annotated[str, Field(min_length=1, max_length=80)]


# 医嘱需本人确认的能力：沿用对应接口的请求体字段与校验，再加 item_id。


class ConfirmItemParams(ItemUpdate):
    item_id: UUID


class UpdateItemParams(ItemUpdate):
    item_id: UUID


class ResolveItemParams(ReasonBody):
    item_id: UUID


class VoidItemParams(ReasonBody):
    item_id: UUID


class ContinueItemParams(ContinueBody):
    item_id: UUID
