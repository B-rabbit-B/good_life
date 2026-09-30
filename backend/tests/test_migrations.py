import uuid
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import text

from app.db import Base, get_engine
from app.security.crypto import decrypt_value

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_migrations_match_models():
    # 会话级 fixture 已把测试库迁移到 head；模型与迁移不一致时这里会列出差异。
    with get_engine().connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def _status_of(user_id: uuid.UUID) -> str:
    with get_engine().connect() as conn:
        return conn.execute(text("SELECT status FROM cycle_settings WHERE user_id = :id"), {"id": user_id}).scalar_one()


def test_status_encryption_migration_converts_existing_rows():
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    user_id = uuid.uuid4()
    command.downgrade(cfg, "0005_cycle")
    try:
        with get_engine().begin() as conn:
            conn.execute(
                text("INSERT INTO users (id, username, password_hash) VALUES (:id, 'migrated', 'x')"), {"id": user_id}
            )
            conn.execute(text("INSERT INTO cycle_settings (user_id, status) VALUES (:id, 'pregnant')"), {"id": user_id})
    finally:
        command.upgrade(cfg, "head")
    encrypted = _status_of(user_id)
    assert "pregnant" not in encrypted
    assert decrypt_value(encrypted) == "pregnant"
    command.downgrade(cfg, "0005_cycle")
    try:
        assert _status_of(user_id) == "pregnant"
    finally:
        command.upgrade(cfg, "head")
