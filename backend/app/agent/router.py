import json
import uuid
from collections.abc import Iterator
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agent import conversations, loop, openings, preferences
from app.agent import settings as agent_settings
from app.agent.models import AgentPreference
from app.agent.schemas import (
    ConversationCreate,
    ConversationDetailOut,
    ConversationOut,
    MessageCreate,
    MessageOut,
    OpeningOut,
    OpeningResponse,
    PreferenceCreate,
    PreferenceOut,
    SettingsOut,
    SettingsUpdate,
    TurnOut,
)
from app.auth.models import User
from app.common.clock import get_today
from app.db import get_db
from app.disclaimer.deps import require_disclaimer_user
from app.errors import AppError
from app.llm.service import AdapterFactory, get_adapter_factory

router = APIRouter(prefix="/api/agent", tags=["agent"])

AgentUser = Annotated[User, Depends(require_disclaimer_user)]
DbSession = Annotated[Session, Depends(get_db)]
Today = Annotated[date, Depends(get_today)]
Factory = Annotated[AdapterFactory, Depends(get_adapter_factory)]

SSE_CHUNK_CHARS = 20


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
                id=message.id,
                role=message.role,
                text=text,
                evidence=content.get("evidence") or "",
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


@router.delete("/conversations", status_code=204)
def clear_conversations(user: AgentUser, db: DbSession) -> Response:
    """清空全部对话历史，开场问候一并清掉。"""
    conversations.clear_all(db, user.id)
    return Response(status_code=204)


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


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _stream_turn(turn: TurnOut) -> Iterator[str]:
    """回答已经通过输出检查，再按段（每段约 20 个字）推送，最后推送 done。"""
    for start in range(0, len(turn.text), SSE_CHUNK_CHARS):
        yield _sse("delta", {"text": turn.text[start:start + SSE_CHUNK_CHARS]})
    yield _sse("done", turn.model_dump(mode="json", exclude={"text"}))


@router.post("/conversations/{conversation_id}/messages", response_model=TurnOut)
def post_message(
    conversation_id: uuid.UUID, body: MessageCreate, user: AgentUser, db: DbSession, today: Today, factory: Factory
) -> TurnOut | StreamingResponse:
    """发一条消息并得到助手的回答。stream 为真时返回 text/event-stream：若干 delta，最后 done 或 error。

    先确认会话属于本人，然后结束自己的读事务再跑一轮（run_turn 用自己的短会话，调用模型期间不占事务）。
    """
    conversations.get_conversation(db, user.id, conversation_id)
    user_id = user.id
    db.close()
    try:
        result = loop.run_turn(user_id, conversation_id, body.text, today=today, factory=factory)
    except AppError as err:
        if not body.stream:
            raise
        error = _sse("error", {"code": err.code, "message": err.message})
        return StreamingResponse(iter([error]), status_code=err.status_code, media_type="text/event-stream")
    turn = TurnOut(message_id=result.message_id, text=result.text, evidence=result.evidence,
                   flags=list(result.flags), tools_used=list(result.tools_used))
    if body.stream:
        return StreamingResponse(_stream_turn(turn), media_type="text/event-stream")
    return turn


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


@router.get("/opening", response_model=OpeningResponse)
def get_opening(user: AgentUser, db: DbSession, today: Today, factory: Factory) -> OpeningResponse:
    """今天最该问的一个问题；今天没有该问的、已问完或设置关闭时是 null。pick_opening 在调用模型之前结束读事务。"""
    opening = openings.pick_opening(db, user.id, today, factory=factory)
    return OpeningResponse(opening=None if opening is None else OpeningOut.model_validate(opening))


@router.post("/opening/{opening_id}/decline", status_code=204)
def decline_opening(opening_id: uuid.UUID, user: AgentUser, db: DbSession) -> Response:
    openings.decline(db, user.id, opening_id)
    return Response(status_code=204)


@router.post("/opening/{opening_id}/answer", status_code=204)
def answer_opening(opening_id: uuid.UUID, user: AgentUser, db: DbSession) -> Response:
    openings.answer(db, user.id, opening_id)
    return Response(status_code=204)
