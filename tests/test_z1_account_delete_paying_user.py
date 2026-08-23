"""Z1/R3: paying user deletes account -> must NOT 500 (credit-economy FKs)."""
import os, uuid
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.db import engine
from app.main import app as main_app
from app.models import User, Entitlement
from app.credits import grant as credit_grant, spend

def _cookie(uid):
    from app.auth import USER_COOKIE, _user_cookie_value
    return {USER_COOKIE: _user_cookie_value(uid)}

def test_z1_paying_user_can_delete_account():
    uid = "u" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        s.add(User(id=uid, phone=uid + "@t", credits=0)); s.commit()
    # give the user credits (topup) AND a spend — both FK to users
    with Session(engine) as s:
        credit_grant(s, uid, 20, "topup", idempotency_key="z1-" + uid)
        spend(s, uid, "explore_card", idempotency_key="z1s-" + uid)
    c = TestClient(main_app)
    r0 = c.get("/account", cookies=_cookie(uid))
    assert r0.status_code == 200, r0.text[:150]
    # fetch CSRF like the real page does? account_delete requires csrf token verify.
    from app.security import CSRF_COOKIE, new_csrf_token
    tok = new_csrf_token()
    ck = _cookie(uid); ck[CSRF_COOKIE] = tok
    r = c.post("/account/delete", data={"csrf_token": tok}, cookies=ck)
    assert r.status_code in (303, 200), f"delete failed: {r.status_code} {r.text[:200]}"
    with Session(engine) as s:
        assert s.get(User, uid) is None  # actually gone


def test_z5_report_upgrade_binds_new_entitlement(monkeypatch):
    """Z5 (Opus R3 P1-2): buying a HIGHER report plan after an existing report
    must bind the NEW entitlement (ref_id) and yield the CORRECT plan_key, so
    the upgraded report downloads (no 403 + no inherited-wrong tier)."""
    uid = "u" + uuid.uuid4().hex[:10]
    from app.astrology.golden_data import GOLDEN_CHARTS
    from app.astrology.engine import compute_from_fields
    with Session(engine) as s:
        s.add(User(id=uid, phone=uid + "@t", credits=0)); s.commit()
        credit_grant(s, uid, 30, "topup", idempotency_key="z5-" + uid)
    p = compute_from_fields(**GOLDEN_CHARTS[0]["birth"]).chart_json
    from app.models import BirthProfile as _BP
    with Session(engine) as s:
        bp = _BP(user_id=uid, raw_year=1373, raw_month=5, raw_day=10); s.add(bp); s.flush()
        from app.models import Chart as _C
        cid = "c" + uuid.uuid4().hex[:8]
        s.add(_C(id=cid, profile_id=bp.id, chart_json=p)); s.commit()
    c = TestClient(main_app); ck = _cookie(uid)
    # buy report_full, create rep1
    import app.main as _m
    monkeypatch.setattr(_m, "_enqueue_report", lambda rid: True)
    r1 = c.post("/api/purchase", json={"action_key": "report_full", "chart_id": cid}, cookies=ck)
    assert r1.status_code == 200, r1.text[:200]
    rep1 = c.post(f"/api/charts/{cid}/report", cookies=ck).json()
    assert rep1.get("report_id"), rep1
    # now UPGRADE to gold and regenerate
    r2 = c.post("/api/purchase", json={"action_key": "report_gold", "chart_id": cid}, cookies=ck)
    assert r2.status_code == 200, r2.text[:200]
    rep2 = c.post(f"/api/charts/{cid}/report?regenerate=1", cookies=ck).json()
    assert rep2.get("plan_key") == "gold", f"plan_key was {rep2.get('plan_key')}"  # Z5: gold not full
    with Session(engine) as s:
        ents = s.exec(select(Entitlement).where(Entitlement.user_id == uid)).all()
        report_ents = [e for e in ents if e.kind == "report"]
        assert len(report_ents) >= 2
        bound = [e for e in report_ents if e.ref_id]
        assert bound, "no entitlement was bound to a report"

