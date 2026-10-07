"""SDK 自己定义的参数模型（REST 里来自路径或查询参数的部分）；全部拒绝多余字段，都不含用户编号。"""

from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.medical.schemas import (
    CATEGORY_TEXT,
    ITEM_ID_TEXT,
    STATUS_TEXT,
    Category,
    ContinueBody,
    ItemStatus,
    ItemUpdate,
    Reason,
    ReasonBody,
)

ItemId = Annotated[UUID, Field(description=ITEM_ID_TEXT)]


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DayParams(_Params):
    day: date | None = Field(default=None, description="要查看的日期，格式 YYYY-MM-DD；不填表示今天")


class QueryParams(_Params):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)] = Field(
        description="要搜索的名称或别名，1 至 50 个字，首尾空格会被去掉"
    )


class FoodIdParams(_Params):
    food_id: Annotated[str, Field(min_length=1, max_length=64)] = Field(
        description="食物编号，取自搜索食物（search_foods）结果里的 id，不要自己编造"
    )


class ItemIdParams(_Params):
    item_id: ItemId


class ItemFilterParams(_Params):
    status: ItemStatus | None = Field(default=None, description=f"按状态筛选，不填表示全部状态。{STATUS_TEXT}")
    category: Category | None = Field(default=None, description=f"按类别筛选，不填表示全部类别。{CATEGORY_TEXT}")


class ConstraintsParams(_Params):
    category: Category | None = Field(default=None, description=f"只看某一类约束，不填表示全部类别。{CATEGORY_TEXT}")


class ProposalParams(_Params):
    item_id: ItemId
    reason: Reason = Field(description="提出解除建议的理由，例如医生复查后允许恢复，1 至 500 个字")


class RangeParams(_Params):
    start: date | None = Field(
        default=None,
        description="开始日期，格式 YYYY-MM-DD；不填表示结束日期及之前共 7 天的第一天；不能晚于结束日期，整段最多 366 天",
    )
    end: date | None = Field(default=None, description="结束日期（含当天），格式 YYYY-MM-DD；不填表示今天")


class WeekParams(_Params):
    start: date | None = Field(
        default=None, description="这一周的开始日期，格式 YYYY-MM-DD，必须是星期一；不填表示本周"
    )


class ExerciseIdParams(_Params):
    exercise_id: Annotated[str, Field(min_length=1, max_length=80)] = Field(
        description="力量动作的编号，取自搜索动作（search_exercises）结果里的 id，不要自己编造"
    )


# 医嘱需本人确认的能力：沿用对应接口的请求体字段与校验，再加 item_id。


class ConfirmItemParams(ItemUpdate):
    item_id: ItemId


class UpdateItemParams(ItemUpdate):
    item_id: ItemId


class ResolveItemParams(ReasonBody):
    item_id: ItemId


class VoidItemParams(ReasonBody):
    item_id: ItemId


class ContinueItemParams(ContinueBody):
    item_id: ItemId
