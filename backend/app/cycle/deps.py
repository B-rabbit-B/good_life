from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth.models import User
from app.consents.deps import require_consent
from app.db import get_db
from app.disclaimer.deps import require_disclaimer_user
from app.errors import AppError
from app.profile.capabilities import compute_capabilities
from app.profile.service import get_or_create_profile


def require_cycle_user(
    user: Annotated[User, Depends(require_disclaimer_user)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """经期接口的统一入口：已确认免责声明、能力清单开放了经期模块，且用户单独同意了处理经期信息。"""
    if not compute_capabilities(get_or_create_profile(db, user.id))["cycle"]:
        raise AppError(403, "cycle_not_available", "经期功能只对档案性别为女性、且没有关闭该功能的用户开放")
    require_consent(db, user.id, "cycle")
    return user
