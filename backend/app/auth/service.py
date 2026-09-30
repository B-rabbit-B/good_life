from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.errors import AppError
from app.security.passwords import hash_password, verify_password
from app.security.tokens import create_access_token


def register_user(db: Session, username: str, password: str) -> User:
    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "username_taken", "该用户名已被注册，请换一个") from None
    db.refresh(user)
    return user


def login(db: Session, username: str, password: str) -> str:
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        raise AppError(401, "invalid_credentials", "用户名或密码错误")
    return create_access_token(user.id, user.token_version)


def logout(db: Session, user: User) -> None:
    """令牌版本号加一，让该用户所有已签发的令牌失效。"""
    user.token_version += 1
    db.commit()
