from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.models import User
from app.db import get_db
from app.disclaimer import service
from app.disclaimer.content import DISCLAIMER_TEXT, DISCLAIMER_VERSION

router = APIRouter(prefix="/api/disclaimer", tags=["disclaimer"])


class DisclaimerOut(BaseModel):
    version: str
    text: str


class DisclaimerStatus(BaseModel):
    current_version: str
    accepted: bool
    accepted_at: datetime | None


class AcceptRequest(BaseModel):
    version: str


@router.get("", response_model=DisclaimerOut)
def get_disclaimer() -> DisclaimerOut:
    return DisclaimerOut(version=DISCLAIMER_VERSION, text=DISCLAIMER_TEXT)


@router.get("/status", response_model=DisclaimerStatus)
def get_status(
    user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]
) -> DisclaimerStatus:
    acceptance = service.get_current_acceptance(db, user.id)
    return DisclaimerStatus(
        current_version=DISCLAIMER_VERSION,
        accepted=acceptance is not None,
        accepted_at=acceptance.accepted_at if acceptance else None,
    )


@router.post("/accept", response_model=DisclaimerStatus)
def accept(
    body: AcceptRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DisclaimerStatus:
    acceptance = service.accept(db, user.id, body.version)
    return DisclaimerStatus(current_version=DISCLAIMER_VERSION, accepted=True, accepted_at=acceptance.accepted_at)
