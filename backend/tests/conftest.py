import os

# 必须在导入 app 之前设置：测试永远连测试库，并使用固定的测试密钥。
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://goodlife:goodlife@127.0.0.1:5433/goodlife_test"
)
os.environ["JWT_SECRET"] = "test-jwt-secret-0123456789-abcdefghijklmnopqrstuvwxyz"
os.environ["FIELD_ENCRYPTION_KEY"] = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
os.environ["LLM_ALLOW_PRIVATE_HOSTS"] = "true"  # 测试与本地模拟服务可以使用 127.0.0.1 地址

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

import app.models  # noqa: F401
from app.auth import limiter
from app.db import Base, get_engine
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    yield
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    if tables:
        with get_engine().begin() as conn:
            conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def reset_login_limits():
    """登录与密码复核的失败计数在进程内：每个测试结束清零，测试之间互不影响。"""
    yield
    limiter.reset_all()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def client():
    with TestClient(create_app()) as test_client:
        yield test_client
