"""演示数据：一个演示账号，录入三份样例医嘱，全部处于待确认状态，供体验确认、复核与解除流程。"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.service import register_user
from app.consents import service as consents_service
from app.consents.content import CONSENT_KINDS, CONSENT_VERSION
from app.db import get_sessionmaker
from app.disclaimer import service as disclaimer_service
from app.disclaimer.content import DISCLAIMER_VERSION
from app.medical import orders
from app.medical.samples import SAMPLE_ORDERS

DEMO_USERNAME = "demo_medical"
DEMO_PASSWORD = "demo-pass-123"


def seed(db: Session, today: date) -> bool:
    if db.scalar(select(User).where(User.username == DEMO_USERNAME)) is not None:
        return False
    user = register_user(db, DEMO_USERNAME, DEMO_PASSWORD)
    disclaimer_service.accept(db, user.id, DISCLAIMER_VERSION)
    for kind in CONSENT_KINDS:
        consents_service.grant(db, user.id, kind, CONSENT_VERSION)
    for text in SAMPLE_ORDERS.values():
        orders.create_order(db, user.id, text, today, today)
    return True


def main() -> None:
    db = get_sessionmaker()()
    try:
        created = seed(db, date.today())
    finally:
        db.close()
    if created:
        print(f"已创建演示账号 {DEMO_USERNAME}（密码 {DEMO_PASSWORD}），录入了 3 份样例医嘱，条目均待确认。")
    else:
        print("演示账号已存在，未重复创建。")


if __name__ == "__main__":
    main()
