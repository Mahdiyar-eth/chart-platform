"""B2 — transit narrative layer (LLM, evidence-constrained).

For each top transit event (from the B1 engine) plus chart data, generate a
Persian narrative {headline, what_it_means, reflection_question, window_text}
that CITES the astronomical evidence and never promises definite external
events, using the same grounded 3-step chain (fact → causal → personal) as the
report sections. The router (omni) is injectable, so the whole layer is fully
testable with a mock at $0 cost.
"""
from __future__ import annotations

import logging

from app.core.llm import build_router
import re as _re
from app.report.qa import FORBIDDEN_PATTERNS, parse_section
from app.report.claim_validation import critical_facts, validate_section
from app.chat.retrieval import CHAT_SYSTEM_PROMPT

log = logging.getLogger("transit_narrative")

# B2 QA gate: 1 retry then double-fail ⇒ refund (transit_3m / transit_12m credit).
MAX_RETRIES = 1
MAX_TOKENS = 640

# ── B2 mandatory prompt rules (checklist that tests assert the prompt contains) ──
B2_RULES = [
    ("ممنوع", "جملهٔ قطعی دربارهٔ آینده"),
    ("ممنوع", "وعدهٔ رویداد بیرونی"),
    ("الزامی", "زبان تأملی و دعوت‌کننده"),
    ("الزامی", "یک سؤال تأمل در پایان"),
    ("الزامی", "شاهد نجومی در هر بند (سیاره‌ی گذر + جنبه + سیاره‌ی تولد + بازه‌ی شمسی)"),
]

JSON_SCHEMA = (
    "خروجی را دقیقاً یک JSON با این کلیدها بده (بدون متن اضافه): "
    "headline, what_it_means, reflection_question, window_text"
)


def _event_evidence(ev) -> str:
    """A single-line astronomical fact string for the event (the evidence anchor)."""
    def _s(x):
        if isinstance(x, list):
            return ", ".join(str(v) for v in x[:3])
        return str(x)

    return (
        f"گذر {ev.get('transit_planet_fa', ev.get('transit_planet',''))} "
        f"در جنبه‌ی {ev.get('aspect_fa', ev.get('aspect',''))} "
        f"با {ev.get('natal_target_fa', ev.get('natal_target',''))} تولد "
        f"خانم/آقا — خانه‌ی {ev.get('natal_house')} ، "
        f"در برج {ev.get('transit_sign_fa','')} ، بازه‌ی تقریبی از {ev.get('window_start','')} "
        f"تا {ev.get('window_end','')} (گذرهای دقیق: {_s(ev.get('exact_dates'))})"
    )


def transit_user_prompt(ev, chart, rag_context: str | None = None) -> str:
    """Build the per-event user prompt honoring the B2 mandatory rules."""
    facts = ""
    try:
        facts = "\n".join(f"- {a}: {b}" for a, b in critical_facts(chart)[:6])
    except Exception:  # noqa: BLE001 — never let facts building break the prompt
        log.warning("critical_facts failed for transit narrative", exc_info=True)
    rag = f"\nبافت RAG (فقط اگر مرتبط بود استفاده کن):\n{rag_context}" if rag_context else ""
    return (
        f"شواهد نجومی این رویداد گذر:\n{_event_evidence(ev)}\n\n"
        f"شواهد پایه‌ی چارت تولد:\n{facts}{rag}\n\n"
        "قوانین اجباری:\n"
        "- هر بند باید شاهد نجومی ذکر کند: «سیاره‌ی گذرکننده در فلان جنبه با فلان سیاره/نقطه‌ی تولدِ تو، از فلان تاریخ تا فلان تاریخ». فقط از شواهد بالا استفاده کن.\n"
        "- ممنوع: جمله‌ی قطعی درباره‌ی آینده؛ ممنوع: وعده‌ی رویداد بیرونی (مثل «شغل جدید می‌گیری»).\n"
        "- الزامی: زبان تأملی و دعوت‌کننده + یک سؤال تأمل در پایان.\n"
        "- زنجیرهٔ سه‌مرحله‌ای: اول واقعیتِ نجومی، بعد پیوندِ علّیِ احتمالی، بعد تفسیرِ شخصیِ محتاطانه.\n\n"
        f"{JSON_SCHEMA}"
    )


def _system_prompt() -> str:
    return (
        CHAT_SYSTEM_PROMPT
        + "\n\n[گذر] تو متخصص اخترشناسیِ تأملی‌ات؛ به همان گیتِ توهمِ چرخه‌ی گزارش پایبند باش. "
        "هرگز رویداد بیرونیِ قطعی وعده نده؛ فقط شواهد نجومی واقعی + احتمالِ تأملی + سؤالِ تأمل."
    )


def _complete(router, user: str, system: str, max_tokens: int = MAX_TOKENS):
    import asyncio
    return asyncio.run(
        router.complete(user, system=system, max_tokens=max_tokens, temperature=0.6, json_mode=True)
    )


_REQ_KEYS = ("headline", "what_it_means", "reflection_question", "window_text")


def _free_narrative(parsed) -> str:
    return _re.sub(r"\u200c", "", " ".join(str(parsed.get(k) or "") for k in _REQ_KEYS))


def _validate(parsed: dict | None, text: str, chart: dict, event: dict | None = None) -> list[str]:
    """Same hallucination gate as the report sections (C-04), adapted to the
    4-field transit schema: structure + forbidden-pattern ban + grounded target.
    """
    if parsed is None:
        return ["خروجی JSON نامعتبر است"]
    errors = []
    missing = [k for k in _REQ_KEYS if not str(parsed.get(k) or "").strip()]
    if missing:
        errors.append(f"فیلدهای جاافتاده: {missing}")
    body = _free_narrative(parsed)
    # qa.py ban (no definite-future / external-promise / death / medical)
    for pat in FORBIDDEN_PATTERNS:
        if _re.search(pat, body):
            errors.append("عبارت ممنوع در روایت گذر")
            break
    # claim_validation grounding — only critical hallucination fails (a transit
    # planet sign is not a natal claim, so the transit-planet grounded=False is
    # ignored and cannot false-fail a correct narrative).
    try:
        rep = validate_section("transit", text, chart)
        if getattr(rep, "critical_hallucination", False):
            errors.append("claim-gate: توهم انتقادی")
    except Exception as e:  # noqa: BLE001
        errors.append(f"claim-gate error: {e}")
    # anchor to the real event target (rejects narratives that drift off-target)
    target = (event or {}).get("natal_target_fa") or (event or {}).get("natal_target")
    if target:
        target = _re.sub(r"\u200c", "", str(target))
        if target and target not in body:
            errors.append("روایت به هدف نجومی رویداد لنگر نشده است")
    return errors


def narrate_transit(events, chart, router=None, rag_context: str | None = None,
                    plan_key: str = "transit_12m", on_event_failed=None):
    """Generate narratives for the N top events (3m→5, 12m→12). QA-gate with
    1 retry; on double-fail raises the `on_event_failed` hook (B3 wires it to a
    credit refund) and bumps metrics['refunded']. Router is injectable ($0 tests).
    """
    router = router or build_router("transit")
    system = _system_prompt()
    n = 12 if "12" in str(plan_key) else 5
    top = sorted(events, key=lambda e: -float(e.get("weight", 0)))[:n]
    narratives = []
    metrics = {"calls": 0, "retries": 0, "total_tokens": 0, "cost_usd": 0.0,
               "qa_failures": 0, "refunded": 0, "provider": set(), "events": len(top)}
    for ev in top:
        user = transit_user_prompt(ev, chart, rag_context)
        ok = False
        for attempt in range(MAX_RETRIES + 1):
            try:
                res = _complete(router, user, system)
            except Exception as e:  # noqa: BLE001
                log.warning("transit LLM call failed (attempt %d): %s", attempt, e)
                metrics["retries"] += 1
                continue
            metrics["calls"] += 1
            if res.usage is not None:
                metrics["total_tokens"] += getattr(res.usage, "total", 0) or 0
            metrics["cost_usd"] += getattr(res, "cost", 0.0) or 0.0
            metrics["provider"].add(getattr(res, "provider", "mock"))
            if not getattr(res, "ok", True):
                metrics["retries"] += 1
                continue
            parsed = parse_section(getattr(res, "text", ""))
            errors = _validate(parsed, getattr(res, "text", ""), chart, ev)
            if not errors:
                narratives.append({"event": ev, **parsed})
                ok = True
                break
            metrics["qa_failures"] += 1
            if attempt < MAX_RETRIES:
                metrics["retries"] += 1
        if not ok:
            metrics["refunded"] += 1
            if on_event_failed:
                try:
                    on_event_failed(ev)
                except Exception as e:  # noqa: BLE001
                    log.warning("on_event_failed hook error: %s", e)
    metrics["provider"] = sorted(metrics["provider"])
    return narratives, metrics