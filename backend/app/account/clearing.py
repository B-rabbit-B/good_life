import uuid

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.cycle.models import CycleDayLog, CyclePeriod, CycleSettings
from app.medical.models import MedicalOrder


def clear_module_data(db: Session, user_id: uuid.UUID, kind: str) -> None:
    """删除本人在一个敏感模块里的全部数据；不提交，由调用方与撤回同意放在同一个事务里。

    经期：经期记录、每日记录与经期状态。医嘱：全部医嘱单，原件、条目与条目事件随外键级联删除。
    """
    if kind == "cycle":
        for model in (CyclePeriod, CycleDayLog, CycleSettings):
            db.execute(delete(model).where(model.user_id == user_id))
    elif kind == "medical":
        db.execute(delete(MedicalOrder).where(MedicalOrder.user_id == user_id))
    else:
        raise ValueError(f"unknown consent kind: {kind}")
