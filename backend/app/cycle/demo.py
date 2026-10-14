"""演示数据：三位经期用户——规律型、波动型、数据不足型。用法见 README 的“经期模块演示”。"""

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
from app.profile.service import update_profile

DEMO_PASSWORD = "demo-pass-123"
DEMO_USERS = {
    "demo_regular": [28, 28, 29, 28],
    "demo_irregular": [24, 33, 27, 36, 31],
    "demo_sparse": [28],
}
LAST_START_DAYS_AGO = 10
PERIOD_DAYS = 5


def build_periods(cycle_lengths: list[int], today: date) -> list[tuple[date, date]]:
    """从最近一次（今天往前 10 天开始）倒推，每次经期 5 天。"""
    starts = [today - timedelta(days=LAST_START_DAYS_AGO)]
    for length in reversed(cycle_lengths):
        starts.insert(0, starts[0] - timedelta(days=length))
    return [(start, start + timedelta(days=PERIOD_DAYS - 1)) for start in starts]


def seed(db: Session, today: date) -> list[str]:
    created = []
    for username, lengths in DEMO_USERS.items():
        if db.scalar(select(User).where(User.username == username)) is not None:
            continue
        user = register_user(db, username, DEMO_PASSWORD)
        disclaimer_service.accept(db, user.id, DISCLAIMER_VERSION)
        for kind in CONSENT_KINDS:
            consents_service.grant(db, user.id, kind, CONSENT_VERSION)
        update_profile(db, user.id, {"gender": "female"})
        for start, end in build_periods(lengths, today):
            records.create_period(db, user.id, start, end, today)
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
