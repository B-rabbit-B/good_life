import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.ownership import owned_by
from app.disclaimer.content import DISCLAIMER_VERSION
from app.disclaimer.models import DisclaimerAcceptance
from app.errors import AppError


def get_current_acceptance(db: Session, user_id: uuid.UUID) -> DisclaimerAcceptance | None:
    return db.scalar(
        owned_by(DisclaimerAcceptance, user_id).where(DisclaimerAcceptance.version == DISCLAIMER_VERSION)
    )


def accept(db: Session, user_id: uuid.UUID, version: str) -> DisclaimerAcceptance:
    if version != DISCLAIMER_VERSION:
        raise AppError(409, "disclaimer_outdated", "免责声明已更新，请重新阅读最新版本后确认")
    existing = get_current_acceptance(db, user_id)
    if existing is not None:
        return existing
    acceptance = DisclaimerAcceptance(user_id=user_id, version=version)
    db.add(acceptance)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return get_current_acceptance(db, user_id)
    db.refresh(acceptance)
    return acceptance
