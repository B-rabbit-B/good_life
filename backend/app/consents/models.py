import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.common.ownership import UserOwnedMixin
from app.db import Base


class SensitiveConsent(UserOwnedMixin, Base):
    """经期、医嘱两类敏感信息的单独同意，每个用户每类一行。

    撤回时只写撤回时间（同一事务里清除该模块的数据）；重新同意时改写同意时间与文案版本并清空撤回时间。
    """

    __tablename__ = "sensitive_consents"
    __table_args__ = (UniqueConstraint("user_id", "kind", name="uq_sensitive_consents_user_kind"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(16))
    text_version: Mapped[str] = mapped_column(String(32))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
