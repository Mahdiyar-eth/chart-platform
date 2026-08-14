"""Admin auth tests — audit P0 (round 3): /api/admin/stats must require admin
login (it was the only admin endpoint missing _is_admin)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app, _ADMIN_COOKIE, _ADMIN_PIN


def test_admin_stats_requires_auth():
    c = TestClient(app)
    r = c.get("/api/admin/stats")
    assert r.status_code == 403


def test_admin_stats_after_login_200():
    c = TestClient(app, follow_redirects=False)
    r = c.post("/admin/login", data={"pin": _ADMIN_PIN})
    assert r.status_code == 303, r.text
    # secure cookie is not sent back by httpx over http://testserver — set it manually
    val = r.cookies.get(_ADMIN_COOKIE)
    assert val, "login must set admin cookie"
    c.cookies.set(_ADMIN_COOKIE, val)
    r2 = c.get("/api/admin/stats")
    assert r2.status_code == 200
    assert "orders_total" in r2.json()
