"""MASTER W6 — «چارت سالیانه» product service (N2).

Gate: 9 credits (`solar_return` action in credit_prices, chart-scoped).
One LLM narrative call (flash) cached permanently per (chart_id, year) —
the SR chart of a given year never changes.
"""
from __future__ import annotations

import json

from app.report.solar import solar_return_for, sr_sections


async def build_solar_product(session, user_id: str, natal_chart: dict,
                              lat: float, lon: float, tz_name: str,
                              zodiac: str = "tropical") -> dict:
    """Deterministic sections + one LLM narrative, permanent-cached."""
    sr = solar_return_for(natal_chart, lat, lon, tz_name, zodiac=zodiac)
    sec = sr_sections(sr, natal_chart)
    sec["narrative"] = None
    # permanent cache per chart+SR-year
    import hashlib
    year_key = sr.moment_utc.strftime("%Y")
    cache_key = f"solar:{hashlib.sha1(f'{user_id}:{lat}:{lon}:{year_key}'.encode()).hexdigest()[:16]}"
    try:
        import redis.asyncio as redis_async
        r = redis_async.from_url(_redis_url(), decode_responses=True)
        raw = await r.get(cache_key)
        await r.aclose()
        if raw:
            sec["narrative"] = raw or None
            sec["cached"] = True
            return sec
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.core.llm import build_chat_router
        router = build_chat_router()
        prompt = _narrative_prompt(sec)
        res = await router.complete(prompt, max_tokens=420, temperature=0.6)
        if res.ok:
            text = (res.text or "").strip()
            if text and not _has_forbidden(text):
                sec["narrative"] = text[:1200]
                try:
                    import redis.asyncio as redis_async
                    r = redis_async.from_url(_redis_url(), decode_responses=True)
                    await r.set(cache_key, sec["narrative"])
                    await r.aclose()
                except Exception:  # noqa: BLE001
                    pass
    except Exception:  # noqa: BLE001 — deterministic content must survive
        pass
    return sec


def _redis_url() -> str:
    import os
    return os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")


def _has_forbidden(text: str) -> bool:
    import re
    from app.report.qa import FORBIDDEN_PATTERNS
    flat = text.replace("\u200c", "")
    return any(re.search(p, flat) for p in FORBIDDEN_PATTERNS)


def _narrative_prompt(sec: dict) -> str:
    transits = "\n".join(f"- {t['date']}: {t['headline']}" for t in sec["transits"]) or "- گذر برجسته‌ای ثبت نشد"
    return f"""تو مشاور تأملی چارت تولد هستی. چارت سالیانهٔ کاربر (بازگشت خورشید) این است:

- لحظهٔ بازگشت خورشید: {sec['moment_utc']} UTC (خطای محاسبه: {sec['precision_arcmin']} دقیقهٔ قوسی)
- تم اصلی سال: {sec['theme']}
- حال‌وهوای سال: {sec['mood']}
- ۵ گذر کلیدی سال با تاریخ:
{transits}

یک روایت ۸ تا ۱۲ جمله‌ای بنویس که سالِ پیشِ روی کاربر را قاب بگیرد:
- به همین خانه و همین گذرها اشاره کن؛ هیچ سیاره/تاریخی از خودت نساز.
- لحن تأملی، صادق، بدون وعده؛ نه فال، نه شانس، نه قطعیت.
- پاسخ فقط متن ساده — بدون مارک‌داون."""
