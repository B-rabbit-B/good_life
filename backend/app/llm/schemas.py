import base64
import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ProviderKind = Literal["openai_compatible", "anthropic", "gemini"]
ModelSource = Literal["fetched", "manual"]
Purpose = Literal["chat", "vision"]
Conclusion = Literal[
    "ok", "ok_listing_unsupported", "invalid_key", "bad_url", "model_unavailable",
    "quota_exceeded", "rate_limited", "timeout", "provider_error", "bad_request",
]
ImageMime = Literal["image/png", "image/jpeg", "image/webp", "image/gif"]
ModelIdText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BASE64_CHARS = (MAX_IMAGE_BYTES + 2) // 3 * 4


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


class ProviderTest(BaseModel):
    """测试还没保存的服务；model_id 是模型编号字符串，给了才做对话测试。"""

    model_config = ConfigDict(extra="forbid")

    kind: ProviderKind
    base_url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    api_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    model_id: ModelIdText | None = None


class SavedProviderTest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: ModelIdText | None = None


class StepReportOut(BaseModel):
    ok: bool
    code: str | None
    message: str


class ConnectionReportOut(BaseModel):
    conclusion: Conclusion
    ok: bool
    message: str
    listing: StepReportOut
    chat: StepReportOut | None
    models_found: int | None
    sample_models: list[str]


class FetchModelsOut(BaseModel):
    added: int
    total: int
    skipped: int
    models: list[ModelOut]


class ImageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mime_type: ImageMime
    data_base64: Annotated[str, StringConstraints(min_length=1, max_length=MAX_IMAGE_BASE64_CHARS)]

    @field_validator("data_base64")
    @classmethod
    def _decodable_and_small(cls, value: str) -> str:
        try:
            data = base64.b64decode(value, validate=True)
        except ValueError:  # 含非法字符、补位不对，或含非 ASCII 字符
            raise ValueError("图片的 base64 编码不合法") from None
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError("单张图片解码后不能超过 5 MB")
        return value


class MessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    text: Annotated[str, StringConstraints(max_length=20000)]
    images: Annotated[list[ImageIn], Field(max_length=4)] = []


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: Purpose
    messages: Annotated[list[MessageIn], Field(min_length=1, max_length=50)]
    max_tokens: Annotated[int, Field(ge=1, le=4096)] = 1024


class ToolCallOut(BaseModel):
    name: str
    arguments: dict
    call_id: str | None


class UsageOut(BaseModel):
    input_tokens: int | None
    output_tokens: int | None


class ChatOut(BaseModel):
    text: str
    tool_calls: list[ToolCallOut]
    model_id: str
    provider_name: str
    usage: UsageOut
