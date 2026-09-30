from datetime import date

from sqlalchemy import select

from app.auth.models import User
from app.db import get_sessionmaker
from app.medical import items, orders
from app.medical.demo import DEMO_USERNAME, seed

TODAY = date(2026, 9, 30)


def test_seed_creates_demo_user_with_three_pending_orders_once():
    db = get_sessionmaker()()
    try:
        assert seed(db, TODAY) is True
        assert seed(db, TODAY) is False
        user_id = db.scalar(select(User.id).where(User.username == DEMO_USERNAME))
        created = orders.list_orders(db, user_id)
        pending = items.list_items(db, user_id, status="pending_confirmation")
    finally:
        db.close()
    assert len(created) == 3
    assert len(pending) == 9
