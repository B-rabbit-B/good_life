from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.models import User
from app.db import get_db
from app.disclaimer.service import get_current_acceptance
from app.errors import AppError


def require_disclaimer_user(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """所有业务接口的统一入口：已登录且已确认当前版本免责声明。"""
    if get_current_acceptance(db, user.id) is None:
        raise AppError(403, "disclaimer_not_accepted", "请先阅读并确认免责声明")
    return user
