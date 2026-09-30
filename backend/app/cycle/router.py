import uuid
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.clock import get_today
from app.cycle import insights, records
from app.cycle.deps import require_cycle_user
from app.cycle.models import CyclePeriod, CycleSettings
from app.cycle.schemas import (
    CycleSettingsOut,
    CycleSettingsUpdate,
    CycleStatsOut,
    DayLogIn,
    DayLogOut,
    PeriodCreate,
    PeriodOut,
    PeriodUpdate,
    PhaseOut,
    PredictionOut,
    TipsOut,
)
from app.db import get_db

router = APIRouter(prefix="/api/cycle", tags=["cycle"])

CycleUser = Annotated[User, Depends(require_cycle_user)]
DbSession = Annotated[Session, Depends(get_db)]
Today = Annotated[date, Depends(get_today)]


@router.get("/periods", response_model=list[PeriodOut])
def list_periods(user: CycleUser, db: DbSession) -> list[CyclePeriod]:
    return records.list_periods(db, user.id)


@router.post("/periods", status_code=201, response_model=PeriodOut)
def create_period(body: PeriodCreate, user: CycleUser, db: DbSession, today: Today) -> CyclePeriod:
    return records.create_period(db, user.id, body.start_date, body.end_date, today)


@router.patch("/periods/{period_id}", response_model=PeriodOut)
def update_period(
    period_id: uuid.UUID, body: PeriodUpdate, user: CycleUser, db: DbSession, today: Today
) -> CyclePeriod:
    return records.update_period(db, user.id, period_id, body.model_dump(exclude_unset=True), today)


@router.delete("/periods/{period_id}", status_code=204)
def delete_period(period_id: uuid.UUID, user: CycleUser, db: DbSession) -> Response:
    records.delete_period(db, user.id, period_id)
    return Response(status_code=204)


@router.get("/settings", response_model=CycleSettingsOut)
def get_settings(user: CycleUser, db: DbSession) -> CycleSettings:
    return records.get_cycle_settings(db, user.id)


@router.put("/settings", response_model=CycleSettingsOut)
def put_settings(body: CycleSettingsUpdate, user: CycleUser, db: DbSession) -> CycleSettings:
    return records.set_cycle_status(db, user.id, body.status)


DAY_LOG_DEFAULT_DAYS = 90


@router.get("/day-logs", response_model=list[DayLogOut])
def list_day_logs(
    user: CycleUser,
    db: DbSession,
    today: Today,
    start: date | None = None,
    end: date | None = None,
) -> list[DayLogOut]:
    end = end or today
    start = start or end - timedelta(days=DAY_LOG_DEFAULT_DAYS - 1)
    return [DayLogOut.from_record(log) for log in records.list_day_logs(db, user.id, start, end)]


@router.put("/day-logs/{log_date}", response_model=DayLogOut)
def put_day_log(log_date: date, body: DayLogIn, user: CycleUser, db: DbSession, today: Today) -> DayLogOut:
    return DayLogOut.from_record(records.upsert_day_log(db, user.id, log_date, body.model_dump(), today))


@router.delete("/day-logs/{log_date}", status_code=204)
def delete_day_log(log_date: date, user: CycleUser, db: DbSession) -> Response:
    records.delete_day_log(db, user.id, log_date)
    return Response(status_code=204)


@router.get("/stats", response_model=CycleStatsOut)
def get_stats(user: CycleUser, db: DbSession, today: Today) -> CycleStatsOut:
    return insights.get_stats(db, user.id, today)


@router.get("/prediction", response_model=PredictionOut)
def get_prediction(user: CycleUser, db: DbSession, today: Today) -> PredictionOut:
    return PredictionOut.model_validate(insights.get_prediction(db, user.id, today))


@router.get("/phase", response_model=PhaseOut)
def get_phase(
    user: CycleUser, db: DbSession, today: Today, day: Annotated[date | None, Query(alias="date")] = None
) -> PhaseOut:
    return PhaseOut.model_validate(insights.get_phase_info(db, user.id, day or today))


@router.get("/tips", response_model=TipsOut)
def get_tips(
    user: CycleUser, db: DbSession, today: Today, day: Annotated[date | None, Query(alias="date")] = None
) -> TipsOut:
    return insights.get_tips(db, user.id, day or today)
