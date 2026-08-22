"""E4 — baseline security headers on all responses (defense in depth)."""
from fastapi.testclient import TestClient
from app.main import app


def _client():
    return TestClient(app)


def test_security_headers_on_public_page():
    c = _client()
    r = c.get("/")
    assert r.status_code == 200
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in (r.headers.get("Permissions-Policy") or "")


def test_csp_report_only_present():
    c = _client()
    r = c.get("/plans")
    csp = r.headers.get("Content-Security-Policy-Report-Only") or ""
    assert "default-src" in csp  # report-only: zero breakage risk, observability first


def test_headers_on_api_too():
    c = _client()
    r = c.get("/readiness")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
