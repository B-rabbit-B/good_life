import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Identity, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.ownership import UserOwnedMixin
from app.db import Base
from app.security.crypto import EncryptedBytes, EncryptedJSON


class MedicalOrder(UserOwnedMixin, Base):
    """用户录入的一份医嘱原文，以及提取时被忽略的句子与说明。"""

    __tablename__ = "medical_orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_date: Mapped[date] = mapped_column(Date)
    source_text: Mapped[str] = mapped_column(EncryptedJSON)
    extractor: Mapped[str] = mapped_column(String(32))
    extraction_notes: Mapped[dict[str, Any]] = mapped_column(EncryptedJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MedicalEvidence(UserOwnedMixin, Base):
    """医嘱图片或文档，加密保存，只对本人可见。"""

    __tablename__ = "medical_evidence"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medical_orders.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(EncryptedJSON)
    content_type: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    content: Mapped[bytes] = mapped_column(EncryptedBytes, deferred=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MedicalItem(UserOwnedMixin, Base):
    """一条结构化医嘱约束。日期、类别、状态明文，便于查询与判断到期；内容加密。"""

    __tablename__ = "medical_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medical_orders.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24))
    origin: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[str | None] = mapped_column(String(8))
    content: Mapped[str] = mapped_column(EncryptedJSON)
    subjects: Mapped[list[str]] = mapped_column(EncryptedJSON)
    source_excerpt: Mapped[str | None] = mapped_column(EncryptedJSON)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    review_date: Mapped[date | None] = mapped_column(Date)
    missing_fields: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    notes: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    resolution_proposed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_reason: Mapped[str | None] = mapped_column(EncryptedJSON)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MedicalItemEvent(UserOwnedMixin, Base):
    """审计记录：每次创建、修改与状态变化各一条。"""

    __tablename__ = "medical_item_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medical_items.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    action: Mapped[str] = mapped_column(String(32))
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    source: Mapped[str] = mapped_column(String(16))
    detail: Mapped[dict[str, Any] | None] = mapped_column(EncryptedJSON)
