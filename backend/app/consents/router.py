from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.models import User
from app.consents import service
from app.consents.schemas import ConsentGrant, ConsentKind, ConsentOut
from app.db import get_db
from app.disclaimer.deps import require_disclaimer_user

router = APIRouter(prefix="/api/consents", tags=["consents"])

DisclaimerUser = Annotated[User, Depends(require_disclaimer_user)]
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[ConsentOut])
def list_consents(user: DisclaimerUser, db: DbSession) -> list[ConsentOut]:
    return service.list_statuses(db, user.id)


@router.post("/{kind}", response_model=ConsentOut)
def grant_consent(kind: ConsentKind, body: ConsentGrant, user: DisclaimerUser, db: DbSession) -> ConsentOut:
    return service.to_out(service.grant(db, user.id, kind, body.version))
