"""今日训练信号：只描述某一天练了什么、强度、估算消耗和与医嘱的冲突，不给任何饮食结论。"""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.fitness import summaries, workouts
from app.fitness.calc import ESTIMATE_NOTE, INTENSITY_LEVELS, WorkoutInput, peak_intensity
from app.fitness.conflicts import EXERCISE_LIMIT, Conflict, find_conflicts
from app.fitness.models import Workout
from app.medical.items import get_current_constraints
from app.profile.service import get_or_create_profile

NO_INTENSITY = "none"
NO_TRAINING_STATUS = "no_training"


@dataclass(frozen=True)
class TrainingSignal:
    day: date
    trained: bool
    kinds: tuple[str, ...]
    intensity: str  # none / light / moderate / vigorous
    energy_low: int | None
    energy_high: int | None
    energy_status: str  # ok / missing_body_weight / no_training
    muscles: tuple[str, ...]
    workout_count: int
    conflicts: tuple[Conflict, ...]
    notes: tuple[str, ...]
    disclaimer: str


def _day_inputs(
    db: Session, user_id: uuid.UUID, day: date
) -> tuple[list[Workout], list[WorkoutInput], list[str]]:
    found = workouts.list_workouts(db, user_id, day, day)
    inputs, deleted_notes = summaries.workout_inputs(db, user_id, workouts.workout_details(db, user_id, found))
    return found, inputs, deleted_notes


def training_energy_low(db: Session, user_id: uuid.UUID, day: date, body_weight_kg: float | None) -> int | None:
    """这一天各次训练估算消耗区间下限之和；休息日或没有体重时为 None。

    只读训练记录，不读医嘱、不写数据库，任何日期都可以安全调用（饮食需求用它计入训练消耗）。
    """
    _, inputs, _ = _day_inputs(db, user_id, day)
    if not inputs:
        return None
    return summaries.total_energy(inputs, body_weight_kg)[0]


def training_signal(db: Session, user_id: uuid.UUID, day: date) -> TrainingSignal:
    """完整的训练信号（含与医嘱的冲突）。读取医嘱会按 day 刷新医嘱状态，所以 day 只能是今天。"""
    found, inputs, deleted_notes = _day_inputs(db, user_id, day)
    constraints = get_current_constraints(db, user_id, day, EXERCISE_LIMIT)
    conflicts = find_conflicts(constraints, [(w.id, inp) for w, inp in zip(found, inputs, strict=True)])
    if not inputs:
        return TrainingSignal(
            day, False, (), NO_INTENSITY, None, None, NO_TRAINING_STATUS, (), 0, conflicts, (), ESTIMATE_NOTE
        )
    low, high, status, notes = summaries.total_energy(inputs, get_or_create_profile(db, user_id).weight_kg)
    kinds = tuple(
        kind for kind, present in (("cardio", any(i.cardio for i in inputs)), ("strength", any(i.strength for i in inputs)))
        if present
    )
    intensity = max((peak_intensity(i) for i in inputs), key=INTENSITY_LEVELS.index)
    muscles = sorted({m for i in inputs for block in i.strength for m in block.exercise.primary_muscles})
    return TrainingSignal(
        day, True, kinds, intensity, low, high, status, tuple(muscles), len(inputs), conflicts,
        tuple([*notes, *deleted_notes]), ESTIMATE_NOTE,
    )
