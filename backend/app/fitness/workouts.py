"""自定义动作与训练记录。"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import delete, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.ownership import get_owned_or_404, owned_by
from app.errors import AppError
from app.fitness.library import BUILTIN_ID_PREFIX, CUSTOM_ID_PREFIX, Exercise, exercise_from_custom, load_library
from app.fitness.models import CardioEntry, CustomExercise, StrengthSet, Workout
from app.fitness.schemas import WorkoutIn

KIND_LABELS = {"strength": "力量", "cardio": "有氧"}


@dataclass(frozen=True)
class StrengthBlock:
    """同一次训练里同一个动作的全部组（按组序排列）。"""

    exercise_id: str
    exercise_name: str
    position: int
    sets: tuple[StrengthSet, ...]


@dataclass(frozen=True)
class WorkoutDetail:
    workout: Workout
    strength: tuple[StrengthBlock, ...]
    cardio: tuple[CardioEntry, ...]


def _not_found() -> AppError:
    return AppError(404, "exercise_not_found", "没有找到这个动作")


def _custom_row(db: Session, user_id: uuid.UUID, exercise_id: str) -> CustomExercise | None:
    try:
        custom_id = uuid.UUID(exercise_id.removeprefix(CUSTOM_ID_PREFIX))
    except ValueError:
        return None
    return db.scalar(owned_by(CustomExercise, user_id).where(CustomExercise.id == custom_id))


def resolve_exercise(db: Session, user_id: uuid.UUID, exercise_id: str) -> Exercise:
    """内置动作或本人的自定义动作；别人的自定义动作与不存在的动作一样返回 404。"""
    if exercise_id.startswith(BUILTIN_ID_PREFIX):
        exercise = load_library().get(exercise_id)
    elif exercise_id.startswith(CUSTOM_ID_PREFIX):
        row = _custom_row(db, user_id, exercise_id)
        exercise = exercise_from_custom(row) if row else None
    else:
        exercise = None
    if exercise is None:
        raise _not_found()
    return exercise


def user_custom_exercises(db: Session, user_id: uuid.UUID) -> tuple[Exercise, ...]:
    rows = db.scalars(owned_by(CustomExercise, user_id).order_by(CustomExercise.name, CustomExercise.id)).all()
    return tuple(exercise_from_custom(row) for row in rows)


def create_custom_exercise(db: Session, user_id: uuid.UUID, fields: dict[str, Any]) -> Exercise:
    row = CustomExercise(user_id=user_id, **fields)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:  # (user_id, name) 唯一约束
        db.rollback()
        raise AppError(409, "custom_exercise_exists", "已经有同名的自定义动作") from None
    db.refresh(row)
    return exercise_from_custom(row)


def delete_custom_exercise(db: Session, user_id: uuid.UUID, exercise_id: str) -> None:
    """删除后，历史训练记录里的动作名称快照仍然保留。"""
    row = _custom_row(db, user_id, exercise_id) if exercise_id.startswith(CUSTOM_ID_PREFIX) else None
    if row is None:
        raise _not_found()
    db.delete(row)
    db.commit()


def _check_payload(db: Session, user_id: uuid.UUID, payload: WorkoutIn, today: date) -> dict[str, Exercise]:
    if payload.performed_on > today:
        raise AppError(422, "workout_in_future", "不能记录未来日期的训练")
    if not payload.strength and not payload.cardio:
        raise AppError(422, "empty_workout", "请至少记录一个力量动作或有氧项目")
    exercises: dict[str, Exercise] = {}
    for kind, items in (("strength", payload.strength), ("cardio", payload.cardio)):
        for item in items:
            exercise = exercises.get(item.exercise_id) or resolve_exercise(db, user_id, item.exercise_id)
            if exercise.kind != kind:
                raise AppError(
                    422,
                    "exercise_kind_mismatch",
                    f"“{exercise.name}”是{KIND_LABELS[exercise.kind]}动作，不能记在{KIND_LABELS[kind]}训练里",
                )
            exercises[item.exercise_id] = exercise
    return exercises


def _add_children(
    db: Session, user_id: uuid.UUID, workout: Workout, payload: WorkoutIn, exercises: dict[str, Exercise]
) -> None:
    for position, item in enumerate(payload.strength, start=1):
        exercise = exercises[item.exercise_id]
        for set_index, item_set in enumerate(item.sets, start=1):
            db.add(StrengthSet(
                user_id=user_id, workout_id=workout.id, exercise_id=exercise.id, exercise_name=exercise.name,
                position=position, set_index=set_index, weight_kg=item_set.weight_kg, reps=item_set.reps,
                rest_seconds=item_set.rest_seconds, rpe=item_set.rpe,
            ))
    for position, cardio in enumerate(payload.cardio, start=1):
        exercise = exercises[cardio.exercise_id]
        db.add(CardioEntry(
            user_id=user_id, workout_id=workout.id, exercise_id=exercise.id, exercise_name=exercise.name,
            position=position, duration_minutes=cardio.duration_minutes, distance_km=cardio.distance_km,
            rpe=cardio.rpe,
        ))


def create_workout(db: Session, user_id: uuid.UUID, payload: WorkoutIn, today: date) -> Workout:
    exercises = _check_payload(db, user_id, payload, today)
    workout = Workout(
        user_id=user_id, performed_on=payload.performed_on, duration_minutes=payload.duration_minutes,
        rpe=payload.rpe, note=payload.note,
    )
    db.add(workout)
    db.flush()
    _add_children(db, user_id, workout, payload, exercises)
    db.commit()
    db.refresh(workout)
    return workout


def replace_workout(
    db: Session, user_id: uuid.UUID, workout_id: uuid.UUID, payload: WorkoutIn, today: date
) -> Workout:
    """整条替换：先校验新内容，再删掉旧的组与有氧条目，写入新的。"""
    workout = get_owned_or_404(db, Workout, user_id, workout_id)
    exercises = _check_payload(db, user_id, payload, today)
    db.execute(delete(StrengthSet).where(StrengthSet.workout_id == workout.id))
    db.execute(delete(CardioEntry).where(CardioEntry.workout_id == workout.id))
    workout.performed_on = payload.performed_on
    workout.duration_minutes = payload.duration_minutes
    workout.rpe = payload.rpe
    workout.note = payload.note
    workout.updated_at = func.now()
    _add_children(db, user_id, workout, payload, exercises)
    db.commit()
    db.refresh(workout)
    return workout


def delete_workout(db: Session, user_id: uuid.UUID, workout_id: uuid.UUID) -> None:
    db.delete(get_owned_or_404(db, Workout, user_id, workout_id))  # 组与有氧条目由外键级联删除
    db.commit()


def get_workout(db: Session, user_id: uuid.UUID, workout_id: uuid.UUID) -> Workout:
    return get_owned_or_404(db, Workout, user_id, workout_id)


def list_workouts(db: Session, user_id: uuid.UUID, start: date, end: date) -> list[Workout]:
    """区间内（含两端）的训练，日期新的在前。"""
    query = owned_by(Workout, user_id).where(Workout.performed_on >= start, Workout.performed_on <= end)
    return list(db.scalars(query.order_by(Workout.performed_on.desc(), Workout.created_at.desc(), Workout.id)))


def workout_details(db: Session, user_id: uuid.UUID, workouts: Sequence[Workout]) -> list[WorkoutDetail]:
    ids = [workout.id for workout in workouts]
    sets_by_workout: dict[uuid.UUID, list[StrengthSet]] = {}
    cardio_by_workout: dict[uuid.UUID, list[CardioEntry]] = {}
    if ids:
        sets = db.scalars(
            owned_by(StrengthSet, user_id)
            .where(StrengthSet.workout_id.in_(ids))
            .order_by(StrengthSet.position, StrengthSet.set_index)
        )
        for row in sets:
            sets_by_workout.setdefault(row.workout_id, []).append(row)
        cardio = db.scalars(
            owned_by(CardioEntry, user_id).where(CardioEntry.workout_id.in_(ids)).order_by(CardioEntry.position)
        )
        for entry in cardio:
            cardio_by_workout.setdefault(entry.workout_id, []).append(entry)
    details = []
    for workout in workouts:
        blocks: dict[int, list[StrengthSet]] = {}
        for row in sets_by_workout.get(workout.id, []):
            blocks.setdefault(row.position, []).append(row)
        strength = tuple(
            StrengthBlock(rows[0].exercise_id, rows[0].exercise_name, position, tuple(rows))
            for position, rows in sorted(blocks.items())
        )
        details.append(WorkoutDetail(workout, strength, tuple(cardio_by_workout.get(workout.id, []))))
    return details


def workout_detail(db: Session, user_id: uuid.UUID, workout: Workout) -> WorkoutDetail:
    return workout_details(db, user_id, [workout])[0]
