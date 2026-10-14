import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

AGE_CONFIRM_MESSAGE = "请确认你已年满 14 周岁"


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)
    age_confirmed: bool = Field(description="用户确认已年满 14 周岁，必须为 true；只做校验，不入库")

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.lower()

    @field_validator("age_confirmed")
    @classmethod
    def must_confirm_age(cls, value: bool) -> bool:
        if not value:
            raise ValueError(AGE_CONFIRM_MESSAGE)
        return value


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.lower()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    created_at: datetime
