"""周汇总与动作趋势：从数据库读出训练，转成 calc 的输入后计算。"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.ownership import owned_by
from app.errors import AppError
from app.fitness import workouts
from app.fitness.calc import (
    ESTIMATE_NOTE,
    MISSING_WEIGHT_NOTE,
    CardioInput,
    SetInput,
    StrengthInput,
    TrendPoint,
    WorkoutInput,
    estimate_workout_energy,
    exercise_trend,
    muscle_volumes,
    strength_volume,
)
from app.fitness.library import Exercise
from app.fitness.models import CardioEntry, StrengthSet, Workout

DAYS_PER_WEEK = 7
DELETED_EXERCISE_MUSCLES = ("full_body",)


@dataclass(frozen=True)
class WeekSummary:
    week_start: date
    week_end: date
    workout_count: int
    training_days: int
    total_volume: float
    muscle_volumes: dict[str, float]
    cardio_minutes: int
    energy_low: int | None
    energy_high: int | None
    energy_status: str
    note: str


def _snapshot_exercise(exercise_id: str, name: str, kind: str) -> Exercise:
    """动作已无法解析（例如自定义动作被删除）时，用记录里保留的名称顶替；没有 MET，肌群按全身。"""
    return Exercise(
        id=exercise_id, name=name, aliases=(), kind=kind, primary_muscles=DELETED_EXERCISE_MUSCLES,
        equipment="other", traits=(), met=None, custom=True,
    )


def _resolve_or_snapshot(
    db: Session, user_id: uuid.UUID, exercise_id: str, name: str, kind: str
) -> tuple[Exercise, bool]:
    try:
        return workouts.resolve_exercise(db, user_id, exercise_id), False
    except AppError as error:
        if error.code != "exercise_not_found":
            raise
        return _snapshot_exercise(exercise_id, name, kind), True


def workout_inputs(
    db: Session, user_id: uuid.UUID, details: list[workouts.WorkoutDetail]
) -> tuple[list[WorkoutInput], list[str]]:
    """转换为 calc 的输入；返回输入与“动作已删除”的说明（按出现顺序、去重）。"""
    cache: dict[str, Exercise] = {}
    deleted_names: dict[str, None] = {}

    def lookup(exercise_id: str, name: str, kind: str) -> Exercise:
        if exercise_id not in cache:
            cache[exercise_id], deleted = _resolve_or_snapshot(db, user_id, exercise_id, name, kind)
            if deleted and kind == "strength":
                deleted_names[name] = None
        return cache[exercise_id]

    inputs = []
    for detail in details:
        workout = detail.workout
        strength = tuple(
            StrengthInput(
                lookup(block.exercise_id, block.exercise_name, "strength"),
                tuple(SetInput(row.weight_kg, row.reps, row.rest_seconds, row.rpe) for row in block.sets),
            )
            for block in detail.strength
        )
        cardio = tuple(
            CardioInput(
                lookup(entry.exercise_id, entry.exercise_name, "cardio"),
                entry.duration_minutes, entry.distance_km, entry.rpe,
            )
            for entry in detail.cardio
        )
        inputs.append(WorkoutInput(workout.performed_on, workout.duration_minutes, workout.rpe, strength, cardio))
    return inputs, [f"“{name}”是已删除的自定义动作，肌群按全身计算。" for name in deleted_names]


def total_energy(
    inputs: list[WorkoutInput], body_weight_kg: float | None
) -> tuple[int | None, int | None, str, list[str]]:
    """各次训练估算区间之和；体重缺失时区间为空并说明。返回（下限、上限、状态、说明句）。"""
    estimates = [estimate_workout_energy(workout, body_weight_kg) for workout in inputs]
    if body_weight_kg is None:
        return None, None, "missing_body_weight", [MISSING_WEIGHT_NOTE]
    extras = dict.fromkeys(
        sentence + "。" for e in estimates for sentence in e.note.removeprefix(ESTIMATE_NOTE).split("。") if sentence
    )
    return sum(e.low for e in estimates), sum(e.high for e in estimates), "ok", [ESTIMATE_NOTE, *extras]


def week_summary(db: Session, user_id: uuid.UUID, week_start: date, body_weight_kg: float | None) -> WeekSummary:
    if week_start.weekday() != 0:
        raise AppError(422, "invalid_week_start", "周汇总的开始日期必须是星期一")
    week_end = week_start + timedelta(days=DAYS_PER_WEEK - 1)
    found = list(reversed(workouts.list_workouts(db, user_id, week_start, week_end)))  # 日期由早到晚
    inputs, deleted_notes = workout_inputs(db, user_id, workouts.workout_details(db, user_id, found))
    low, high, status, notes = total_energy(inputs, body_weight_kg)
    return WeekSummary(
        week_start=week_start,
        week_end=week_end,
        workout_count=len(inputs),
        training_days=len({workout.performed_on for workout in inputs}),
        total_volume=sum(strength_volume(block.sets) for workout in inputs for block in workout.strength),
        muscle_volumes=muscle_volumes(inputs),
        cardio_minutes=sum(c.duration_minutes for workout in inputs for c in workout.cardio),
        energy_low=low,
        energy_high=high,
        energy_status=status,
        note="".join([*notes, *deleted_notes]),
    )


def _used_exercise(db: Session, user_id: uuid.UUID, exercise_id: str) -> Exercise:
    """动作无法解析时：只要用户的训练里用过它，就用记录里的名称顶替；否则 404。"""
    for model, kind in ((StrengthSet, "strength"), (CardioEntry, "cardio")):
        row = db.scalar(owned_by(model, user_id).where(model.exercise_id == exercise_id).order_by(model.id).limit(1))
        if row is not None:
            return _snapshot_exercise(exercise_id, row.exercise_name, kind)
    raise AppError(404, "exercise_not_found", "没有找到这个动作")


def exercise_trend_for(db: Session, user_id: uuid.UUID, exercise_id: str) -> tuple[Exercise, tuple[TrendPoint, ...]]:
    try:
        exercise = workouts.resolve_exercise(db, user_id, exercise_id)
    except AppError as error:
        if error.code != "exercise_not_found":
            raise
        exercise = _used_exercise(db, user_id, exercise_id)
    rows = db.execute(
        select(Workout.performed_on, StrengthSet.weight_kg, StrengthSet.reps)
        .join(Workout, Workout.id == StrengthSet.workout_id)
        .where(StrengthSet.user_id == user_id, Workout.user_id == user_id, StrengthSet.exercise_id == exercise.id)
        .order_by(Workout.performed_on, StrengthSet.workout_id, StrengthSet.position, StrengthSet.set_index)
    ).all()
    points = [TrendPoint(day, weight, weight * reps, reps, 1) for day, weight, reps in rows]
    return exercise, exercise_trend(points)
