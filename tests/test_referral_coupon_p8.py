"""ZAYCHE P8 (phase J) — referral 10% reward, 1-credit signup bonus on the
referred user's first paid order, referral-cycle voiding, and the LANCH20
coupon (20% first deep report, max uses, expiry, stacking gate)."""
import os
import sys
import uuid

os.environ["APP_ENV"] = "test"
os.environ.setdefault("DATABASE_URL",
                      "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
sys.path.insert(0, "/root/chart-platform")

from sqlmodel import Session, select

from tests.conftest import engine
from app.models import (BirthProfile, Chart, Coupon, CreditTransaction, Order,
                        ReferralEvent, User)
from app.payment.orders import (get_or_create_referral_code, reward_referral,
                                REFERRAL_REWARD_PERCENT)


def _mk_user() -> str:
    with Session(engine) as s:
        u = User(id=uuid.uuid4().hex, phone="+98p8" + uuid.uuid4().hex[:8], credits=0)
        s.add(u)
        s.commit()
        return u.id


def _mk_chart(uid: str) -> str:
    with Session(engine) as s:
        p = BirthProfile(user_id=uid, name="تست", raw_year=1373, raw_month=6,
                         raw_day=1, time_known=True, hour=6, minute=10,
                         city_fa="تهران", lat=35.6892, lon=51.3890,
                         tz_name="Asia/Tehran")
        s.add(p)
        s.commit()
        s.refresh(p)
        ch = Chart(profile_id=p.id, user_id=uid,
                   chart_json={"planets": {}, "houses": {}, "angles": {}})
        s.add(ch)
        s.commit()
        return ch.id


def _mk_paid_order(uid: str, cid: str, plan_key: str = "basic",
                   ref_code: str = "", amount_rial: int = 1_490_000) -> str:
    with Session(engine) as s:
        o = Order(user_id=uid, chart_id=cid, plan_key=plan_key,
                  amount_rial=amount_rial, authority="A8" + uuid.uuid4().hex[:20],
                  status="paid", ref_id="sim", paid_at=__import__(
                      "app.timeutil", fromlist=["utcnow"]).utcnow())
        s.add(o)
        s.commit()
        s.refresh(o)
        if ref_code:
            ev = ReferralEvent(code=ref_code, referrer_user_id=None,
                               new_user_id=uid, order_id=o.id,
                               amount_rial=amount_rial,
                               reward_rial=int(amount_rial * REFERRAL_REWARD_PERCENT / 100),
                               status="pending")
            s.add(ev)
            s.commit()
            s.refresh(ev)
        return o.id


# ── J: 10% referral reward (plan v2.0 §13) ──────────────────────────────────
def test_referral_reward_is_10_percent():
    ref = _mk_user()
    buyer = _mk_user()
    cid = _mk_chart(buyer)
    code = get_or_create_referral_code(Session(engine), ref)
    oid = _mk_paid_order(buyer, cid, ref_code=code, amount_rial=250_000)
    with Session(engine) as s:
        ev = s.exec(select(ReferralEvent).where(ReferralEvent.order_id == oid)).first()
        ev.referrer_user_id = ref
        ev.new_user_id = buyer
        s.add(ev)
        s.commit()
        reward_referral(s, s.get(Order, oid))
        s.refresh(ev)
        assert ev.status == "rewarded"
        r = s.get(User, ref)
        assert r.balance_rial == 25_000  # 10% of 250k


def test_referred_user_gets_one_credit_on_first_purchase():
    ref = _mk_user()
    buyer = _mk_user()
    cid = _mk_chart(buyer)
    code = get_or_create_referral_code(Session(engine), ref)
    oid = _mk_paid_order(buyer, cid, ref_code=code, amount_rial=250_000)
    with Session(engine) as s:
        ev = s.exec(select(ReferralEvent).where(ReferralEvent.order_id == oid)).first()
        ev.referrer_user_id = ref
        ev.new_user_id = buyer
        s.add(ev)
        s.commit()
        reward_referral(s, s.get(Order, oid))
        b = s.get(User, buyer)
        assert b.credits == 1
        tx = s.exec(select(CreditTransaction).where(
            CreditTransaction.user_id == buyer,
            CreditTransaction.reason == "referral_bonus")).first()
        assert tx is not None and tx.amount == 1
        # a SECOND paid order gives no extra credit
        oid2 = _mk_paid_order(buyer, _mk_chart(buyer), plan_key="full",
                              ref_code=code, amount_rial=3_490_000)
        ev2 = s.exec(select(ReferralEvent).where(ReferralEvent.order_id == oid2)).first()
        ev2.referrer_user_id = ref
        ev2.new_user_id = buyer
        s.add(ev2)
        s.commit()
        reward_referral(s, s.get(Order, oid2))
        b2 = s.get(User, buyer)
        assert b2.credits == 1  # bonus granted exactly once


def test_referral_cycle_a_to_b_to_a_is_voided():
    a, b = _mk_user(), _mk_user()
    code_a = get_or_create_referral_code(Session(engine), a)
    code_b = get_or_create_referral_code(Session(engine), b)
    # step 1: B buys with A's code (A→B edge, legitimate)
    oid1 = _mk_paid_order(b, _mk_chart(b), ref_code=code_a, amount_rial=1_000_000)
    with Session(engine) as s:
        ev1 = s.exec(select(ReferralEvent).where(ReferralEvent.order_id == oid1)).first()
        ev1.referrer_user_id = a
        ev1.new_user_id = b
        s.add(ev1)
        s.commit()
        reward_referral(s, s.get(Order, oid1))
        s.refresh(ev1)
        assert ev1.status == "rewarded"
        ra = s.get(User, a)
        assert ra.balance_rial == 100_000  # 10% of 1M
    # step 2: A buys with B's code (B→A edge) — B sits in A's ancestry → void
    oid2 = _mk_paid_order(a, _mk_chart(a), ref_code=code_b, amount_rial=1_000_000)
    with Session(engine) as s:
        ev2 = s.exec(select(ReferralEvent).where(ReferralEvent.order_id == oid2)).first()
        ev2.referrer_user_id = b
        ev2.new_user_id = a
        s.add(ev2)
        s.commit()
        reward_referral(s, s.get(Order, oid2))
        s.refresh(ev2)
        assert ev2.status == "voided"
        rb = s.get(User, b)
        assert rb.balance_rial == 0


# ── J: LANCH20 — 20% first deep report ─────────────────────────────────────
def _ensure_lanch20():
    with Session(engine) as s:
        c = s.exec(select(Coupon).where(Coupon.code == "LANCH20")).first()
        if not c:
            s.add(Coupon(code="LANCH20", percent=20, max_uses=10_000,
                         active=True, report_only=True))
            s.commit()


def test_lanch20_ok_on_first_deep_report():
    """R13/N3: LANCH20 lives in the CREDIT path — the coupon check endpoint
    accepts it for deep-report actions and rejects it after a prior report
    spend (the ledger IS the source of truth now)."""
    buyer = _mk_user()
    _ensure_lanch20()
    from fastapi.testclient import TestClient
    from app.auth import _user_cookie_value
    from app.main import app as main_app
    c = TestClient(main_app)
    c.cookies.set("chart_user", _user_cookie_value(buyer))
    r = c.get("/api/coupons/check?code=LANCH20")
    assert r.status_code == 200 and r.json().get("percent") == 20, r.text


def test_lanch20_rejected_on_second_report_and_packs():
    """R13/N3: after ANY prior deep-report credit spend, the coupon check
    endpoint refuses the coupon (the ledger IS the source of truth now)."""
    from fastapi.testclient import TestClient
    buyer = _mk_user()
    _mk_chart(buyer)
    _ensure_lanch20()
    # simulate a PRIOR deep-report credit spend in the ledger
    with Session(engine) as s:
        from app.models import CreditTransaction as _CT
        s.add(_CT(user_id=buyer, amount=-7, reason="report_full"))
        s.commit()
    from app.auth import _user_cookie_value
    from app.main import app as main_app
    c = TestClient(main_app)
    c.cookies.set("chart_user", _user_cookie_value(buyer))
    r = c.get("/api/coupons/check?code=LANCH20")
    assert r.status_code == 404, f"prior report spend must void LANCH20: {r.text}"


# ── J: /api/coupons/check validates without consuming ──────────────────────
def test_coupon_check_endpoint():
    _ensure_lanch20()
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    r = c.get("/api/coupons/check?code=LANCH20")
    assert r.status_code == 200
    j = r.json()
    assert j["percent"] == 20 and "اولین گزارش" in j["scope"]
    r2 = c.get("/api/coupons/check?code=NOPE123")
    assert r2.status_code == 404


# ── P9 — landing pages render with plan-v2.0 headlines ──────────────────────
def test_landing_pages_render():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    for path, headline in [
        ("/deep-report", "فقط یک چارت نبین"),
        ("/self-discovery", "سؤال‌های سخت درباره‌ی خودت"),
        ("/sky-today", "هر روز یک لحظه برای دیدن آسمان"),
    ]:
        r = c.get(path)
        assert r.status_code == 200, path
        assert headline in r.text, path
    sm = c.get("/sitemap.xml").text
    assert "/deep-report" in sm and "/self-discovery" in sm and "/sky-today" in sm
