"""把医嘱、经期、档案、当天训练与当日摄入组装成约束引擎需要的上下文。"""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.cycle.insights import get_phase_info
from app.fitness.signals import TrainingSignal, training_energy_low, training_signal
from app.medical.items import get_current_constraints
from app.nutrition import meals
from app.nutrition.engine import EvaluationContext, HardConstraint, TrainingConflict, TrainingContext
from app.nutrition.needs import Needs, needs_for_profile, with_training_bonus
from app.profile.capabilities import compute_capabilities
from app.profile.models import Profile
from app.profile.service import get_or_create_profile


def _training_signal(db: Session, user_id: uuid.UUID, today: date, profile: Profile) -> TrainingSignal | None:
    """只在开放健身模块时读取今天的训练信号（含冲突，会按今天读取医嘱）。"""
    if not compute_capabilities(profile)["fitness"]:
        return None
    return training_signal(db, user_id, today)


def _with_training(needs: Needs, signal: TrainingSignal | None) -> Needs:
    """有训练且估算可用时，把估算消耗的下限加进需求；休息日、没有体重无法估算时原样返回。"""
    if signal is None:
        return needs
    return with_training_bonus(needs, signal.energy_low or 0)


def _training_context(signal: TrainingSignal | None) -> TrainingContext | None:
    if signal is None:
        return None
    conflicts = tuple(
        TrainingConflict(str(c.item_id), c.content, c.subject, c.level, c.message) for c in signal.conflicts
    )
    return TrainingContext(signal.trained, signal.kinds, signal.intensity, signal.energy_low, conflicts)


def needs_for_day(db: Session, user_id: uuid.UUID, day: date, today: date) -> Needs:
    """某一天的需求：按档案估算，再加上这一天训练估算消耗的下限。

    只读训练记录与档案，不读医嘱，没有副作用；今天以后的日期不读训练，直接给按档案估算的需求。
    """
    profile = get_or_create_profile(db, user_id)
    needs = needs_for_profile(profile, today)
    if day > today or not compute_capabilities(profile)["fitness"]:
        return needs
    return with_training_bonus(needs, training_energy_low(db, user_id, day, profile.weight_kg) or 0)


def build_context(db: Session, user_id: uuid.UUID, today: date) -> EvaluationContext:
    profile = get_or_create_profile(db, user_id)
    capabilities = compute_capabilities(profile)
    constraints: tuple[HardConstraint, ...] = ()
    if capabilities["medical"]:
        constraints = tuple(
            HardConstraint(
                item_id=str(constraint.item_id),
                category=constraint.category,
                content=constraint.content,
                subjects=tuple(constraint.subjects),
                needs_review=constraint.needs_review,
            )
            for constraint in get_current_constraints(db, user_id, today)
        )
    cycle_phase = None
    if capabilities["cycle"]:
        phase = get_phase_info(db, user_id, today, today).phase
        cycle_phase = phase if phase != "unknown" else None
    signal = _training_signal(db, user_id, today, profile)
    return EvaluationContext(
        constraints=constraints,
        cycle_phase=cycle_phase,
        goal=profile.goal,
        needs=_with_training(needs_for_profile(profile, today), signal),
        day_totals=meals.day_totals(db, user_id, today),
        food_avoidances=tuple(profile.food_avoidances or ()),
        diet_preferences=tuple(profile.diet_preferences or ()),
        training=_training_context(signal),
    )
