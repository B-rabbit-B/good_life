from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    database_url: str
    jwt_secret: str
    field_encryption_key: str
    access_token_expire_minutes: int = 60 * 24 * 7

    @field_validator("jwt_secret", "field_encryption_key")
    @classmethod
    def _not_placeholder(cls, value: str) -> str:
        if value.startswith("replace-with"):
            raise ValueError("仍是 .env.example 里的占位值，请换成真实密钥 (placeholder value, set a real secret)")
        return value

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_long_enough(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET 至少需要 32 个字符 (JWT_SECRET must be at least 32 characters)")
        return value

    @field_validator("field_encryption_key")
    @classmethod
    def _fernet_key_valid(cls, value: str) -> str:
        try:
            Fernet(value.encode("ascii"))
        except (ValueError, UnicodeEncodeError):
            raise ValueError(
                "FIELD_ENCRYPTION_KEY 不是有效的 Fernet 密钥 (FIELD_ENCRYPTION_KEY is not a valid Fernet key)"
            ) from None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
