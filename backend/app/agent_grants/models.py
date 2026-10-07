import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.common.ownership import UserOwnedMixin
from app.db import Base


class AgentGrant(UserOwnedMixin, Base):
    """用户签发给智能体的授权。只存令牌的 SHA-256 哈希，明文只在创建时返回一次。"""

    __tablename__ = "agent_grants"
    __table_args__ = (Index("uq_agent_grants_token_hash", "token_hash", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50))
    token_hash: Mapped[str] = mapped_column(String(64))
    access: Mapped[str] = mapped_column(String(16))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SdkCallAudit(Base):
    """每次 SDK 调用（含被拒绝的）一行。绝不记录参数、返回内容、令牌或医嘱正文。

    未认证的调用没有用户，所以 user_id 可空，不使用 UserOwnedMixin；查询仍统一从 owned_by 开始。
    """

    __tablename__ = "sdk_call_audits"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    grant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_grants.id", ondelete="SET NULL"))
    credential_kind: Mapped[str] = mapped_column(String(16))
    client_name: Mapped[str] = mapped_column(String(64))
    capability: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(8))
    error_code: Mapped[str | None] = mapped_column(String(64))
    duration_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
