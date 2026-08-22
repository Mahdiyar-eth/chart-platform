"""B2 — transit narrative layer acceptance tests (LLM mocked → $0, no live network)."""
import os, types, json
os.environ.setdefault("SWISSEPH_EPHE_PATH", "/root/chart-platform/ephe")
from datetime import datetime, timezone
from sqlmodel import Session
from app.db import engine
from app.astrology.engine import compute_from_fields, ensure_ephe
from app.astrology.golden_data import GOLDEN_CHARTS
from app.report.transit_narrative import (
    narrate_transit, transit_user_prompt, B2_RULES, MAX_RETRIES,
)


def _chart():
    ensure_ephe()
    return compute_from_fields(**GOLDEN_CHARTS[0]["birth"]).chart_json


def _event(name="e1", target="خورشید", weight=5.0, planet="مشتری", aspect="همنشینی"):
    return {
        "id": name, "transit_planet": "Jupiter", "transit_planet_fa": planet,
        "natal_target": "Sun", "natal_target_fa": target,
        "aspect": "conjunction", "aspect_fa": aspect,
        "window_start": "2026-10-01", "window_end": "2026-12-15",
        "exact_dates": ["2026-11-06T14:10:00Z", "2027-01-18T09:00:00Z"],
        "natal_house": 3, "transit_sign_fa": "قوس", "weight": weight,
    }


def _make_narrative(target="خورشید"):
    return {
        "headline": f"زحلِ گذرکننده در {target}ِ تولد تو — یک پنجرهٔ تأمل",
        "what_it_means": f"گذرِ زحل در همنشینی با {target}ِ تولد، از ۱۰ مهر تا ۲۵ آذر، "
                         f"تو را به ساده‌کردن و مرور بنیادها دعوت می‌کند. این یک دورهٔ درونی است.",
        "reflection_question": "اگر فقط یک تعهد را در این بازه سبک‌تر کنی، کدام است؟",
        "window_text": f"بازهٔ تقریبی از ۲۰۲۶-۱۰-۰۱ تا ۲۰۲۶-۱۲-۱۵، با گذرهای دقیق در آبان و دی.",
    }


def _router(outputs):
    """Fake router whose .complete is async (mirrors await style of the LLM router)."""
    class _R:
        def __init__(self, out):
            self.out = list(out); self.n = 0
        async def complete(self, prompt, system=None, max_tokens=None,
                           temperature=None, json_mode=None, **_k):
            txt = self.out[min(self.n, len(self.out) - 1)]
            self.n += 1
            return types.SimpleNamespace(
                ok=True, text=txt, usage=types.SimpleNamespace(total=120),
                cost=0.0011, provider="mock")
    return _R(outputs)


def _valid_text(target="خورشید"):
    return json.dumps(_make_narrative(target), ensure_ascii=False)


# B2 rules present in the prompt (test asserts the checklist)
def test_1_prompt_obeys_mandatory_rules():
    p = transit_user_prompt(_event(), _chart())
    assert "ممنوع" in p and "قطع" in p
    assert "تأمل" in p
    assert "یک سؤال تأمل در پایان" in p or "reflection" in p.lower()
    assert "خورشید" in p and "مشتری" in p  # evidence anchor


def test_2_prompt_contains_event_evidence():
    p = transit_user_prompt(_event(), _chart())
    assert "مشتری" in p and "خورشید" in p and "همنشینی" in p
    assert "2026-10-01" in p and "2026-12-15" in p


def test_3_narrate_returns_4_fields():
    cj = _chart()
    evs = [_event("a", weight=9.0)]
    out, m = narrate_transit(evs, cj, router=_router([_valid_text()]))
    assert len(out) == 1
    for k in ("headline", "what_it_means", "reflection_question", "window_text"):
        assert str(out[0].get(k) or "").strip()
    assert m["refunded"] == 0 and m["calls"] == 1


def test_4_qa_fail_then_retry_succeeds():
    cj = _chart()
    bad = json.dumps({"headline": "قطعی است که تو ارتقا خواهی گرفت", "what_it_means": "قطعی است", "reflection_question": "x", "window_text": "x"}, ensure_ascii=False)
    evs = [_event(weight=9.0)]
    out, m = narrate_transit(evs, cj, router=_router([bad, _valid_text()]))
    assert len(out) == 1, "QA fail then retry should still produce a (corrected) narrative"
    assert m["retries"] >= 1 and m["calls"] >= 2


def test_5_double_fail_refunds():
    cj = _chart()
    bad = json.dumps({"headline": "قطعی است که تو ارتقا خواهی گرفت", "what_it_means": "قطعی است که موفق خواهی شد", "reflection_question": "x", "window_text": "x"}, ensure_ascii=False)
    evs = [_event(weight=9.0)]
    refunded = {"n": 0}
    out, m = narrate_transit(evs, cj, router=_router([bad, bad]),
                             on_event_failed=lambda e: refunded.__setitem__("n", refunded["n"] + 1))
    assert m["refunded"] == 1, "double QA-fail must refund the event"
    assert refunded["n"] == 1, "refund hook must fire"
    assert len(out) == 0


def test_6_top_5_vs_12_selection():
    cj = _chart()
    evs = [_event(f"e{i}", weight=float(i)) for i in range(1, 16)]
    out3, m3 = narrate_transit(evs, cj, router=_router([_valid_text()]), plan_key="transit_3m")
    out12, m12 = narrate_transit(evs, cj, router=_router([_valid_text()]), plan_key="transit_12m")
    assert {e["event"]["id"] for e in out3} == {f"e{i}" for i in range(15, 10, -1)}
    assert len(out3) == 5 and len(out12) == 12
    assert m3["events"] == 5 and m12["events"] == 12