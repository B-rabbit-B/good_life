from datetime import date, timedelta

from sqlalchemy import select

from app.auth.models import User
from app.cycle import insights
from app.cycle.demo import DEMO_USERS, build_periods, seed
from app.db import get_sessionmaker

TODAY = date(2026, 9, 1)


def test_build_periods_ends_before_today():
    periods = build_periods([28, 29], TODAY)
    starts = [start for start, _ in periods]
    assert starts == [date(2026, 6, 26), date(2026, 7, 24), date(2026, 8, 22)]
    assert [(b - a).days for a, b in zip(starts, starts[1:])] == [28, 29]
    assert starts[-1] == TODAY - timedelta(days=10)
    assert all(end <= TODAY and (end - start).days == 4 for start, end in periods)


def test_seed_creates_three_demo_users_once():
    db = get_sessionmaker()()
    try:
        assert seed(db, TODAY) == list(DEMO_USERS)
        assert seed(db, TODAY) == []
        users = {u.username: u.id for u in db.scalars(select(User))}
        regular = insights.get_prediction(db, users["demo_regular"], TODAY)
        irregular = insights.get_prediction(db, users["demo_irregular"], TODAY)
        sparse = insights.get_prediction(db, users["demo_sparse"], TODAY)
    finally:
        db.close()
    assert regular.status == "ok" and regular.flags == []
    assert "irregular" in irregular.flags
    assert sparse.status == "insufficient_data"
