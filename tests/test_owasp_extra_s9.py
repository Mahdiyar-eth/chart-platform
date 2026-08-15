"""ZAYCHE §9 — OWASP extra matrix: path traversal, SSRF, session expiry,
OTP replay/expiry, debug endpoints.

Auth routes: POST /api/auth/otp/request + verify; account delete via
/account/delete (CSRF + cookie). OTP codes are single-use (deleted on
verify) and per-phone rate limited — verified by design.
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import app
from app.db import engine
from app.models import Chart, Order, Report, User

_UNIQ = [0]


def _uniq_phone() -> str:
    """Unique phone per call — time alone collides within the same second."""
    _UNIQ[0] += 1
    return f"0912{(int(time.time()) % 100000 + _UNIQ[0] * 7) % 1000000:06d}{_UNIQ[0] % 10}"


@pytest.fixture
def client():
    # https base_url: app sets Secure cookies — httpx drops them on plain http
    with TestClient(app, follow_redirects=False, base_url="https://testserver") as c:
        yield c


@pytest.fixture(autouse=True)
def _otp_dev(monkeypatch):
    """Tests exercise the real OTP flow — enable dev mode so the code is
    returned in the response instead of sending SMS; also bypass the shared
    IP limiter (tests run with the same testclient IP)."""
    import app.auth as _a
    monkeypatch.setattr(_a, "_OTP_DEV_MODE", True)
    # routes/auth.py does `from app.main import _rate_limit` — patch the
    # module attribute itself so the shared-IP limiter never trips tests
    import app.main as _m
    monkeypatch.setattr(_m, "_rate_limit", lambda *a, **k: True)


def _clear_otp(phone: str):
    """Drop shared counters so tests never trip each other — both the redis
    keys AND the in-memory sliding-window store (tests run with one IP)."""
    import app.security as _sec
    _sec._RATE_LIMITS.clear()
    import redis as _r
    r = _r.from_url("redis://127.0.0.1:6379")
    for pattern in ("rl:otp:*", "otp:*", "pay:*"):
        for k in r.scan_iter(match=pattern):
            r.delete(k)


def _otp_code(client, phone: str) -> str:
    _clear_otp(phone)
    r = client.post("/api/auth/otp/request", data={"phone": phone})
    assert r.status_code == 200, r.text
    return r.json()["dev_code"]


def _login(client, phone: str) -> int:
    code = _otp_code(client, phone)
    return client.post("/api/auth/otp/verify", data={"phone": phone, "code": code}).status_code


def _make_owned_report():
    phone = _uniq_phone()
    with Session(engine) as s:
        u = User(phone=phone, name="sec")
        s.add(u)
        s.flush()
        ch = Chart(chart_json={"planets": {}, "engine_config": {"zodiac": "tropical"}})
        s.add(ch)
        s.flush()
        o = Order(plan_key="full", amount_rial=1_490_000, status="paid",
                  authority="SECAUTH1", chart_id=ch.id)
        s.add(o)
        s.flush()
        rep = Report(chart_id=ch.id, plan_key="full", status="done",
                     pdf_path="/root/chart-platform/reports/real.pdf")
        s.add(rep)
        s.commit()
        return {"phone": phone, "user": u.id, "chart": ch.id, "report": rep.id}


# ── path traversal ──────────────────────────────────────

def test_report_pdf_path_traversal_blocked(client):
    o = _make_owned_report()
    _login(client, o["phone"])
    r = client.get(f"/api/reports/{o['report']}.pdf?path=../../../../etc/passwd")
    assert r.status_code != 200 or "root:" not in r.text
    assert r.status_code in (302, 404, 403, 400)


def test_report_download_requires_owner(client):
    o = _make_owned_report()
    # anonymous → redirect to login / 403
    r = client.get(f"/api/reports/{o['report']}.pdf")
    assert r.status_code in (302, 303, 403, 404)


# ── SSRF ────────────────────────────────────────────────

def test_payment_callback_url_server_built():
    """Callback URL is built server-side from PUBLIC_BASE_URL — never client input."""
    import inspect
    from app.payment.orders import create_order
    src = inspect.getsource(create_order)
    assert "callback_url = f\"{public_base}/api/payments/verify\"" in src


def test_zarinpal_base_pinned():
    from app.payment import zarinpal as z
    assert z.SANDBOX_BASE.startswith("https://sandbox.zarinpal.com/")
    assert z.PROD_BASE.startswith("https://payment.zarinpal.com/")
    assert "http://" not in z.SANDBOX_BASE and "http://" not in z.PROD_BASE


# ── OTP replay / expiry ─────────────────────────────────

def test_otp_code_replay_rejected(client):
    phone = _uniq_phone()
    code = _otp_code(client, phone)
    first = client.post("/api/auth/otp/verify", data={"phone": phone, "code": code})
    assert first.status_code in (200, 303)
    second = client.post("/api/auth/otp/verify", data={"phone": phone, "code": code})
    assert second.status_code in (400, 401, 403)  # single-use: deleted after verify


def test_otp_wrong_code_rejected(client):
    phone = _uniq_phone()
    _otp_code(client, phone)
    r = client.post("/api/auth/otp/verify", data={"phone": phone, "code": "00000"})
    assert r.status_code in (400, 401, 403)


def test_otp_expired_code_rejected(client):
    """Code expires after OTP_TTL — simulate by deleting the redis key."""
    import redis as _r
    phone = _uniq_phone()
    code = _otp_code(client, phone)
    r = _r.from_url("redis://127.0.0.1:6379")
    for k in r.scan_iter(match=f"otp:*{phone}*"):
        r.delete(k)
    r2 = client.post("/api/auth/otp/verify", data={"phone": phone, "code": code})
    assert r2.status_code in (400, 401, 403)


def test_otp_enumeration_rate_limited(client):
    """Per-phone limiter (request_otp) trips 429 after OTP_REQ_LIMIT requests."""
    phone = _uniq_phone()
    _clear_otp(phone)
    codes = []
    for _ in range(12):
        r = client.post("/api/auth/otp/request", data={"phone": phone})
        codes.append(r.status_code)
    assert 429 in codes


# ── debug endpoints ─────────────────────────────────────

def test_no_debug_endpoints():
    import app.main as m
    routes = [getattr(rt, "path", "") for rt in m.app.routes]
    bad = [p for p in routes if any(x in p for x in ("/debug", "/__debug", "/_debug"))]
    assert bad == []


def test_docs_disabled_in_prod_env():
    """/docs must be disabled when APP_ENV=prod (fresh interpreter, prod env)."""
    import subprocess
    code = (
        "import os; os.environ['APP_ENV']='prod'\n"
        f"os.environ['DATABASE_URL']={os.environ['DATABASE_URL']!r}\n"
        "os.environ['RATE_LIMIT_BACKEND']='redis'; os.environ['REDIS_URL']='redis://127.0.0.1:6379/15'\n"
        "import app.main as m\n"
        "from fastapi.testclient import TestClient\n"
        "with TestClient(m.app) as c:\n"
        "    print('DOCS', c.get('/docs').status_code, 'OPENAPI', c.get('/openapi.json').status_code)\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       cwd=str(Path(__file__).resolve().parent.parent), timeout=60)
    out = r.stdout + r.stderr
    assert "DOCS 404" in out or "DOCS 405" in out, out[-400:]


# ── session / privacy ───────────────────────────────────

def test_logout_invalidates_session(client):
    phone = _uniq_phone()
    _login(client, phone)
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json().get("user")
    client.post("/api/auth/logout")
    after = client.get("/api/auth/me")
    assert after.json().get("user") is None
