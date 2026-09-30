import uuid
from typing import Any

from sqlalchemy import ForeignKey, Select, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.errors import AppError


class UserOwnedMixin:
    """业务表统一带上用户归属列。"""

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


def owned_by(model: Any, user_id: uuid.UUID) -> Select:
    """所有业务查询的起点：只查当前用户的数据。"""
    return select(model).where(model.user_id == user_id)


def get_owned_or_404(db: Session, model: Any, user_id: uuid.UUID, record_id: uuid.UUID) -> Any:
    """按编号取当前用户的一条记录；别人的记录与不存在的记录一样返回 404，不暴露是否存在。"""
    record = db.scalar(owned_by(model, user_id).where(model.id == record_id))
    if record is None:
        raise AppError(404, "not_found", "记录不存在")
    return record
