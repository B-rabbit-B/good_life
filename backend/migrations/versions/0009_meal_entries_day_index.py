"""index meal entries by user and day

Revision ID: 0009_meal_entries_day_index
Revises: 0008_nutrition
"""

from alembic import op

revision = "0009_meal_entries_day_index"
down_revision = "0008_nutrition"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_meal_entries_user_day", "meal_entries", ["user_id", "eaten_on"])


def downgrade() -> None:
    op.drop_index("ix_meal_entries_user_day", table_name="meal_entries")
