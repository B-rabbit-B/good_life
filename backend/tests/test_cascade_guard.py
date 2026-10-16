"""删除与级联守护：从数据库实际结构检查每张带 user_id 的表都对 users 级联删除；填满助手确实覆盖每张表。"""

from sqlalchemy import text

from app.db import get_engine
from tests.agent_fake import scripted  # noqa: F401
from tests.amap_fake import fake  # noqa: F401
from tests.db_inspect import cascade_problems, row_counts, user_tables
from tests.full_user import fill_every_table
from tests.helpers import ready_user


def _user_id(username: str) -> str:
    with get_engine().connect() as conn:
        return str(conn.execute(text("SELECT id FROM users WHERE username = :u"), {"u": username}).scalar_one())


def test_every_user_table_cascades_from_users():
    assert len(user_tables()) >= 28
    assert cascade_problems() == []


def test_cascade_check_flags_a_table_without_cascade():
    with get_engine().connect() as conn:
        transaction = conn.begin()
        try:
            conn.execute(text("CREATE TABLE cascade_probe (id integer PRIMARY KEY, "
                              "user_id uuid REFERENCES users(id) ON DELETE NO ACTION)"))
            conn.execute(text("CREATE TABLE cascade_probe_loose (id integer PRIMARY KEY, user_id uuid)"))
            assert cascade_problems(conn) == ["cascade_probe", "cascade_probe_loose"]
            assert {"cascade_probe", "cascade_probe_loose"} <= set(user_tables(conn))
        finally:
            transaction.rollback()
    assert cascade_problems() == []


def test_fill_helper_touches_every_user_table(client, scripted, fake):  # noqa: F811
    headers = ready_user(client, "filly")
    fill_every_table(client, headers, marker="mkfill01", scripted=scripted, amap=fake)
    counts = row_counts(_user_id("filly"))
    assert set(counts) == {"users", *user_tables()}
    assert [table for table, count in counts.items() if count == 0] == []
