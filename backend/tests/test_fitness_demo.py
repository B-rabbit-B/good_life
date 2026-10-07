from datetime import date, timedelta

from sqlalchemy import select

from app.auth.models import User
from app.db import get_sessionmaker
from app.fitness import signals, summaries, workouts
from app.fitness.demo import DEMO_USERNAME, seed
from app.fitness.models import CustomExercise

TODAY = date(2026, 10, 7)


def _user_id(db):
    return db.scalar(select(User.id).where(User.username == DEMO_USERNAME))


def test_seed_creates_the_demo_user_once():
    db = get_sessionmaker()()
    try:
        assert seed(db, TODAY) is True
        assert seed(db, TODAY) is False
        user_id = _user_id(db)
        found = workouts.list_workouts(db, user_id, TODAY - timedelta(days=6), TODAY)
        assert len(found) == 6
        assert len(db.scalars(select(CustomExercise).where(CustomExercise.user_id == user_id)).all()) == 1
    finally:
        db.close()


def test_week_covers_each_day_but_the_rest_day():
    db = get_sessionmaker()()
    try:
        seed(db, TODAY)
        user_id = _user_id(db)
        days = {w.performed_on for w in workouts.list_workouts(db, user_id, TODAY - timedelta(days=6), TODAY)}
        assert days == {TODAY - timedelta(days=back) for back in (6, 5, 4, 2, 1, 0)}
        assert signals.training_signal(db, user_id, TODAY - timedelta(days=3)).trained is False
        today_signal = signals.training_signal(db, user_id, TODAY)
        assert (today_signal.trained, today_signal.kinds, today_signal.intensity) == (True, ("strength",), "vigorous")
    finally:
        db.close()


def test_bench_press_trend_goes_up():
    db = get_sessionmaker()()
    try:
        seed(db, TODAY)
        _, points = summaries.exercise_trend_for(db, _user_id(db), "ex:bench_press")
        assert [p.day for p in points] == [TODAY - timedelta(days=6), TODAY]
        assert points[0].max_weight_kg < points[1].max_weight_kg
        assert points[0].total_volume < points[1].total_volume
    finally:
        db.close()
