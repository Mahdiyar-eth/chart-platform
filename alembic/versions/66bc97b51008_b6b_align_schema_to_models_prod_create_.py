"""b6b: align schema to models (prod create_all drift)

PROD was created by an old `create_all` (never via Alembic) while the test DB
is rebuilt fresh — the two schemas drifted apart (index naming, nullable,
unique). This migration converges BOTH to the models' definition, using
IF EXISTS / IF NOT EXISTS so it is a no-op on already-aligned schemas.

Generated 2026-08-14 (audit r4 B6 — alembic check must be clean everywhere).
"""
from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence

# revision identifiers, used by Alembic.
revision: str = '66bc97b51008'
down_revision: Union[str, Sequence[str], None] = 'd4db5d787f91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── orders ────────────────────────────────────────────────────────────
    op.execute("DROP INDEX IF EXISTS idx_orders_chart_status")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_chat_id ON orders (chat_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_secondary_chart_id ON orders (secondary_chart_id)")
    # ── referral_codes ────────────────────────────────────────────────────
    op.execute("ALTER TABLE referral_codes ALTER COLUMN user_id SET NOT NULL")
    op.execute("ALTER TABLE referral_codes ALTER COLUMN code SET NOT NULL")
    op.execute("ALTER TABLE referral_codes ALTER COLUMN created_at SET NOT NULL")
    op.execute("ALTER TABLE referral_codes DROP CONSTRAINT IF EXISTS referral_codes_code_key")
    op.execute("DROP INDEX IF EXISTS ix_referral_codes_code")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_referral_codes_code ON referral_codes (code)")
    # ── referral_events ───────────────────────────────────────────────────
    op.execute("ALTER TABLE referral_events ALTER COLUMN code SET NOT NULL")
    op.execute("ALTER TABLE referral_events ALTER COLUMN amount_rial SET NOT NULL")
    op.execute("ALTER TABLE referral_events ALTER COLUMN reward_rial SET NOT NULL")
    op.execute("ALTER TABLE referral_events ALTER COLUMN status SET NOT NULL")
    op.execute("ALTER TABLE referral_events ALTER COLUMN created_at SET NOT NULL")
    op.execute("DROP INDEX IF EXISTS ix_ref_code")
    op.execute("CREATE INDEX IF NOT EXISTS ix_referral_events_code ON referral_events (code)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_referral_events_order_id ON referral_events (order_id)")
    # ── reports ───────────────────────────────────────────────────────────
    op.execute("DROP INDEX IF EXISTS idx_reports_chart")
    # ── subscriptions / weekly_reflections nullable+defaults ──────────────
    op.execute("ALTER TABLE subscriptions ALTER COLUMN plan_key SET NOT NULL")
    op.execute("ALTER TABLE subscriptions ALTER COLUMN expires_at DROP NOT NULL")
    op.execute("ALTER TABLE weekly_reflections ALTER COLUMN text SET NOT NULL")
    op.execute("ALTER TABLE weekly_reflections ALTER COLUMN created_at SET NOT NULL")


def downgrade() -> None:
    # Best-effort reverse (kept minimal — this migration is one-way drift fix)
    op.execute("CREATE INDEX IF NOT EXISTS idx_orders_chart_status ON orders (chart_id, status)")
    op.execute("DROP INDEX IF EXISTS ix_orders_chat_id")
    op.execute("DROP INDEX IF EXISTS ix_orders_secondary_chart_id")
    op.execute("ALTER TABLE referral_codes ALTER COLUMN user_id DROP NOT NULL")
    op.execute("ALTER TABLE referral_codes ALTER COLUMN code DROP NOT NULL")
    op.execute("ALTER TABLE referral_codes ALTER COLUMN created_at DROP NOT NULL")
    op.execute("ALTER TABLE referral_codes ADD CONSTRAINT referral_codes_code_key UNIQUE (code)")
    op.execute("DROP INDEX IF EXISTS ix_referral_codes_code")
    op.execute("DROP INDEX IF EXISTS ix_referral_events_code")
    op.execute("DROP INDEX IF EXISTS ix_referral_events_order_id")
    op.execute("ALTER TABLE referral_events ALTER COLUMN code DROP NOT NULL")
    op.execute("ALTER TABLE referral_events ALTER COLUMN amount_rial DROP NOT NULL")
    op.execute("ALTER TABLE referral_events ALTER COLUMN reward_rial DROP NOT NULL")
    op.execute("ALTER TABLE referral_events ALTER COLUMN status DROP NOT NULL")
    op.execute("ALTER TABLE referral_events ALTER COLUMN created_at DROP NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_reports_chart ON reports (chart_id, created_at)")
    op.execute("ALTER TABLE subscriptions ALTER COLUMN plan_key DROP NOT NULL")
    op.execute("ALTER TABLE weekly_reflections ALTER COLUMN text DROP NOT NULL")
    op.execute("ALTER TABLE weekly_reflections ALTER COLUMN created_at DROP NOT NULL")
