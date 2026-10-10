import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.ownership import UserOwnedMixin
from app.db import Base
from app.security.crypto import EncryptedBytes, EncryptedJSON


class PhotoRecognition(UserOwnedMixin, Base):
    """一次拍照识别：草稿（可修正）→ 已确认（写入了饮食记录）或已放弃。

    识别项加密存储（模型的说明文字不保存）；图片只在用户选择保留时保存（处理后的 JPEG，加密、延迟加载）。
    """

    __tablename__ = "photo_recognitions"
    __table_args__ = (Index("ix_photo_recognitions_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(16))
    items: Mapped[list[dict[str, Any]]] = mapped_column(EncryptedJSON)
    image: Mapped[bytes | None] = mapped_column(EncryptedBytes, deferred=True)
    image_kept: Mapped[bool] = mapped_column(Boolean)
    model_id: Mapped[str] = mapped_column(String(200))
    eaten_on: Mapped[date | None] = mapped_column(Date)
    meal_type: Mapped[str | None] = mapped_column(String(16))
    meal_entry_ids: Mapped[list[str] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
