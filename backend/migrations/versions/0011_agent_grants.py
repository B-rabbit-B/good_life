"""create agent grants table

Revision ID: 0011_agent_grants
Revises: 0010_fitness
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_agent_grants"
down_revision = "0010_fitness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_grants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("access", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agent_grants_user_id", "agent_grants", ["user_id"])
    op.create_index("uq_agent_grants_token_hash", "agent_grants", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("agent_grants")
