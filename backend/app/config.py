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
    llm_allow_private_hosts: bool = False  # 为真时模型服务地址不做内网检查，只用于测试与本地模拟服务
    llm_timeout_seconds: float = 20.0
    amap_key: str | None = None  # 高德 Web 服务密钥；留空则附近餐厅功能关闭
    amap_base_url: str = "https://restapi.amap.com"
    amap_timeout_seconds: float = 8.0
    frontend_dist_dir: Path | None = None  # 前端构建目录；留空用仓库里的 frontend/dist，没有构建产物时不提供前端

    @field_validator("frontend_dist_dir", mode="before")
    @classmethod
    def _blank_dist_dir_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("amap_key", mode="before")
    @classmethod
    def _blank_amap_key_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

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
