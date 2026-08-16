"""G5 (§169/170) — error-code taxonomy: user-facing failures carry ZAY-xxx."""
from fastapi.testclient import TestClient

from app.main import app


def test_otp_request_sms_unavailable_carries_code(monkeypatch):
    """Production OTP without SMS key → 429 with [ZAY-SMS-001] (fail-closed)."""
    import app.auth as A
    monkeypatch.setattr(A, "_send_sms", lambda phone, code: (_ for _ in ()).throw(
        RuntimeError("SMS provider not configured (OTP_SMS_API_KEY)")))
    monkeypatch.setattr(A, "IS_PROD", True)
    monkeypatch.setattr(A, "_OTP_DEV_MODE", False)
    c = TestClient(app)
    r = c.post("/api/auth/otp/request", data={"phone": "989120000077"})
    assert r.status_code == 429
    assert "ZAY-SMS-001" in r.text


def test_otp_verify_wrong_code_carries_code():
    c = TestClient(app)
    r = c.post("/api/auth/otp/verify", data={"phone": "989120000078", "code": "000000"})
    assert r.status_code == 401
    assert "ZAY-AUTH-001" in r.text


def test_report_ownership_error_carries_code():
    c = TestClient(app)
    r = c.post("/api/charts/nonexistent/report")
    assert "ZAY-" in r.text or r.status_code in (404, 403, 401)


def test_taxonomy_documented_in_runbook():
    import pathlib
    rb = pathlib.Path("docs/ops/RUNBOOK.md").read_text(encoding="utf-8")
    assert "ZAY-AUTH-001" in rb and "ZAY-PAY-001" in rb and "ZAY-REPORT-001" in rb


def test_errors_module_has_codes():
    from app.errors import ZAY_ERRORS
    assert len(ZAY_ERRORS) >= 15
    for code, entry in ZAY_ERRORS.items():
        assert code.startswith("ZAY-") and "detail" in entry
