import logging
import time
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.account.clearing import clear_module_data
from app.account.deletion import delete_account
from app.account.export import build_export
from app.account.schemas import AccountDelete, PasswordConfirm
from app.auth.deps import get_current_user
from app.auth.models import User
from app.auth.service import verify_user_password
from app.common.clock import get_today
from app.consents import service as consents
from app.consents.schemas import ConsentKind
from app.db import get_db
from app.errors import AppError
from app.sdk import audit

logger = logging.getLogger(__name__)

# 用户处置自己数据的接口只要求登录：免责声明升版后、重新确认之前也必须能撤回同意、导出与删除自己的数据。
router = APIRouter(tags=["account"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]
EXPORT_CAPABILITY = "account.export"


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


@router.post(
    "/api/account/export",
    response_class=Response,
    responses={200: {"content": {"application/zip": {}}, "description": "压缩包：每个模块一份 JSON、原件、照片与说明"}},
)
def export_data(
    body: PasswordConfirm, user: CurrentUser, db: DbSession, today: Annotated[date, Depends(get_today)]
) -> Response:
    """重新输入密码后导出本人全部数据（压缩包，禁止缓存）；成功后记一行审计 account.export。"""
    started = time.perf_counter()
    verify_user_password(db, user, body.password)
    filename, content = build_export(db, user, datetime.now(UTC), today=today)
    audit.record_call(user_id=user.id, grant_id=None, credential_kind="user_session", client_name="app",
                      capability=EXPORT_CAPABILITY, outcome="ok", error_code=None,
                      duration_ms=int((time.perf_counter() - started) * 1000))
    logger.info("账号导出完成")
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store",
                 "Pragma": "no-cache"},
    )


@router.post("/api/account/delete", status_code=204)
def delete_my_account(body: AccountDelete, user: CurrentUser, db: DbSession) -> Response:
    """重新输入密码并勾选确认后，立即彻底删除账号与全部数据（不可恢复）；登录令牌与智能体授权随之失效。"""
    verify_user_password(db, user, body.password)
    delete_account(db, user.id)
    logger.info("账号已删除")
    return Response(status_code=204)
