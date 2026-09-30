# 步骤 01 项目底座与账号档案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭好 good-life 的后端底座：FastAPI 服务、PostgreSQL、注册登录退出、多用户隔离、个人档案（含修改记录与敏感字段加密）、免责声明确认闸门，并满足 `docs/01-项目底座与账号档案.md` 的 7 条验收标准。

**Architecture:** 单个 FastAPI 应用，按领域分包（`auth`、`disclaimer`、`profile`），每个包内 models / schemas / service / router 各司其职。数据库用 Docker 跑 PostgreSQL 16，结构由 Alembic 手写迁移管理。认证用 JWT，令牌里带 `token_version`，退出时版本号加一，让旧令牌全部失效。敏感字段通过一个 SQLAlchemy 自定义类型 `EncryptedJSON` 做 Fernet 加密。

**Tech Stack:** Python 3.12、uv、FastAPI、SQLAlchemy 2（同步）、psycopg 3、Alembic、pydantic-settings、argon2-cffi、PyJWT、cryptography、pytest、httpx；PostgreSQL 16（Docker Compose）。

**Spec:** `docs/01-项目底座与账号档案.md`（总览见 `docs/00-总览与串联.md`）

## Global Constraints

- 运行平台是 Windows 11，终端是 PowerShell 5.1（不支持 `&&`，多条命令用 `;` 或分多次执行）；也可以用 Bash 工具。
- 所有后端命令都在 `E:\workspace\good-life\backend` 目录下执行，统一用 `uv run ...`。
- PostgreSQL 映射到本机 **5433** 端口，账号、密码、库名都是 `goodlife`；测试库名是 `goodlife_test`。
- 密钥（`JWT_SECRET`、`FIELD_ENCRYPTION_KEY`）只能来自环境变量或 `backend/.env`；`.env` 不入库，仓库里只放 `.env.example`。
- 密码只存 argon2 哈希；档案里的身高、体重、健康状况、备注，以及档案修改记录，都必须用 `EncryptedJSON` 加密存储。
- 统一错误格式：`{"error": {"code": "<机器可读码>", "message": "<中文提示>"}}`；参数校验错误额外带 `details`。
- 除 `users` 表外，每张业务表都必须有 `user_id` 列；查询统一走 `app.common.ownership.owned_by`。
- 任何接口都不接受客户端传入的 user_id；当前用户只从令牌里取。
- 不做：第三方登录、验证码、经期/医嘱/饮食/健身业务、任何大模型调用。
- 提交信息以如下一行结尾：`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## 文件结构

```
good-life/
├── .gitignore
├── README.md                          # 环境搭建与运行说明（任务 6）
├── docker-compose.yml                 # PostgreSQL 16
├── deploy/db-init/01-create-test-db.sql
├── docs/01-交付物/                    # 数据表说明、接口清单、验收记录（任务 6，不含代码）
└── backend/
    ├── pyproject.toml
    ├── .env.example
    ├── alembic.ini
    ├── migrations/
    │   ├── env.py
    │   └── versions/
    │       ├── 0001_users.py
    │       ├── 0002_disclaimer_acceptances.py
    │       └── 0003_profiles.py
    ├── app/
    │   ├── __init__.py
    │   ├── main.py                    # create_app、挂路由
    │   ├── config.py                  # Settings
    │   ├── db.py                      # Base、engine、get_db
    │   ├── errors.py                  # AppError + 统一错误处理
    │   ├── models.py                  # 汇总导入全部模型，供 Alembic 和测试使用
    │   ├── common/ownership.py        # UserOwnedMixin、owned_by
    │   ├── security/passwords.py      # argon2 哈希
    │   ├── security/tokens.py         # JWT 签发与解析
    │   ├── security/crypto.py         # EncryptedJSON 加密类型
    │   ├── auth/{models,schemas,service,deps,router}.py
    │   ├── disclaimer/{content,models,service,deps,router}.py
    │   └── profile/{models,schemas,service,capabilities,router}.py
    └── tests/
        ├── __init__.py
        ├── conftest.py
        ├── helpers.py
        ├── test_health.py
        ├── test_security.py
        ├── test_auth.py
        ├── test_disclaimer.py
        └── test_profile.py
```

---

### Task 1: 仓库、数据库容器与服务骨架

**Files:**
- Create: `.gitignore`, `docker-compose.yml`, `deploy/db-init/01-create-test-db.sql`
- Create: `backend/pyproject.toml`, `backend/.env.example`, `backend/.env`（不提交）
- Create: `backend/app/__init__.py`, `backend/app/config.py`, `backend/app/db.py`, `backend/app/errors.py`, `backend/app/models.py`, `backend/app/main.py`
- Create: `backend/alembic.ini`, `backend/migrations/env.py`（由 alembic init 生成后改写）
- Test: `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`

**Interfaces:**
- Produces:
  - `app.config.get_settings() -> Settings`，字段：`database_url: str`、`jwt_secret: str`、`field_encryption_key: str`、`access_token_expire_minutes: int`
  - `app.db.Base`（DeclarativeBase）、`app.db.get_engine() -> Engine`、`app.db.get_db() -> Iterator[Session]`（FastAPI 依赖）
  - `app.errors.AppError(status_code: int, code: str, message: str)`
  - `app.main.create_app() -> FastAPI`
  - 测试夹具：`client`（TestClient）；每个测试结束后自动清空所有表

- [ ] **Step 1: 初始化 git 与根目录文件**

在 `E:\workspace\good-life` 执行 `git init`，然后创建：

`.gitignore`
```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.env
```

`docker-compose.yml`
```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: goodlife
      POSTGRES_PASSWORD: goodlife
      POSTGRES_DB: goodlife
    ports:
      - "5433:5432"
    volumes:
      - goodlife-pgdata:/var/lib/postgresql/data
      - ./deploy/db-init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U goodlife"]
      interval: 2s
      timeout: 3s
      retries: 30

volumes:
  goodlife-pgdata:
```

`deploy/db-init/01-create-test-db.sql`
```sql
CREATE DATABASE goodlife_test OWNER goodlife;
```

启动数据库：`docker compose up -d --wait db`
Expected: 容器 healthy。用 `docker compose exec db psql -U goodlife -l` 能看到 `goodlife` 和 `goodlife_test` 两个库。

- [ ] **Step 2: 创建后端项目与依赖**

`backend/pyproject.toml`
```toml
[project]
name = "good-life-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[dependency-groups]
dev = []

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

在 `backend/` 执行：
```
uv add fastapi "uvicorn[standard]" "sqlalchemy>=2.0" "psycopg[binary]>=3.2" alembic pydantic-settings argon2-cffi pyjwt cryptography
uv add --dev pytest httpx
```

`backend/.env.example`
```
DATABASE_URL=postgresql+psycopg://goodlife:goodlife@localhost:5433/goodlife
JWT_SECRET=replace-with-a-random-string-of-at-least-32-chars
FIELD_ENCRYPTION_KEY=replace-with-output-of-the-fernet-generate-command-in-README
ACCESS_TOKEN_EXPIRE_MINUTES=10080
```

生成本地 `.env`（不提交）：先把 `.env.example` 复制为 `.env`，再把两个密钥替换成真实值。
- `JWT_SECRET`：用 `uv run python -c "import secrets; print(secrets.token_urlsafe(48))"` 生成
- `FIELD_ENCRYPTION_KEY`：用 `uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` 生成

- [ ] **Step 3: 写配置、数据库、错误处理、应用入口**

`backend/app/__init__.py`：空文件。

`backend/app/config.py`
```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    jwt_secret: str
    field_encryption_key: str
    access_token_expire_minutes: int = 60 * 24 * 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`backend/app/db.py`
```python
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
```

`backend/app/errors.py`
```python
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """业务错误，统一转成 {"error": {"code", "message"}}。"""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _body(code: str, message: str, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(part) for part in err["loc"][1:]), "message": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(status_code=422, content=_body("validation_error", "请求参数不合法", details))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_body("http_error", str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )
```

`backend/app/models.py`
```python
"""汇总导入全部 ORM 模型，让 Base.metadata 完整。Alembic 和测试都依赖这里。"""
```

`backend/app/main.py`
```python
from fastapi import FastAPI

from app.errors import register_error_handlers


def create_app() -> FastAPI:
    app = FastAPI(title="good-life API", version="0.1.0")
    register_error_handlers(app)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 4: 初始化 Alembic 并改写 env.py**

在 `backend/` 执行 `uv run alembic init migrations`。生成的 `alembic.ini` 保持不动（其中 `sqlalchemy.url` 会被 env.py 覆盖）。把 `backend/migrations/env.py` 整个替换为：

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401  注册全部模型
from app.config import get_settings
from app.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)
config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 5: 写测试夹具与失败测试**

`backend/tests/__init__.py`：空文件。

`backend/tests/conftest.py`
```python
import os

# 必须在导入 app 之前设置：测试永远连测试库，并使用固定的测试密钥。
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://goodlife:goodlife@localhost:5433/goodlife_test"
)
os.environ["JWT_SECRET"] = "test-jwt-secret-0123456789-abcdefghijklmnopqrstuvwxyz"
os.environ["FIELD_ENCRYPTION_KEY"] = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

import app.models  # noqa: F401
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


@pytest.fixture
def client():
    with TestClient(create_app()) as test_client:
        yield test_client
```

`backend/tests/test_health.py`
```python
def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_route_uses_unified_error_format(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_error"
```

- [ ] **Step 6: 运行测试**

Run（在 `backend/`）：`uv run pytest -v`
Expected: 2 passed。如果连不上数据库，先检查 `docker compose ps` 里 db 是否 healthy。

- [ ] **Step 7: 提交**

```
git add .gitignore docker-compose.yml deploy backend/pyproject.toml backend/uv.lock backend/.env.example backend/alembic.ini backend/migrations backend/app backend/tests
git commit -m "chore: scaffold backend, postgres compose and test harness"
```
（提交前用 `git status` 确认 `backend/.env` 没有被加入。）

---

### Task 2: 安全基础组件（密码哈希、令牌、字段加密）

**Files:**
- Create: `backend/app/security/__init__.py`, `backend/app/security/passwords.py`, `backend/app/security/tokens.py`, `backend/app/security/crypto.py`
- Test: `backend/tests/test_security.py`

**Interfaces:**
- Consumes: `app.config.get_settings()`
- Produces:
  - `hash_password(password: str) -> str`、`verify_password(password: str, password_hash: str) -> bool`
  - `create_access_token(user_id: uuid.UUID, token_version: int, *, now: datetime | None = None) -> str`
  - `decode_access_token(token: str) -> TokenClaims`，`TokenClaims(user_id: uuid.UUID, token_version: int)`；非法或过期令牌抛 `InvalidTokenError`
  - `encrypt_value(value: Any) -> str`、`decrypt_value(token: str) -> Any`
  - `EncryptedJSON`：SQLAlchemy 列类型，任意可 JSON 序列化的值加密后以 Text 存储

- [ ] **Step 1: 写失败测试**

`backend/tests/test_security.py`
```python
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.security.crypto import decrypt_value, encrypt_value
from app.security.passwords import hash_password, verify_password
from app.security.tokens import InvalidTokenError, create_access_token, decode_access_token


def test_password_hash_is_not_plaintext_and_verifies():
    hashed = hash_password("my-secret-pass")
    assert hashed != "my-secret-pass"
    assert hashed.startswith("$argon2id$")
    assert verify_password("my-secret-pass", hashed)
    assert not verify_password("wrong-pass", hashed)


def test_verify_password_rejects_garbage_hash():
    assert not verify_password("anything", "not-a-hash")


def test_token_roundtrip():
    user_id = uuid.uuid4()
    claims = decode_access_token(create_access_token(user_id, 3))
    assert claims.user_id == user_id
    assert claims.token_version == 3


def test_expired_token_is_rejected():
    long_ago = datetime.now(UTC) - timedelta(days=365)
    token = create_access_token(uuid.uuid4(), 0, now=long_ago)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_tampered_token_is_rejected():
    token = create_access_token(uuid.uuid4(), 0)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token[:-2] + ("aa" if token[-2:] != "aa" else "bb"))


def test_encryption_roundtrip_and_ciphertext_hides_plaintext():
    value = {"health_conditions": "轻度高血压", "height_cm": 172.5}
    token = encrypt_value(value)
    assert "高血压" not in token
    assert "172.5" not in token
    assert decrypt_value(token) == value


def test_encryption_is_randomized():
    assert encrypt_value("同样的内容") != encrypt_value("同样的内容")
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_security.py -v`
Expected: FAIL，报 `ModuleNotFoundError: No module named 'app.security'`

- [ ] **Step 3: 实现**

`backend/app/security/__init__.py`：空文件。

`backend/app/security/passwords.py`
```python
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False
```

`backend/app/security/tokens.py`
```python
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings

ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    pass


@dataclass(frozen=True)
class TokenClaims:
    user_id: uuid.UUID
    token_version: int


def create_access_token(user_id: uuid.UUID, token_version: int, *, now: datetime | None = None) -> str:
    settings = get_settings()
    issued_at = now or datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> TokenClaims:
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "ver", "exp"]},
        )
        return TokenClaims(user_id=uuid.UUID(payload["sub"]), token_version=int(payload["ver"]))
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise InvalidTokenError(str(exc)) from exc
```

`backend/app/security/crypto.py`
```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest -v`
Expected: 全部通过（2 + 7 = 9 passed）

- [ ] **Step 5: 提交**

```
git add backend/app/security backend/tests/test_security.py
git commit -m "feat: add password hashing, JWT tokens and field encryption"
```

---

### Task 3: 用户注册、登录、退出与当前用户

**Files:**
- Create: `backend/app/auth/__init__.py`, `backend/app/auth/models.py`, `backend/app/auth/schemas.py`, `backend/app/auth/service.py`, `backend/app/auth/deps.py`, `backend/app/auth/router.py`
- Create: `backend/migrations/versions/0001_users.py`
- Modify: `backend/app/models.py`, `backend/app/main.py`
- Test: `backend/tests/helpers.py`, `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `hash_password`、`verify_password`、`create_access_token`、`decode_access_token`、`InvalidTokenError`、`AppError`、`get_db`、`Base`
- Produces:
  - ORM `app.auth.models.User`：`id: uuid.UUID`、`username: str`、`password_hash: str`、`token_version: int`、`created_at: datetime`；表名 `users`
  - 依赖 `app.auth.deps.get_current_user(...) -> User`：无令牌抛 401 `not_authenticated`，非法、过期或已退出的令牌抛 401 `invalid_token`
  - 接口：`POST /api/auth/register`（201，返回 `{id, username, created_at}`）、`POST /api/auth/login`（200，返回 `{access_token, token_type}`）、`POST /api/auth/logout`（204）、`GET /api/auth/me`
  - 测试辅助 `tests.helpers.register_and_login(client, username, password="secret-pass-1") -> dict[str, str]`（返回 Authorization 请求头）

- [ ] **Step 1: 写失败测试**

`backend/tests/helpers.py`
```python
def register_and_login(client, username: str, password: str = "secret-pass-1") -> dict[str, str]:
    response = client.post("/api/auth/register", json={"username": username, "password": password})
    assert response.status_code == 201, response.text
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
```

`backend/tests/test_auth.py`
```python
import uuid
from datetime import UTC, datetime, timedelta

from app.security.tokens import create_access_token
from tests.helpers import register_and_login


def test_register_returns_user_without_password(client):
    response = client.post("/api/auth/register", json={"username": "Alice", "password": "secret-pass-1"})
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "alice"
    assert "password" not in body and "password_hash" not in body


def test_duplicate_username_is_rejected_case_insensitively(client):
    client.post("/api/auth/register", json={"username": "alice", "password": "secret-pass-1"})
    response = client.post("/api/auth/register", json={"username": "ALICE", "password": "another-pass-2"})
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "username_taken"
    assert "已被注册" in error["message"]


def test_register_validates_input(client):
    response = client.post("/api/auth/register", json={"username": "a!", "password": "short"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_login_with_wrong_password_or_unknown_user_is_rejected(client):
    client.post("/api/auth/register", json={"username": "alice", "password": "secret-pass-1"})
    wrong = client.post("/api/auth/login", json={"username": "alice", "password": "wrong-pass-9"})
    unknown = client.post("/api/auth/login", json={"username": "nobody", "password": "secret-pass-1"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"] == "invalid_credentials"


def test_me_requires_login(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_me_returns_current_user(client):
    headers = register_and_login(client, "alice")
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["username"] == "alice"


def test_garbage_token_is_rejected(client):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_token_for_unknown_user_is_rejected(client):
    token = create_access_token(uuid.uuid4(), 0)
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_expired_token_is_rejected(client):
    headers = register_and_login(client, "alice")
    user_id = uuid.UUID(client.get("/api/auth/me", headers=headers).json()["id"])
    token = create_access_token(user_id, 0, now=datetime.now(UTC) - timedelta(days=365))
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_logout_invalidates_existing_token(client):
    headers = register_and_login(client, "alice")
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"
    login = client.post("/api/auth/login", json={"username": "alice", "password": "secret-pass-1"})
    new_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/auth/me", headers=new_headers).status_code == 200
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_auth.py -v`
Expected: FAIL（接口不存在，返回 404）

- [ ] **Step 3: 模型与迁移**

`backend/app/auth/__init__.py`：空文件。

`backend/app/auth/models.py`
```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

`backend/app/models.py`（追加导入）
```python
"""汇总导入全部 ORM 模型，让 Base.metadata 完整。Alembic 和测试都依赖这里。"""

from app.auth import models as auth_models  # noqa: F401
```

`backend/migrations/versions/0001_users.py`
```python
"""create users

Revision ID: 0001_users
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_users"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("username", sa.String(32), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("users")
```

- [ ] **Step 4: schemas、service、deps、router**

`backend/app/auth/schemas.py`
```python
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.lower()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.lower()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    created_at: datetime
```

`backend/app/auth/service.py`
```python
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
```

`backend/app/auth/deps.py`
```python
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
```

`backend/app/auth/router.py`
```python
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.deps import get_current_user
from app.auth.models import User
from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.db import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=UserOut)
def register(body: RegisterRequest, db: Annotated[Session, Depends(get_db)]) -> User:
    return service.register_user(db, body.username, body.password)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    return TokenResponse(access_token=service.login(db, body.username, body.password))


@router.post("/logout", status_code=204)
def logout(
    user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]
) -> Response:
    service.logout(db, user)
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
```

`backend/app/main.py`：在 `register_error_handlers(app)` 之后加一行 `app.include_router(auth_router)`，文件顶部加 `from app.auth.router import router as auth_router`。

- [ ] **Step 5: 运行确认通过**

Run: `uv run pytest -v`
Expected: 全部通过

- [ ] **Step 6: 提交**

```
git add backend/app backend/migrations backend/tests
git commit -m "feat: add user registration, login, logout with token versioning"
```

---

### Task 4: 免责声明与确认闸门

**Files:**
- Create: `backend/app/disclaimer/__init__.py`, `content.py`, `models.py`, `service.py`, `deps.py`, `router.py`（均在 `backend/app/disclaimer/` 下）
- Create: `backend/migrations/versions/0002_disclaimer_acceptances.py`
- Modify: `backend/app/models.py`, `backend/app/main.py`
- Test: `backend/tests/test_disclaimer.py`；`backend/tests/helpers.py` 追加 `accept_disclaimer`

**Interfaces:**
- Consumes: `User`、`get_current_user`、`get_db`、`AppError`、`Base`
- Produces:
  - `app.disclaimer.content.DISCLAIMER_VERSION: str`、`DISCLAIMER_TEXT: str`
  - ORM `DisclaimerAcceptance`：`id`、`user_id`、`version`、`accepted_at`；表名 `disclaimer_acceptances`，`(user_id, version)` 唯一
  - 依赖 `app.disclaimer.deps.require_disclaimer_user(...) -> User`：未确认当前版本时抛 403 `disclaimer_not_accepted`。**后续所有业务接口都必须依赖它，而不是直接依赖 get_current_user。**
  - 接口：`GET /api/disclaimer`（公开，返回 `{version, text}`）、`GET /api/disclaimer/status`（需登录，返回 `{current_version, accepted, accepted_at}`）、`POST /api/disclaimer/accept`（需登录，请求 `{version}`，版本不对返回 409 `disclaimer_outdated`，重复确认幂等）
  - 测试辅助 `tests.helpers.accept_disclaimer(client, headers) -> None`

- [ ] **Step 1: 写失败测试**

`backend/tests/helpers.py` 追加：
```python
def accept_disclaimer(client, headers: dict[str, str]) -> None:
    version = client.get("/api/disclaimer").json()["version"]
    response = client.post("/api/disclaimer/accept", json={"version": version}, headers=headers)
    assert response.status_code == 200, response.text
```

`backend/tests/test_disclaimer.py`
```python
from typing import Annotated

from fastapi import Depends
from fastapi.testclient import TestClient

from app.auth.models import User
from app.disclaimer.deps import require_disclaimer_user
from app.main import create_app
from tests.helpers import accept_disclaimer, register_and_login


def test_disclaimer_is_public_and_says_not_medical_advice(client):
    response = client.get("/api/disclaimer")
    assert response.status_code == 200
    body = response.json()
    assert body["version"]
    assert "不构成医疗诊断" in body["text"]


def test_status_before_and_after_accept(client):
    headers = register_and_login(client, "alice")
    before = client.get("/api/disclaimer/status", headers=headers).json()
    assert before["accepted"] is False and before["accepted_at"] is None
    accept_disclaimer(client, headers)
    after = client.get("/api/disclaimer/status", headers=headers).json()
    assert after["accepted"] is True and after["accepted_at"] is not None


def test_accept_is_idempotent(client):
    headers = register_and_login(client, "alice")
    accept_disclaimer(client, headers)
    accept_disclaimer(client, headers)
    assert client.get("/api/disclaimer/status", headers=headers).json()["accepted"] is True


def test_accepting_wrong_version_is_rejected(client):
    headers = register_and_login(client, "alice")
    response = client.post("/api/disclaimer/accept", json={"version": "old-version"}, headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "disclaimer_outdated"


def test_business_routes_are_blocked_until_disclaimer_accepted():
    app = create_app()

    @app.get("/api/_test/business")
    def business(user: Annotated[User, Depends(require_disclaimer_user)]) -> dict[str, str]:
        return {"username": user.username}

    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        blocked = client.get("/api/_test/business", headers=headers)
        assert blocked.status_code == 403
        assert blocked.json()["error"]["code"] == "disclaimer_not_accepted"
        accept_disclaimer(client, headers)
        assert client.get("/api/_test/business", headers=headers).status_code == 200


def test_acceptance_is_per_user(client):
    alice = register_and_login(client, "alice")
    bob = register_and_login(client, "bob")
    accept_disclaimer(client, alice)
    assert client.get("/api/disclaimer/status", headers=bob).json()["accepted"] is False
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_disclaimer.py -v`
Expected: FAIL，报 `ModuleNotFoundError: No module named 'app.disclaimer'`

- [ ] **Step 3: 实现**

`backend/app/disclaimer/__init__.py`：空文件。

`backend/app/disclaimer/content.py`
```python
DISCLAIMER_VERSION = "2026-09-30"

DISCLAIMER_TEXT = (
    "good-life 提供的所有内容，包括饮食建议、经期与排卵预测、训练建议和智能体的回答，"
    "仅用于日常生活方式参考，不构成医疗诊断、治疗建议或用药指导，"
    "不能替代医生、药师或营养师的专业意见。\n"
    "如果你正在接受治疗、处于孕期或哺乳期、患有慢性病，或出现身体不适，"
    "请以医嘱为准并及时就医。\n"
    "经期与排卵预测仅供参考，不能用于避孕或诊断。\n"
    "你提供的健康相关信息会加密保存，仅用于为你本人生成建议。"
)
```

`backend/app/disclaimer/models.py`
```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DisclaimerAcceptance(Base):
    __tablename__ = "disclaimer_acceptances"
    __table_args__ = (UniqueConstraint("user_id", "version", name="uq_disclaimer_user_version"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    version: Mapped[str] = mapped_column(String(32))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

`backend/migrations/versions/0002_disclaimer_acceptances.py`
```python
"""create disclaimer_acceptances

Revision ID: 0002_disclaimer_acceptances
Revises: 0001_users
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_disclaimer_acceptances"
down_revision = "0001_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "disclaimer_acceptances",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "version", name="uq_disclaimer_user_version"),
    )
    op.create_index("ix_disclaimer_acceptances_user_id", "disclaimer_acceptances", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_disclaimer_acceptances_user_id", table_name="disclaimer_acceptances")
    op.drop_table("disclaimer_acceptances")
```

`backend/app/models.py` 追加一行：
```python
from app.disclaimer import models as disclaimer_models  # noqa: F401
```

`backend/app/disclaimer/service.py`
```python
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.disclaimer.content import DISCLAIMER_VERSION
from app.disclaimer.models import DisclaimerAcceptance
from app.errors import AppError


def get_current_acceptance(db: Session, user_id: uuid.UUID) -> DisclaimerAcceptance | None:
    return db.scalar(
        select(DisclaimerAcceptance).where(
            DisclaimerAcceptance.user_id == user_id,
            DisclaimerAcceptance.version == DISCLAIMER_VERSION,
        )
    )


def accept(db: Session, user_id: uuid.UUID, version: str) -> DisclaimerAcceptance:
    if version != DISCLAIMER_VERSION:
        raise AppError(409, "disclaimer_outdated", "免责声明已更新，请重新阅读最新版本后确认")
    existing = get_current_acceptance(db, user_id)
    if existing is not None:
        return existing
    acceptance = DisclaimerAcceptance(user_id=user_id, version=version)
    db.add(acceptance)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return get_current_acceptance(db, user_id)
    db.refresh(acceptance)
    return acceptance
```

`backend/app/disclaimer/deps.py`
```python
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.models import User
from app.db import get_db
from app.disclaimer.service import get_current_acceptance
from app.errors import AppError


def require_disclaimer_user(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """所有业务接口的统一入口：已登录且已确认当前版本免责声明。"""
    if get_current_acceptance(db, user.id) is None:
        raise AppError(403, "disclaimer_not_accepted", "请先阅读并确认免责声明")
    return user
```

`backend/app/disclaimer/router.py`
```python
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.models import User
from app.db import get_db
from app.disclaimer import service
from app.disclaimer.content import DISCLAIMER_TEXT, DISCLAIMER_VERSION

router = APIRouter(prefix="/api/disclaimer", tags=["disclaimer"])


class DisclaimerOut(BaseModel):
    version: str
    text: str


class DisclaimerStatus(BaseModel):
    current_version: str
    accepted: bool
    accepted_at: datetime | None


class AcceptRequest(BaseModel):
    version: str


@router.get("", response_model=DisclaimerOut)
def get_disclaimer() -> DisclaimerOut:
    return DisclaimerOut(version=DISCLAIMER_VERSION, text=DISCLAIMER_TEXT)


@router.get("/status", response_model=DisclaimerStatus)
def get_status(
    user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]
) -> DisclaimerStatus:
    acceptance = service.get_current_acceptance(db, user.id)
    return DisclaimerStatus(
        current_version=DISCLAIMER_VERSION,
        accepted=acceptance is not None,
        accepted_at=acceptance.accepted_at if acceptance else None,
    )


@router.post("/accept", response_model=DisclaimerStatus)
def accept(
    body: AcceptRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DisclaimerStatus:
    acceptance = service.accept(db, user.id, body.version)
    return DisclaimerStatus(current_version=DISCLAIMER_VERSION, accepted=True, accepted_at=acceptance.accepted_at)
```

`backend/app/main.py`：加 `from app.disclaimer.router import router as disclaimer_router` 与 `app.include_router(disclaimer_router)`。

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest -v`
Expected: 全部通过

- [ ] **Step 5: 提交**

```
git add backend/app backend/migrations backend/tests
git commit -m "feat: add disclaimer acceptance and business-route gate"
```

---

### Task 5: 个人档案、修改记录、能力清单与归属约定

**Files:**
- Create: `backend/app/common/__init__.py`, `backend/app/common/ownership.py`
- Create: `backend/app/profile/__init__.py`, `models.py`, `schemas.py`, `service.py`, `capabilities.py`, `router.py`（均在 `backend/app/profile/` 下）
- Create: `backend/migrations/versions/0003_profiles.py`
- Modify: `backend/app/models.py`, `backend/app/main.py`
- Test: `backend/tests/test_profile.py`

**Interfaces:**
- Consumes: `Base`、`EncryptedJSON`、`User`、`require_disclaimer_user`、`get_db`、`get_engine`、`decrypt_value`
- Produces:
  - `app.common.ownership.UserOwnedMixin`（提供 `user_id` 外键列，带索引）、`owned_by(model, user_id) -> Select`
  - ORM `Profile`（表 `profiles`，主键 `user_id`）、`ProfileChange`（表 `profile_changes`）
  - `app.profile.service.get_or_create_profile(db, user_id) -> Profile`、`update_profile(db, user_id, changes: dict) -> Profile`、`list_profile_changes(db, user_id, limit=50) -> list[ProfileChange]`
  - `app.profile.capabilities.compute_capabilities(profile: Profile) -> dict[str, bool]`，键为 `cycle`、`medical`、`nutrition`、`fitness`。**哪些模块向用户开放，只在这里判断。**
  - 接口（全部依赖 `require_disclaimer_user`）：`GET /api/profile`、`PATCH /api/profile`、`GET /api/profile/changes`、`GET /api/me/capabilities`

档案字段与取值：

| 字段 | 类型 | 取值或范围 | 存储 |
|---|---|---|---|
| gender | 字符串或空 | female、male、other | 明文 |
| birth_year | 整数或空 | 1900 至今年 | 明文 |
| height_cm | 数字或空 | 50 至 250 | 加密 |
| weight_kg | 数字或空 | 20 至 300 | 加密 |
| activity_level | 字符串或空 | sedentary、light、moderate、active、very_active | 明文 |
| goal | 字符串或空 | lose_fat、gain_muscle、maintain、none | 明文 |
| diet_preferences | 字符串列表 | 最多 30 项，每项 1 至 32 字 | 明文 |
| food_avoidances | 字符串列表 | 最多 30 项，每项 1 至 32 字 | 明文 |
| health_conditions | 文本或空 | 最多 1000 字 | 加密 |
| notes | 文本或空 | 最多 1000 字 | 加密 |
| cycle_tracking_opt_out | 布尔 | 默认 false | 明文 |

PATCH 语义：只修改请求里出现的字段；显式传 null 表示清空（列表字段清空为空列表，`cycle_tracking_opt_out` 清空为 false）；出现未知字段（例如 `user_id`）返回 422。只有值真正变化时才写一条修改记录，内容为 `{字段: {"old": 旧值, "new": 新值}}`，整条加密存储。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_profile.py`
```python
from sqlalchemy import text

from app.db import Base, get_engine
from app.security.crypto import decrypt_value
from tests.helpers import accept_disclaimer, register_and_login


def _ready_user(client, username: str) -> dict[str, str]:
    headers = register_and_login(client, username)
    accept_disclaimer(client, headers)
    return headers


def test_profile_requires_disclaimer(client):
    headers = register_and_login(client, "alice")
    for method, path in [("get", "/api/profile"), ("patch", "/api/profile"),
                         ("get", "/api/profile/changes"), ("get", "/api/me/capabilities")]:
        kwargs = {"json": {"goal": "maintain"}} if method == "patch" else {}
        response = getattr(client, method)(path, headers=headers, **kwargs)
        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "disclaimer_not_accepted"


def test_profile_requires_login(client):
    assert client.get("/api/profile").status_code == 401


def test_new_user_gets_empty_profile(client):
    headers = _ready_user(client, "alice")
    body = client.get("/api/profile", headers=headers).json()
    assert body["gender"] is None
    assert body["height_cm"] is None
    assert body["diet_preferences"] == []
    assert body["cycle_tracking_opt_out"] is False


def test_update_then_read_returns_new_values(client):
    headers = _ready_user(client, "alice")
    patch = {"gender": "female", "birth_year": 1998, "height_cm": 162.5, "weight_kg": 52,
             "activity_level": "light", "goal": "lose_fat", "diet_preferences": ["清淡"],
             "food_avoidances": ["香菜"], "health_conditions": "轻度贫血", "notes": "胃不太好"}
    response = client.patch("/api/profile", json=patch, headers=headers)
    assert response.status_code == 200
    body = client.get("/api/profile", headers=headers).json()
    for key, value in patch.items():
        assert body[key] == value, key


def test_update_writes_change_record_only_when_values_change(client):
    headers = _ready_user(client, "alice")
    client.patch("/api/profile", json={"weight_kg": 60}, headers=headers)
    client.patch("/api/profile", json={"weight_kg": 58.5}, headers=headers)
    client.patch("/api/profile", json={"weight_kg": 58.5}, headers=headers)
    changes = client.get("/api/profile/changes", headers=headers).json()
    assert len(changes) == 2
    assert changes[0]["changes"] == {"weight_kg": {"old": 60, "new": 58.5}}
    assert changes[1]["changes"] == {"weight_kg": {"old": None, "new": 60}}


def test_null_clears_field(client):
    headers = _ready_user(client, "alice")
    client.patch("/api/profile", json={"notes": "临时备注", "diet_preferences": ["素食"]}, headers=headers)
    client.patch("/api/profile", json={"notes": None, "diet_preferences": None}, headers=headers)
    body = client.get("/api/profile", headers=headers).json()
    assert body["notes"] is None
    assert body["diet_preferences"] == []


def test_invalid_values_and_unknown_fields_are_rejected(client):
    headers = _ready_user(client, "alice")
    assert client.patch("/api/profile", json={"height_cm": 999}, headers=headers).status_code == 422
    assert client.patch("/api/profile", json={"gender": "robot"}, headers=headers).status_code == 422
    assert client.patch("/api/profile", json={"birth_year": 3000}, headers=headers).status_code == 422
    response = client.patch("/api/profile", json={"user_id": "00000000-0000-0000-0000-000000000000"},
                            headers=headers)
    assert response.status_code == 422


def test_users_cannot_see_each_others_profile(client):
    alice = _ready_user(client, "alice")
    bob = _ready_user(client, "bob")
    client.patch("/api/profile", json={"health_conditions": "高血压", "weight_kg": 70}, headers=alice)
    bob_profile = client.get("/api/profile", headers=bob).json()
    assert bob_profile["health_conditions"] is None
    assert bob_profile["weight_kg"] is None
    assert client.get("/api/profile/changes", headers=bob).json() == []
    assert client.get("/api/profile", headers=alice).json()["health_conditions"] == "高血压"


def test_capabilities_follow_gender_and_opt_out(client):
    headers = _ready_user(client, "alice")
    assert client.get("/api/me/capabilities", headers=headers).json()["cycle"] is False
    client.patch("/api/profile", json={"gender": "female"}, headers=headers)
    caps = client.get("/api/me/capabilities", headers=headers).json()
    assert caps == {"cycle": True, "medical": True, "nutrition": True, "fitness": True}
    client.patch("/api/profile", json={"cycle_tracking_opt_out": True}, headers=headers)
    assert client.get("/api/me/capabilities", headers=headers).json()["cycle"] is False
    client.patch("/api/profile", json={"gender": "male", "cycle_tracking_opt_out": False}, headers=headers)
    assert client.get("/api/me/capabilities", headers=headers).json()["cycle"] is False


def test_sensitive_columns_are_encrypted_at_rest(client):
    headers = _ready_user(client, "alice")
    client.patch("/api/profile", json={"height_cm": 172.5, "weight_kg": 65.25,
                                       "health_conditions": "轻度高血压", "notes": "少盐"}, headers=headers)
    with get_engine().connect() as conn:
        row = conn.execute(text(
            "SELECT height_cm, weight_kg, health_conditions, notes FROM profiles"
        )).one()
        change = conn.execute(text("SELECT changes FROM profile_changes")).scalar_one()
        password_hash = conn.execute(text("SELECT password_hash FROM users")).scalar_one()
    raw = " ".join(row) + change
    for plaintext in ["172.5", "65.25", "高血压", "少盐"]:
        assert plaintext not in raw
    assert decrypt_value(row[0]) == 172.5
    assert decrypt_value(row[2]) == "轻度高血压"
    assert password_hash.startswith("$argon2id$")
    assert "secret-pass-1" not in password_hash


def test_every_business_table_has_user_id():
    for name, table in Base.metadata.tables.items():
        if name == "users":
            continue
        assert "user_id" in table.columns, f"{name} 缺少 user_id 列"
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_profile.py -v`
Expected: FAIL（`/api/profile` 返回 404，加密测试报表不存在）

- [ ] **Step 3: 归属约定**

`backend/app/common/__init__.py`：空文件。

`backend/app/common/ownership.py`
```python
import uuid
from typing import Any

from sqlalchemy import ForeignKey, Select, select
from sqlalchemy.orm import Mapped, mapped_column


class UserOwnedMixin:
    """业务表统一带上用户归属列。"""

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


def owned_by(model: Any, user_id: uuid.UUID) -> Select:
    """所有业务查询的起点：只查当前用户的数据。"""
    return select(model).where(model.user_id == user_id)
```

- [ ] **Step 4: 模型与迁移**

`backend/app/profile/__init__.py`：空文件。

`backend/app/profile/models.py`
```python
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.ownership import UserOwnedMixin
from app.db import Base
from app.security.crypto import EncryptedJSON


class Profile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    gender: Mapped[str | None] = mapped_column(String(16))
    birth_year: Mapped[int | None] = mapped_column(Integer)
    height_cm: Mapped[float | None] = mapped_column(EncryptedJSON)
    weight_kg: Mapped[float | None] = mapped_column(EncryptedJSON)
    activity_level: Mapped[str | None] = mapped_column(String(16))
    goal: Mapped[str | None] = mapped_column(String(16))
    diet_preferences: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    food_avoidances: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    health_conditions: Mapped[str | None] = mapped_column(EncryptedJSON)
    notes: Mapped[str | None] = mapped_column(EncryptedJSON)
    cycle_tracking_opt_out: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProfileChange(UserOwnedMixin, Base):
    __tablename__ = "profile_changes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    changes: Mapped[dict[str, Any]] = mapped_column(EncryptedJSON)
```

`backend/app/models.py` 追加一行：
```python
from app.profile import models as profile_models  # noqa: F401
```

`backend/migrations/versions/0003_profiles.py`
```python
"""create profiles and profile_changes

Revision ID: 0003_profiles
Revises: 0002_disclaimer_acceptances
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_profiles"
down_revision = "0002_disclaimer_acceptances"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("gender", sa.String(16)),
        sa.Column("birth_year", sa.Integer()),
        sa.Column("height_cm", sa.Text()),
        sa.Column("weight_kg", sa.Text()),
        sa.Column("activity_level", sa.String(16)),
        sa.Column("goal", sa.String(16)),
        sa.Column("diet_preferences", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("food_avoidances", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("health_conditions", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("cycle_tracking_opt_out", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "profile_changes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changes", sa.Text(), nullable=False),
    )
    op.create_index("ix_profile_changes_user_id", "profile_changes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_profile_changes_user_id", table_name="profile_changes")
    op.drop_table("profile_changes")
    op.drop_table("profiles")
```

- [ ] **Step 5: schemas、service、capabilities、router**

`backend/app/profile/schemas.py`
```python
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Gender = Literal["female", "male", "other"]
ActivityLevel = Literal["sedentary", "light", "moderate", "active", "very_active"]
Goal = Literal["lose_fat", "gain_muscle", "maintain", "none"]
Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    gender: Gender | None
    birth_year: int | None
    height_cm: float | None
    weight_kg: float | None
    activity_level: ActivityLevel | None
    goal: Goal | None
    diet_preferences: list[str]
    food_avoidances: list[str]
    health_conditions: str | None
    notes: str | None
    cycle_tracking_opt_out: bool
    updated_at: datetime


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gender: Gender | None = None
    birth_year: int | None = Field(default=None, ge=1900)
    height_cm: float | None = Field(default=None, ge=50, le=250)
    weight_kg: float | None = Field(default=None, ge=20, le=300)
    activity_level: ActivityLevel | None = None
    goal: Goal | None = None
    diet_preferences: list[Tag] | None = Field(default=None, max_length=30)
    food_avoidances: list[Tag] | None = Field(default=None, max_length=30)
    health_conditions: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=1000)
    cycle_tracking_opt_out: bool | None = None

    @field_validator("birth_year")
    @classmethod
    def not_in_future(cls, value: int | None) -> int | None:
        if value is not None and value > datetime.now(UTC).year:
            raise ValueError("出生年份不能晚于今年")
        return value


class ProfileChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    changed_at: datetime
    changes: dict[str, Any]
```

`backend/app/profile/service.py`
```python
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.common.ownership import owned_by
from app.profile.models import Profile, ProfileChange

# 显式传 null 时，这些字段回到默认值而不是 None。
_NULL_MEANS_DEFAULT: dict[str, Any] = {
    "diet_preferences": [],
    "food_avoidances": [],
    "cycle_tracking_opt_out": False,
}


def get_or_create_profile(db: Session, user_id: uuid.UUID) -> Profile:
    profile = db.scalar(owned_by(Profile, user_id))
    if profile is None:
        profile = Profile(user_id=user_id, diet_preferences=[], food_avoidances=[], cycle_tracking_opt_out=False)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def update_profile(db: Session, user_id: uuid.UUID, changes: dict[str, Any]) -> Profile:
    profile = get_or_create_profile(db, user_id)
    diff: dict[str, dict[str, Any]] = {}
    for field, new_value in changes.items():
        if new_value is None and field in _NULL_MEANS_DEFAULT:
            new_value = _NULL_MEANS_DEFAULT[field]
        old_value = getattr(profile, field)
        if old_value != new_value:
            diff[field] = {"old": old_value, "new": new_value}
            setattr(profile, field, new_value)
    if diff:
        db.add(ProfileChange(user_id=user_id, changes=diff))
        db.commit()
        db.refresh(profile)
    return profile


def list_profile_changes(db: Session, user_id: uuid.UUID, limit: int = 50) -> list[ProfileChange]:
    query = owned_by(ProfileChange, user_id).order_by(ProfileChange.changed_at.desc()).limit(limit)
    return list(db.scalars(query))
```

`backend/app/profile/capabilities.py`
```python
from app.profile.models import Profile


def compute_capabilities(profile: Profile) -> dict[str, bool]:
    """决定哪些业务模块向该用户开放。后续步骤只能从这里判断，不要各处重复写规则。"""
    return {
        "cycle": profile.gender == "female" and not profile.cycle_tracking_opt_out,
        "medical": True,
        "nutrition": True,
        "fitness": True,
    }
```

`backend/app/profile/router.py`
```python
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.models import User
from app.db import get_db
from app.disclaimer.deps import require_disclaimer_user
from app.profile import service
from app.profile.capabilities import compute_capabilities
from app.profile.models import Profile, ProfileChange
from app.profile.schemas import ProfileChangeOut, ProfileOut, ProfileUpdate

router = APIRouter(prefix="/api", tags=["profile"])

CurrentUser = Annotated[User, Depends(require_disclaimer_user)]
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/profile", response_model=ProfileOut)
def get_profile(user: CurrentUser, db: DbSession) -> Profile:
    return service.get_or_create_profile(db, user.id)


@router.patch("/profile", response_model=ProfileOut)
def patch_profile(body: ProfileUpdate, user: CurrentUser, db: DbSession) -> Profile:
    return service.update_profile(db, user.id, body.model_dump(exclude_unset=True))


@router.get("/profile/changes", response_model=list[ProfileChangeOut])
def get_profile_changes(user: CurrentUser, db: DbSession) -> list[ProfileChange]:
    return service.list_profile_changes(db, user.id)


@router.get("/me/capabilities")
def get_capabilities(user: CurrentUser, db: DbSession) -> dict[str, bool]:
    return compute_capabilities(service.get_or_create_profile(db, user.id))
```

`backend/app/main.py`：加 `from app.profile.router import router as profile_router` 与 `app.include_router(profile_router)`。

- [ ] **Step 6: 运行确认通过**

Run: `uv run pytest -v`
Expected: 全部通过。若 `test_update_writes_change_record_only_when_values_change` 里 `old` 显示为 `60.0` 而不是 `60`，这是等价值（Python 中 `60 == 60.0`），断言照样通过。

- [ ] **Step 7: 提交**

```
git add backend/app backend/migrations backend/tests
git commit -m "feat: add profile with encrypted fields, change history and capabilities"
```

---

### Task 6: 交付文档与干净环境复现验证

**Files:**
- Create: `README.md`（仓库根目录，环境搭建与运行说明，允许出现命令）
- Create: `docs/01-交付物/数据表说明.md`、`docs/01-交付物/接口清单.md`、`docs/01-交付物/验收记录.md`（这三份**不得出现代码或命令**，只用中文表格与自然语言）
- Modify: `docs/00-总览与串联.md`（步骤 01 状态改为"待验收"）

**Interfaces:**
- Consumes: 任务 1 至 5 的全部成果

- [ ] **Step 1: 写 README.md**

内容必须包含以下小节，每节给出可直接执行的命令：
1. 前置条件：Docker Desktop、Python 3.12、uv。
2. 启动数据库：`docker compose up -d --wait db`。
3. 安装依赖：进入 `backend` 后执行 `uv sync`。
4. 配置：把 `backend/.env.example` 复制为 `backend/.env`，并给出生成 `JWT_SECRET` 与 `FIELD_ENCRYPTION_KEY` 的两条命令（同任务 1 Step 2）。强调 `.env` 不能提交，加密密钥丢失后已加密的数据无法解密。
5. 建表：`uv run alembic upgrade head`。
6. 运行测试：`uv run pytest -v`（测试使用 `goodlife_test` 库，不会影响开发库）。
7. 启动服务：`uv run uvicorn app.main:app --reload --port 8000`，接口文档地址 `http://localhost:8000/docs`。
8. 手动体验顺序：注册、登录、确认免责声明、读写档案（说明在 `/docs` 页面点 Authorize 填入令牌）。
9. 常见问题：5433 端口被占用时如何改端口（同时改 compose 与 `.env`）；测试库不存在时（数据卷在加 init 脚本之前就已创建）用 `docker compose down -v` 重建。

- [ ] **Step 2: 写三份交付文档（不含代码）**

`docs/01-交付物/数据表说明.md`：逐表说明 `users`、`disclaimer_acceptances`、`profiles`、`profile_changes`。每张表用表格列出：字段、含义、是否必填、是否加密、取值说明。末尾写"归属约定"：除 users 外每张表都有用户归属列，所有查询都限定在当前用户内，并有自动化检查保证后续新增表也遵守。

`docs/01-交付物/接口清单.md`：用表格列出全部接口：方法、路径、是否需要登录、是否需要已确认免责声明、用途、主要错误码。再单独一节列出统一错误格式与全部错误码及中文含义：`validation_error`、`http_error`、`username_taken`、`invalid_credentials`、`not_authenticated`、`invalid_token`、`disclaimer_not_accepted`、`disclaimer_outdated`。

`docs/01-交付物/验收记录.md`：把 `docs/01-项目底座与账号档案.md` 的 7 条验收标准逐条列成表格，列为：验收项、自动化测试（写测试文件名与测试名）、手动核对方法（用自然语言描述在接口文档页面怎么点）、结果。结果列由执行者在 Step 3 验证后填写"已通过自动化验证"，另留一列"用户验收"为空，等用户填写。

对应关系：
- 第 1 条 → Step 3 的干净环境复现
- 第 2 条 → `test_auth.py::test_duplicate_username_is_rejected_case_insensitively`
- 第 3 条 → `test_profile.py::test_profile_requires_login`、`test_auth.py::test_me_requires_login`、`test_profile.py::test_new_user_gets_empty_profile`
- 第 4 条 → `test_profile.py::test_users_cannot_see_each_others_profile`、`test_profile.py::test_every_business_table_has_user_id`
- 第 5 条 → `test_profile.py::test_update_then_read_returns_new_values`、`test_profile.py::test_update_writes_change_record_only_when_values_change`
- 第 6 条 → `test_profile.py::test_sensitive_columns_are_encrypted_at_rest`
- 第 7 条 → `test_disclaimer.py::test_business_routes_are_blocked_until_disclaimer_accepted`、`test_profile.py::test_profile_requires_disclaimer`

- [ ] **Step 3: 干净环境复现验证（验收第 1 条）**

1. 先提交全部改动，确保工作区干净（`git status` 无改动）。
2. 在原仓库根目录执行 `docker compose down -v`，删掉本计划创建的数据库容器与数据卷。
3. 把仓库克隆到临时目录：`git clone E:\workspace\good-life <会话临时目录>\good-life-clean`。
4. **只按 README 的步骤**，在克隆目录里从头执行：启动数据库、`uv sync`、生成 `.env`、`alembic upgrade head`、`pytest -v`。
5. 在克隆目录启动 uvicorn（后台运行），请求 `http://localhost:8000/api/health` 应返回 `{"status":"ok"}`；然后停止 uvicorn。
6. 在克隆目录执行 `docker compose down -v` 清理，再回到原仓库执行 `docker compose up -d --wait db` 与 `uv run alembic upgrade head`，恢复开发环境。
7. 如果 README 有任何一步照做不通，修 README 并回到第 1 步重来。
8. 把复现结果（每一步是否成功、测试通过数量）写进 `docs/01-交付物/验收记录.md` 第 1 条。

- [ ] **Step 4: 更新总览状态**

把 `docs/00-总览与串联.md` 步骤总表中步骤 01 的状态从"未开始"改为"待验收"。

- [ ] **Step 5: 最终检查与提交**

Run（在 `backend/`）：`uv run pytest -v`
Expected: 全部通过。

```
git add README.md docs
git commit -m "docs: add step 01 setup guide, schema, API list and acceptance record"
```
