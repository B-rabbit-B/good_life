import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

CycleStatus = Literal["tracking", "pregnant", "paused"]


class PeriodCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date
    end_date: date | None = None


class PeriodUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date | None = None
    end_date: date | None = None

    @field_validator("start_date")
    @classmethod
    def start_date_not_null(cls, value: date | None) -> date:
        if value is None:
            raise ValueError("开始日期不能为空")
        return value


class PeriodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    start_date: date
    end_date: date | None
    created_at: datetime


class CycleSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CycleStatus


class CycleSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: CycleStatus
    updated_at: datetime


Flow = Literal["none", "spotting", "light", "medium", "heavy"]
Mood = Literal["good", "normal", "low", "irritable", "anxious"]
Symptom = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]


class DayLogIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flow: Flow | None = None
    pain: int | None = Field(default=None, ge=0, le=3)
    mood: Mood | None = None
    symptoms: list[Symptom] = Field(default_factory=list, max_length=20)
    note: str | None = Field(default=None, max_length=500)


class DayLogOut(BaseModel):
    log_date: date
    flow: Flow | None
    pain: int | None
    mood: Mood | None
    symptoms: list[str]
    note: str | None
    updated_at: datetime

    @classmethod
    def from_record(cls, record: Any) -> "DayLogOut":
        return cls(log_date=record.log_date, updated_at=record.updated_at, **record.details)


class DateRangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    earliest: date
    latest: date


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: Literal["ok", "insufficient_data", "paused"]
    next_period_start: date | None
    next_period_range: DateRangeOut | None
    ovulation_day: date | None
    ovulation_range: DateRangeOut | None
    fertile_window: DateRangeOut | None
    flags: list[str]
    notes: list[str]
    disclaimer: str


class PhaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    phase: Literal["menstrual", "follicular", "ovulation", "luteal", "unknown"]
    cycle_day: int | None
    days_until_next_period: int | None
    is_predicted: bool
    reason: str | None


class SymptomCountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symptom: str
    days: int


class CycleStatsOut(BaseModel):
    cycle_count: int
    period_count: int
    avg_cycle_length: float | None
    cycle_length_std: float | None
    shortest_cycle: int | None
    longest_cycle: int | None
    avg_period_length: float | None
    recent_cycle_lengths: list[int]
    logged_days: int
    top_symptoms: list[SymptomCountOut]
    average_pain_on_bleeding_days: float | None


class TipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    phase: str
    category: str
    severity: str
    title: str
    content: str
    basis: str


class TipsOut(BaseModel):
    phase: PhaseOut
    tips: list[TipOut]
    disclaimer: str
