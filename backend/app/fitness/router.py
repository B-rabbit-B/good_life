import uuid
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.clock import get_today
from app.db import get_db
from app.errors import AppError
from app.fitness import workouts
from app.fitness.deps import require_fitness_user
from app.fitness.library import MET_SOURCE_NOTE, STRENGTH_MET, Exercise, load_library
from app.fitness.models import Workout
from app.fitness.schemas import (
    CardioOut,
    CustomExerciseIn,
    ExerciseDetailOut,
    ExerciseSearchOut,
    ExerciseSummaryOut,
    MetOut,
    SetOut,
    StrengthBlockOut,
    WorkoutIn,
    WorkoutOut,
)

router = APIRouter(prefix="/api/fitness", tags=["fitness"])

FitnessUser = Annotated[User, Depends(require_fitness_user)]
DbSession = Annotated[Session, Depends(get_db)]
Today = Annotated[date, Depends(get_today)]
EXACT_MATCH_TYPES = ("exact_name", "exact_alias")
PARTIAL_MATCH_MESSAGE = "没有完全一致的动作，下面是名称相近的候选，请确认是否是你要找的"
CUSTOM_MET_NOTE = "能量代谢当量（MET）由你自行填写，仅用于粗略估算能量消耗，个体差异较大。"
DEFAULT_RANGE_DAYS = 7
MAX_RANGE_DAYS = 366


def _exercise_detail(exercise: Exercise) -> ExerciseDetailOut:
    if exercise.met is None:
        met, note = MetOut(**STRENGTH_MET), MET_SOURCE_NOTE
    else:
        met = MetOut(light=exercise.met[0], moderate=exercise.met[1], vigorous=exercise.met[2])
        note = CUSTOM_MET_NOTE if exercise.custom else MET_SOURCE_NOTE
    return ExerciseDetailOut(
        id=exercise.id,
        name=exercise.name,
        aliases=list(exercise.aliases),
        kind=exercise.kind,
        primary_muscles=list(exercise.primary_muscles),
        equipment=exercise.equipment,
        traits=list(exercise.traits),
        custom=exercise.custom,
        met=met,
        met_source_note=note,
    )


def _workout_out(detail: workouts.WorkoutDetail) -> WorkoutOut:
    workout = detail.workout
    return WorkoutOut(
        id=workout.id,
        performed_on=workout.performed_on,
        duration_minutes=workout.duration_minutes,
        rpe=workout.rpe,
        note=workout.note,
        strength=[
            StrengthBlockOut(
                exercise_id=block.exercise_id,
                exercise_name=block.exercise_name,
                position=block.position,
                sets=[
                    SetOut(
                        set_index=row.set_index, weight_kg=row.weight_kg, reps=row.reps,
                        rest_seconds=row.rest_seconds, rpe=row.rpe,
                    )
                    for row in block.sets
                ],
            )
            for block in detail.strength
        ],
        cardio=[
            CardioOut(
                exercise_id=entry.exercise_id, exercise_name=entry.exercise_name, position=entry.position,
                duration_minutes=entry.duration_minutes, distance_km=entry.distance_km, rpe=entry.rpe,
            )
            for entry in detail.cardio
        ],
        created_at=workout.created_at,
        updated_at=workout.updated_at,
    )


def _one_workout(db: Session, user: User, workout: Workout) -> WorkoutOut:
    return _workout_out(workouts.workout_detail(db, user.id, workout))


@router.get("/exercises/search", response_model=ExerciseSearchOut)
def search_exercises(
    user: FitnessUser, db: DbSession, q: Annotated[str, Query(min_length=1, max_length=50)]
) -> ExerciseSearchOut:
    hits = load_library().search(q, extra=workouts.user_custom_exercises(db, user.id))
    results = [
        ExerciseSummaryOut(
            id=hit.exercise.id,
            name=hit.exercise.name,
            kind=hit.exercise.kind,
            primary_muscles=list(hit.exercise.primary_muscles),
            equipment=hit.exercise.equipment,
            custom=hit.exercise.custom,
            match=hit.match,
        )
        for hit in hits
    ]
    exact = bool(results) and results[0].match in EXACT_MATCH_TYPES
    if not results:
        message = f"未找到与“{q}”匹配的动作，可以新增自定义动作"
    elif not exact:
        message = PARTIAL_MATCH_MESSAGE
    else:
        message = ""
    return ExerciseSearchOut(query=q, found=bool(results), exact=exact, results=results, message=message)


@router.get("/exercises/custom", response_model=list[ExerciseDetailOut])
def list_custom_exercises(user: FitnessUser, db: DbSession) -> list[ExerciseDetailOut]:
    return [_exercise_detail(exercise) for exercise in workouts.user_custom_exercises(db, user.id)]


@router.get("/exercises/{exercise_id}", response_model=ExerciseDetailOut)
def get_exercise(exercise_id: str, user: FitnessUser, db: DbSession) -> ExerciseDetailOut:
    return _exercise_detail(workouts.resolve_exercise(db, user.id, exercise_id))


@router.post("/exercises", status_code=201, response_model=ExerciseDetailOut)
def create_custom_exercise(body: CustomExerciseIn, user: FitnessUser, db: DbSession) -> ExerciseDetailOut:
    return _exercise_detail(workouts.create_custom_exercise(db, user.id, body.model_dump()))


@router.delete("/exercises/custom/{exercise_id}", status_code=204)
def delete_custom_exercise(exercise_id: str, user: FitnessUser, db: DbSession) -> Response:
    workouts.delete_custom_exercise(db, user.id, exercise_id)
    return Response(status_code=204)


@router.post("/workouts", status_code=201, response_model=WorkoutOut)
def create_workout(body: WorkoutIn, user: FitnessUser, db: DbSession, today: Today) -> WorkoutOut:
    return _one_workout(db, user, workouts.create_workout(db, user.id, body, today))


@router.get("/workouts", response_model=list[WorkoutOut])
def list_workouts(
    user: FitnessUser, db: DbSession, today: Today, start: date | None = None, end: date | None = None
) -> list[WorkoutOut]:
    end = end or today
    start = start or end - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    if start > end or (end - start).days >= MAX_RANGE_DAYS:
        raise AppError(422, "invalid_range", f"日期范围不合法：开始日期不能晚于结束日期，且最多 {MAX_RANGE_DAYS} 天")
    found = workouts.list_workouts(db, user.id, start, end)
    return [_workout_out(detail) for detail in workouts.workout_details(db, user.id, found)]


@router.get("/workouts/{workout_id}", response_model=WorkoutOut)
def get_workout(workout_id: uuid.UUID, user: FitnessUser, db: DbSession) -> WorkoutOut:
    return _one_workout(db, user, workouts.get_workout(db, user.id, workout_id))


@router.put("/workouts/{workout_id}", response_model=WorkoutOut)
def replace_workout(
    workout_id: uuid.UUID, body: WorkoutIn, user: FitnessUser, db: DbSession, today: Today
) -> WorkoutOut:
    return _one_workout(db, user, workouts.replace_workout(db, user.id, workout_id, body, today))


@router.delete("/workouts/{workout_id}", status_code=204)
def delete_workout(workout_id: uuid.UUID, user: FitnessUser, db: DbSession) -> Response:
    workouts.delete_workout(db, user.id, workout_id)
    return Response(status_code=204)
