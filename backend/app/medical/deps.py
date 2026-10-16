from datetime import date
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.clock import get_today
from app.consents.deps import require_consent
from app.db import get_db
from app.disclaimer.deps import require_disclaimer_user
from app.errors import AppError
from app.medical import items
from app.profile.capabilities import compute_capabilities
from app.profile.service import get_or_create_profile


def require_medical_user(
    user: Annotated[User, Depends(require_disclaimer_user)],
    db: Annotated[Session, Depends(get_db)],
    today: Annotated[date, Depends(get_today)],
) -> User:
    """医嘱接口的统一入口：已确认免责声明、能力清单开放了医嘱模块、用户单独同意了处理医嘱与健康信息；
    每次请求前刷新到期状态。"""
    if not compute_capabilities(get_or_create_profile(db, user.id))["medical"]:
        raise AppError(403, "medical_not_available", "医嘱功能当前不可用")
    require_consent(db, user.id, "medical")
    items.refresh_statuses(db, user.id, today)
    return user
