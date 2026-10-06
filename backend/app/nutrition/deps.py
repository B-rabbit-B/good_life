from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth.models import User
from app.db import get_db
from app.disclaimer.deps import require_disclaimer_user
from app.errors import AppError
from app.profile.capabilities import compute_capabilities
from app.profile.service import get_or_create_profile


def require_nutrition_user(
    user: Annotated[User, Depends(require_disclaimer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """饮食接口的统一入口：已确认免责声明、能力清单开放了饮食模块。"""
    if not compute_capabilities(get_or_create_profile(db, user.id))["nutrition"]:
        raise AppError(403, "nutrition_not_available", "饮食功能当前不可用")
    return user
