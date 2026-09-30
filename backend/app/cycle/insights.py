"""把数据库里的经期数据交给引擎计算，并处理暂停状态。"""

import uuid
from dataclasses import asdict
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.cycle import engine, records
from app.cycle.schemas import CycleStatsOut, PhaseOut, TipOut, TipsOut
from app.cycle.tips import TIPS_DISCLAIMER, tips_for_phase

SYMPTOM_WINDOW_DAYS = 365
PAUSED_NOTES = {
    "pregnant": "已标记为孕期，经期预测已暂停。孕期相关问题请以产检医生的意见为准。",
    "paused": "经期预测已暂停，可以在经期设置中恢复。",
}


def engine_periods(db: Session, user_id: uuid.UUID) -> list[engine.Period]:
    return [engine.Period(p.start_date, p.end_date) for p in records.list_periods(db, user_id)]


def _paused_status(db: Session, user_id: uuid.UUID) -> str | None:
    status = records.get_cycle_settings(db, user_id).status
    return None if status == "tracking" else status


def get_stats(db: Session, user_id: uuid.UUID, today: date) -> CycleStatsOut:
    stats = engine.compute_stats(engine_periods(db, user_id))
    logs = records.list_day_logs(db, user_id, today - timedelta(days=SYMPTOM_WINDOW_DAYS), today)
    symptoms = engine.summarize_symptoms([log.details for log in logs])
    return CycleStatsOut(**asdict(stats), **asdict(symptoms))


def get_prediction(db: Session, user_id: uuid.UUID, today: date) -> engine.Prediction:
    paused = _paused_status(db, user_id)
    if paused:
        return engine.Prediction(status="paused", notes=[PAUSED_NOTES[paused]])
    return engine.predict(engine_periods(db, user_id), today)


def get_phase_info(db: Session, user_id: uuid.UUID, day: date, today: date) -> engine.PhaseInfo:
    paused = _paused_status(db, user_id)
    if paused:
        return engine.PhaseInfo(day=day, phase="unknown", reason=paused)
    return engine.get_phase(engine_periods(db, user_id), day, today)


def get_tips(db: Session, user_id: uuid.UUID, day: date, today: date) -> TipsOut:
    phase = get_phase_info(db, user_id, day, today)
    return TipsOut(
        phase=PhaseOut.model_validate(phase),
        tips=[TipOut.model_validate(rule) for rule in tips_for_phase(phase.phase)],
        disclaimer=TIPS_DISCLAIMER,
    )
