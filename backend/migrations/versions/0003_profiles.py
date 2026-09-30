"""create profiles and profile_changes

Revision ID: 0003_profiles
Revises: 0002_disclaimer_acceptances
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_profiles"
down_revision = "0002_disclaimer_acceptances"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("gender", sa.String(16)),
        sa.Column("birth_year", sa.Integer()),
        sa.Column("height_cm", sa.Text()),
        sa.Column("weight_kg", sa.Text()),
        sa.Column("activity_level", sa.String(16)),
        sa.Column("goal", sa.String(16)),
        sa.Column("diet_preferences", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("food_avoidances", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("health_conditions", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("cycle_tracking_opt_out", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "profile_changes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changes", sa.Text(), nullable=False),
    )
    op.create_index("ix_profile_changes_user_id", "profile_changes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_profile_changes_user_id", table_name="profile_changes")
    op.drop_table("profile_changes")
    op.drop_table("profiles")
