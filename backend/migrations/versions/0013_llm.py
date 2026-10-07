"""create llm provider, model and assignment tables

Revision ID: 0013_llm
Revises: 0012_sdk_call_audits
"""

import sqlalchemy as sa
from alembic import op

revision = "0013_llm"
down_revision = "0012_sdk_call_audits"
branch_labels = None
depends_on = None


def _user_id() -> sa.Column:
    return sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "llm_providers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_id(),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("base_url", sa.String(300), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=False),
        sa.Column("key_hint", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "name", name="uq_llm_providers_user_name"),
    )
    op.create_index("ix_llm_providers_user_id", "llm_providers", ["user_id"])
    op.create_table(
        "llm_models",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_id(),
        sa.Column("provider_id", sa.Uuid(), sa.ForeignKey("llm_providers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_id", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(200)),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("vision_override", sa.Boolean()),
        sa.Column("tools_override", sa.Boolean()),
        sa.Column("chat_override", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider_id", "model_id", name="uq_llm_models_provider_model"),
    )
    op.create_index("ix_llm_models_user_id", "llm_models", ["user_id"])
    op.create_index("ix_llm_models_provider_id", "llm_models", ["provider_id"])
    op.create_table(
        "llm_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_id(),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("llm_model_id", sa.Uuid(), sa.ForeignKey("llm_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "purpose", name="uq_llm_assignments_user_purpose"),
    )
    op.create_index("ix_llm_assignments_user_id", "llm_assignments", ["user_id"])


def downgrade() -> None:
    op.drop_table("llm_assignments")
    op.drop_table("llm_models")
    op.drop_table("llm_providers")
