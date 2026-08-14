"""h1.3 llm_runs user_id kind

Revision ID: bad790d98ddf
Revises: cc51bd1b6bf1
Create Date: 2026-08-14

HARDENING H1.3 — per-user / per-kind LLM cost metering:
  llm_runs.user_id  → who paid (or NULL for anonymous)
  llm_runs.kind     → report | chat | transit | article
"""
from alembic import op
import sqlalchemy as sa

revision = "bad790d98ddf"
down_revision = "cc51bd1b6bf1"


def upgrade() -> None:
    op.add_column("llm_runs", sa.Column("user_id", sa.String(), nullable=True))
    op.add_column("llm_runs", sa.Column("kind", sa.String(), nullable=False,
                                        server_default="report"))
    op.create_index("ix_llm_runs_user_id", "llm_runs", ["user_id"])
    op.create_index("ix_llm_runs_kind", "llm_runs", ["kind"])
    op.create_index("ix_llm_runs_created_kind", "llm_runs", ["created_at", "kind"])


def downgrade() -> None:
    op.drop_index("ix_llm_runs_created_kind", table_name="llm_runs")
    op.drop_index("ix_llm_runs_kind", table_name="llm_runs")
    op.drop_index("ix_llm_runs_user_id", table_name="llm_runs")
    op.drop_column("llm_runs", "kind")
    op.drop_column("llm_runs", "user_id")
