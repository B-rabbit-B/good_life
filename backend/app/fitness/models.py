import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.ownership import UserOwnedMixin
from app.db import Base
from app.security.crypto import EncryptedJSON


class CustomExercise(UserOwnedMixin, Base):
    """用户自定义的动作，只对本人可见。有氧动作必须带三档 MET。"""

    __tablename__ = "custom_exercises"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_custom_exercises_user_name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64))
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    kind: Mapped[str] = mapped_column(String(16))
    primary_muscles: Mapped[list[str]] = mapped_column(JSONB)
    equipment: Mapped[str] = mapped_column(String(16))
    traits: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    met_light: Mapped[float | None] = mapped_column(Float)
    met_moderate: Mapped[float | None] = mapped_column(Float)
    met_vigorous: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Workout(UserOwnedMixin, Base):
    """一次训练。备注加密；时长、强度等数值明文。"""

    __tablename__ = "workouts"
    __table_args__ = (Index("ix_workouts_user_day", "user_id", "performed_on"),)  # 按用户与日期范围查训练

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    performed_on: Mapped[date] = mapped_column(Date)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    rpe: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(EncryptedJSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StrengthSet(UserOwnedMixin, Base):
    """力量训练的一组。动作名称为记录时的快照；position 是动作在本次训练中的顺序，set_index 是组序。"""

    __tablename__ = "strength_sets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workout_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workouts.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[str] = mapped_column(String(64))
    exercise_name: Mapped[str] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer)
    set_index: Mapped[int] = mapped_column(Integer)
    weight_kg: Mapped[float] = mapped_column(Float)
    reps: Mapped[int] = mapped_column(Integer)
    rest_seconds: Mapped[int | None] = mapped_column(Integer)
    rpe: Mapped[int | None] = mapped_column(Integer)


class CardioEntry(UserOwnedMixin, Base):
    """一条有氧记录。动作名称为记录时的快照；position 是它在本次训练有氧条目中的顺序。"""

    __tablename__ = "cardio_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workout_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workouts.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[str] = mapped_column(String(64))
    exercise_name: Mapped[str] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    distance_km: Mapped[float | None] = mapped_column(Float)
    rpe: Mapped[int | None] = mapped_column(Integer)
