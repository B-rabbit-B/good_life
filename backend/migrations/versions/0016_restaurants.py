"""create restaurant settings table

Revision ID: 0016_restaurants
Revises: 0015_photos
"""

import sqlalchemy as sa
from alembic import op

revision = "0016_restaurants"
down_revision = "0015_photos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "restaurant_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("location_consent", sa.String(16), nullable=False, server_default="not_asked"),
        sa.Column("consent_updated_at", sa.DateTime(timezone=True)),
        sa.Column("area", sa.Text()),
        sa.Column("area_saved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_restaurant_settings_user"),
    )
    op.create_index("ix_restaurant_settings_user_id", "restaurant_settings", ["user_id"])


def downgrade() -> None:
    op.drop_table("restaurant_settings")
