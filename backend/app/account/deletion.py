import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session


def delete_account(db: Session, user_id: uuid.UUID) -> None:
    """立即彻底删除账号：锁住用户行，执行一条删除用户的语句，全部数据随外键级联在同一个事务里删除并提交。

    先 SELECT ... FOR UPDATE：正在写入该用户数据的并发事务（外键检查会给用户行加 KEY SHARE 锁）先提交，
    它们写入的行也随级联删除；之后再来的写入因用户行已不存在而失败。不做冻结期与软删除，不可恢复。
    每张带 user_id 的表都对 users 级联删除，由 tests/test_cascade_guard.py 按数据库实际结构守护。
    """
    db.execute(text("SELECT id FROM users WHERE id = :id FOR UPDATE"), {"id": user_id})
    db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
    db.commit()
