"""create disclaimer_acceptances

Revision ID: 0002_disclaimer_acceptances
Revises: 0001_users
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_disclaimer_acceptances"
down_revision = "0001_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "disclaimer_acceptances",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "version", name="uq_disclaimer_user_version"),
    )
    op.create_index("ix_disclaimer_acceptances_user_id", "disclaimer_acceptances", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_disclaimer_acceptances_user_id", table_name="disclaimer_acceptances")
    op.drop_table("disclaimer_acceptances")
