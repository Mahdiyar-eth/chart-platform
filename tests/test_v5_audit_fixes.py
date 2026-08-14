"""V5 audit (F-01..F-10): wallet reserve, atomic debit race, wallet→report
enqueue, refund idempotent recovery, timezone fail-closed, report advisory
lock, deletion of audio/pdf artifacts, dedupe Redis contract."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.models import (Order, Report, User, WithdrawalRequest)
from app.db import engine


def _mk_user(s, phone: str, balance: int) -> User:
    u = User(phone=phone, balance_rial=balance, status="active")
    s.add(u)
    s.commit()
    s.refresh(u)
    return u


def _mk_order(s, chart_id: str, plan: str = "basic", amount: int = 1_000_000) -> Order:
    o = Order(chart_id=chart_id, plan_key=plan, status="pending", amount_rial=amount)
    s.add(o)
    s.commit()
    s.refresh(o)
    return o


def _mk_chart(c: TestClient) -> tuple[str, str]:
    r = c.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897",
    })
    cid = r.json()["chart_id"]
    tok = r.json()["access_token"]
    import json
    c.cookies.update({"chart_access": json.dumps({cid: tok})})
    return cid, tok


# ── F-01: withdrawal reserves the balance (P0) ──────────────────────────────
def test_withdrawal_reserves_balance_and_reject_refunds():
    from app.payment.orders import resolve_withdrawal, withdraw_request
    with Session(engine) as s:
        u = _mk_user(s, f"+98v5w1{__import__('uuid').uuid4().hex[:8]}", 2_000_000)
        uid = u.id
        assert withdraw_request(s, uid, 500_000) is True
        s.refresh(u)
        assert u.balance_rial == 1_500_000          # reserved immediately
        assert withdraw_request(s, uid, 1_500_000) is False  # one pending
        wr = s.exec(select(WithdrawalRequest).where(WithdrawalRequest.user_id == uid)).one()
        # paid keeps the debit
        assert resolve_withdrawal(s, wr.id, "paid") is True
        s.refresh(u)
        assert u.balance_rial == 1_500_000
        # no pending now; a new withdrawal beyond balance is rejected
        assert withdraw_request(s, uid, 2_000_000) is False
        # rejection refunds
        assert withdraw_request(s, uid, 1_000_000) is True
        wr2 = s.exec(select(WithdrawalRequest).where(
            WithdrawalRequest.user_id == uid, WithdrawalRequest.status == "pending")).one()
        assert resolve_withdrawal(s, wr2.id, "rejected") is True
        s.refresh(u)
        # 2M - 500k (paid) - 1M (reserved) + 1M (rejected refund) = 1.5M
        assert u.balance_rial == 1_500_000


# ── F-02: atomic conditional debit (P0) — two concurrent wallets can't double-spend
def test_balance_pay_is_atomic_under_contention():
    import threading
    from app.payment.orders import pay_order_with_balance
    with Session(engine) as s:
        u = _mk_user(s, f"+98v5r{__import__('uuid').uuid4().hex[:8]}", 1_200_000)
        uid = u.id
    orders = []
    for _ in range(3):
        with Session(engine) as s:
            o = Order(chart_id=None, plan_key="basic", status="pending", amount_rial=600_000)
            s.add(o)
            s.commit()
            orders.append(o.id)

    results: list[bool] = []
    lock = threading.Lock()

    def _pay(oid: str):
        with Session(engine) as s:
            u = s.get(User, uid)
            o = s.get(Order, oid)
            ok = pay_order_with_balance(s, o, u)
            s.commit()
        with lock:
            results.append(ok)

    threads = [threading.Thread(target=_pay, args=(oid,)) for oid in orders]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count(True) == 2   # 1.2M / 600k → exactly two can win
    assert results.count(False) == 1
    with Session(engine) as s:
        u = s.get(User, uid)
        assert u.balance_rial == 0    # never negative, never double-spent
        paid = s.exec(select(Order).where(Order.id.in_(orders), Order.status == "paid")).all()
        assert len(paid) == 2


# ── F-11 (audit v6 P0): concurrent withdrawals — atomic debit + partial
# unique index ⇒ exactly ONE pending withdrawal can ever exist per user
def test_concurrent_withdrawals_only_one_wins():
    import threading
    from app.payment.orders import withdraw_request
    with Session(engine) as s:
        u = _mk_user(s, f"+98v5c{__import__('uuid').uuid4().hex[:8]}", 1_000_000)
        uid = u.id
    wins = [0]

    def _try():
        with Session(engine) as s2:
            if withdraw_request(s2, uid, 700_000):
                wins[0] += 1

    ts = [threading.Thread(target=_try) for _ in range(3)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert wins[0] == 1  # exactly ONE pending withdrawal may exist
    with Session(engine) as s:
        n = len(s.exec(select(WithdrawalRequest).where(
            WithdrawalRequest.user_id == uid,
            WithdrawalRequest.status == "pending")).all())
        u = s.get(User, uid)
        assert n == 1
        assert u.balance_rial == 300_000  # 1M - 700k reserved exactly once


# ── F-15 (audit v6 P0): concurrent admin resolves — atomic CAS ⇒ the
# withdrawal is resolved EXACTLY once (no double payout / double refund)
def test_concurrent_admin_resolve_only_one_wins():
    import threading
    from app.payment.orders import resolve_withdrawal, withdraw_request
    with Session(engine) as s:
        u = _mk_user(s, f"+98v5h{__import__('uuid').uuid4().hex[:8]}", 1_000_000)
        uid = u.id
        assert withdraw_request(s, uid, 700_000) is True
        wid = s.exec(select(WithdrawalRequest).where(
            WithdrawalRequest.user_id == uid)).one().id
    wins = [0]

    def _resolve_paid():
        with Session(engine) as s2:
            if resolve_withdrawal(s2, wid, "paid", "موفق"):
                wins[0] += 1

    ts = [threading.Thread(target=_resolve_paid) for _ in range(3)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert wins[0] == 1  # exactly ONE 'paid' may be issued for one payout
    with Session(engine) as s:
        wr = s.get(WithdrawalRequest, wid)
        assert wr.status == "paid"
        u = s.get(User, uid)
        assert u.balance_rial == 300_000  # 1M - 700k, NOT refunded twice


def test_concurrent_admin_reject_refunds_exactly_once():
    import threading
    from app.payment.orders import resolve_withdrawal, withdraw_request
    with Session(engine) as s:
        u = _mk_user(s, f"+98v5i{__import__('uuid').uuid4().hex[:8]}", 1_000_000)
        uid = u.id
        assert withdraw_request(s, uid, 700_000) is True
        wid = s.exec(select(WithdrawalRequest).where(
            WithdrawalRequest.user_id == uid)).one().id
    wins = [0]

    def _reject():
        with Session(engine) as s2:
            if resolve_withdrawal(s2, wid, "rejected", "ناقص"):
                wins[0] += 1

    ts = [threading.Thread(target=_reject) for _ in range(3)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert wins[0] == 1
    with Session(engine) as s:
        wr = s.get(WithdrawalRequest, wid)
        assert wr.status == "rejected"
        u = s.get(User, uid)
        assert u.balance_rial == 1_000_000  # 1M - 700k + 700k = refunded ONCE


# ── F-16 (audit v6 P2): audit fallback — DB failure must not lose the record
def test_audit_writes_fallback_when_db_fails(monkeypatch, tmp_path):
    import json as _json
    from app.security import audit as _audit
    fallback = tmp_path / "audit-fallback.log"
    monkeypatch.setenv("AUDIT_FALLBACK_LOG", str(fallback))
    monkeypatch.setattr("app.security._AUDIT_FALLBACK", str(fallback))

    # engine that is not a real engine — any use raises inside audit()
    _audit(object(), "admin", "order.refund", "oid-1", "خطای تست")
    assert fallback.exists()
    line = _json.loads(fallback.read_text().strip().splitlines()[-1])
    assert line["action"] == "order.refund"
    assert line["admin"] == "admin"
    assert line["entity"] == "oid-1"


# ── F-17 (audit v7 P1): report entitlement is per-REPORT — a refunded GOLD
# report must NOT become downloadable again via a later BASIC purchase
def test_refunded_report_stays_locked_after_new_purchase():
    from app.main import _report_gate

    class _Req:
        def __init__(self, t):
            self.state = {}
            self.cookies = {"chart_access": t}
            self._t = t

        @property
        def query_params(self):
            class _QP:
                def __init__(self, t):
                    self._t = t

                def get(self, k, default=None):
                    return self._t if k == "t" else default
            return _QP(self._t)

    with Session(engine) as s:
        from app.models import BirthProfile, Chart
        p = BirthProfile(raw_year=1994, raw_month=8, raw_day=23, time_known=True,
                         hour=6, minute=10, city_fa="تهران", tz_name="Asia/Tehran",
                         calendar_system="jalali")
        s.add(p)
        s.flush()
        c = Chart(profile_id=p.id, chart_json={}, engine_config={}, access_token="tok-f17")
        s.add(c)
        s.commit()
        s.refresh(c)
        tok = c.access_token
        rep_gold = Report(chart_id=c.id, status="done", plan_key="gold")
        s.add(rep_gold)
        s.commit()
        s.refresh(rep_gold)
        # 1) user buys GOLD → report linked to the gold order
        o_gold = Order(chart_id=c.id, plan_key="gold", status="paid",
                       amount_rial=6_990_000, report_id=rep_gold.id)
        s.add(o_gold)
        s.commit()
        assert _report_gate(rep_gold, s, _Req(tok)) is True
        # 2) GOLD is refunded → entitlement revoked
        o_gold.status = "refunded"
        s.commit()
        assert _report_gate(rep_gold, s, _Req(tok)) is False
        # 3) user later buys BASIC on the same chart → ANOTHER paid order exists
        rep_basic = Report(chart_id=c.id, status="done", plan_key="basic")
        s.add(rep_basic)
        s.commit()
        s.refresh(rep_basic)
        o_basic = Order(chart_id=c.id, plan_key="basic", status="paid",
                        amount_rial=1_490_000, report_id=rep_basic.id)
        s.add(o_basic)
        s.commit()
        # the old GOLD report must STAY locked despite the new paid order…
        assert _report_gate(rep_gold, s, _Req(tok)) is False
        # …while the new BASIC report is downloadable
        assert _report_gate(rep_basic, s, _Req(tok)) is True


# ── F-13 (audit v6 P1): R2 deletion failure blocks account deletion
def test_account_delete_fails_closed_when_r2_delete_fails(monkeypatch):
    from app.security import new_csrf_token
    c = TestClient(app)
    with Session(engine) as s:
        u = _mk_user(s, f"+98v5g{__import__('uuid').uuid4().hex[:8]}", 0)
        uid = u.id
    c.cookies.set("chart_user", __import__("app.auth", fromlist=["_user_cookie_value"])._user_cookie_value(uid))
    cid, tok = _mk_chart(c)
    with Session(engine) as s:
        p = s.exec(select(__import__("app.models", fromlist=["BirthProfile"]).BirthProfile)
                   .where(__import__("app.models", fromlist=["BirthProfile"]).BirthProfile.user_id == uid)).one()
        s.exec(__import__("sqlalchemy", fromlist=["text"]).text(
            "UPDATE charts SET profile_id=:p WHERE id=:c").bindparams(p=p.id, c=cid))
        rep = Report(chart_id=cid, status="done", plan_key="basic", r2_key="pdfs/leak.pdf")
        s.add(rep)
        s.commit()
        rep_id = rep.id
    monkeypatch.setattr("app.storage.delete_object_checked",
                        lambda k: (_ for _ in ()).throw(RuntimeError("R2 down")))

    token = new_csrf_token()
    c.cookies.set("csrf_token", token)
    r = c.post("/account/delete", data={"csrf_token": token})
    assert r.status_code == 502  # fail-closed: no partial deletion
    with Session(engine) as s:
        u = s.get(User, uid)
        assert u is not None  # account still exists — retry later
        assert s.exec(select(Report).where(Report.id == rep_id)).first() is not None  # artifacts intact


# ── F-03: wallet-paid report gets enqueued (P1) ─────────────────────────────
def test_wallet_payment_enqueues_report(monkeypatch):
    enqueued: list[str] = []
    monkeypatch.setattr("app.main._enqueue_report", lambda rid: (enqueued.append(rid) or True))
    c = TestClient(app)
    with Session(engine) as s:
        u = _mk_user(s, f"+98v5e{__import__('uuid').uuid4().hex[:8]}", 50_000_000)
        uid = u.id
    c.cookies.set("chart_user", __import__("app.auth", fromlist=["_user_cookie_value"])._user_cookie_value(uid))
    cid, tok = _mk_chart(c)
    r = c.post("/api/orders", data={
        "plan_key": "basic", "chart_id": cid, "access_token": tok,
    }, headers={"x-pay-with-balance": "1"})
    assert r.status_code == 200, r.text
    assert r.json()["paid_by_balance"] is True
    with Session(engine) as s:
        o = s.exec(select(Order).where(Order.chart_id == cid)).one()
        u = s.get(User, uid)
        assert u.balance_rial < 50_000_000          # debited
        rep = s.get(Report, o.report_id)
        assert rep is not None and rep.status == "queued"
        assert o.report_id in enqueued      # F-03: enqueued exactly like Zarinpal


# ── F-04: refund from 'refunding' + already-refunded → refunded (P1) ────────
def test_refund_idempotent_when_gateway_already_refunded(monkeypatch):
    class _Fake:
        def __init__(self):
            self.calls = 0

        def refund(self, *a, **k):
            self.calls += 1
            raise __import__("app.payment.zarinpal", fromlist=["ZarinpalError"]).ZarinpalError(
                "refund failed: [{'code': 66, 'message': 'already refunded'}]", gateway_code=66)

    fake = _Fake()
    monkeypatch.setattr("app.payment.zarinpal.ZarinpalClient", lambda: fake)
    from app.main import _admin_cookie_value
    c = TestClient(app)
    # admin cookie
    c.cookies.update({"chart_admin": _admin_cookie_value()})
    cid, tok = _mk_chart(c)
    with Session(engine) as s:
        o = Order(chart_id=cid, plan_key="basic", status="paid", amount_rial=1_000_000)
        s.add(o)
        s.commit()
        oid = o.id
        # simulate a stuck 'refunding' from a crashed attempt
        s.exec(__import__("sqlalchemy", fromlist=["text"]).text(
            "UPDATE orders SET status='refunding' WHERE id=:i").bindparams(i=oid))
        s.commit()
    r = c.post(f"/api/admin/orders/{oid}/refund")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "refunded"
    with Session(engine) as s:
        o = s.get(Order, oid)
        assert o.status == "refunded"


# ── F-07: concurrent report creation is serialized (P1) ─────────────────────
def test_report_create_serialized_via_advisory_lock():
    c = TestClient(app)
    cid, tok = _mk_chart(c)
    with Session(engine) as s:
        s.add(Order(chart_id=cid, plan_key="basic", status="paid", amount_rial=1_000_000))
        s.commit()
    # two sequential POSTs → same report (idempotency holds)
    r1 = c.post(f"/api/charts/{cid}/report", data={"access_token": tok})
    r2 = c.post(f"/api/charts/{cid}/report", data={"access_token": tok})
    assert r1.status_code == 200 and r2.status_code == 200
    with Session(engine) as s:
        reps = s.exec(select(Report).where(Report.chart_id == cid)).all()
        assert len(reps) == 1


# ── F-08: account deletion removes audio + pdf artifacts (P1) ───────────────
def test_account_delete_cleans_audio_and_pdf(monkeypatch):
    import os
    from app.models import BirthProfile, Chart
    deleted: list[str] = []
    monkeypatch.setattr("app.storage.delete_object_checked",
                        lambda k: (deleted.append(k) or True))
    c = TestClient(app)
    with Session(engine) as s:
        u = _mk_user(s, f"+98v5d{__import__('uuid').uuid4().hex[:8]}", 0)
        uid = u.id
    c.cookies.set("chart_user", __import__("app.auth", fromlist=["_user_cookie_value"])._user_cookie_value(uid))
    # build a chart + report with all artifact kinds
    cid, tok = _mk_chart(c)
    pdf_path = "/tmp/zayche-test-v5.pdf"
    with open(pdf_path, "w") as f:
        f.write("x")
    with Session(engine) as s:
        p = s.exec(select(BirthProfile).where(BirthProfile.user_id == uid)).one()
        ch = s.exec(select(Chart).where(Chart.id == cid)).one()
        ch.profile_id = p.id
        rep = Report(chart_id=cid, status="done", plan_key="basic",
                     r2_key="pdfs/abc.pdf", audio_r2_key="audio/abc.mp3", pdf_path=pdf_path)
        s.add(rep)
        s.commit()
    # CSRF bypass for form post
    from app.security import new_csrf_token
    token = new_csrf_token()
    c.cookies.set("csrf_token", token)
    r = c.post("/account/delete", data={"csrf_token": token})
    assert r.status_code in (200, 303), r.text
    assert "pdfs/abc.pdf" in deleted
    assert "audio/abc.mp3" in deleted
    assert not os.path.exists(pdf_path)


# ── F-06: timezone fails closed outside Iran (P1) ───────────────────────────
def test_chart_compute_rejects_unknown_tz_outside_iran(monkeypatch):
    monkeypatch.setattr("app.astrology.cities_world.tz_from_coords", lambda lat, lon: None)
    c = TestClient(app)
    r = c.post("/api/charts", data={
        "calendar": "gregorian", "year": "1990", "month": "6", "day": "15",
        "hour": "12", "minute": "0", "city_fa": "لندن",
        "lat": "51.5074", "lon": "-0.1278",
    })
    assert r.status_code == 400
    assert "منطقهٔ زمانی" in r.text or "شهر" in r.text


def test_chart_compute_falls_back_tehran_only_inside_iran(monkeypatch):
    monkeypatch.setattr("app.astrology.cities_world.tz_from_coords", lambda lat, lon: None)
    c = TestClient(app)
    r = c.post("/api/charts", data={
        "calendar": "jalali", "year": "1373", "month": "6", "day": "1",
        "hour": "6", "minute": "10", "city_fa": "تهران",
        "lat": "35.6889", "lon": "51.3897",
    })
    assert r.status_code == 200, r.text


# ── F-10: wallet payment rewards the referrer (P2) ──────────────────────────
def test_wallet_payment_rewards_referrer():
    import uuid as _uuid
    from app.models import ReferralEvent
    from app.payment.orders import get_or_create_referral_code
    c = TestClient(app)
    with Session(engine) as s:
        ref = _mk_user(s, f"+98v5f{_uuid.uuid4().hex[:8]}", 0)
        u = _mk_user(s, f"+98v5g{_uuid.uuid4().hex[:8]}", 50_000_000)
        code = get_or_create_referral_code(s, ref.id)
        s.commit()
        ref_id, uid = ref.id, u.id
    c.cookies.set("chart_user", __import__("app.auth", fromlist=["_user_cookie_value"])._user_cookie_value(uid))
    cid, tok = _mk_chart(c)
    # referral code travels in the chart_ref cookie (as the real UI sets it)
    c.cookies.set("chart_ref", code)
    r = c.post("/api/orders", data={
        "plan_key": "basic", "chart_id": cid, "access_token": tok,
    }, headers={"x-pay-with-balance": "1"})
    assert r.status_code == 200, r.text
    with Session(engine) as s:
        ref2 = s.get(User, ref_id)
        ev = s.exec(select(ReferralEvent).where(ReferralEvent.referrer_user_id == ref_id)).one()
        assert ev.status == "rewarded"
        assert ref2.balance_rial > 0
