"""演示数据：四个饮食演示账号——有忌口医嘱、经期、增肌、健康无约束。用法见 README 的“饮食与约束引擎演示”。"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.service import register_user
from app.consents import service as consents_service
from app.consents.content import CONSENT_KINDS, CONSENT_VERSION
from app.cycle import records
from app.db import get_sessionmaker
from app.disclaimer import service as disclaimer_service
from app.disclaimer.content import DISCLAIMER_VERSION
from app.medical import items, orders
from app.profile.service import update_profile

DEMO_PASSWORD = "demo-pass-123"
AVOID_ORDER_TEXT = "一周内忌食辛辣、油腻食物，禁酒。"
CYCLE_LENGTHS = [28, 29, 28]
PERIOD_DAYS = 5
DEMO_USERS = {
    "demo_avoid": {
        "gender": "male", "birth_year": 1985, "height_cm": 175, "weight_kg": 72, "activity_level": "light",
        "goal": "maintain",
    },
    "demo_period": {
        "gender": "female", "birth_year": 1996, "height_cm": 162, "weight_kg": 54, "activity_level": "light",
        "goal": "maintain",
    },
    "demo_muscle": {
        "gender": "male", "birth_year": 1994, "height_cm": 178, "weight_kg": 70, "activity_level": "moderate",
        "goal": "gain_muscle",
    },
    "demo_healthy": {
        "gender": "male", "birth_year": 1990, "height_cm": 170, "weight_kg": 65, "activity_level": "light",
        "goal": "maintain",
    },
}


def build_periods(today: date) -> list[tuple[date, date | None]]:
    """从最近一次（昨天开始、尚未结束）按 28、29、28 天的周期倒推出共四次月经，早期每次 5 天。"""
    starts = [today - timedelta(days=1)]
    for length in reversed(CYCLE_LENGTHS):
        starts.insert(0, starts[0] - timedelta(days=length))
    periods = [(start, start + timedelta(days=PERIOD_DAYS - 1)) for start in starts[:-1]]
    return [*periods, (starts[-1], None)]


def _record_and_confirm_avoid_order(db: Session, user: User, today: date) -> None:
    order = orders.create_order(db, user.id, AVOID_ORDER_TEXT, today, today)
    for item in orders.list_order_items(db, user.id, order.id):
        items.confirm_item(db, user.id, item.id, {}, today)


def _record_periods(db: Session, user: User, today: date) -> None:
    for start, end in build_periods(today):
        records.create_period(db, user.id, start, end, today)


EXTRA_SETUP = {"demo_avoid": _record_and_confirm_avoid_order, "demo_period": _record_periods}


def seed(db: Session, today: date) -> list[str]:
    created = []
    for username, profile in DEMO_USERS.items():
        if db.scalar(select(User).where(User.username == username)) is not None:
            continue
        user = register_user(db, username, DEMO_PASSWORD)
        disclaimer_service.accept(db, user.id, DISCLAIMER_VERSION)
        for kind in CONSENT_KINDS:
            consents_service.grant(db, user.id, kind, CONSENT_VERSION)
        update_profile(db, user.id, profile)
        if username in EXTRA_SETUP:
            EXTRA_SETUP[username](db, user, today)
        created.append(username)
    return created


def main() -> None:
    db = get_sessionmaker()()
    try:
        created = seed(db, date.today())
    finally:
        db.close()
    if created:
        print(f"已创建演示账号：{'、'.join(created)}，密码均为 {DEMO_PASSWORD}")
    else:
        print("演示账号已存在，未重复创建。")


if __name__ == "__main__":
    main()
