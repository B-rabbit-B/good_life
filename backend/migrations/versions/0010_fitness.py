"""create fitness tables

Revision ID: 0010_fitness
Revises: 0009_meal_entries_day_index
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_fitness"
down_revision = "0009_meal_entries_day_index"
branch_labels = None
depends_on = None


def _user_id() -> sa.Column:
    return sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "custom_exercises",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_id(),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("aliases", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("primary_muscles", postgresql.JSONB(), nullable=False),
        sa.Column("equipment", sa.String(16), nullable=False),
        sa.Column("traits", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("met_light", sa.Float()),
        sa.Column("met_moderate", sa.Float()),
        sa.Column("met_vigorous", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "name", name="uq_custom_exercises_user_name"),
    )
    op.create_index("ix_custom_exercises_user_id", "custom_exercises", ["user_id"])
    op.create_table(
        "workouts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_id(),
        sa.Column("performed_on", sa.Date(), nullable=False),
        sa.Column("duration_minutes", sa.Integer()),
        sa.Column("rpe", sa.Integer()),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workouts_user_id", "workouts", ["user_id"])
    op.create_index("ix_workouts_user_day", "workouts", ["user_id", "performed_on"])
    op.create_table(
        "strength_sets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_id(),
        sa.Column("workout_id", sa.Uuid(), sa.ForeignKey("workouts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exercise_id", sa.String(64), nullable=False),
        sa.Column("exercise_name", sa.String(64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("set_index", sa.Integer(), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=False),
        sa.Column("rest_seconds", sa.Integer()),
        sa.Column("rpe", sa.Integer()),
    )
    op.create_index("ix_strength_sets_user_id", "strength_sets", ["user_id"])
    op.create_index("ix_strength_sets_workout_id", "strength_sets", ["workout_id"])
    op.create_table(
        "cardio_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_id(),
        sa.Column("workout_id", sa.Uuid(), sa.ForeignKey("workouts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exercise_id", sa.String(64), nullable=False),
        sa.Column("exercise_name", sa.String(64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("distance_km", sa.Float()),
        sa.Column("rpe", sa.Integer()),
    )
    op.create_index("ix_cardio_entries_user_id", "cardio_entries", ["user_id"])
    op.create_index("ix_cardio_entries_workout_id", "cardio_entries", ["workout_id"])


def downgrade() -> None:
    op.drop_table("cardio_entries")
    op.drop_table("strength_sets")
    op.drop_table("workouts")
    op.drop_table("custom_exercises")
