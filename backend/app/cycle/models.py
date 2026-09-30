import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.ownership import UserOwnedMixin
from app.db import Base
from app.security.crypto import EncryptedJSON


class CyclePeriod(UserOwnedMixin, Base):
    """一次月经。起止日期明文存储，预测需要按日期排序与查询。"""

    __tablename__ = "cycle_periods"
    __table_args__ = (UniqueConstraint("user_id", "start_date", name="uq_cycle_periods_user_start"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CycleDayLog(UserOwnedMixin, Base):
    """某一天的记录。流量、疼痛、情绪、症状、备注整体加密。"""

    __tablename__ = "cycle_day_logs"
    __table_args__ = (UniqueConstraint("user_id", "log_date", name="uq_cycle_day_logs_user_date"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    log_date: Mapped[date] = mapped_column(Date)
    details: Mapped[dict[str, Any]] = mapped_column(EncryptedJSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CycleSettings(Base):
    __tablename__ = "cycle_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="tracking", server_default=text("'tracking'"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
