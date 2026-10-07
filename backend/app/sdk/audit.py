"""SDK 调用审计：独立会话写入，业务回滚不影响审计；绝不记录参数、返回内容或令牌。"""

import logging
import uuid

from app.agent_grants.models import SdkCallAudit
from app.db import get_sessionmaker

logger = logging.getLogger(__name__)


def record_call(
    *,
    user_id: uuid.UUID | None,
    grant_id: uuid.UUID | None,
    credential_kind: str,
    client_name: str,
    capability: str,
    outcome: str,
    error_code: str | None,
    duration_ms: int,
) -> None:
    try:
        with get_sessionmaker()() as db:
            db.add(SdkCallAudit(
                user_id=user_id,
                grant_id=grant_id,
                credential_kind=credential_kind,
                client_name=client_name,
                capability=capability,
                outcome=outcome,
                error_code=error_code,
                duration_ms=duration_ms,
            ))
            db.commit()
    except Exception:
        # 只记能力名与结果，不带参数；写审计失败不改变调用结果。
        logger.exception("写入 SDK 调用审计失败：%s %s", capability, outcome)
