"""从数据库实际结构（pg_catalog）检查带 user_id 的表，不读模型定义。

- user_tables：当前模式里全部带 user_id 列的表；
- cascade_problems：带 user_id、却没有“user_id 指向 users(id) 且删除时级联（confdeltype = 'c'）”外键的表；
- row_counts：某个用户在每张带 user_id 的表里的行数，外加 users 表本身；
- user_fingerprint：某个用户全部行按表与主键排序后的摘要，用来判断“这个用户的数据没变”。

都可以传入一个已有的连接（例如一个之后回滚的事务），不传时自己开一个只读连接。
"""

import hashlib
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection, text

from app.db import get_engine

_USER_TABLES = text("""
    SELECT c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'user_id' AND NOT a.attisdropped
    WHERE c.relkind IN ('r', 'p') AND n.nspname = current_schema()
    ORDER BY c.relname
""")

_CASCADE_PROBLEMS = text("""
    SELECT c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'user_id' AND NOT a.attisdropped
    WHERE c.relkind IN ('r', 'p') AND n.nspname = current_schema()
      AND NOT EXISTS (
        SELECT 1
        FROM pg_constraint k
        JOIN pg_class target ON target.oid = k.confrelid
        JOIN pg_namespace tn ON tn.oid = target.relnamespace
        JOIN pg_attribute ta ON ta.attrelid = target.oid AND ta.attname = 'id'
        WHERE k.contype = 'f' AND k.conrelid = c.oid
          AND target.relname = 'users' AND tn.nspname = current_schema()
          AND k.conkey = ARRAY[a.attnum] AND k.confkey = ARRAY[ta.attnum]
          AND k.confdeltype = 'c'
      )
    ORDER BY c.relname
""")

_PRIMARY_KEY = text("""
    SELECT a.attname
    FROM pg_index i
    JOIN pg_class c ON c.oid = i.indrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey)
    WHERE i.indisprimary AND c.relname = :table AND n.nspname = current_schema()
    ORDER BY array_position(i.indkey, a.attnum)
""")


@contextmanager
def _connection(conn: Connection | None) -> Iterator[Connection]:
    if conn is not None:
        yield conn
        return
    with get_engine().connect() as own:
        yield own


def user_tables(conn: Connection | None = None) -> list[str]:
    with _connection(conn) as c:
        return list(c.execute(_USER_TABLES).scalars())


def cascade_problems(conn: Connection | None = None) -> list[str]:
    with _connection(conn) as c:
        return list(c.execute(_CASCADE_PROBLEMS).scalars())


def row_counts(user_id: uuid.UUID | str, conn: Connection | None = None) -> dict[str, int]:
    with _connection(conn) as c:
        counts = {"users": c.execute(text("SELECT count(*) FROM users WHERE id = :id"), {"id": user_id}).scalar_one()}
        for table in user_tables(c):
            counts[table] = c.execute(
                text(f'SELECT count(*) FROM "{table}" WHERE user_id = :id'), {"id": user_id}).scalar_one()
        return counts


def user_fingerprint(user_id: uuid.UUID | str, conn: Connection | None = None) -> str:
    digest = hashlib.sha256()
    with _connection(conn) as c:
        targets = [("users", "id"), *((table, "user_id") for table in user_tables(c))]
        for table, column in targets:
            keys = ", ".join(f'"{key}"' for key in c.execute(_PRIMARY_KEY, {"table": table}).scalars())
            rows = c.execute(text(f'SELECT t::text FROM "{table}" t WHERE "{column}" = :id ORDER BY {keys}'),
                             {"id": user_id}).scalars()
            digest.update(f"[{table}]".encode())
            for row in rows:
                digest.update(row.encode())
                digest.update(b"\n")
    return digest.hexdigest()
