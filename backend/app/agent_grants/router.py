import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.agent_grants import service
from app.agent_grants.models import AgentGrant
from app.agent_grants.schemas import AuditOut, GrantCreate, GrantCreatedOut, GrantOut
from app.auth.models import User
from app.db import get_db
from app.disclaimer.deps import require_disclaimer_user

router = APIRouter(prefix="/api/agent-grants", tags=["agent-grants"])

GrantUser = Annotated[User, Depends(require_disclaimer_user)]
DbSession = Annotated[Session, Depends(get_db)]


def _out(grant: AgentGrant, now: datetime) -> GrantOut:
    return GrantOut(
        id=grant.id,
        name=grant.name,
        access=grant.access,
        status=service.grant_status(grant, now),
        expires_at=grant.expires_at,
        created_at=grant.created_at,
        revoked_at=grant.revoked_at,
        last_used_at=grant.last_used_at,
    )


@router.post("", status_code=201, response_model=GrantCreatedOut)
def create_grant(body: GrantCreate, user: GrantUser, db: DbSession, response: Response) -> GrantCreatedOut:
    response.headers["Cache-Control"] = "no-store"  # 响应里有令牌明文，不得被缓存
    grant, token = service.create_grant(db, user.id, body.name, body.access, body.expires_in_days, service.now())
    return GrantCreatedOut(
        id=grant.id,
        name=grant.name,
        access=grant.access,
        expires_at=grant.expires_at,
        created_at=grant.created_at,
        token=token,
    )


@router.get("", response_model=list[GrantOut])
def list_grants(user: GrantUser, db: DbSession) -> list[GrantOut]:
    current = service.now()
    return [_out(g, current) for g in service.list_grants(db, user.id)]


@router.get("/audit", response_model=list[AuditOut])
def list_audits(
    user: GrantUser, db: DbSession, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> list[AuditOut]:
    return [AuditOut.model_validate(a) for a in service.list_audits(db, user.id, limit)]


@router.delete("/{grant_id}", status_code=204)
def revoke_grant(grant_id: uuid.UUID, user: GrantUser, db: DbSession) -> Response:
    service.revoke_grant(db, user.id, grant_id, service.now())
    return Response(status_code=204)
