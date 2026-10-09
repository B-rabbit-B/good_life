import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.agent import conversations, preferences
from app.agent import settings as agent_settings
from app.agent.models import AgentPreference
from app.agent.schemas import (
    ConversationCreate,
    ConversationDetailOut,
    ConversationOut,
    MessageOut,
    PreferenceCreate,
    PreferenceOut,
    SettingsOut,
    SettingsUpdate,
)
from app.auth.models import User
from app.db import get_db
from app.disclaimer.deps import require_disclaimer_user

router = APIRouter(prefix="/api/agent", tags=["agent"])

AgentUser = Annotated[User, Depends(require_disclaimer_user)]
DbSession = Annotated[Session, Depends(get_db)]


def _visible_messages(db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID) -> list[MessageOut]:
    """只给前端用户消息和有正文的助手消息；工具消息、只含工具调用的助手消息、provider_state 都不出去。"""
    visible = []
    for message in conversations.messages(db, user_id, conversation_id):
        content = message.content
        text = content.get("text") or ""
        if message.role not in ("user", "assistant"):
            continue
        if message.role == "assistant" and (content.get("tool_calls") or not text):
            continue  # 带工具调用的助手消息整条不给前端，即使带了旁白文字；空正文的也不给
        visible.append(
            MessageOut(
                role=message.role,
                text=text,
                evidence=content.get("evidence") or [],
                flags=content.get("flags") or [],
                created_at=message.created_at,
            )
        )
    return visible


@router.post("/conversations", status_code=201, response_model=ConversationOut)
def create_conversation(body: ConversationCreate, user: AgentUser, db: DbSession) -> ConversationOut:
    return ConversationOut.model_validate(conversations.create_conversation(db, user.id, body.title))


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(user: AgentUser, db: DbSession) -> list[ConversationOut]:
    return [ConversationOut.model_validate(c) for c in conversations.list_conversations(db, user.id)]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(conversation_id: uuid.UUID, user: AgentUser, db: DbSession) -> ConversationDetailOut:
    conversation = conversations.get_conversation(db, user.id, conversation_id)
    return ConversationDetailOut(
        **ConversationOut.model_validate(conversation).model_dump(),
        messages=_visible_messages(db, user.id, conversation_id),
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: uuid.UUID, user: AgentUser, db: DbSession) -> Response:
    conversations.delete_conversation(db, user.id, conversation_id)
    return Response(status_code=204)


@router.get("/preferences", response_model=list[PreferenceOut])
def list_preferences(user: AgentUser, db: DbSession) -> list[AgentPreference]:
    return preferences.list_preferences(db, user.id)


@router.post("/preferences", status_code=201, response_model=PreferenceOut)
def add_preference(body: PreferenceCreate, user: AgentUser, db: DbSession) -> AgentPreference:
    return preferences.add_preference(db, user.id, body.content, "user")


@router.delete("/preferences/{preference_id}", status_code=204)
def delete_preference(preference_id: uuid.UUID, user: AgentUser, db: DbSession) -> Response:
    preferences.delete_preference(db, user.id, preference_id)
    return Response(status_code=204)


@router.get("/settings", response_model=SettingsOut)
def get_settings(user: AgentUser, db: DbSession) -> SettingsOut:
    return SettingsOut.model_validate(agent_settings.get_settings(db, user.id))


@router.put("/settings", response_model=SettingsOut)
def put_settings(body: SettingsUpdate, user: AgentUser, db: DbSession) -> SettingsOut:
    return SettingsOut.model_validate(agent_settings.set_openings_enabled(db, user.id, body.openings_enabled))
