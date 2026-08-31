"""MASTER W2 — the free preview must answer the user's OWN question.

AC-1: a chart created with the question «آیا شغلم را عوض کنم؟» must show
`question_answer` (LLM, cached forever per chart_id) + 3 patterns each with
evidence + 1 upcoming transit with a date. Second load of the same chart =
ZERO additional LLM calls (permanent Redis cache `freepreview:{chart_id}`).
Brand gate: zero «فال/شانس/پیش‌بینی» words in any produced text.
"""
import asyncio
import json
import os
import uuid

os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:***@127.0.0.1:5432/chart_platform_test")
os.environ["CREATE_ALL_ON_BOOT"] = "1"

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import engine
from app.main import app as main_app
from app.models import BirthProfile, Chart, User


QUESTION = "آیا شغلم را عوض کنم؟"

GOOD_ANSWER_JSON = json.dumps({
    "question_answer": ("چارتت نشان می‌دهد که خورشید در خانهٔ دهم است؛ یعنی مسئلهٔ شغل و جایگاه اجتماعی "
                        "همیشه یکی از فشارهای اصلی زندگی تو بوده. مشتری روی همین نقطه نشسته و رشد از "
                        "راه یادگیری و مهارت تازه برایت آسان‌تر از بقیه جواب داده. تغییر مسیر شغلی برای "
                        "تو بیشتر یک تصمیم لایه‌ای است نه یک پرش کامل؛ اول بخش‌هایی از کار فعلی که با "
                        "کنجکاوی‌ات هم‌خوان است را پررنگ کن."),
    "patterns": [
        {"title": "هویت عمل‌گرا", "text": "خورشید در خانهٔ دهم به هویت تو پیوند مستقیم با کار و مسئولیت می‌دهد؛ احساس ارزش تو با ساختن چیزهای واقعی تغذیه می‌شود.", "evidence": "خورشید در جدی در خانهٔ ۱۰"},
        {"title": "رشد از راه یادگیری", "text": "مشتری فعال در چارتت یعنی هرجا یاد گرفتی، فرصت باز شده؛ این الگو در کل زندگی تکرار شده.", "evidence": "مشتری در سنبله در خانهٔ ۲"},
        {"title": "احساس عمیق", "text": "ماه در خانهٔ هشتم عمق احساسی بالا می‌خواهد و وقتی امنیت داشته باشی، قدرت تحول بزرگی می‌شود.", "evidence": "ماه در عقرب در خانهٔ ۸"},
    ],
}, ensure_ascii=False)


class FakeResult:
    def __init__(self, text):
        self.text = text
        self.ok = True
        self.provider = "fake"
        self.model = "fake"
        self.usage = type("U", (), {"total": 100, "prompt_tokens": 60, "completion_tokens": 40})()
        self.cost = 0.0
        self.error = None
        self.latency_ms = 10


class CountingRouter:
    """Counts every complete() call so the test can prove cache = zero calls."""
    calls = 0

    def __init__(self, text=GOOD_ANSWER_JSON):
        self._text = text

    async def complete(self, prompt, **kw):
        CountingRouter.calls += 1
        assert QUESTION in prompt, "the LLM prompt must contain the user's own question"
        return FakeResult(self._text)


def _mk_user() -> tuple[str, str]:
    uid = "u" + uuid.uuid4().hex[:10]
    with Session(engine) as s:
        s.add(User(id=uid, phone=uid + "@w2", credits=0)); s.commit()
        p = BirthProfile(user_id=uid, name="تست", raw_year=1373, raw_month=6, raw_day=1,
                         time_known=True, hour=6, minute=10, city_fa="تهران",
                         lat=35.6892, lon=51.3890,
                         focus_areas=["شغل", "پول"], personal_question=QUESTION)
        s.add(p)
        s.flush()  # assign p.id before the Chart references it (FK)
        ch = Chart(profile_id=p.id, chart_json={
            "birth": {"time_known": True},
            "planets": {
                "Sun": {"longitude": 270.0, "sign_index": 9, "sign_en": "Capricorn",
                        "sign_fa": "جدی", "house": 10, "degree": 3},
                "Moon": {"longitude": 220.0, "sign_index": 7, "sign_en": "Scorpio",
                         "sign_fa": "عقرب", "house": 8, "degree": 10},
                "Mercury": {"longitude": 160.0, "sign_index": 5, "sign_en": "Virgo",
                            "sign_fa": "سنبله", "house": 2, "degree": 10},
            },
            "angles": {"ASC": {"longitude": 100.0, "sign_index": 3, "sign_en": "Cancer",
                               "sign_fa": "سرطان"}},
            "elements": {"Fire": 2, "Earth": 4, "Air": 1, "Water": 3},
            "modalities": {"Cardinal": 4, "Fixed": 2, "Mutable": 4},
            "aspects": [], "moon_phase": "Waxing",
        }, access_token="tok" + uuid.uuid4().hex[:16])
        s.add(ch)
        s.commit(); s.refresh(p); s.refresh(ch)
        return uid, ch.id


def _client_with_chart(cid: str) -> TestClient:
    c = TestClient(main_app, base_url="https://testserver")
    with Session(engine) as s:
        ch = s.get(Chart, cid)
        assert ch is not None, "chart fixture missing"
    # query-param capability token (same path the UI uses)
    return c


def _flush_cache(cid: str) -> None:
    import app.main as m
    try:
        import redis.asyncio as ra
        r = ra.from_url(m._REDIS_URL, decode_responses=True)
        asyncio.get_event_loop().run_until_complete(_del(r, f"freepreview:{cid}"))
    except Exception:  # noqa: BLE001 — tests must not depend on Redis being up
        pass


async def _del(r, key):
    await r.delete(key)
    await r.aclose()


def _client_as_user(uid: str, cid: str) -> TestClient:
    """Logged-in owner client (chart_access cookie also set)."""
    from app.auth import _user_cookie_value
    c = TestClient(main_app, base_url="https://testserver")
    c.cookies.set("chart_user", _user_cookie_value(uid))
    with Session(engine) as s:
        ch = s.get(Chart, cid)
        assert ch is not None, "chart fixture missing"
        tok = ch.access_token or ""
    if tok:
        c.cookies.set("chart_access", json.dumps({cid: tok}))
    return c


def test_w2_preview_answers_the_users_question(monkeypatch):
    uid, cid = _mk_user()
    monkeypatch.setenv("ENRICH_INSIGHTS", "1")  # conftest disables it globally
    monkeypatch.setattr("app.core.llm.build_router", lambda part="report": CountingRouter())
    c = _client_as_user(uid, cid)
    _flush_cache(cid)
    r = c.get(f"/api/charts/{cid}/preview")
    assert r.status_code == 200, r.text
    d = r.json()
    # 1 — the question is actually answered
    assert d.get("question_answer"), "free preview must contain an answer to the user's question"
    assert d.get("personal_question") == QUESTION
    # 2 — exactly 3 dominant patterns, each with astrological evidence
    pats = d.get("patterns") or []
    assert len(pats) == 3, f"expected 3 patterns, got {len(pats)}"
    for p in pats:
        assert p["evidence"], f"pattern without evidence: {p}"
        assert len(p.get("text") or p["insight"]) > 40
    # 3 — one upcoming transit WITH a date
    nt = d.get("next_transit")
    assert nt and nt["date"].count("-") == 2, "next transit teaser needs a real date"
    assert nt["headline"]
    # 4 — element distribution present
    es = d.get("element_summary")
    assert es and es.get("line"), "element summary line missing"
    # brand gate on everything we produce
    blob = json.dumps(d, ensure_ascii=False)
    for bad in ("فال", "شانس", "پیشگویی", "مقدر", "قطعاً"):
        assert bad not in blob, f"forbidden word in free preview: {bad}"


def test_w2_second_load_costs_zero_llm_calls(monkeypatch):
    uid, cid = _mk_user()
    monkeypatch.setenv("ENRICH_INSIGHTS", "1")  # conftest disables it globally
    monkeypatch.setattr("app.core.llm.build_router", lambda part="report": CountingRouter())
    c = _client_as_user(uid, cid)
    _flush_cache(cid)
    before = CountingRouter.calls
    r1 = c.get(f"/api/charts/{cid}/preview")
    after_first = CountingRouter.calls
    assert r1.json().get("enriched"), "first load should be enriched (LLM)"
    r2 = c.get(f"/api/charts/{cid}/preview")
    d2 = r2.json()
    assert d2.get("cached") is True, "second load must come from the permanent cache"
    assert CountingRouter.calls == after_first == before + 1, \
        f"cache failed: calls before={before} after-first={after_first} final={CountingRouter.calls}"


def test_w2_no_question_keeps_deterministic_baseline(monkeypatch):
    """A chart without personal_question must still get patterns/transit/elements."""
    from app.report.preview import free_insights
    chart_json = {
        "birth": {"time_known": True},
        "planets": {
            "Sun": {"longitude": 147.0, "sign_index": 4, "sign_en": "Leo",
                    "sign_fa": "اسد", "house": 1, "degree": 27},
            "Moon": {"longitude": 320.0, "sign_index": 10, "sign_en": "Aquarius",
                     "sign_fa": "دلو", "house": 11, "degree": 20},
            "Mercury": {"longitude": 120.0, "sign_index": 3, "sign_en": "Cancer",
                        "sign_fa": "سرطان", "house": 12, "degree": 0},
        },
        "angles": {"ASC": {"longitude": 135.0, "sign_index": 4, "sign_en": "Leo",
                           "sign_fa": "اسد"}},
        "elements": {"Fire": 3, "Earth": 2, "Air": 2, "Water": 3},
        "modalities": {"Cardinal": 2, "Fixed": 4, "Mutable": 4},
        "aspects": [], "moon_phase": "Full",
    }
    r = free_insights(chart_json)
    assert len(r["patterns"]) == 3
    assert all(p["evidence"] for p in r["patterns"])
    assert r["next_transit"] is None or r["next_transit"]["date"]
    assert r["full_report_teaser"]


def test_w2_forbidden_llm_text_is_rejected():
    """The QA gate must refuse divination-flavoured answers (brand rule)."""
    from app.report.preview import _qa_ok
    assert not _qa_ok("این کار یعنی مقدر است که شغلت عوض شود.")
    assert not _qa_ok("به‌زودی اتفاق می‌افتد.")
    assert _qa_ok("چارتت گرایش تو به ساختارهای مشخص را نشان می‌دهد.")
