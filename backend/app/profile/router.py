from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.models import User
from app.db import get_db
from app.disclaimer.deps import require_disclaimer_user
from app.profile import service
from app.profile.capabilities import compute_capabilities
from app.profile.models import Profile, ProfileChange
from app.profile.schemas import ProfileChangeOut, ProfileOut, ProfileUpdate

router = APIRouter(prefix="/api", tags=["profile"])

CurrentUser = Annotated[User, Depends(require_disclaimer_user)]
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/profile", response_model=ProfileOut)
def get_profile(user: CurrentUser, db: DbSession) -> Profile:
    return service.get_or_create_profile(db, user.id)


@router.patch("/profile", response_model=ProfileOut)
def patch_profile(body: ProfileUpdate, user: CurrentUser, db: DbSession) -> Profile:
    return service.update_profile(db, user.id, body.model_dump(exclude_unset=True))


@router.get("/profile/changes", response_model=list[ProfileChangeOut])
def get_profile_changes(user: CurrentUser, db: DbSession) -> list[ProfileChange]:
    return service.list_profile_changes(db, user.id)


@router.get("/me/capabilities")
def get_capabilities(user: CurrentUser, db: DbSession) -> dict[str, bool]:
    return compute_capabilities(service.get_or_create_profile(db, user.id))
