import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

ProviderKind = Literal["openai_compatible", "anthropic", "gemini"]
ModelSource = Literal["fetched", "manual"]
Purpose = Literal["chat", "vision"]


class ProviderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    kind: ProviderKind
    base_url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    api_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class ProviderUpdate(BaseModel):
    """服务类型不可改（extra=forbid 会拒绝 kind）；字段缺省或为 null 都表示保持原值。"""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)] | None = None
    base_url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)] | None = None
    api_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)] | None = None


class ModelCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = None


class OverridesUpdate(BaseModel):
    """出现的项才会修改；值为 true、false 或 null（null 表示回到对照表）。"""

    model_config = ConfigDict(extra="forbid")

    vision: bool | None = None
    tools: bool | None = None
    chat: bool | None = None


class AssignmentSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: uuid.UUID


class PresetOut(BaseModel):
    id: str
    name: str
    kind: ProviderKind
    base_url: str


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: ProviderKind
    base_url: str
    key_hint: str
    created_at: dt.datetime
    updated_at: dt.datetime


class CapabilitiesOut(BaseModel):
    vision: bool | None
    tools: bool | None
    chat: bool | None


class ModelOut(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    model_id: str
    display_name: str | None
    source: ModelSource
    capabilities: CapabilitiesOut
    table_capabilities: CapabilitiesOut
    overrides: CapabilitiesOut
    capability_note: str | None


class ModelUpdatedOut(ModelOut):
    assignment_warnings: list[str]


class AssignmentOut(BaseModel):
    purpose: Purpose
    model: ModelOut
    provider_name: str
