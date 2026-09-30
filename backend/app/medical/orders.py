"""医嘱原文、提取入库与手动补充条目。"""

import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.ownership import get_owned_or_404, owned_by
from app.errors import AppError
from app.medical.extraction import get_extractor
from app.medical.items import PENDING_CONFIRMATION, record_event, validate_item_dates
from app.medical.models import MedicalItem, MedicalOrder


def create_order(db: Session, user_id: uuid.UUID, text: str, order_date: date, today: date) -> MedicalOrder:
    if order_date > today:
        raise AppError(422, "order_in_future", "医嘱日期不能晚于今天")
    result = get_extractor().extract(text, order_date)
    order = MedicalOrder(
        user_id=user_id,
        order_date=order_date,
        source_text=text,
        extractor=result.extractor,
        extraction_notes={
            "ignored": [{"text": ignored.text, "reason": ignored.reason} for ignored in result.ignored],
            "notes": result.notes,
        },
    )
    db.add(order)
    db.flush()
    for position, extracted in enumerate(result.items, start=1):
        item = MedicalItem(
            user_id=user_id,
            order_id=order.id,
            position=position,
            category=extracted.category,
            status=PENDING_CONFIRMATION,
            origin="extracted",
            confidence=extracted.confidence,
            content=extracted.content,
            subjects=extracted.subjects,
            source_excerpt=extracted.source_excerpt,
            start_date=extracted.start_date,
            end_date=extracted.end_date,
            review_date=extracted.review_date,
            missing_fields=extracted.missing_fields,
            notes=extracted.notes,
        )
        db.add(item)
        db.flush()
        record_event(db, item, "created", from_status=None, source="extractor")
    db.commit()
    db.refresh(order)
    return order


def list_orders(db: Session, user_id: uuid.UUID) -> list[MedicalOrder]:
    return list(db.scalars(owned_by(MedicalOrder, user_id).order_by(MedicalOrder.created_at.desc())))


def get_order(db: Session, user_id: uuid.UUID, order_id: uuid.UUID) -> MedicalOrder:
    return get_owned_or_404(db, MedicalOrder, user_id, order_id)


def list_order_items(db: Session, user_id: uuid.UUID, order_id: uuid.UUID) -> list[MedicalItem]:
    query = owned_by(MedicalItem, user_id).where(MedicalItem.order_id == order_id).order_by(MedicalItem.position)
    return list(db.scalars(query))


def add_manual_item(db: Session, user_id: uuid.UUID, order_id: uuid.UUID, fields: dict[str, Any]) -> MedicalItem:
    """用户手动补充提取器漏掉的条目。与提取的条目一样先进入待确认。"""
    order = get_order(db, user_id, order_id)
    start = fields.get("start_date") or order.order_date
    end = fields.get("end_date")
    review = fields.get("review_date")
    validate_item_dates(start, end, review)
    last = db.scalar(select(func.max(MedicalItem.position)).where(MedicalItem.order_id == order.id)) or 0
    item = MedicalItem(
        user_id=user_id,
        order_id=order.id,
        position=last + 1,
        category=fields["category"],
        status=PENDING_CONFIRMATION,
        origin="manual",
        confidence=None,
        content=fields["content"],
        subjects=fields.get("subjects") or [],
        source_excerpt=None,
        start_date=start,
        end_date=end,
        review_date=review,
        missing_fields=[],
        notes=[],
    )
    db.add(item)
    db.flush()
    record_event(db, item, "created", from_status=None, source="user")
    db.commit()
    db.refresh(item)
    return item
