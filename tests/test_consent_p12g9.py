"""G9 (§85) — consent records at signup + transparency endpoint."""
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.main import app
from app.models import ConsentLog, User
from tests.conftest import fake_authority


def test_consent_recorded_at_signup_and_readable(monkeypatch):
    from app.auth import _user_cookie_value, request_otp
    import app.auth as A

    phone = f"98g9{fake_authority(8)}"
    # simulate full OTP signup without SMS (dev mode — restore after)
    monkeypatch.setattr(A, "_OTP_DEV_MODE", True)
    code = request_otp(phone)["dev_code"]
    u = A.verify_otp(phone, code)
    with Session(engine) as s:
        uid = s.exec(select(User.id).where(User.phone == phone)).first()
        consents = s.exec(select(ConsentLog).where(ConsentLog.user_id == uid)).all()
        purposes = {r.purpose for r in consents}
    assert {"terms", "privacy"} <= purposes

    c = TestClient(app)
    c.cookies.set("chart_user", _user_cookie_value(uid))
    d = c.get("/api/consent").json()
    assert len(d["consents"]) >= 2
    assert any(x["purpose"] == "terms" for x in d["consents"])


def test_consent_requires_auth():
    c = TestClient(app)
    assert c.get("/api/consent").status_code == 401
