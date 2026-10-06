"""create nutrition tables

Revision ID: 0008_nutrition
Revises: 0007_medical
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_nutrition"
down_revision = "0007_medical"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meal_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("eaten_on", sa.Date(), nullable=False),
        sa.Column("meal_type", sa.String(16), nullable=False),
        sa.Column("food_id", sa.String(64), nullable=False),
        sa.Column("food_name", sa.String(128), nullable=False),
        sa.Column("grams", sa.Float(), nullable=False),
        sa.Column("energy_kcal", sa.Float()),
        sa.Column("protein_g", sa.Float()),
        sa.Column("fat_g", sa.Float()),
        sa.Column("carbohydrate_g", sa.Float()),
        sa.Column("fiber_g", sa.Float()),
        sa.Column("sodium_mg", sa.Float()),
        sa.Column("iron_mg", sa.Float()),
        sa.Column("calcium_mg", sa.Float()),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_meal_entries_user_id", "meal_entries", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_meal_entries_user_id", table_name="meal_entries")
    op.drop_table("meal_entries")
