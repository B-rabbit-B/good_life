import uuid

from sqlalchemy.orm import Session

from app.consents.service import has_consent
from app.errors import AppError

CONSENT_REQUIRED_MESSAGES = {
    "cycle": "使用经期记录前，需要你单独同意处理经期信息",
    "medical": "使用医嘱前，需要你单独同意处理医嘱与健康信息",
}


def require_consent(db: Session, user_id: uuid.UUID, kind: str) -> None:
    """经期与医嘱模块门槛的最后一步：没有有效的单独同意时拒绝（403 consent_required）。
    由 cycle、medical 的 require_*_user 在能力检查之后调用，SDK、MCP 与站内智能体复用同一个门槛。"""
    if not has_consent(db, user_id, kind):
        raise AppError(403, "consent_required", CONSENT_REQUIRED_MESSAGES[kind])
