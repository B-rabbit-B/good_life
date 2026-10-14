from pydantic import BaseModel, ConfigDict, Field, field_validator

DELETE_CONFIRM_MESSAGE = "请勾选确认后再删除"


class PasswordConfirm(BaseModel):
    """敏感操作前复核本人密码。"""

    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=128)


class AccountDelete(PasswordConfirm):
    confirm: bool = Field(description="用户勾选了“我知道删除后不能恢复”，必须为 true")

    @field_validator("confirm")
    @classmethod
    def must_confirm(cls, value: bool) -> bool:
        if not value:
            raise ValueError(DELETE_CONFIRM_MESSAGE)
        return value
