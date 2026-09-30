import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.clock import get_today
from app.cycle import records
from app.cycle.deps import require_cycle_user
from app.cycle.models import CyclePeriod, CycleSettings
from app.cycle.schemas import CycleSettingsOut, CycleSettingsUpdate, PeriodCreate, PeriodOut, PeriodUpdate
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
