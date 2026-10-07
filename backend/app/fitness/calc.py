"""训练量、能量估算与动作趋势：全部是纯函数，同样输入同样输出。"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from math import floor

from app.fitness.library import STRENGTH_MET, Exercise

WORK_SECONDS_PER_SET = 40
DEFAULT_REST_SECONDS = 90
ESTIMATE_RANGE = (0.8, 1.2)
ESTIMATE_NOTE = "能量消耗仅为估算：按代谢当量粗略计算，个体差异很大，给出的是大致区间。"
MISSING_WEIGHT_NOTE = "还不能估算能量消耗：请先在档案里填写体重。能量消耗仅为估算，需要体重才能计算。"
INTENSITY_LEVELS = ("light", "moderate", "vigorous")
LIGHT_MAX_RPE = 4
MODERATE_MAX_RPE = 7


def intensity_from_rpe(rpe: int | None) -> str:
    """主观强度分档：1 至 4 轻度、5 至 7 中等、8 至 10 高强度；未填按中等。"""
    if rpe is None:
        return "moderate"
    if rpe <= LIGHT_MAX_RPE:
        return "light"
    return "moderate" if rpe <= MODERATE_MAX_RPE else "vigorous"


@dataclass(frozen=True)
class SetInput:
    weight_kg: float
    reps: int
    rest_seconds: int | None
    rpe: int | None


@dataclass(frozen=True)
class StrengthInput:
    exercise: Exercise
    sets: tuple[SetInput, ...]


@dataclass(frozen=True)
class CardioInput:
    exercise: Exercise
    duration_minutes: int
    distance_km: float | None
    rpe: int | None


@dataclass(frozen=True)
class WorkoutInput:
    performed_on: date
    duration_minutes: int | None
    rpe: int | None
    strength: tuple[StrengthInput, ...]
    cardio: tuple[CardioInput, ...]


def strength_volume(sets: Iterable[SetInput]) -> float:
    """训练量 = Σ 重量 × 次数；自重动作重量为 0，不计入。"""
    return sum(s.weight_kg * s.reps for s in sets)


def total_reps(sets: Iterable[SetInput]) -> int:
    return sum(s.reps for s in sets)


@dataclass(frozen=True)
class EnergyEstimate:
    kcal: float | None
    low: int | None
    high: int | None
    status: str  # ok / missing_body_weight
    note: str


def _round_half_up(value: float) -> int:
    return floor(value + 0.5)


def _kcal(met: float, body_weight_kg: float, minutes: float) -> float:
    return met * body_weight_kg * minutes / 60


def _strength_minutes(workout: WorkoutInput) -> float:
    """力量部分的分钟数：填了整次时长就用“总时长 − 有氧时长”，否则按每组工作时间加组间休息累加。"""
    if not workout.strength:
        return 0.0
    if workout.duration_minutes is not None:
        cardio_minutes = sum(c.duration_minutes for c in workout.cardio)
        return float(max(workout.duration_minutes - cardio_minutes, 0))
    seconds = sum(
        WORK_SECONDS_PER_SET + (DEFAULT_REST_SECONDS if s.rest_seconds is None else s.rest_seconds)
        for block in workout.strength
        for s in block.sets
    )
    return seconds / 60


def estimate_workout_energy(workout: WorkoutInput, body_weight_kg: float | None) -> EnergyEstimate:
    if body_weight_kg is None:
        return EnergyEstimate(None, None, None, "missing_body_weight", MISSING_WEIGHT_NOTE)
    notes = [ESTIMATE_NOTE]
    total = 0.0
    for cardio in workout.cardio:
        met = cardio.exercise.met
        if met is None:
            notes.append(f"“{cardio.exercise.name}”的代谢当量已无法获得（自定义动作已删除），这一项没有计入估算。")
            continue
        level = intensity_from_rpe(workout.rpe if cardio.rpe is None else cardio.rpe)
        total += _kcal(met[INTENSITY_LEVELS.index(level)], body_weight_kg, cardio.duration_minutes)
    level = intensity_from_rpe(workout.rpe)
    total += _kcal(STRENGTH_MET[level], body_weight_kg, _strength_minutes(workout))
    low, high = (_round_half_up(total * factor) for factor in ESTIMATE_RANGE)
    return EnergyEstimate(total, low, high, "ok", "".join(notes))


def muscle_volumes(workouts: Iterable[WorkoutInput]) -> dict[str, float]:
    """各肌群训练量：动作的训练量完整计入它的每个主要肌群；按肌群名排序。"""
    volumes: dict[str, float] = {}
    for workout in workouts:
        for block in workout.strength:
            volume = strength_volume(block.sets)
            for muscle in block.exercise.primary_muscles:
                volumes[muscle] = volumes.get(muscle, 0) + volume
    return dict(sorted(volumes.items()))


@dataclass(frozen=True)
class TrendPoint:
    day: date
    max_weight_kg: float
    total_volume: float
    total_reps: int
    sets: int


def exercise_trend(points: Sequence[TrendPoint]) -> tuple[TrendPoint, ...]:
    """按日期升序；同一天的多个点合并（最高重量取最大，其余相加）。"""
    merged: dict[date, TrendPoint] = {}
    for point in points:
        old = merged.get(point.day)
        merged[point.day] = point if old is None else TrendPoint(
            point.day,
            max(old.max_weight_kg, point.max_weight_kg),
            old.total_volume + point.total_volume,
            old.total_reps + point.total_reps,
            old.sets + point.sets,
        )
    return tuple(merged[day] for day in sorted(merged))
