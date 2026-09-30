"""add profile_changes.seq for stable ordering

Revision ID: 0004_profile_changes_seq
Revises: 0003_profiles
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_profile_changes_seq"
down_revision = "0003_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profile_changes",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("profile_changes", "seq")
