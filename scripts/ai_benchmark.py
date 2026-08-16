#!/usr/bin/env python3
"""G17 (master-spec §61/Quality) — AI grounding benchmark across 50+ charts.

Sends the SAME deterministic question (sun-sign meaning) for 50 diverse
birth charts and asserts every answer is grounded (contains the expected
sign name or its Persian equivalent) — no hallucinations, no empty answers.

Uses the real production LLM router (OpenCode Go). Cost: ~50 short calls.

Run:  PYTHONPATH=/root/chart-platform venv/bin/python scripts/ai_benchmark.py [n_charts]
"""
import asyncio
import sys

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
SIGNS_FA = ["حمل", "ثور", "جوزا", "سرطان", "اسد", "سنبله",
            "میزان", "عقرب", "قوس", "جدی", "دلو", "حوت"]


def make_chart(i: int) -> dict:
    """Synthetic chart: sun at sign (i % 12), deterministic, valid JSON shape."""
    sign = SIGNS[i % 12]
    lon = (i % 12) * 30.0 + 15.0
    return {
        "planets": {"Sun": {"longitude": lon}, "Moon": {"longitude": (lon + 90) % 360}},
        "angles": {"ASC": {"longitude": (lon + 30) % 360}},
        "signs": [{"key": sign, "sign_fa": SIGNS_FA[i % 12]}],
        "birth": {"city_fa": "تهران", "local_time": f"۱۳۶۰/۰۱/{(i % 28) + 1} ۰۶:۱۰"},
    }


async def run(n: int) -> int:
    from app.core.llm import build_router
    router = build_router("chat")
    ok, fail = 0, []
    for i in range(n):
        sign = SIGNS[i % 12]
        sign_fa = SIGNS_FA[i % 12]
        chart = make_chart(i)
        prompt = (
            "بر اساس چارت زیر فقط یک جمله بگو: خورشید در کدام برج است و این برج "
            "در یک کلمه چه ویژگی‌ای دارد؟\n"
            f"{chart}\n"
            "پاسخ: "
        )
        res = await router.complete(prompt, system="مختصر و دقیق جواب بده.", max_tokens=80)
        if not res.ok or not res.text.strip():
            fail.append((i, "empty/failed", res.error))
            continue
        text = res.text
        if sign.lower() not in text.lower() and sign_fa not in text:
            fail.append((i, "wrong sign", text[:60]))
            continue
        ok += 1
        if i % 10 == 0:
            print(f"  …{i+1}/{n} ok={ok} fail={len(fail)}")
    print(f"AI-BENCH: {ok}/{n} grounded")
    for i, why, detail in fail[:5]:
        print(f"  fail #{i}: {why} — {detail}")
    if fail:
        print(f"AI-BENCH: FAILED ({len(fail)} ungrounded)")
        return 1
    print("AI-BENCH: OK")
    return 0


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 52
    return asyncio.run(run(n))


if __name__ == "__main__":
    sys.exit(main())
