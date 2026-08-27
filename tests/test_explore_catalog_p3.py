"""ZAYCHE P3 (D6) — self-discovery catalog tests.

Coverage: catalog contract (10 cards, valid domains), financial integrity
(atomic 1-credit deduction, ledger rows, insufficient → 402, refund on
failed generation, no double spend), API guards (auth, ownership/IDOR,
invalid card, rate limit), and the QA gate on generated content.
"""
from __future__ import annotations

import asyncio
import os
import uuid

os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ.setdefault("RATE_LIMIT_BACKEND", "memory")

import json  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import BirthProfile, Chart, CreditTransaction, Exploration, User  # noqa: E402

SUF = uuid.uuid4().hex[:6]

GOOD_JSON = json.dumps({
    "intro": "پاسخ کلی این است که الگوی اصلی شخصیت تو ترکیبی از درون‌نگری و کنش عملی است که در ادامه به تفصیل می‌آید و قابل بررسی است.",
    "insights": [
        {"insight": "خورشید در برج اسد نشان می‌دهد که هستهٔ انگیزشی تو بر ابراز وجود و گرما استوار است. این انرژی وقتی با ماه در خانهٔ هشتم ترکیب می‌شود، به عمق احساسی و کنجکاوی درونی تبدیل می‌شود. تو معمولاً وقتی امنیت عاطفی داری، خلاقیتت چند برابر می‌شود. در مقابل، بی‌توجهی به نیازهای احساسی می‌تواند تو را محتاط و سرد کند. این الگو در طول زندگی پایدار است و با شناخت آن می‌توانی تعادل بهتری بین احساس و عمل برقرار کنی. در کارهای گروهی هم این ترکیب به تو نقش طبیعی رهبری عاطفی می‌دهد.",
         "evidence": ["Sun in Leo", "ASC in Leo"],
         "practical_advice": "امروز ده دقیقه به یک خواستهٔ شخصی فکر کن و آن را روی کاغذ بنویس."},
        {"insight": "طالع تو در برج اسد قرار دارد و این یعنی اولین تأثیری که بر دیگران می‌گذاری گرم و صریح است. عطارد در خانهٔ سوم هم به تو توانایی بیان سریع و شیرین می‌دهد. این ترکیب تو را در گفت‌وگوهای گروهی فعال و تأثیرگذار می‌کند. فقط مراقب باش سرعت بیان، شنیدن را قربانی نکند. این توانایی یک دارایی پایدار در ارتباطات توست و با تمرین می‌توانی از آن در موقعیت‌های حرفه‌ای هم استفاده کنی. تو معمولاً حرف خودت را با اعتماد به نفس می‌زنی و این برای دیگران جذاب است.",
         "evidence": ["ASC in Leo", "Mercury in 3rd house"],
         "practical_advice": "در گفت‌وگوی بعدی، پیش از پاسخ دادن دو ثانیه مکث کن."},
    ],
}, ensure_ascii=False)


TEST_CHART = {
    "birth": {"time_known": True},
    "planets": {
        "Sun": {"longitude": 147.5, "sign": "Leo", "house": 1},
        "Moon": {"longitude": 320.0, "sign": "Pisces", "house": 8},
        "Mercury": {"longitude": 120.0, "sign": "Gemini", "house": 3},
    },
    "angles": {"ASC": {"longitude": 135.0}},
}


class FakeResult:
    def __init__(self, text, ok=True, provider="fake", model="fake", usage=None,
                 cost=0.0, error=None, latency_ms=10):
        self.text = text
        self.ok = ok
        self.provider = provider
        self.model = model
        self.usage = type("U", (), {"total": 100, "prompt_tokens": 60, "completion_tokens": 40})()
        self.cost = cost
        self.error = error
        self.latency_ms = latency_ms


class FakeRouter:
    """Deterministic LLM router: scripted texts per call, then GOOD_JSON."""
    def __init__(self, texts=None):
        self._texts = list(texts or [])
        self.calls = 0

    async def complete(self, prompt, **kw):
        self.calls += 1
        if self._texts:
            return FakeResult(self._texts.pop(0))
        return FakeResult(GOOD_JSON)


def _mk_user(c) -> str:
    from app.auth import _user_cookie_value
    phone = f"+98p3{SUF}{uuid.uuid4().hex[:6]}"
    with Session(engine) as s:
        u = User(phone=phone, credits=5)
        s.add(u)
        s.commit()
        uid = u.id
    c.cookies.set("chart_user", _user_cookie_value(uid))
    return uid


def _mk_chart(uid: str) -> str:
    with Session(engine) as s:
        p = BirthProfile(user_id=uid, name="تست", raw_year=1373, raw_month=6, raw_day=1,
                         time_known=True, hour=6, minute=10, city_fa="تهران",
                         lat=35.6892, lon=51.3890)
        s.add(p)
        s.commit()
        s.refresh(p)
        ch = Chart(profile_id=p.id, user_id=uid, chart_json=TEST_CHART)
        s.add(ch)
        s.commit()
        s.refresh(ch)
        return ch.id


def _ledger(uid: str) -> list[CreditTransaction]:
    with Session(engine) as s:
        return list(s.exec(select(CreditTransaction).where(CreditTransaction.user_id == uid)).all())


def _credit_balance(uid: str) -> int:
    with Session(engine) as s:
        return s.get(User, uid).credits


# ── catalog (D1/D2) ─────────────────────────────────────────────────────────
def test_catalog_has_ten_cards_with_contract():
    from app.explore.cards import CARD_CATALOG, CARD_MAP
    from app.report.rules import DOMAINS
    assert len(CARD_CATALOG) == 10
    assert len(CARD_MAP) == 10
    for c in CARD_CATALOG:
        assert c.key and c.title_fa and c.benefit_fa and c.question_fa
        assert c.domains, f"{c.key}: no domains"
        for d in c.domains:
            assert d in DOMAINS, f"{c.key}: unknown domain {d}"


def test_catalog_endpoint_public():
    c = TestClient(app)
    r = c.get("/api/explore/cards")
    assert r.status_code == 200
    cards = r.json()["cards"]
    assert len(cards) == 10
    assert all({"key", "title_fa", "benefit_fa"} <= set(k) for k in cards)


# ── API guards (D6) ─────────────────────────────────────────────────────────
def test_explore_requires_auth():
    c = TestClient(app)
    # real user exists but NO cookie set → must be 401
    with Session(engine) as s:
        u = User(phone=f"+98p3na{uuid.uuid4().hex[:6]}")
        s.add(u)
        s.commit()
        cid = _mk_chart(u.id)
    r = c.post("/api/explore/personality", data={"chart_id": cid})
    assert r.status_code == 401


def _mk_ghost_user() -> str:
    """A real user we never log in as (no cookie) — for negative tests."""
    with Session(engine) as s:
        u = User(phone=f"+98p3gh{uuid.uuid4().hex[:6]}")
        s.add(u)
        s.commit()
        return u.id


def test_explore_invalid_card():
    c = TestClient(app)
    _mk_user(c)
    cid = _mk_chart(_mk_ghost_user())
    r = c.post("/api/explore/not-a-card", data={"chart_id": cid})
    assert r.status_code == 404


def test_explore_ownership_required():
    """Bare UUID of someone else's chart must NOT consume credits (IDOR)."""
    c = TestClient(app)
    uid = _mk_user(c)
    other = _mk_chart(_mk_ghost_user())
    r = c.post("/api/explore/personality", data={"chart_id": other})
    assert r.status_code == 403
    assert _credit_balance(uid) == 5  # untouched


# ── financial integrity (D5) ────────────────────────────────────────────────
def test_explore_spends_one_credit_atomically(monkeypatch):
    c = TestClient(app)
    uid = _mk_user(c)
    cid = _mk_chart(uid)
    monkeypatch.setattr("app.core.llm.build_chat_router", lambda: FakeRouter())

    r = c.post("/api/explore/personality", data={"chart_id": cid})
    assert r.status_code == 200
    body = r.text
    assert "event: done" in body
    assert _credit_balance(uid) == 4
    tx = _ledger(uid)
    assert len(tx) == 1 and tx[0].amount == -1 and tx[0].reason == "explore_card"
    with Session(engine) as s:
        e = s.exec(select(Exploration).where(Exploration.user_id == uid)).first()
        assert e.status == "done"
        assert e.credits_cost == 1
        assert len(e.result["insights"]) >= 2
        assert e.metrics["calls"] == 1


def test_explore_insufficient_credit_is_402_no_negative(monkeypatch):
    """D5 — broke AND free-exploration already used → 402, never negative."""
    c = TestClient(app)
    uid = _mk_user(c)
    with Session(engine) as s:
        u = s.get(User, uid)
        u.credits = 0
        u.free_exploration_used = True  # freebie already consumed
        s.commit()
    cid = _mk_chart(uid)
    monkeypatch.setattr("app.core.llm.build_chat_router", lambda: FakeRouter())
    r = c.post("/api/explore/personality", data={"chart_id": cid})
    assert r.status_code == 402
    assert _credit_balance(uid) == 0  # never negative
    assert _ledger(uid) == []  # no ledger row for the failed spend


def test_explore_refund_on_failed_generation(monkeypatch):
    c = TestClient(app)
    uid = _mk_user(c)
    cid = _mk_chart(uid)
    # router that always fails → generation exhausts retries → auto refund
    bad = FakeResult("not json at all", ok=False, error="boom")
    monkeypatch.setattr("app.core.llm.build_chat_router", lambda: FakeRouter([bad] * 10))
    r = c.post("/api/explore/personality", data={"chart_id": cid})
    assert r.status_code == 200
    assert "event: error" in r.text
    assert _credit_balance(uid) == 5  # refunded back to original
    with Session(engine) as s:
        e = s.exec(select(Exploration).where(Exploration.user_id == uid)).first()
        assert e.status == "failed" and e.refunded is True
    tx = [t.reason for t in _ledger(uid)]
    assert tx.count("explore_card") == 1 and tx.count("failed_generation") == 1


def test_explore_no_double_spend_when_stream_dies(monkeypatch):
    """A generation that raises mid-stream must refund exactly once."""
    class BoomRouter:
        async def complete(self, prompt, **kw):
            raise RuntimeError("connection reset")

    c = TestClient(app)
    uid = _mk_user(c)
    cid = _mk_chart(uid)
    monkeypatch.setattr("app.core.llm.build_chat_router", BoomRouter)
    r = c.post("/api/explore/personality", data={"chart_id": cid})
    assert r.status_code == 200
    assert "event: error" in r.text
    assert _credit_balance(uid) == 5
    tx = [t.reason for t in _ledger(uid)]
    assert tx.count("explore_card") == 1 and tx.count("failed_generation") == 1


# ── history & delete (D3) ───────────────────────────────────────────────────
def test_explore_history_only_own_rows(monkeypatch):
    c = TestClient(app)
    uid = _mk_user(c)
    cid = _mk_chart(uid)
    monkeypatch.setattr("app.core.llm.build_chat_router", lambda: FakeRouter())
    c.post("/api/explore/personality", data={"chart_id": cid})
    c.post("/api/explore/career", data={"chart_id": cid})

    r = c.get("/api/explore/history")
    assert r.status_code == 200
    keys = {i["card_key"] for i in r.json()["items"]}
    assert keys == {"personality", "career"}

    # a second user sees nothing
    c2 = TestClient(app)
    uid2 = _mk_user(c2)
    _mk_chart(uid2)
    r2 = c2.get("/api/explore/history")
    assert r2.json()["items"] == []


def test_explore_delete_own_only():
    c = TestClient(app)
    uid = _mk_user(c)
    with Session(engine) as s:
        e = Exploration(user_id=uid, card_key="personality", status="done",
                        result={"insights": []})
        s.add(e)
        s.commit()
        eid = e.id
    # another user cannot delete it
    c2 = TestClient(app)
    _mk_user(c2)
    assert c2.delete(f"/api/explore/{eid}").status_code == 404
    # owner can
    assert c.delete(f"/api/explore/{eid}").status_code == 200
    assert c.delete(f"/api/explore/{eid}").status_code == 404


# ── generation & QA (D3) ────────────────────────────────────────────────────
def test_generate_passes_qa_and_returns_metrics():
    from app.explore.cards import CARD_MAP
    from app.explore.service import generate_exploration
    chart = TEST_CHART
    result, metrics = asyncio.run(generate_exploration(FakeRouter(), chart, CARD_MAP["personality"]))
    assert result is not None
    assert len(result["insights"]) >= 2
    assert metrics["calls"] == 1
    assert metrics["retries"] == 0
    assert metrics["duration_s"] >= 0


def test_generate_retries_on_banned_words_then_recovers():
    from app.explore.cards import CARD_MAP
    from app.explore.service import generate_exploration
    chart = TEST_CHART
    banned = GOOD_JSON.replace("این الگو در طول زندگی پایدار است",
                               "این الگو نشان می‌دهد قطعاً موفق خواهد شد")
    router = FakeRouter([banned, banned, GOOD_JSON])
    result, metrics = asyncio.run(generate_exploration(router, chart, CARD_MAP["personality"]))
    assert result is not None
    assert metrics["calls"] == 3
    assert metrics["qa_failures"] == 2
    assert metrics["retries"] == 2


def test_build_prompt_only_uses_card_domains():
    from app.explore.cards import CARD_MAP
    from app.explore.service import build_explore_prompt
    chart = TEST_CHART
    prompt, ctx = build_explore_prompt(chart, CARD_MAP["money"])
    assert set(ctx["domains"]) == {"money"}  # only allowed domains
    assert "سؤال کاربر" in prompt and "عوامل فعال" in prompt


def test_qa_accepts_persian_and_invisible_char_evidence():
    """Prod bug 2026-08-26 — explore QA rejected the model's Persian evidence
    («خورشید», «طالع», «عطارد») because the whitelist holds canonical English
    names; every card then failed all 5 QA retries and the user saw nothing.
    Evidence must be normalized (invisible chars + Persian→English) first."""
    from app.explore.cards import CARD_MAP
    from app.explore.service import qa_explore
    chart = TEST_CHART
    card = CARD_MAP["personality"]
    long_i1 = "این الگو در طول زندگی پایدار است و هویت اصلی تو را می‌سازد؛ خورشید در این ترکیب نقش مرکزی دارد و هر تصمیم بزرگ تو را جهت می‌دهد و به آن معنا می‌بخشد."
    long_i2 = "طالع تو لایهٔ بیرونی شخصیت را نشان می‌دهد و عطارد شیوهٔ پردازش ذهنی‌ات را؛ این سه با هم تصویر کامل‌تری از شخصیت می‌سازند و در روابط و کار هم دیده می‌شوند."
    base = {
        "intro": "بررسی شخصیت تو بر پایهٔ خورشید، طالع و عطارد انجام شد و الگوی اصلی آن روشن شد.",
        "insights": [
            {"insight": long_i1, "practical_advice": "با تمرکز روی این الگو تصمیم‌های بهتری می‌گیری.",
             "evidence": ["خورشید در \u200cاسد", "Sun in Leo"]},
            {"insight": long_i2, "practical_advice": "از این شناخت در تعاملات روزانه استفاده کن.",
             "evidence": ["طالع/ASC", "عطارد", "Mercury"]},
        ],
    }
    errs = qa_explore(base, chart, card)
    # only a *genuine* off-card factor (Moon) must trip the whitelist
    assert not any("خارج از عوامل" in e for e in errs), errs


# ── F5 funnel: first exploration free (loss aversion) ───────────────────────
def test_first_exploration_free_when_broke(monkeypatch):
    """F5 — 0-credit user gets ONE free exploration, then 402."""
    c = TestClient(app)
    uid = _mk_user(c)
    with Session(engine) as s:
        u = s.get(User, uid)
        u.credits = 0
        s.commit()
    cid = _mk_chart(uid)
    monkeypatch.setattr("app.core.llm.build_chat_router",
                        lambda: FakeRouter([GOOD_JSON]))
    r = c.post("/api/explore/personality", data={"chart_id": cid})
    assert r.status_code == 200 and "event: done" in r.text
    with Session(engine) as s:
        u = s.get(User, uid)
        assert u.credits == 0 and u.free_exploration_used is True
        free_rows = s.exec(select(CreditTransaction).where(
            CreditTransaction.reason == "free_exploration",
            CreditTransaction.user_id == uid)).all()
        assert len(free_rows) == 1 and free_rows[0].amount == 0
    r2 = c.post("/api/explore/personality", data={"chart_id": cid})
    assert r2.status_code == 402


def test_free_exploration_failure_grants_no_refund(monkeypatch):
    """F5 — a failed free exploration must NOT mint credits, AND must NOT burn
    the user's one-time freebie (prod bug 2026-08-26: generation failed →
    free_exploration_used stayed true → every later click was a silent 402)."""
    c = TestClient(app)
    uid = _mk_user(c)
    with Session(engine) as s:
        u = s.get(User, uid)
        u.credits = 0
        s.commit()
    cid = _mk_chart(uid)
    bad = FakeResult("not json at all", ok=False, error="boom")
    monkeypatch.setattr("app.core.llm.build_chat_router",
                        lambda: FakeRouter([bad] * 10))
    r = c.post("/api/explore/personality", data={"chart_id": cid})
    assert r.status_code == 200 and "event: error" in r.text
    with Session(engine) as s:
        u = s.get(User, uid)
        assert u.credits == 0  # nothing minted
        assert u.free_exploration_used is False  # restored — freebie NOT burned
