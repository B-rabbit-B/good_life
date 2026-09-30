import uuid
from typing import Any

from sqlalchemy import ForeignKey, Select, select
from sqlalchemy.orm import Mapped, mapped_column


class UserOwnedMixin:
    """业务表统一带上用户归属列。"""

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


def owned_by(model: Any, user_id: uuid.UUID) -> Select:
    """所有业务查询的起点：只查当前用户的数据。"""
    return select(model).where(model.user_id == user_id)
