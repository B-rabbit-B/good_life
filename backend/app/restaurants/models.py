import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.common.ownership import UserOwnedMixin
from app.db import Base
from app.security.crypto import EncryptedJSON


class RestaurantSettings(UserOwnedMixin, Base):
    """附近餐厅设置，每个用户一行：定位授权状态与（用户选择记住时的）粗略区域。

    精确坐标、手动输入的地点原文与检索内容都不入库；粗略区域加密存储，坐标取整到小数点后两位。
    """

    __tablename__ = "restaurant_settings"
    __table_args__ = (UniqueConstraint("user_id", name="uq_restaurant_settings_user"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    location_consent: Mapped[str] = mapped_column(String(16), server_default="not_asked", default="not_asked")
    consent_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    area: Mapped[dict[str, Any] | None] = mapped_column(EncryptedJSON)  # {"name", "adcode", "lng", "lat"}
    area_saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
