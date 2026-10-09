import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Gender = Literal["female", "male", "other"]
ActivityLevel = Literal["sedentary", "light", "moderate", "active", "very_active"]
Goal = Literal["lose_fat", "gain_muscle", "maintain", "none"]
Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    gender: Gender | None
    birth_year: int | None
    height_cm: float | None
    weight_kg: float | None
    activity_level: ActivityLevel | None
    goal: Goal | None
    diet_preferences: list[str]
    food_avoidances: list[str]
    health_conditions: str | None
    notes: str | None
    cycle_tracking_opt_out: bool
    updated_at: datetime


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gender: Gender | None = None
    birth_year: int | None = Field(default=None, ge=1900)
    height_cm: float | None = Field(default=None, ge=50, le=250)
    weight_kg: float | None = Field(default=None, ge=20, le=300)
    activity_level: ActivityLevel | None = None
    goal: Goal | None = None
    diet_preferences: list[Tag] | None = Field(default=None, max_length=30)
    food_avoidances: list[Tag] | None = Field(default=None, max_length=30)
    health_conditions: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=1000)
    cycle_tracking_opt_out: bool | None = None

    @field_validator("birth_year")
    @classmethod
    def not_in_future(cls, value: int | None) -> int | None:
        if value is not None and value > datetime.now(UTC).year:
            raise ValueError("出生年份不能晚于今年")
        return value


class ProfileBasicsOut(BaseModel):
    """给智能体与 SDK 调用方的档案内容：只含生活方式建议用得上的字段，不含健康状况与备注这类自由文字。"""

    model_config = ConfigDict(from_attributes=True)

    gender: Gender | None
    birth_year: int | None
    height_cm: float | None
    weight_kg: float | None
    activity_level: ActivityLevel | None
    goal: Goal | None
    diet_preferences: list[str]
    food_avoidances: list[str]
    cycle_tracking_opt_out: bool
    updated_at: datetime


class ProfileChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    changed_at: datetime
    changes: dict[str, Any]
