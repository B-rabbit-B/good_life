"""医嘱条目的状态流转、审计记录与约束查询。每一次创建、修改与状态变化都写审计记录。"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
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


REVIEW_LEAD_DAYS = 1
SUBJECT_REQUIRED_CATEGORIES = ("diet_avoid", "diet_require", "medication_diet", "exercise_limit")
CONSTRAINT_REMINDER = "以上是你确认过的医嘱约束，请遵医嘱；待复核的条目在你确认解除之前仍按原要求执行，如有疑问请咨询医生。"


@dataclass(frozen=True)
class Constraint:
    item_id: uuid.UUID
    category: str
    content: str
    subjects: list[str]
    start_date: date
    end_date: date | None
    review_date: date | None
    status: str
    needs_review: bool
    resolution_proposed: bool


def _transition(
    db: Session, item: MedicalItem, action: str, to_status: str, source: str, detail: dict[str, Any] | None = None
) -> None:
    from_status = item.status
    item.status = to_status
    if to_status in (RESOLVED, VOIDED):
        item.closed_at = now()
    record_event(db, item, action, from_status=from_status, source=source, detail=detail)


def _apply_changes(item: MedicalItem, changes: dict[str, Any], require_subjects: bool = False) -> None:
    """先校验合并后的日期，校验通过才写入，避免出错时留下改了一半的数据。"""
    unknown = set(changes) - set(EDITABLE_FIELDS)
    if unknown:
        raise ValueError(f"fields not editable through changes: {sorted(unknown)}")
    merged = {name: changes.get(name, getattr(item, name)) for name in EDITABLE_FIELDS}
    validate_item_dates(merged["start_date"], merged["end_date"], merged["review_date"])
    if require_subjects and merged["category"] in SUBJECT_REQUIRED_CATEGORIES and not merged["subjects"]:
        raise AppError(422, "subjects_required", "请至少填写一个涉及的食物或行为，再确认这条医嘱")
    for name, value in changes.items():
        setattr(item, name, value)
    item.missing_fields = [name for name in item.missing_fields if not getattr(item, name)]


def _due_reason(item: Any, today: date) -> str | None:
    if item.review_date is not None and item.review_date <= today:
        return "已到复查日期，请确认是否还需要继续遵守"
    if item.end_date is not None and item.end_date - timedelta(days=REVIEW_LEAD_DAYS) <= today:
        if item.end_date < today:
            return "已过预计结束日期，请确认是否还需要继续遵守"
        if item.end_date == today:
            return "今天是预计结束日期，请确认是否还需要继续遵守"
        return "即将到预计结束日期，请确认是否还需要继续遵守"
    return None


def _clear_proposal(item: MedicalItem) -> None:
    item.resolution_proposed_at = None
    item.resolution_reason = None


def refresh_statuses(db: Session, user_id: uuid.UUID, today: date) -> int:
    """到期的生效条目转为待复核；过了预计结束日期仍未确认的条目自动作废。"""
    changed = 0
    query = owned_by(MedicalItem, user_id).where(MedicalItem.status.in_([ACTIVE, PENDING_CONFIRMATION]))
    for item in list(db.scalars(query)):
        if item.status == ACTIVE:
            reason = _due_reason(item, today)
            if reason:
                _transition(db, item, "review_due", PENDING_REVIEW, "system", {"reason": reason})
                changed += 1
        elif item.end_date is not None and item.end_date < today:
            _transition(db, item, "expired", VOIDED, "system", {"reason": "未确认的条目已过预计结束日期，自动作废"})
            changed += 1
    if changed:
        db.commit()
    return changed


def update_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID, changes: dict[str, Any]) -> MedicalItem:
    item = get_item(db, user_id, item_id)
    if item.status not in EDITABLE_STATUSES:
        raise AppError(409, "item_closed", "已解除或已作废的条目不能再修改")
    if changes:
        # 生效中与待复核的条目是硬约束，编辑后同样必须有涉及对象；待确认的条目可以自由修改
        _apply_changes(item, changes, require_subjects=item.status in HARD_CONSTRAINT_STATUSES)
        record_event(db, item, "edited", from_status=item.status, source="user", detail={"fields": sorted(changes)})
        db.commit()
        db.refresh(item)
    return item


def confirm_item(
    db: Session, user_id: uuid.UUID, item_id: uuid.UUID, changes: dict[str, Any], today: date
) -> MedicalItem:
    item = get_item(db, user_id, item_id)
    if item.status != PENDING_CONFIRMATION:
        raise AppError(409, "invalid_transition", "只有待确认的条目可以确认")
    _apply_changes(item, changes, require_subjects=True)
    item.missing_fields = []  # 用户确认即表示接受当前内容，未填结束日期视为长期
    item.confirmed_at = now()
    _transition(db, item, "confirmed", ACTIVE, "user", {"fields": sorted(changes)} if changes else None)
    db.commit()
    refresh_statuses(db, user_id, today)
    db.refresh(item)
    return item


def void_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID, reason: str | None) -> MedicalItem:
    item = get_item(db, user_id, item_id)
    if item.status not in EDITABLE_STATUSES:
        raise AppError(409, "item_closed", "已解除或已作废的条目不能再作废")
    detail: dict[str, Any] = {"reason": reason} if reason else {}
    if item.resolution_proposed_at is not None:
        detail["proposal_cleared"] = True
    _clear_proposal(item)
    _transition(db, item, "voided", VOIDED, "user", detail or None)
    db.commit()
    db.refresh(item)
    return item


def continue_item(
    db: Session,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    end_date: date | None,
    review_date: date | None,
    today: date,
) -> MedicalItem:
    item = get_item(db, user_id, item_id)
    if item.status != PENDING_REVIEW:
        raise AppError(409, "invalid_transition", "只有待复核的条目可以继续执行")
    validate_item_dates(item.start_date, end_date, review_date)
    if _due_reason(SimpleNamespace(end_date=end_date, review_date=review_date), today):
        raise AppError(422, "still_due", "新的预计结束日期或复查日期仍然已到期，请设置更晚的日期，或者确认解除")
    item.end_date, item.review_date = end_date, review_date
    detail: dict[str, Any] = {
        "end_date": end_date.isoformat() if end_date else None,
        "review_date": review_date.isoformat() if review_date else None,
    }
    if item.resolution_proposed_at is not None:
        detail["proposal_cleared"] = True
    _clear_proposal(item)
    _transition(db, item, "continued", ACTIVE, "user", detail)
    db.commit()
    db.refresh(item)
    return item


def propose_resolution(
    db: Session, user_id: uuid.UUID, item_id: uuid.UUID, reason: str, source: str
) -> MedicalItem:
    """只记录"建议解除"，不改变约束。source 为 user 或 agent（步骤 08 的智能体）。"""
    if source not in ("user", "agent"):
        raise ValueError(f"resolution can only be proposed by user or agent, got {source}")
    item = get_item(db, user_id, item_id)
    if item.status not in HARD_CONSTRAINT_STATUSES:
        raise AppError(409, "invalid_transition", "只有生效中或待复核的条目可以提出解除建议")
    item.resolution_proposed_at = now()
    item.resolution_reason = reason
    record_event(db, item, "resolution_proposed", from_status=item.status, source=source, detail={"reason": reason})
    db.commit()
    db.refresh(item)
    return item


def cancel_resolution_proposal(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> MedicalItem:
    item = get_item(db, user_id, item_id)
    if item.resolution_proposed_at is None:
        raise AppError(409, "no_proposal", "这个条目没有待处理的解除建议")
    _clear_proposal(item)
    record_event(db, item, "resolution_proposal_cancelled", from_status=item.status, source="user")
    db.commit()
    db.refresh(item)
    return item


def resolve_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID, reason: str | None) -> MedicalItem:
    """只能由用户确认解除。可以先有解除建议，也可以直接解除。"""
    item = get_item(db, user_id, item_id)
    if item.status not in HARD_CONSTRAINT_STATUSES:
        raise AppError(409, "invalid_transition", "只有生效中或待复核的条目可以解除")
    if reason:
        item.resolution_reason = reason
    item.resolution_proposed_at = None
    _transition(db, item, "resolved", RESOLVED, "user", {"reason": item.resolution_reason})
    db.commit()
    db.refresh(item)
    return item


def get_current_constraints(
    db: Session, user_id: uuid.UUID, today: date, category: str | None = None
) -> list[Constraint]:
    """当天生效的全部医嘱硬约束（生效中与待复核）。步骤 04 的约束引擎从这里读取。"""
    refresh_statuses(db, user_id, today)
    query = owned_by(MedicalItem, user_id).where(
        MedicalItem.status.in_(HARD_CONSTRAINT_STATUSES), MedicalItem.start_date <= today
    )
    if category is not None:
        query = query.where(MedicalItem.category == category)
    query = query.order_by(
        MedicalItem.category, MedicalItem.start_date, MedicalItem.position, MedicalItem.created_at, MedicalItem.id
    )
    return [
        Constraint(
            item_id=item.id,
            category=item.category,
            content=item.content,
            subjects=list(item.subjects),
            start_date=item.start_date,
            end_date=item.end_date,
            review_date=item.review_date,
            status=item.status,
            needs_review=item.status == PENDING_REVIEW,
            resolution_proposed=item.resolution_proposed_at is not None,
        )
        for item in db.scalars(query)
    ]


def list_reviews(db: Session, user_id: uuid.UUID, today: date) -> list[MedicalItem]:
    """需要用户处理的条目：待复核的，以及有待处理解除建议的。步骤 08 的智能体开场时读取。"""
    refresh_statuses(db, user_id, today)
    query = owned_by(MedicalItem, user_id).where(
        MedicalItem.status.in_(HARD_CONSTRAINT_STATUSES),
        (MedicalItem.status == PENDING_REVIEW) | MedicalItem.resolution_proposed_at.is_not(None),
    )
    return list(
        db.scalars(
            query.order_by(MedicalItem.start_date, MedicalItem.position, MedicalItem.created_at, MedicalItem.id)
        )
    )
