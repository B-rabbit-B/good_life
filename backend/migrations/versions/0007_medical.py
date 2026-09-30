"""create medical tables

Revision ID: 0007_medical
Revises: 0006_cycle_status_encrypt
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_medical"
down_revision = "0006_cycle_status_encrypt"
branch_labels = None
depends_on = None


def _user_fk() -> sa.Column:
    return sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "medical_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_fk(),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("extractor", sa.String(32), nullable=False),
        sa.Column("extraction_notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_medical_orders_user_id", "medical_orders", ["user_id"])

    op.create_table(
        "medical_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_fk(),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("medical_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_medical_evidence_user_id", "medical_evidence", ["user_id"])
    op.create_index("ix_medical_evidence_order_id", "medical_evidence", ["order_id"])

    op.create_table(
        "medical_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_fk(),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("medical_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("confidence", sa.String(8)),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("subjects", sa.Text(), nullable=False),
        sa.Column("source_excerpt", sa.Text()),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        sa.Column("review_date", sa.Date()),
        sa.Column("missing_fields", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("notes", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("resolution_proposed_at", sa.DateTime(timezone=True)),
        sa.Column("resolution_reason", sa.Text()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_medical_items_user_id", "medical_items", ["user_id"])
    op.create_index("ix_medical_items_order_id", "medical_items", ["order_id"])

    op.create_table(
        "medical_item_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_fk(),
        sa.Column("item_id", sa.Uuid(), sa.ForeignKey("medical_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("from_status", sa.String(24)),
        sa.Column("to_status", sa.String(24), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("detail", sa.Text()),
    )
    op.create_index("ix_medical_item_events_user_id", "medical_item_events", ["user_id"])
    op.create_index("ix_medical_item_events_item_id", "medical_item_events", ["item_id"])


def downgrade() -> None:
    op.drop_table("medical_item_events")
    op.drop_table("medical_items")
    op.drop_table("medical_evidence")
    op.drop_table("medical_orders")
