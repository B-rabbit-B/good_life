"""encrypt cycle_settings.status

Revision ID: 0006_cycle_status_encrypt
Revises: 0005_cycle
"""

from collections.abc import Callable

import sqlalchemy as sa
from alembic import op

from app.security.crypto import decrypt_value, encrypt_value

revision = "0006_cycle_status_encrypt"
down_revision = "0005_cycle"
branch_labels = None
depends_on = None

SELECT_ROWS = sa.text("SELECT user_id, status FROM cycle_settings")
UPDATE_ROW = sa.text("UPDATE cycle_settings SET status = :status WHERE user_id = :user_id")


def _convert(convert: Callable[[str], str]) -> None:
    conn = op.get_bind()
    for user_id, status in conn.execute(SELECT_ROWS).all():
        conn.execute(UPDATE_ROW, {"status": convert(status), "user_id": user_id})


def upgrade() -> None:
    op.alter_column(
        "cycle_settings",
        "status",
        type_=sa.Text(),
        existing_type=sa.String(16),
        existing_nullable=False,
        server_default=None,
    )
    _convert(encrypt_value)


def downgrade() -> None:
    _convert(decrypt_value)
    op.alter_column(
        "cycle_settings",
        "status",
        type_=sa.String(16),
        existing_type=sa.Text(),
        existing_nullable=False,
        server_default=sa.text("'tracking'"),
    )
