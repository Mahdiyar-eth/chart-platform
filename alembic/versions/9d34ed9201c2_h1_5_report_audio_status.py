"""h1.5 report audio status

Revision ID: 9d34ed9201c2
Revises: bad790d98ddf
Create Date: 2026-08-14

HARDENING H1.5 — async (queued) TTS for report audio. edge-tts used to run
inline in the request (up to ~1 min for a full report); now a worker job
generates the audio and the API surfaces generating/ready/failed.

  reports.audio_status  none | generating | ready | failed
  reports.audio_r2_key  R2 object key once uploaded
"""
from alembic import op
import sqlalchemy as sa

revision = "9d34ed9201c2"
down_revision = "bad790d98ddf"


def upgrade() -> None:
    op.add_column("reports", sa.Column("audio_status", sa.String(), nullable=False,
                                       server_default="none"))
    op.add_column("reports", sa.Column("audio_r2_key", sa.String(), nullable=True))
    op.create_index("ix_reports_audio_status", "reports", ["audio_status"])


def downgrade() -> None:
    op.drop_index("ix_reports_audio_status", table_name="reports")
    op.drop_column("reports", "audio_r2_key")
    op.drop_column("reports", "audio_status")
