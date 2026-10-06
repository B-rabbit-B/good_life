"""把医嘱、经期、档案与当日摄入组装成约束引擎需要的上下文。"""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.cycle.insights import get_phase_info
from app.medical.items import get_current_constraints
from app.nutrition import meals
from app.nutrition.engine import EvaluationContext, HardConstraint
from app.nutrition.needs import needs_for_profile
from app.profile.capabilities import compute_capabilities
from app.profile.service import get_or_create_profile


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
    return EvaluationContext(
        constraints=constraints,
        cycle_phase=cycle_phase,
        goal=profile.goal,
        needs=needs_for_profile(profile, today),
        day_totals=meals.day_totals(db, user_id, today),
        food_avoidances=tuple(profile.food_avoidances or ()),
        diet_preferences=tuple(profile.diet_preferences or ()),
    )
