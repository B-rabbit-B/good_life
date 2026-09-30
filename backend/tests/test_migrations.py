from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.db import Base, get_engine


def test_migrations_match_models():
    # 会话级 fixture 已把测试库迁移到 head；模型与迁移不一致时这里会列出差异。
    with get_engine().connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []
