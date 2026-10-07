import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_grants.models import AgentGrant
from app.common.ownership import get_owned_or_404, owned_by
from app.errors import AppError

TOKEN_PREFIX = "gl_"
ACCESS_LEVELS = ("read", "read_write")
MAX_ACTIVE_GRANTS = 20


def now() -> datetime:
    return datetime.now(UTC)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def grant_status(grant: AgentGrant, now: datetime) -> str:
    if grant.revoked_at is not None:
        return "revoked"
    if grant.expires_at <= now:
        return "expired"
    return "active"


def create_grant(
    db: Session, user_id: uuid.UUID, name: str, access: str, expires_in_days: int, now: datetime
) -> tuple[AgentGrant, str]:
    active = [g for g in list_grants(db, user_id) if grant_status(g, now) == "active"]
    if len(active) >= MAX_ACTIVE_GRANTS:
        raise AppError(409, "too_many_grants", f"有效的智能体授权最多 {MAX_ACTIVE_GRANTS} 个，请先吊销不用的授权")
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    grant = AgentGrant(
        user_id=user_id,
        name=name,
        token_hash=hash_token(token),
        access=access,
        expires_at=now + timedelta(days=expires_in_days),
    )
    db.add(grant)
    db.commit()
    db.refresh(grant)
    return grant, token


def list_grants(db: Session, user_id: uuid.UUID) -> list[AgentGrant]:
    return list(db.scalars(owned_by(AgentGrant, user_id).order_by(AgentGrant.created_at.desc(), AgentGrant.id)))


def revoke_grant(db: Session, user_id: uuid.UUID, grant_id: uuid.UUID, now: datetime) -> AgentGrant:
    grant = get_owned_or_404(db, AgentGrant, user_id, grant_id)
    if grant.revoked_at is None:
        grant.revoked_at = now
        db.commit()
        db.refresh(grant)
    return grant


def authenticate_grant(db: Session, token: str, now: datetime) -> AgentGrant | None:
    """按哈希查授权；未吊销且未过期才返回，并记录最近使用时间。"""
    grant = db.scalar(select(AgentGrant).where(AgentGrant.token_hash == hash_token(token)))
    if grant is None or grant_status(grant, now) != "active":
        return None
    grant.last_used_at = now
    db.commit()
    db.refresh(grant)
    return grant
