import secrets
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import limiter
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


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """用户不存在时拿来校验的假哈希：首次使用时用随机密码生成，之后固定，让两种失败耗时相同。"""
    return hash_password(secrets.token_urlsafe(16))


def login(db: Session, username: str, password: str) -> str:
    """同一用户名 15 分钟内失败 5 次后一律 429（用户不存在也计数）；成功清零。"""
    key = f"name:{username}"
    limiter.check(key)
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        verify_password(password, _dummy_hash())  # 消除“用户不存在”与“密码错误”之间的时间差
        matched = False
    else:
        matched = verify_password(password, user.password_hash)
    if not matched:
        limiter.record_failure(key)
        raise AppError(401, "invalid_credentials", "用户名或密码错误")
    limiter.reset(key)
    return create_access_token(user.id, user.token_version)


def verify_user_password(db: Session, user: User, password: str) -> None:
    """导出、删除账号之类的敏感操作前复核本人密码。错了是 403：用户仍在登录状态，401 会让前端清掉令牌。

    与登录一样限速，键是用户编号（与登录的键分开）。
    """
    key = f"user:{user.id}"
    limiter.check(key)
    if not verify_password(password, user.password_hash):
        limiter.record_failure(key)
        raise AppError(403, "password_incorrect", "密码不正确，请重新输入")
    limiter.reset(key)


def logout(db: Session, user: User) -> None:
    """令牌版本号加一，让该用户所有已签发的令牌失效。"""
    user.token_version += 1
    db.commit()
