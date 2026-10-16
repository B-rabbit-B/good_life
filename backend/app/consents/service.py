import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.ownership import owned_by
from app.consents.content import CONSENT_KINDS, CONSENT_TEXTS, CONSENT_TITLES, CONSENT_VERSION
from app.consents.models import SensitiveConsent
from app.consents.schemas import ConsentOut
from app.errors import AppError


def get_consent(db: Session, user_id: uuid.UUID, kind: str) -> SensitiveConsent | None:
    return db.scalar(owned_by(SensitiveConsent, user_id).where(SensitiveConsent.kind == kind))


def has_consent(db: Session, user_id: uuid.UUID, kind: str) -> bool:
    consent = get_consent(db, user_id, kind)
    return consent is not None and consent.withdrawn_at is None


def grant(db: Session, user_id: uuid.UUID, kind: str, version: str) -> SensitiveConsent:
    """同意并提交。已经有效的同意原样返回（幂等）；撤回过的行改写同意时间与版本、清空撤回时间。"""
    if version != CONSENT_VERSION:
        raise AppError(409, "consent_outdated", "单独同意的说明已更新，请重新阅读最新版本后同意")
    existing = get_consent(db, user_id, kind)
    if existing is not None:
        if existing.withdrawn_at is None and existing.text_version == version:
            return existing
        existing.granted_at = datetime.now(UTC)
        existing.text_version = version
        existing.withdrawn_at = None
        db.commit()
        db.refresh(existing)
        return existing
    consent = SensitiveConsent(user_id=user_id, kind=kind, text_version=version, granted_at=datetime.now(UTC))
    db.add(consent)
    try:
        db.commit()
    except IntegrityError:  # 并发的首次同意撞上唯一约束：对方已经写入，读回那一行
        db.rollback()
        return get_consent(db, user_id, kind)
    db.refresh(consent)
    return consent


def mark_withdrawn(db: Session, user_id: uuid.UUID, kind: str) -> None:
    """记下撤回时间；不提交，由调用方与清除该模块数据放在同一个事务里。"""
    consent = get_consent(db, user_id, kind)
    if consent is not None and consent.withdrawn_at is None:
        consent.withdrawn_at = datetime.now(UTC)
        db.flush()


def _status(kind: str, consent: SensitiveConsent | None) -> ConsentOut:
    return ConsentOut(
        kind=kind,
        title=CONSENT_TITLES[kind],
        text=CONSENT_TEXTS[kind],
        current_version=CONSENT_VERSION,
        granted=consent is not None and consent.withdrawn_at is None,
        granted_at=consent.granted_at if consent else None,
        granted_version=consent.text_version if consent else None,
        withdrawn_at=consent.withdrawn_at if consent else None,
    )


def to_out(consent: SensitiveConsent) -> ConsentOut:
    return _status(consent.kind, consent)


def list_statuses(db: Session, user_id: uuid.UUID) -> list[ConsentOut]:
    """固定两项，顺序同 CONSENT_KINDS；没有记录的一项也列出（未同意）。"""
    rows = {c.kind: c for c in db.scalars(owned_by(SensitiveConsent, user_id))}
    return [_status(kind, rows.get(kind)) for kind in CONSENT_KINDS]
