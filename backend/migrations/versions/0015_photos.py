"""create photo recognition table

Revision ID: 0015_photos
Revises: 0014_agent
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015_photos"
down_revision = "0014_agent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "photo_recognitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("items", sa.Text(), nullable=False),
        sa.Column("image", sa.LargeBinary()),
        sa.Column("image_kept", sa.Boolean(), nullable=False),
        sa.Column("model_id", sa.String(200), nullable=False),
        sa.Column("eaten_on", sa.Date()),
        sa.Column("meal_type", sa.String(16)),
        sa.Column("meal_entry_ids", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_photo_recognitions_user_id", "photo_recognitions", ["user_id"])
    op.create_index("ix_photo_recognitions_user_created", "photo_recognitions", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("photo_recognitions")
