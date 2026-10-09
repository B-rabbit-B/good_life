import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.common.ownership import UserOwnedMixin
from app.db import Base
from app.security.crypto import EncryptedJSON


class AgentConversation(UserOwnedMixin, Base):
    """一段与智能体的对话。标题加密存储，可为空。"""

    __tablename__ = "agent_conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str | None] = mapped_column(EncryptedJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AgentMessage(UserOwnedMixin, Base):
    """对话里的一条消息。内容整体加密：text、tool_calls、tool_call_id、tool_name、provider_state、evidence、flags。

    position 在会话内从 1 递增，由 append_message 在锁住会话行后分配；唯一约束是并发写入的最后一道防线。
    """

    __tablename__ = "agent_messages"
    __table_args__ = (UniqueConstraint("conversation_id", "position", name="uq_agent_messages_conversation_position"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[dict[str, Any]] = mapped_column(EncryptedJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentPreference(UserOwnedMixin, Base):
    """偏好记忆：只存口味、习惯这类软偏好，医嘱与健康状况类内容在写入前已被过滤。"""

    __tablename__ = "agent_preferences"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    content: Mapped[str] = mapped_column(EncryptedJSON)
    source: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentOpening(UserOwnedMixin, Base):
    """某天主动问过的一个开场问题；同一用户同一天同一类只会有一条。"""

    __tablename__ = "agent_openings"
    __table_args__ = (UniqueConstraint("user_id", "day", "kind", name="uq_agent_openings_user_day_kind"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    day: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    question: Mapped[str] = mapped_column(EncryptedJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentSettings(UserOwnedMixin, Base):
    """智能体设置，每个用户一行。"""

    __tablename__ = "agent_settings"
    __table_args__ = (UniqueConstraint("user_id", name="uq_agent_settings_user"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    openings_enabled: Mapped[bool] = mapped_column(Boolean, server_default=true(), default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
