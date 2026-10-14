from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.account.clearing import clear_module_data
from app.auth.deps import get_current_user
from app.auth.models import User
from app.consents import service as consents
from app.consents.schemas import ConsentKind
from app.db import get_db
from app.errors import AppError

# 用户处置自己数据的接口只要求登录：免责声明升版后、重新确认之前也必须能撤回同意并清除数据。
router = APIRouter(tags=["account"])


@router.post("/api/account/consents/{kind}/withdraw", status_code=204)
def withdraw_consent(
    kind: ConsentKind,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """撤回单独同意：同一个事务里清除该模块的全部数据并记下撤回时间，模块随即关闭。"""
    if not consents.has_consent(db, user.id, kind):
        raise AppError(404, "not_found", "记录不存在")
    clear_module_data(db, user.id, kind)
    consents.mark_withdrawn(db, user.id, kind)
    db.commit()
    return Response(status_code=204)
