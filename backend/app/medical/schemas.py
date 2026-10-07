import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field, field_validator

Category = Literal["diet_avoid", "diet_require", "medication_diet", "exercise_limit", "other"]
ItemStatus = Literal["pending_confirmation", "active", "pending_review", "resolved", "voided"]
Confidence = Literal["high", "medium", "low"]
EventSource = Literal["user", "system", "extractor", "agent"]
Subject = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
Content = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]

# 字段说明：进入接口文档与 SDK 能力清单，智能体按它填写参数。
CATEGORY_TEXT = (
    "类别取值：diet_avoid 饮食禁忌，diet_require 饮食要求，medication_diet 用药期间的饮食禁忌，"
    "exercise_limit 运动限制，other 其他"
)
STATUS_TEXT = (
    "状态取值：pending_confirmation 待用户确认，active 生效中，pending_review 待复核，resolved 已解除，voided 已作废"
)
ITEM_ID_TEXT = (
    "医嘱条目编号（UUID），取自列出医嘱条目（list_items）或待处理列表（list_reviews）结果里的 id，"
    "或今天的约束（get_constraints）结果里的 item_id"
)


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)] = Field(
        description="医嘱、病历或复诊单的原文，1 至 5000 个字；照用户给出的原文提交，不要改写或补充"
    )
    order_date: date | None = Field(
        default=None, description="医嘱开具日期，格式 YYYY-MM-DD，不能晚于今天；不填表示今天"
    )


class ManualItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category
    content: Content
    subjects: list[Subject] = Field(default_factory=list, max_length=30)
    start_date: date | None = None
    end_date: date | None = None
    review_date: date | None = None


class ItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category | None = Field(default=None, description=f"条目类别；不填表示不修改，不能填 null。{CATEGORY_TEXT}")
    content: Content | None = Field(
        default=None, description="条目内容，1 至 500 个字；不填表示不修改，不能填 null"
    )
    subjects: list[Subject] | None = Field(
        default=None,
        max_length=30,
        description="涉及的食物或行为，例如 辛辣、酒；每项 1 至 64 个字，最多 30 项；不填表示不修改，不能填 null；确认时至少要有一项",
    )
    start_date: date | None = Field(
        default=None, description="生效日期，格式 YYYY-MM-DD；不填表示不修改，不能填 null；生效中的条目不能改到今天之后"
    )
    end_date: date | None = Field(
        default=None, description="预计结束日期，格式 YYYY-MM-DD，不能早于生效日期；填 null 表示长期；不填表示不修改"
    )
    review_date: date | None = Field(
        default=None, description="复查日期，格式 YYYY-MM-DD，不能早于生效日期；填 null 表示没有复查日；不填表示不修改"
    )

    @field_validator("category", "content", "subjects", "start_date")
    @classmethod
    def not_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("这个字段不能为空")
        return value


class ReasonBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason | None = Field(default=None, description="理由，可不填；填写时 1 至 500 个字")


class ProposalBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason = Field(description="提出解除建议的理由，例如医生复查后允许恢复，1 至 500 个字")


class ContinueBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    end_date: date | None = Field(
        default=None,
        description="新的预计结束日期，格式 YYYY-MM-DD，不能早于生效日期，且至少在今天之后两天（否则仍算到期）；不填表示不设结束日期",
    )
    review_date: date | None = Field(
        default=None, description="新的复查日期，格式 YYYY-MM-DD，不能早于生效日期，且必须晚于今天；不填表示不设复查日期"
    )


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    category: Category
    status: ItemStatus
    origin: Literal["extracted", "manual"]
    confidence: Confidence | None
    content: str
    subjects: list[str]
    source_excerpt: str | None
    start_date: date
    end_date: date | None
    review_date: date | None
    missing_fields: list[str]
    notes: list[str]
    resolution_proposed_at: datetime | None
    resolution_reason: str | None
    confirmed_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def low_confidence(self) -> bool:
        return self.confidence == "low"


class IgnoredOut(BaseModel):
    text: str
    reason: str


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime


class OrderOut(BaseModel):
    id: uuid.UUID
    order_date: date
    source_text: str
    extractor: str
    created_at: datetime
    ignored: list[IgnoredOut]
    notes: list[str]
    items: list[ItemOut]
    evidence: list[EvidenceOut]


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seq: int
    occurred_at: datetime
    action: str
    from_status: ItemStatus | None
    to_status: ItemStatus
    source: EventSource
    detail: dict[str, Any] | None


class ConstraintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: uuid.UUID
    category: Category
    content: str
    subjects: list[str]
    start_date: date
    end_date: date | None
    review_date: date | None
    status: ItemStatus
    needs_review: bool
    resolution_proposed: bool


class ConstraintsOut(BaseModel):
    constraints: list[ConstraintOut]
    reminder: str
