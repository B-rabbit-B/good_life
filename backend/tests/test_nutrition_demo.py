from datetime import date

from sqlalchemy import select

from app.auth.models import User
from app.db import get_sessionmaker
from app.nutrition.catalog import load_catalog
from app.nutrition.context import build_context
from app.nutrition.demo import DEMO_USERS, seed
from app.nutrition.engine import CAUTION, NOT_RECOMMENDED, SUITABLE, evaluate_food

TODAY = date(2026, 10, 6)


def _evaluate(db, user_id, food_name):
    catalog = load_catalog()
    food = catalog.search(food_name)[0].food
    context = build_context(db, user_id, TODAY)
    return evaluate_food(food, food.default_grams, context, catalog)


def test_seed_creates_four_demo_users_once():
    db = get_sessionmaker()()
    try:
        assert seed(db, TODAY) == list(DEMO_USERS)
        assert seed(db, TODAY) == []
    finally:
        db.close()
    assert len(DEMO_USERS) == 4


def test_each_demo_user_gets_the_expected_verdict():
    db = get_sessionmaker()()
    try:
        seed(db, TODAY)
        ids = {u.username: u.id for u in db.scalars(select(User))}
        avoid, period, muscle, healthy = (ids[name] for name in DEMO_USERS)

        mapo = _evaluate(db, avoid, "麻婆豆腐")
        assert mapo.conclusion == NOT_RECOMMENDED
        assert any(r.source == "medical" and r.effect == "block" for r in mapo.reasons)

        melon = _evaluate(db, period, "西瓜")
        assert melon.conclusion == CAUTION
        assert any(r.source == "cycle" and r.ref == "menstrual-warm" for r in melon.reasons)
        assert not any(r.source == "medical" for r in melon.reasons)

        breast = _evaluate(db, muscle, "鸡胸肉")
        assert any(r.source == "goal" and r.effect == "prefer" for r in breast.reasons)

        tomato = _evaluate(db, healthy, "番茄炒蛋")
        assert tomato.conclusion == SUITABLE
        assert tomato.reasons == ()
    finally:
        db.close()
