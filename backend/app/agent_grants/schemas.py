import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Access = Literal["read", "read_write"]
GrantStatus = Literal["active", "expired", "revoked"]

TOKEN_NOTICE = "令牌只显示这一次，请立即保存；遗失后只能吊销并重新创建。"


class GrantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    access: Access
    expires_in_days: Annotated[int, Field(ge=1, le=365)] = 90


class GrantCreatedOut(BaseModel):
    id: uuid.UUID
    name: str
    access: Access
    expires_at: dt.datetime
    created_at: dt.datetime
    token: str
    token_notice: str = TOKEN_NOTICE


class GrantOut(BaseModel):
    id: uuid.UUID
    name: str
    access: Access
    status: GrantStatus
    expires_at: dt.datetime
    created_at: dt.datetime
    revoked_at: dt.datetime | None
    last_used_at: dt.datetime | None


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    grant_id: uuid.UUID | None
    credential_kind: str
    client_name: str
    capability: str
    outcome: str
    error_code: str | None
    duration_ms: int
    created_at: dt.datetime
