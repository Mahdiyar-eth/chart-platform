"""A7 (ChatGPT directive) — admin KPI matrix: endpoint + live keys."""
from fastapi.testclient import TestClient

from app.main import app


def test_kpi_endpoint_requires_admin():
    c = TestClient(app)
    r = c.get("/api/admin/kpi")
    assert r.status_code in (401, 403)


def test_kpi_matrix_shape():
    from sqlmodel import Session
    from app.db import engine
    from app.kpi import kpi_matrix
    with Session(engine) as s:
        k = kpi_matrix(s)
    required = ["dau_24h", "wau_7d", "mau_30d", "total_users", "revenue_30d_toman",
                "revenue_total_toman", "aov_30d_toman", "arpu_30d_toman", "ltv_toman",
                "subscriptions_active_30d", "churn_30d", "renewal_30d",
                "repeat_purchase_users", "refund_rate_pct", "reports_total",
                "reports_done", "report_completion_pct", "chat_messages_30d",
                "explorations_30d", "weekly_reflections_30d", "push_subscriptions_total",
                "transit_llm_runs_30d", "llm_runs_total", "llm_fail_30d",
                "llm_latency_avg_ms", "qa_fail_latest_30d"]
    assert all(key in k for key in required)
    assert isinstance(k["mau_30d"], int)
    assert isinstance(k["report_completion_pct"], float)
