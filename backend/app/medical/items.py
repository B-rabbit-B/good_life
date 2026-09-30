"""医嘱条目的状态流转、审计记录与约束查询。每一次创建、修改与状态变化都写审计记录。"""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.common.ownership import get_owned_or_404, owned_by
from app.errors import AppError
from app.medical.models import MedicalItem, MedicalItemEvent

PENDING_CONFIRMATION = "pending_confirmation"
ACTIVE = "active"
PENDING_REVIEW = "pending_review"
RESOLVED = "resolved"
VOIDED = "voided"
STATUSES = (PENDING_CONFIRMATION, ACTIVE, PENDING_REVIEW, RESOLVED, VOIDED)
HARD_CONSTRAINT_STATUSES = (ACTIVE, PENDING_REVIEW)  # 待复核期间仍按原要求执行
EDITABLE_STATUSES = (PENDING_CONFIRMATION, ACTIVE, PENDING_REVIEW)
EDITABLE_FIELDS = ("category", "content", "subjects", "start_date", "end_date", "review_date")
SOURCES = ("user", "system", "extractor", "agent")


def now() -> datetime:
    return datetime.now(UTC)


def validate_item_dates(start: date, end: date | None, review: date | None) -> None:
    if end is not None and end < start:
        raise AppError(422, "invalid_item_dates", "预计结束日期不能早于生效日期")
    if review is not None and review < start:
        raise AppError(422, "invalid_item_dates", "复查日期不能早于生效日期")


def record_event(
    db: Session,
    item: MedicalItem,
    action: str,
    *,
    from_status: str | None,
    source: str,
    detail: dict[str, Any] | None = None,
) -> None:
    if source not in SOURCES:
        raise ValueError(f"unknown event source: {source}")
    db.add(
        MedicalItemEvent(
            user_id=item.user_id,
            item_id=item.id,
            action=action,
            from_status=from_status,
            to_status=item.status,
            source=source,
            detail=detail,
        )
    )


def get_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> MedicalItem:
    return get_owned_or_404(db, MedicalItem, user_id, item_id)


def list_items(
    db: Session, user_id: uuid.UUID, status: str | None = None, category: str | None = None
) -> list[MedicalItem]:
    query = owned_by(MedicalItem, user_id)
    if status is not None:
        query = query.where(MedicalItem.status == status)
    if category is not None:
        query = query.where(MedicalItem.category == category)
    return list(db.scalars(query.order_by(MedicalItem.created_at.desc(), MedicalItem.position)))


def list_events(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> list[MedicalItemEvent]:
    item = get_item(db, user_id, item_id)
    query = owned_by(MedicalItemEvent, user_id).where(MedicalItemEvent.item_id == item.id)
    return list(db.scalars(query.order_by(MedicalItemEvent.seq)))
