"""经期相关数据的读写与校验。所有查询都从 owned_by 开始。"""

import uuid
from datetime import date
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.common.ownership import get_owned_or_404, owned_by
from app.cycle.models import CycleDayLog, CyclePeriod, CycleSettings
from app.errors import AppError

MAX_PERIOD_DAYS = 15


def list_periods(db: Session, user_id: uuid.UUID) -> list[CyclePeriod]:
    return list(db.scalars(owned_by(CyclePeriod, user_id).order_by(CyclePeriod.start_date.desc())))


def _validate_period(
    db: Session,
    user_id: uuid.UUID,
    start: date,
    end: date | None,
    today: date,
    exclude_id: uuid.UUID | None = None,
) -> None:
    if start > today or (end is not None and end > today):
        raise AppError(422, "period_in_future", "经期日期不能晚于今天")
    if end is not None and end < start:
        raise AppError(422, "invalid_period_range", "结束日期不能早于开始日期")
    if end is not None and (end - start).days > MAX_PERIOD_DAYS - 1:
        raise AppError(422, "period_too_long", f"单次经期不能超过 {MAX_PERIOD_DAYS} 天，请检查日期")
    if end is None and (today - start).days > MAX_PERIOD_DAYS - 1:
        raise AppError(
            422, "period_too_long", f"这次经期已超过 {MAX_PERIOD_DAYS} 天还没有填写结束日期，请补全结束日期"
        )
    new_last = end or today  # 没有结束日视为一直持续到今天
    for other in list_periods(db, user_id):
        if other.id == exclude_id:
            continue
        other_last = other.end_date or today
        if start <= other_last and other.start_date <= new_last:
            if other.end_date is None:
                message = "与一次尚未结束的经期重叠，请先填写那次经期的结束日期"
            else:
                message = "与已有的经期记录日期重叠"
            raise AppError(409, "period_overlap", message)


def create_period(db: Session, user_id: uuid.UUID, start: date, end: date | None, today: date) -> CyclePeriod:
    _validate_period(db, user_id, start, end, today)
    period = CyclePeriod(user_id=user_id, start_date=start, end_date=end)
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


def update_period(
    db: Session, user_id: uuid.UUID, period_id: uuid.UUID, changes: dict[str, Any], today: date
) -> CyclePeriod:
    period = get_owned_or_404(db, CyclePeriod, user_id, period_id)
    start = changes.get("start_date", period.start_date)
    end = changes["end_date"] if "end_date" in changes else period.end_date
    _validate_period(db, user_id, start, end, today, exclude_id=period.id)
    period.start_date, period.end_date = start, end
    db.commit()
    db.refresh(period)
    return period


def delete_period(db: Session, user_id: uuid.UUID, period_id: uuid.UUID) -> None:
    db.delete(get_owned_or_404(db, CyclePeriod, user_id, period_id))
    db.commit()


def get_cycle_settings(db: Session, user_id: uuid.UUID) -> CycleSettings:
    settings = db.scalar(owned_by(CycleSettings, user_id))
    if settings is None:
        # 与档案相同：并发的首次请求主键冲突时什么都不做，再查一次。
        db.execute(
            insert(CycleSettings)
            .values(user_id=user_id, status="tracking")
            .on_conflict_do_nothing(index_elements=[CycleSettings.user_id])
        )
        db.commit()
        settings = db.scalar(owned_by(CycleSettings, user_id))
    return settings


def set_cycle_status(db: Session, user_id: uuid.UUID, status: str) -> CycleSettings:
    settings = get_cycle_settings(db, user_id)
    settings.status = status
    db.commit()
    db.refresh(settings)
    return settings


def upsert_day_log(
    db: Session, user_id: uuid.UUID, log_date: date, details: dict[str, Any], today: date
) -> CycleDayLog:
    if log_date > today:
        raise AppError(422, "log_in_future", "不能记录未来日期")
    log = db.scalar(owned_by(CycleDayLog, user_id).where(CycleDayLog.log_date == log_date))
    if log is None:
        log = CycleDayLog(user_id=user_id, log_date=log_date, details=details)
        db.add(log)
    else:
        log.details = details  # 整条替换；加密列必须重新赋值才会被保存
    db.commit()
    db.refresh(log)
    return log


def list_day_logs(db: Session, user_id: uuid.UUID, start: date, end: date) -> list[CycleDayLog]:
    query = (
        owned_by(CycleDayLog, user_id)
        .where(CycleDayLog.log_date >= start, CycleDayLog.log_date <= end)
        .order_by(CycleDayLog.log_date)
    )
    return list(db.scalars(query))


def delete_day_log(db: Session, user_id: uuid.UUID, log_date: date) -> None:
    log = db.scalar(owned_by(CycleDayLog, user_id).where(CycleDayLog.log_date == log_date))
    if log is None:
        raise AppError(404, "not_found", "记录不存在")
    db.delete(log)
    db.commit()
