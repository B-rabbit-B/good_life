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
from app.medical.models import MedicalEvidence, MedicalItem, MedicalOrder


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


MAX_EVIDENCE_BYTES = 10 * 1024 * 1024
MAX_EVIDENCE_PER_ORDER = 10
EVIDENCE_EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}


def sniff_content_type(content: bytes) -> str | None:
    """按文件头判断类型，不相信客户端声明的类型。"""
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def add_evidence(
    db: Session, user_id: uuid.UUID, order_id: uuid.UUID, filename: str, content: bytes
) -> MedicalEvidence:
    order = get_order(db, user_id, order_id)
    if not content:
        raise AppError(422, "evidence_empty", "上传的文件是空的")
    # 锁住医嘱单行再数，并发上传不会一起越过上限
    db.execute(select(MedicalOrder.id).where(MedicalOrder.id == order.id).with_for_update())
    count = db.scalar(select(func.count()).select_from(MedicalEvidence).where(MedicalEvidence.order_id == order.id))
    if count >= MAX_EVIDENCE_PER_ORDER:
        raise AppError(409, "evidence_limit_reached", f"每份医嘱最多上传 {MAX_EVIDENCE_PER_ORDER} 个文件")
    if len(content) > MAX_EVIDENCE_BYTES:
        raise AppError(413, "evidence_too_large", "文件不能超过 10 MB")
    content_type = sniff_content_type(content)
    if content_type is None:
        raise AppError(415, "evidence_type_not_allowed", "只支持 JPG、PNG、WEBP 图片或 PDF 文件")
    evidence = MedicalEvidence(
        user_id=user_id,
        order_id=order.id,
        filename=(filename or "未命名文件")[:200],
        content_type=content_type,
        size_bytes=len(content),
        content=content,
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


def list_evidence(db: Session, user_id: uuid.UUID, order_id: uuid.UUID) -> list[MedicalEvidence]:
    query = owned_by(MedicalEvidence, user_id).where(MedicalEvidence.order_id == order_id)
    return list(db.scalars(query.order_by(MedicalEvidence.created_at)))


def get_evidence(db: Session, user_id: uuid.UUID, evidence_id: uuid.UUID) -> MedicalEvidence:
    return get_owned_or_404(db, MedicalEvidence, user_id, evidence_id)
