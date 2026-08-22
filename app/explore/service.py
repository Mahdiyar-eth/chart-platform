"""ZAYCHE P3 (D3) — self-discovery exploration generation.

Card → intent → allowed domains → chart factors (evidence) → focused prompt
→ LLM → QA → retry (feedback with whitelist) → result {insights, evidence}.
Same QA gates as deep reports: FORBIDDEN_PATTERNS scan across ALL free text,
active-factor grounding, min 2 insights, min length.
"""
from __future__ import annotations

import json
import logging
import re
import time

from app.explore.cards import Card
from app.report.prompt_builder import factors_block
from app.report.qa import FORBIDDEN_PATTERNS
from app.report.rules import evaluate

log = logging.getLogger("zayche.explore")

EXPLORE_MAX_RETRIES = 4

SYSTEM_PROMPT = (
    "تو یک تحلیلگر خودشناسی هستی که بر پایهٔ داده‌های واقعی چارت تولد کار می‌کنی.\n"
    "قوانین طلایی:\n"
    "- فقط از عوامل نجومی که در «عوامل فعال» آمده‌اند استفاده کن؛ هیچ سیاره/برج/خانه‌ای را اختراع نکن.\n"
    "- هیچ پیش‌گویی قطعی، ادعای پزشکی، تشخیص روان‌شناسی، یا «مقدر شده» ننویس.\n"
    "- پاسخ فقط JSON معتبر — بدون مقدمه و بدون مارک‌داون.\n"
)

EXPLORE_TEMPLATE = """## سؤال کاربر
{question}

## عوامل فعال چارت (تنها منبع مجاز شواهد)
{factors}

## دستور خروجی
یک JSON با این ساختار برگردان:
{{
  "intro": "یک پاراگراف کوتاه (۲-۳ جمله) که پاسخ کلی به سؤال را جمع‌بندی می‌کند",
  "insights": [
    {{
      "insight": "بینش اصلی (۵-۷ جمله، بر پایهٔ شواهد، با لحن محترمانه)",
      "evidence": ["نام عامل واقعی از عوامل فعال، مثل: Sun in Leo / Moon in 4th house / Venus trine Mars"],
      "practical_advice": "یک اقدام کوچک و مشخص امروز (۱-۲ جمله)"
    }}
  ]
}}
- دقیقاً ۲ تا ۴ insight بنویس.
- هر insight حداقل ۵ جمله باشد.
- evidence فقط از عوامل فعال — به فارسی یا انگلیسی استاندارد.
- focus: {focus}
"""


def build_explore_prompt(chart: dict, card: Card) -> tuple[str, dict]:
    """Gather evidence from ALL allowed domains of the card, then one prompt."""
    ctx: dict = {"domains": list(card.domains), "factors": [], "active_rules": []}
    for d in card.domains:
        active = evaluate(chart).get(d, [])
        ctx["active_rules"].extend(r["rule_id"] for r in active)
        block = factors_block(chart, d, active)
        if block and block not in ctx["factors"]:
            ctx["factors"].append(block)
    # fall back to Big Three when nothing is active for these domains
    if not ctx["factors"]:
        ctx["factors"].append(factors_block(chart, "identity", []))
    prompt = SYSTEM_PROMPT + EXPLORE_TEMPLATE.format(
        question=card.question_fa,
        factors="\n".join(ctx["factors"]),
        focus=card.focus,
    )
    return prompt, ctx


def _parse(text: str) -> dict | None:
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        m = text[text.find("{"): text.rfind("}") + 1] if "{" in text else None
        if m:
            try:
                return json.loads(m)
            except Exception:  # noqa: BLE001
                return None
        return None


def qa_explore(result: dict | None, chart: dict, card: Card) -> list[str]:
    """Gates: valid JSON, banned words across ALL free text, evidence only
    from factors ACTIVE in ANY allowed domain of the card (union — a card
    may cite Mercury when mind is one of its domains), min 2 insights,
    min lengths. Mirrors qa_section but with a card-wide whitelist."""
    if result is None:
        return ["خروجی JSON نامعتبر است"]

    def _free_text() -> str:
        parts = [result.get("intro") or ""]
        for ins in result.get("insights", []):
            if isinstance(ins, dict):
                parts.append(ins.get("insight") or "")
                parts.append(ins.get("practical_advice") or "")
        return "\n".join(str(p) for p in parts if isinstance(p, str))

    errors: list[str] = []
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, _free_text().replace("\u200c", "")):
            errors.append(f"عبارت ممنوع «{pat}» در متن")
            break

    # union of active factors across ALL card domains
    allowed: set[str] = set()
    for d in card.domains:
        try:
            allowed |= {r["factor"] for r in evaluate(chart).get(d, [])}
        except Exception:  # noqa: BLE001
            pass
    allow_any = not allowed

    insights = result.get("insights", [])
    if not isinstance(insights, list) or len(insights) < 2:
        errors.append(f"تعداد insight کافی نیست ({len(insights)})")
    if result.get("intro") and len(result["intro"].strip()) < 40:
        errors.append("intro خیلی کوتاه است (حداقل ۲-۳ جمله)")

    total_words = 0
    for i, ins in enumerate(insights):
        if not isinstance(ins, dict):
            errors.append(f"insight {i + 1}: ساختار نامعتبر")
            continue
        text = (ins.get("insight") or "").strip()
        words = len(text.split())
        total_words += words
        if words < 60:
            errors.append(f"insight {i + 1}: کوتاه است ({words} کلمه)")
        ev = ins.get("evidence") or []
        if not isinstance(ev, list) or not ev:
            errors.append(f"insight {i + 1}: شواهد (evidence) خالی است")
            continue
        for e in ev:
            tok = str(e).split()[0].rstrip("،,.")
            if not allow_any and tok not in allowed:
                errors.append(f"عامل {tok} خارج از عوامل فعال این کارت است")
                break
    if total_words < 150:
        errors.append(f"کل بخش کوتاه است ({total_words} کلمه)")
    return errors


async def generate_exploration(router, chart: dict, card: Card,
                               exploration_id: str | None = None,
                               user_id: str | None = None,
                               report_id: str | None = None) -> tuple[dict | None, dict]:
    """Generate a card exploration with QA+retry. Returns (result, metrics)."""
    prompt, ctx = build_explore_prompt(chart, card)
    metrics = {"calls": 0, "retries": 0, "total_tokens": 0, "cost_usd": 0.0,
               "qa_failures": 0, "provider": set(), "latency_ms": []}
    t0 = time.monotonic()
    for attempt in range(EXPLORE_MAX_RETRIES + 1):
        res = await router.complete(prompt, max_tokens=2048, temperature=0.6, json_mode=True)
        metrics["calls"] += 1
        metrics["total_tokens"] += res.usage.total
        metrics["cost_usd"] += res.cost
        metrics["provider"].add(res.provider)
        metrics["latency_ms"].append(getattr(res, "latency_ms", 0) or 0)
        _log_run(exploration_id, user_id, res, report_id)
        if not res.ok:
            metrics["retries"] += 1
            continue
        result = _parse(res.text)
        errors = qa_explore(result, chart, card)
        if not errors:
            metrics["duration_s"] = round(time.monotonic() - t0, 1)
            metrics["provider"] = sorted(metrics["provider"])
            return result, metrics
        metrics["qa_failures"] += 1
        log.warning("explore QA fail %s (attempt %d/%d): %s", card.key, attempt + 1,
                    EXPLORE_MAX_RETRIES + 1, errors[:3])
        if attempt < EXPLORE_MAX_RETRIES:
            metrics["retries"] += 1
            hint = "\n\n⚠️ تلاش قبلی به این دلایل رد شد — فقط همین موارد را اصلاح کن:\n" + \
                "\n".join(f"- {e}" for e in errors[:5])
            prompt = prompt + hint
    metrics["duration_s"] = round(time.monotonic() - t0, 1)
    metrics["provider"] = sorted(metrics["provider"])
    return None, metrics


def _log_run(exploration_id, user_id, res, report_id) -> None:
    try:
        from sqlmodel import Session
        from app.db import engine as _e
        from app.models import LLMRun
        with Session(_e) as s:
            s.add(LLMRun(report_id=report_id, user_id=user_id, kind="explore",
                         provider=res.provider, model=res.model, gateway=res.provider,
                         prompt_tokens=res.usage.prompt_tokens,
                         completion_tokens=res.usage.completion_tokens,
                         latency_ms=getattr(res, "latency_ms", 0) or 0,
                         cost_usd=res.cost, ok=res.ok,
                         error=(res.error or "")[:300]))
            s.commit()
    except Exception:  # noqa: BLE001 — metering must never break exploration
        pass


# ── financial integrity (D5) ────────────────────────────────────────────────
def spend_credit(session, user_id: str, exploration_id: str, cost: int = 1) -> bool:
    """Atomic credit deduction with ledger row. Returns False when broke.
    A2: delegates to the central credit service (price from credit_prices DB)."""
    from sqlmodel import select
    from app import credits as _c
    from app.models import CreditTransaction
    # idempotency: same exploration never double-charged
    key = f"explore:{exploration_id}"
    existing = session.exec(
        select(CreditTransaction).where(CreditTransaction.idempotency_key == key)
    ).first()
    if existing:
        return True
    try:
        _c.spend(session, user_id, "explore_card",
                 idempotency_key=key, chart_id=exploration_id)
        return True
    except _c.InsufficientCredits:
        return False


def mark_free_exploration(session, user, exploration_id: str) -> None:
    """F5 — first-ever exploration is free (loss-aversion funnel)."""
    from sqlalchemy import text
    from app.models import CreditTransaction
    session.execute(text(
        "UPDATE users SET free_exploration_used = true WHERE id = :uid"
    ), params={"uid": user.id})
    session.add(CreditTransaction(user_id=user.id, amount=0,
                                  reason="free_exploration", ref_id=exploration_id))
    session.commit()


def refund_credit(session, user_id: str, exploration_id: str, cost: int = 1) -> None:
    """Refund on failed generation (D5). No-op for free explorations (cost=0)."""
    if cost <= 0:
        return
    from sqlmodel import select
    from app import credits as _c
    from app.models import CreditTransaction
    orig = session.exec(
        select(CreditTransaction).where(
            CreditTransaction.idempotency_key == f"explore:{exploration_id}"
        )
    ).first()
    if orig:
        _c.refund(session, orig.id, "failed_generation")


def grant_free_credit(session, user_id: str, amount: int = 1) -> None:
    """First-exploration free gift (free funnel, P5). Idempotent per user."""
    from app import credits as _c
    _c.grant(session, user_id, amount, "free_gift",
             idempotency_key=f"free_gift:{user_id}")
