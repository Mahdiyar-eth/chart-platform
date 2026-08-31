"""Y4/N7 follow-up: align schema with models (CI alembic-drift gate).

Detected by `alembic check` after c7f1a2b9d4e6:
- funnel_events: rename indexes to model names (event, session_id)
- notification_prefs.transit_alerts: server-side NOT NULL alignment
- transit_alert_log: index on user_key (non-unique per model)
- transit_forecasts.chart_id FK: models declare plain FK without CASCADE

revision: c8d2e3f4a5b6
down_revision: c7f1a2b9d4e6
"""
from alembic import op
import sqlalchemy as sa

revision = 'c8d2e3f4a5b6'
down_revision = 'c7f1a2b9d4e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    has_idx = lambda t, n: any(i.get("name") == n for i in insp.get_indexes(t))
    # funnel_events: drop old-named indexes, create the model-named ones
    if has_idx("funnel_events", "ix_funnel_events_event_time"):
        op.drop_index('ix_funnel_events_event_time', table_name='funnel_events')
    if has_idx("funnel_events", "ix_funnel_events_session"):
        op.drop_index('ix_funnel_events_session', table_name='funnel_events')
    op.create_index('ix_funnel_events_event', 'funnel_events', ['event'])
    op.create_index('ix_funnel_events_session_id', 'funnel_events', ['session_id'])

    # notification_prefs.transit_alerts: model column is nullable (plain Column(Boolean))
    op.alter_column('notification_prefs', 'transit_alerts',
                    existing_type=sa.Boolean(),
                    nullable=True,
                    server_default=sa.true())

    # transit_alert_log.user_key: non-unique index per current model
    if has_idx("transit_alert_log", "ix_transit_alert_log_user_key"):
        op.drop_index('ix_transit_alert_log_user_key', table_name='transit_alert_log')
    op.create_index('ix_transit_alert_log_user_key', 'transit_alert_log', ['user_key'],
                    unique=False)

    # Z2/R3 correction: this drop is guarded — on a FRESH chain (baseline had no
    # FK) there is nothing to drop; only legacy prod DBs carried it.
    if any(fk.get("name") == "transit_forecasts_chart_id_fkey"
           for fk in insp.get_foreign_keys("transit_forecasts")):
        op.drop_constraint('transit_forecasts_chart_id_fkey', 'transit_forecasts',
                           type_='foreignkey')


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    has_idx = lambda t, n: any(i.get("name") == n for i in insp.get_indexes(t))
    op.create_foreign_key('transit_forecasts_chart_id_fkey', 'transit_forecasts',
                          'charts', ['chart_id'], ['id'], ondelete='CASCADE')
    if has_idx("transit_alert_log", "ix_transit_alert_log_user_key"):
        op.drop_index('ix_transit_alert_log_user_key', table_name='transit_alert_log')
    op.create_index('ix_transit_alert_log_user_key', 'transit_alert_log', ['user_key'],
                    unique=True)
    op.alter_column('notification_prefs', 'transit_alerts',
                    existing_type=sa.Boolean(), nullable=False)
    if has_idx("funnel_events", "ix_funnel_events_session_id"):
        op.drop_index('ix_funnel_events_session_id', table_name='funnel_events')
    if has_idx("funnel_events", "ix_funnel_events_event"):
        op.drop_index('ix_funnel_events_event', table_name='funnel_events')
    op.create_index('ix_funnel_events_session', 'funnel_events', ['session_id'])
    op.create_index('ix_funnel_events_event_time', 'funnel_events', ['event', 'created_at'])
