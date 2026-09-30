import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

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
