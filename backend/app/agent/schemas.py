import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.agent.preferences import MAX_PREFERENCE_CHARS

TitleText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
PreferenceSource = Literal["agent", "user"]
MAX_MESSAGE_CHARS = 2000


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: TitleText | None = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    """给前端看的消息：只有用户与助手的可见内容，没有工具调用、工具结果与 provider_state。"""

    role: Literal["user", "assistant"]
    text: str
    evidence: str  # 依据段（evidence_section 的结果），没有时为空串
    flags: list[str]
    created_at: datetime


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARS)]
    stream: bool = True


class TurnOut(BaseModel):
    """一轮对话的结果；流式时 done 事件里是除 text 以外的字段。"""

    message_id: uuid.UUID
    text: str
    evidence: str
    flags: list[str]
    tools_used: list[str]


class ConversationDetailOut(ConversationOut):
    messages: list[MessageOut]


class PreferenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_PREFERENCE_CHARS)]


class PreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content: str
    source: PreferenceSource
    created_at: datetime


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    openings_enabled: bool


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    openings_enabled: bool


class OpeningOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    question: str


class OpeningResponse(BaseModel):
    opening: OpeningOut | None
