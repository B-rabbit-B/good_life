"""create agent conversation, message, preference, opening and settings tables

Revision ID: 0014_agent
Revises: 0013_llm
"""

import sqlalchemy as sa
from alembic import op

revision = "0014_agent"
down_revision = "0013_llm"
branch_labels = None
depends_on = None


def _user_id() -> sa.Column:
    return sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def _updated_at() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "agent_conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_id(),
        sa.Column("title", sa.Text()),
        _created_at(),
        _updated_at(),
    )
    op.create_index("ix_agent_conversations_user_id", "agent_conversations", ["user_id"])
    op.create_table(
        "agent_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_id(),
        sa.Column(
            "conversation_id", sa.Uuid(), sa.ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        _created_at(),
        sa.UniqueConstraint("conversation_id", "position", name="uq_agent_messages_conversation_position"),
    )
    op.create_index("ix_agent_messages_user_id", "agent_messages", ["user_id"])
    op.create_index("ix_agent_messages_conversation_id", "agent_messages", ["conversation_id"])
    op.create_table(
        "agent_preferences",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_id(),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        _created_at(),
    )
    op.create_index("ix_agent_preferences_user_id", "agent_preferences", ["user_id"])
    op.create_table(
        "agent_openings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_id(),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        _created_at(),
        sa.UniqueConstraint("user_id", "day", "kind", name="uq_agent_openings_user_day_kind"),
    )
    op.create_index("ix_agent_openings_user_id", "agent_openings", ["user_id"])
    op.create_table(
        "agent_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_id(),
        sa.Column("openings_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        _updated_at(),
        sa.UniqueConstraint("user_id", name="uq_agent_settings_user"),
    )
    op.create_index("ix_agent_settings_user_id", "agent_settings", ["user_id"])


def downgrade() -> None:
    op.drop_table("agent_settings")
    op.drop_table("agent_openings")
    op.drop_table("agent_preferences")
    op.drop_table("agent_messages")
    op.drop_table("agent_conversations")
