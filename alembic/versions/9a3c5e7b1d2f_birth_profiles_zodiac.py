"""birth profiles zodiac

Revision ID: 9a3c5e7b1d2f
Revises: d4f2580df4bf
Create Date: 2026-08-14 06:40:00.000000

Adds birth_profiles.zodiac (tropical default) — audit r3: the user-facing
zodiac-system preference must be stored on the profile, not only inside each
chart's engine_config snapshot.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9a3c5e7b1d2f'
down_revision: Union[str, Sequence[str], None] = 'd4f2580df4bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('birth_profiles', sa.Column('zodiac', sa.String(), nullable=False, server_default='tropical'))


def downgrade() -> None:
    op.drop_column('birth_profiles', 'zodiac')
