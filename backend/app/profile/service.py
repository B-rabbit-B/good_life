import uuid
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.common.ownership import owned_by
from app.profile.models import Profile, ProfileChange

# 显式传 null 时，这些字段回到默认值而不是 None。
_NULL_MEANS_DEFAULT: dict[str, Any] = {
    "diet_preferences": [],
    "food_avoidances": [],
    "cycle_tracking_opt_out": False,
}


def get_or_create_profile(db: Session, user_id: uuid.UUID) -> Profile:
    profile = db.scalar(owned_by(Profile, user_id))
    if profile is None:
        # 并发的首次请求可能同时走到这里；主键冲突时什么都不做，再统一查一次。
        db.execute(
            insert(Profile)
            .values(user_id=user_id, diet_preferences=[], food_avoidances=[], cycle_tracking_opt_out=False)
            .on_conflict_do_nothing(index_elements=[Profile.user_id])
        )
        db.commit()
        profile = db.scalar(owned_by(Profile, user_id))
    return profile


def update_profile(db: Session, user_id: uuid.UUID, changes: dict[str, Any]) -> Profile:
    profile = get_or_create_profile(db, user_id)
    diff: dict[str, dict[str, Any]] = {}
    for field, new_value in changes.items():
        if new_value is None and field in _NULL_MEANS_DEFAULT:
            new_value = _NULL_MEANS_DEFAULT[field]
        old_value = getattr(profile, field)
        if old_value != new_value:
            diff[field] = {"old": old_value, "new": new_value}
            setattr(profile, field, new_value)
    if diff:
        db.add(ProfileChange(user_id=user_id, changes=diff))
        db.commit()
        db.refresh(profile)
    return profile


def list_profile_changes(db: Session, user_id: uuid.UUID, limit: int = 50) -> list[ProfileChange]:
    query = (
        owned_by(ProfileChange, user_id)
        .order_by(ProfileChange.changed_at.desc(), ProfileChange.seq.desc())
        .limit(limit)
    )
    return list(db.scalars(query))
