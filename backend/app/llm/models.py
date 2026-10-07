import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.common.ownership import UserOwnedMixin
from app.db import Base
from app.security.crypto import EncryptedJSON


class LlmProvider(UserOwnedMixin, Base):
    """用户配置的一个模型服务。密钥加密保存且延迟加载，只有真正调用服务的代码才会读取。"""

    __tablename__ = "llm_providers"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_llm_providers_user_name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50))
    kind: Mapped[str] = mapped_column(String(32))
    base_url: Mapped[str] = mapped_column(String(300))
    api_key: Mapped[str] = mapped_column(EncryptedJSON, deferred=True)
    key_hint: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LlmModel(UserOwnedMixin, Base):
    """某个服务下的一个模型。三个覆盖列为真、假或空（空表示以对照表为准）。"""

    __tablename__ = "llm_models"
    __table_args__ = (UniqueConstraint("provider_id", "model_id", name="uq_llm_models_provider_model"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("llm_providers.id", ondelete="CASCADE"), index=True)
    model_id: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(16))
    vision_override: Mapped[bool | None] = mapped_column(Boolean)
    tools_override: Mapped[bool | None] = mapped_column(Boolean)
    chat_override: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LlmAssignment(UserOwnedMixin, Base):
    """用途（chat、vision）到模型的分配，每个用户每个用途至多一条。"""

    __tablename__ = "llm_assignments"
    __table_args__ = (UniqueConstraint("user_id", "purpose", name="uq_llm_assignments_user_purpose"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    purpose: Mapped[str] = mapped_column(String(16))
    llm_model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("llm_models.id", ondelete="CASCADE"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
