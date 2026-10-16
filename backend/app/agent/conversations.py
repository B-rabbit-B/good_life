import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.agent.models import AgentConversation, AgentMessage, AgentOpening
from app.common.ownership import get_owned_or_404, owned_by

ROLES = ("user", "assistant", "tool")
HISTORY_LIMIT = 40


def create_conversation(db: Session, user_id: uuid.UUID, title: str | None = None) -> AgentConversation:
    conversation = AgentConversation(user_id=user_id, title=title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def list_conversations(db: Session, user_id: uuid.UUID) -> list[AgentConversation]:
    query = owned_by(AgentConversation, user_id).order_by(
        AgentConversation.updated_at.desc(), AgentConversation.id.desc()
    )
    return list(db.scalars(query))


def get_conversation(db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID) -> AgentConversation:
    return get_owned_or_404(db, AgentConversation, user_id, conversation_id)


def delete_conversation(db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID) -> None:
    db.delete(get_conversation(db, user_id, conversation_id))  # 消息由外键级联删除
    db.commit()


def clear_all(db: Session, user_id: uuid.UUID) -> None:
    """清空本人全部对话历史：删除全部会话（消息由外键级联删除），再删除全部开场记录，一个事务提交。

    开场问候可能带医嘱内容或经期预测日期，所以与对话一并清掉；删除之后当天可以重新开场。偏好与设置不动。
    """
    db.execute(delete(AgentConversation).where(AgentConversation.user_id == user_id))
    db.execute(delete(AgentOpening).where(AgentOpening.user_id == user_id))
    db.commit()


def append_message(
    db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID, role: str, content: dict[str, Any]
) -> AgentMessage:
    """在会话末尾追加一条消息，并把会话的更新时间推到现在。

    先对会话行加行锁（SELECT ... FOR UPDATE）再取下一个序号：同一会话的并发追加在这里排队，
    序号不会重复；(conversation_id, position) 唯一约束是兜底。
    """
    if role not in ROLES:
        raise ValueError(f"unknown message role: {role}")
    if not isinstance(content, dict):
        raise ValueError("message content must be a dict")
    conversation = db.scalar(
        owned_by(AgentConversation, user_id).where(AgentConversation.id == conversation_id).with_for_update()
    )
    if conversation is None:
        get_owned_or_404(db, AgentConversation, user_id, conversation_id)  # 统一抛 404
        raise AssertionError("unreachable: get_owned_or_404 raises when the conversation is missing")
    last = db.scalar(select(func.max(AgentMessage.position)).where(AgentMessage.conversation_id == conversation_id))
    message = AgentMessage(
        user_id=user_id, conversation_id=conversation_id, position=(last or 0) + 1, role=role, content=content
    )
    db.add(message)
    conversation.updated_at = func.now()
    db.commit()
    db.refresh(message)
    return message


def messages(db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID) -> list[AgentMessage]:
    """会话的全部消息，按 position 从旧到新。"""
    query = owned_by(AgentMessage, user_id).where(AgentMessage.conversation_id == conversation_id)
    return list(db.scalars(query.order_by(AgentMessage.position)))


def history(
    db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID, limit: int = HISTORY_LIMIT
) -> list[AgentMessage]:
    """最近 limit 条消息，按 position 从旧到新（给模型当上下文用）。别人的会话抛 404。"""
    get_conversation(db, user_id, conversation_id)
    query = (
        owned_by(AgentMessage, user_id)
        .where(AgentMessage.conversation_id == conversation_id)
        .order_by(AgentMessage.position.desc())
        .limit(limit)
    )
    return list(reversed(list(db.scalars(query))))
