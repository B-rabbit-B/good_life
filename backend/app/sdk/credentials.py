"""SDK 凭证：智能体授权令牌或用户登录令牌。用户身份只来自凭证。"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.agent_grants.service import authenticate_grant
from app.auth.models import User
from app.sdk.errors import SdkError
from app.security.tokens import InvalidTokenError, decode_access_token


@dataclass(frozen=True)
class AgentGrantToken:
    """用户签发给智能体的授权令牌（gl_ 开头）。repr 不显示令牌，避免进日志。"""

    token: str = field(repr=False)


@dataclass(frozen=True)
class UserAccessToken:
    """用户本人的登录令牌；只有它能调用 user_confirmed 级别的能力。"""

    token: str = field(repr=False)


@dataclass(frozen=True)
class Caller:
    user: User
    credential_kind: str
    grant_id: uuid.UUID | None
    can_write: bool
    user_confirmed: bool


def authenticate(db: Session, credential: AgentGrantToken | UserAccessToken | None, now: datetime) -> Caller:
    if isinstance(credential, AgentGrantToken):
        grant = authenticate_grant(db, credential.token, now)
        user = db.get(User, grant.user_id) if grant is not None else None
        if grant is None or user is None:
            raise SdkError("unauthenticated", "invalid_grant", "智能体授权无效、已过期或已吊销")
        return Caller(user, "agent_grant", grant.id, grant.access == "read_write", False)
    if isinstance(credential, UserAccessToken):
        try:
            claims = decode_access_token(credential.token)
        except InvalidTokenError:
            raise SdkError("unauthenticated", "invalid_token", "登录已失效，请重新登录") from None
        user = db.get(User, claims.user_id)
        if user is None or user.token_version != claims.token_version:
            raise SdkError("unauthenticated", "invalid_token", "登录已失效，请重新登录")
        return Caller(user, "user_session", None, True, True)
    raise SdkError("unauthenticated", "missing_credential", "没有提供凭证")
