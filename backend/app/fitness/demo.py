"""演示数据：一个男性增肌用户一周的训练记录。用法见 README 的“健身模块演示”。"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.service import register_user
from app.db import get_sessionmaker
from app.disclaimer import service as disclaimer_service
from app.disclaimer.content import DISCLAIMER_VERSION
from app.fitness import workouts
from app.fitness.schemas import WorkoutIn
from app.profile.service import update_profile

DEMO_USERNAME = "demo_fitness"
DEMO_PASSWORD = "demo-pass-123"
PROFILE = {
    "gender": "male", "birth_year": 1994, "height_cm": 178, "weight_kg": 70, "activity_level": "moderate",
    "goal": "gain_muscle",
}
CUSTOM_EXERCISE = {
    "name": "史密斯机划船", "aliases": ["史密斯划船"], "kind": "strength", "primary_muscles": ["back", "biceps"],
    "equipment": "machine", "traits": ["bending"],
}
BENCH_WEIGHT_WEEK_AGO = 60
BENCH_WEIGHT_TODAY = 65


def _strength(exercise_id: str, weight_kg: float, reps: int, sets: int, rest_seconds: int = 90) -> dict:
    return {
        "exercise_id": exercise_id,
        "sets": [{"weight_kg": weight_kg, "reps": reps, "rest_seconds": rest_seconds} for _ in range(sets)],
    }


def build_week(today: date, custom_id: str) -> list[dict]:
    """以今天为第七天往前倒推六天；一周前是胸与三头日，今天卧推，重量比一周前增加；第四天是休息日。"""

    def day(back: int) -> str:
        return (today - timedelta(days=back)).isoformat()

    return [
        {
            "performed_on": day(6), "rpe": 7, "note": "胸与三头日",
            "strength": [
                _strength("ex:bench_press", BENCH_WEIGHT_WEEK_AGO, 8, 3, 120),
                _strength("ex:dumbbell_fly", 14, 12, 3),
                _strength("ex:triceps_pushdown", 25, 12, 3),
            ],
        },
        {
            "performed_on": day(5), "rpe": 6,
            "cardio": [{"exercise_id": "ex:running", "duration_minutes": 30, "distance_km": 4.5}],
        },
        {
            "performed_on": day(4), "rpe": 7, "note": "背与二头日",
            "strength": [
                _strength("ex:pull_up", 0, 8, 3),
                _strength("ex:barbell_row", 50, 10, 3),
                _strength(custom_id, 40, 10, 3),
                _strength("ex:dumbbell_curl", 12, 12, 3),
            ],
        },
        {
            "performed_on": day(2), "rpe": 8, "note": "腿日",
            "strength": [
                _strength("ex:squat", 80, 8, 4, 150),
                _strength("ex:leg_press", 120, 12, 3),
                _strength("ex:calf_raise", 60, 15, 3, 60),
            ],
        },
        {
            "performed_on": day(1), "rpe": 5,
            "cardio": [{"exercise_id": "ex:swimming", "duration_minutes": 40, "distance_km": 1.2}],
        },
        {
            "performed_on": day(0), "rpe": 8, "note": "卧推比一周前加重",
            "strength": [
                _strength("ex:bench_press", BENCH_WEIGHT_TODAY, 8, 3, 120),
                _strength("ex:dumbbell_bench_press", 24, 10, 3),
            ],
        },
    ]


def seed(db: Session, today: date) -> bool:
    """创建演示账号与一周训练；账号已存在时什么都不做并返回 False。"""
    if db.scalar(select(User).where(User.username == DEMO_USERNAME)) is not None:
        return False
    user = register_user(db, DEMO_USERNAME, DEMO_PASSWORD)
    disclaimer_service.accept(db, user.id, DISCLAIMER_VERSION)
    update_profile(db, user.id, PROFILE)
    custom = workouts.create_custom_exercise(db, user.id, dict(CUSTOM_EXERCISE))
    for payload in build_week(today, custom.id):
        workouts.create_workout(db, user.id, WorkoutIn.model_validate(payload), today)
    return True


def main() -> None:
    db = get_sessionmaker()()
    try:
        created = seed(db, date.today())
    finally:
        db.close()
    if created:
        print(f"已创建演示账号：{DEMO_USERNAME}，密码为 {DEMO_PASSWORD}，并写入一周的训练记录。")
    else:
        print("演示账号已存在，未重复创建。")


if __name__ == "__main__":
    main()
