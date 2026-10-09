import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.agent.models import AgentSettings
from app.common.ownership import owned_by


def get_settings(db: Session, user_id: uuid.UUID) -> AgentSettings:
    settings = db.scalar(owned_by(AgentSettings, user_id))
    if settings is None:
        # 并发的首次请求撞上唯一约束时什么都不做，再查一次。
        db.execute(
            insert(AgentSettings)
            .values(id=uuid.uuid4(), user_id=user_id, openings_enabled=True)
            .on_conflict_do_nothing(index_elements=[AgentSettings.user_id])
        )
        db.commit()
        settings = db.scalar(owned_by(AgentSettings, user_id))
    return settings


def set_openings_enabled(db: Session, user_id: uuid.UUID, enabled: bool) -> AgentSettings:
    settings = get_settings(db, user_id)
    settings.openings_enabled = enabled
    db.commit()
    db.refresh(settings)
    return settings
