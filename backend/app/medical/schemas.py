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


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
    order_date: date | None = None


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

    category: Category | None = None
    content: Content | None = None
    subjects: list[Subject] | None = Field(default=None, max_length=30)
    start_date: date | None = None
    end_date: date | None = None
    review_date: date | None = None

    @field_validator("category", "content", "subjects", "start_date")
    @classmethod
    def not_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("这个字段不能为空")
        return value


class ReasonBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason | None = None


class ProposalBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason


class ContinueBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    end_date: date | None = None
    review_date: date | None = None


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
