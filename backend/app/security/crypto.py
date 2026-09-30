import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().field_encryption_key.encode("ascii"))


def encrypt_value(value: Any) -> str:
    plaintext = json.dumps(value, ensure_ascii=False).encode("utf-8")
    return _fernet().encrypt(plaintext).decode("ascii")


def decrypt_value(token: str) -> Any:
    return json.loads(_fernet().decrypt(token.encode("ascii")).decode("utf-8"))


class EncryptedJSON(TypeDecorator):
    """任意 JSON 值加密后以文本存储，数据库里只能看到密文。"""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        return None if value is None else encrypt_value(value)

    def process_result_value(self, value: str | None, dialect: Any) -> Any:
        return None if value is None else decrypt_value(value)
