from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.models import User
from app.db import get_db
from app.errors import AppError
from app.security.tokens import InvalidTokenError, decode_access_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None:
        raise AppError(401, "not_authenticated", "请先登录")
    try:
        claims = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise AppError(401, "invalid_token", "登录已失效，请重新登录") from None
    user = db.get(User, claims.user_id)
    if user is None or user.token_version != claims.token_version:
        raise AppError(401, "invalid_token", "登录已失效，请重新登录")
    return user
