"""create sdk call audits table

Revision ID: 0012_sdk_call_audits
Revises: 0011_agent_grants
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_sdk_call_audits"
down_revision = "0011_agent_grants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sdk_call_audits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("grant_id", sa.Uuid(), sa.ForeignKey("agent_grants.id", ondelete="SET NULL")),
        sa.Column("credential_kind", sa.String(16), nullable=False),
        sa.Column("client_name", sa.String(64), nullable=False),
        sa.Column("capability", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(8), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sdk_call_audits_user_id", "sdk_call_audits", ["user_id"])


def downgrade() -> None:
    op.drop_table("sdk_call_audits")
