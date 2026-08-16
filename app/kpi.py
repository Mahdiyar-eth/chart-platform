"""A7 (ChatGPT directive) — admin KPI matrix.

Each KPI: source table, SQL query, time window, admin UI, test.
Computed live from the DB — no caching, no LLM.
"""
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, text


def _scalar(s: Session, sql: str) -> float:
    v = s.exec(text(sql)).first()
    return float(v[0] if v and v[0] is not None else 0)


def kpi_matrix(s: Session) -> dict:
    """All KPIs with source/query/window — single DB round-trip per metric."""
    now = datetime.now(timezone.utc)
    d1 = (now - timedelta(days=1)).isoformat()
    d7 = (now - timedelta(days=7)).isoformat()
    d30 = (now - timedelta(days=30)).isoformat()
    q = {
        'dau_24h': f"SELECT count(DISTINCT user_id) FROM llm_runs WHERE created_at >= '{d1}'",
        'wau_7d': f"SELECT count(DISTINCT user_id) FROM llm_runs WHERE created_at >= '{d7}'",
        'mau_30d': f"SELECT count(DISTINCT user_id) FROM llm_runs WHERE created_at >= '{d30}'",
        'total_users': "SELECT count(*) FROM users",
        'revenue_30d_toman': f"SELECT sum(amount_rial) FROM orders WHERE status='paid' AND paid_at >= '{d30}'",
        'revenue_total_toman': "SELECT sum(amount_rial) FROM orders WHERE status='paid'",
        'orders_paid_30d': f"SELECT count(*) FROM orders WHERE status='paid' AND paid_at >= '{d30}'",
        'aov_30d_toman': f"SELECT sum(amount_rial)/count(*) FROM orders WHERE status='paid' AND paid_at >= '{d30}'",
        'arpu_30d_toman': f"SELECT (SELECT sum(amount_rial) FROM orders WHERE status='paid' AND paid_at >= '{d30}') / NULLIF((SELECT count(DISTINCT user_id) FROM llm_runs WHERE created_at >= '{d30}'),0)",
        'ltv_toman': "SELECT sum(amount_rial::float)/NULLIF(count(*),0) FROM orders WHERE status='paid'",
        'subscriptions_active_30d': f"SELECT count(*) FROM subscriptions WHERE active AND (expires_at IS NULL OR expires_at >= '{d30}')",
        'churn_30d': f"SELECT count(*) FROM subscriptions WHERE NOT active AND updated_at >= '{d30}'" if False else f"SELECT count(*) FROM subscriptions WHERE expires_at IS NOT NULL AND expires_at >= '{d30}' AND NOT active",
        'renewal_30d': f"SELECT count(*) FROM subscriptions WHERE active AND created_at >= '{d30}'",
        'repeat_purchase_users': "SELECT count(*) FROM (SELECT user_id FROM orders WHERE status='paid' GROUP BY user_id HAVING count(*) >= 2) t",
        'refund_rate_pct': "SELECT count(*)::float/NULLIF((SELECT count(*) FROM orders WHERE status='paid' OR status='refund_failed'),0)*100 FROM orders WHERE status='refund_failed'",
        'reports_total': "SELECT count(*) FROM reports",
        'reports_done': "SELECT count(*) FROM reports WHERE status='done'",
        'report_completion_pct': "SELECT count(*)::float/NULLIF((SELECT count(*) FROM reports),0)*100 FROM reports WHERE status='done'",
        'chat_messages_30d': f"SELECT count(*) FROM chat_messages WHERE created_at >= '{d30}'",
        'explorations_30d': f"SELECT count(*) FROM explorations WHERE created_at >= '{d30}'",
        'weekly_reflections_30d': f"SELECT count(*) FROM weekly_reflections WHERE created_at >= '{d30}'",
        'push_subscriptions_total': "SELECT count(*) FROM push_subscriptions",
        'transit_llm_runs_30d': f"SELECT count(*) FROM llm_runs WHERE kind='transit' AND created_at >= '{d30}'",
        'llm_runs_total': "SELECT count(*) FROM llm_runs",
        'llm_fail_30d': f"SELECT count(*) FROM llm_runs WHERE NOT ok AND created_at >= '{d30}'",
        'llm_latency_avg_ms': "SELECT avg(latency_ms) FROM llm_runs WHERE latency_ms > 0",
        'qa_fail_latest_30d': f"SELECT count(*) FROM reports WHERE status='failed' AND updated_at >= '{d30}'",
    }
    out = {}
    for k, sql in q.items():
        v = _scalar(s, sql)
        out[k] = round(v, 1) if k in ('refund_rate_pct', 'report_completion_pct', 'aov_30d_toman', 'arpu_30d_toman', 'ltv_toman', 'llm_latency_avg_ms') else int(v)
    return out
