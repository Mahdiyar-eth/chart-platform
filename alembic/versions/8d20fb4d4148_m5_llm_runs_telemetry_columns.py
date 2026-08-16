"""m5 llm_runs telemetry columns

Revision ID: 8d20fb4d4148
Revises: 575c0e692ce6
Create Date: 2026-08-16 11:01:34.937994

M5 (multi-provider plan): per-key / per-section observability.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import sqlmodel.sql.sqltypes  # noqa: F401 — SQLModel AutoString type

# revision identifiers, used by Alembic.
revision: str = '8d20fb4d4148'
down_revision: Union[str, Sequence[str], None] = '575c0e692ce6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('llm_runs', sa.Column('key_slot', sa.String(), nullable=True))
    op.add_column('llm_runs', sa.Column('section', sa.String(), nullable=True))
    op.add_column('llm_runs', sa.Column('attempt', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('llm_runs', sa.Column('error_code', sa.String(), nullable=True))
    op.add_column('llm_runs', sa.Column('fallback_used', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('llm_runs', sa.Column('prompt_version', sa.String(), nullable=True))
    op.create_index('ix_llm_runs_key_slot', 'llm_runs', ['key_slot'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_llm_runs_key_slot', table_name='llm_runs')
    op.drop_column('llm_runs', 'prompt_version')
    op.drop_column('llm_runs', 'fallback_used')
    op.drop_column('llm_runs', 'error_code')
    op.drop_column('llm_runs', 'attempt')
    op.drop_column('llm_runs', 'section')
    op.drop_column('llm_runs', 'key_slot')
