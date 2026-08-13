"""add chat_messages (AI chat history + usage metering)

Revision ID: c4f1a2b3e5d7
Revises: dfb85378c2bf
Create Date: 2026-08-13 18:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlmodel.sql.sqltypes  # noqa: F401

revision: str = 'c4f1a2b3e5d7'
down_revision: Union[str, Sequence[str], None] = 'dfb85378c2bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('chat_messages',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('chart_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('role', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('content', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('intent', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('domains', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('model', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('cost_usd', sa.Float(), nullable=False),
        sa.Column('ok', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['chart_id'], ['charts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_messages_chart_id'), 'chat_messages', ['chart_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_chat_messages_chart_id'), table_name='chat_messages')
    op.drop_table('chat_messages')
