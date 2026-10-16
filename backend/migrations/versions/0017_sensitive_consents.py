"""create sensitive consents table

Revision ID: 0017_sensitive_consents
Revises: 0016_restaurants
"""

import sqlalchemy as sa
from alembic import op

revision = "0017_sensitive_consents"
down_revision = "0016_restaurants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sensitive_consents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("text_version", sa.String(32), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "kind", name="uq_sensitive_consents_user_kind"),
    )
    op.create_index("ix_sensitive_consents_user_id", "sensitive_consents", ["user_id"])


def downgrade() -> None:
    op.drop_table("sensitive_consents")
