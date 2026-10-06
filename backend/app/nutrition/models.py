import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.common.ownership import UserOwnedMixin
from app.db import Base
from app.security.crypto import EncryptedJSON


class MealEntry(UserOwnedMixin, Base):
    """一次饮食记录。营养为记录时按克数计算的快照；备注加密。"""

    __tablename__ = "meal_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    eaten_on: Mapped[date] = mapped_column(Date)
    meal_type: Mapped[str] = mapped_column(String(16))
    food_id: Mapped[str] = mapped_column(String(64))
    food_name: Mapped[str] = mapped_column(String(128))
    grams: Mapped[float] = mapped_column(Float)
    energy_kcal: Mapped[float | None] = mapped_column(Float)
    protein_g: Mapped[float | None] = mapped_column(Float)
    fat_g: Mapped[float | None] = mapped_column(Float)
    carbohydrate_g: Mapped[float | None] = mapped_column(Float)
    fiber_g: Mapped[float | None] = mapped_column(Float)
    sodium_mg: Mapped[float | None] = mapped_column(Float)
    iron_mg: Mapped[float | None] = mapped_column(Float)
    calcium_mg: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(EncryptedJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
