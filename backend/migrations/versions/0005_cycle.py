"""create cycle tables

Revision ID: 0005_cycle
Revises: 0004_profile_changes_seq
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_cycle"
down_revision = "0004_profile_changes_seq"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cycle_periods",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "start_date", name="uq_cycle_periods_user_start"),
    )
    op.create_index("ix_cycle_periods_user_id", "cycle_periods", ["user_id"])
    op.create_table(
        "cycle_day_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "log_date", name="uq_cycle_day_logs_user_date"),
    )
    op.create_index("ix_cycle_day_logs_user_id", "cycle_day_logs", ["user_id"])
    op.create_table(
        "cycle_settings",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'tracking'")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("cycle_settings")
    op.drop_index("ix_cycle_day_logs_user_id", table_name="cycle_day_logs")
    op.drop_table("cycle_day_logs")
    op.drop_index("ix_cycle_periods_user_id", table_name="cycle_periods")
    op.drop_table("cycle_periods")
