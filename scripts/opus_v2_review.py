"""Zayche closure review v2 — opus-4.6-thinking reviews FINAL-GO v2 claims + the
P1-P5 fixes applied since its last audit. Same guarded pattern as opus_resume.py
(45s spacing, OmniRoute, moderate max_tokens — no gateway saturation)."""
import asyncio, json, sys, time
sys.path.insert(0, "/root/chart-platform")
import httpx

OMNI = "http://127.0.0.1:20128/v1/chat/completions"
KEY = open("/root/backups/omniroute-api-key.txt").read().strip()
MODEL = "antigravity/claude-opus-4-6-thinking"

SYSTEM = ("You are the chief technical reviewer for Zayche (chart.negar.io), a "
          "Persian astrology web app. You previously audited this codebase "
          "(6-dim, 41 findings, 9 blockers). The team fixed the 3 real bugs and "
          "hardened others. Your job NOW: review the CLOSURE report (FINAL-GO v2) "
          "and the new code changes. Be precise, skeptical but FAIR: verify claims "
          "against the evidence shown; do NOT invent issues not supported by the "
          "text (previous false positives wasted the team's time). Verdicts: "
          "AGREE / DISAGREE / UNVERIFIABLE per claim, with 1-line reasons. "
          "Answer in English; numbered output.")


def _read_final_go() -> str:
    return open("/root/chart-platform/reports/launch/FINAL-GO.md").read()


def _read_routing() -> str:
    return open("/root/chart-platform/docs/ROUTING.md").read()


def _read_verdict() -> str:
    return open("/root/chart-platform/docs/audit/opus/VERDICT-VERIFIED.md").read()


def _read_patch() -> str:
    return open("/tmp/opus_v2_patch.txt").read()


async def call(payload: dict, retries: int = 3) -> dict:
    for attempt in range(retries):
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=600) as c:
                r = await c.post(OMNI, json=payload,
                                 headers={"Authorization": f"Bearer {KEY}",
                                          "Content-Type": "application/json"})
        except Exception as e:  # noqa: BLE001
            last = f"http {e}"; await asyncio.sleep(30); continue
        dt = time.monotonic() - t0
        if r.status_code == 200:
            try:
                j = r.json()
            except Exception as e:  # noqa: BLE001
                last = f"bad json: {e}"; await asyncio.sleep(30); continue
            text = ((j.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            if text.strip():
                u = j.get("usage") or {}
                cost = (u.get("prompt_tokens", 0) * 5 + u.get("completion_tokens", 0) * 25) / 1e6
                return {"ok": True, "text": text, "cost": cost, "sec": int(dt),
                        "status": 200, "error": ""}
        last = f"status={r.status_code} body={r.text[:150]}"
        await asyncio.sleep(30)
    return {"ok": False, "text": "", "cost": 0.0, "sec": 0, "status": 0, "error": last}


def _msg(user: str) -> dict:
    return {"model": MODEL, "messages": [{"role": "system", "content": SYSTEM},
                                         {"role": "user", "content": user}],
            "max_tokens": 8000, "temperature": 0.4, "stream": False}


CHUNK1 = ("REVIEW THE CLOSURE REPORT. Below are FINAL-GO v2 (the closure report), "
          "ROUTING.md (the routing matrix), and VERDICT-VERIFIED.md (my claim-by-claim "
          "verification of your last audit). Assess line by line: "
          "(1) Is the routing matrix sane given the cost/speed/quality table? "
          "(2) Is the M3 gate handling honest (24h rolling window, clean-window "
          "p95≈17s, cron tomorrow)? (3) Is the P5 personalization methodology valid "
          "(real charts, GO-pro judge, 8.4-8.9 across models)? Any methodological "
          "hole? (4) Are the cost tables plausible? (5) Is 'CODE COMPLETE + AI "
          "QUALITY OK, launch = 7 user-side actions' a justified verdict?\n"
          "Give AGREE/DISAGREE/UNVERIFIABLE per claim with one-line reasons. "
          "Keep it under 600 words.\n\n=== FINAL-GO v2 ===\n"
          + _read_final_go() + "\n\n=== ROUTING.md ===\n" + _read_routing() +
          "\n\n=== VERDICT-VERIFIED.md ===\n" + _read_verdict())


CHUNK2 = ("VERIFY THE FIXES. This is the git diff of the code changes applied since "
          "your last audit (P1-P5): wallet-payment settlement now activates "
          "yearly/monthly subscriptions and credit packs (F-29); LANCH20 coupon "
          "seed in a fresh session (F-11); Placidus-house validation with whole-sign "
          "fallback (F-26); two-step cancel modal Alpine state (F-37); weekly LLM "
          "text escaped + _safe_json for all template JSON embeds (F-08); chat "
          "prompt v3 personalization; admin panel routing matrix + defaults; "
          "ROUTING.md. For each fix: does it actually close your P0/P1 finding? "
          "Any NEW bug you can spot? Answer in numbered AGREE/DISAGREE/UNVERIFIABLE "
          "lines. Under 700 words.\n\n=== DIFF ===\n" + _read_patch())


async def main():
    print("STEP 1/3 — closure-report review...", flush=True)
    r1 = await call(_msg(CHUNK1))
    print(f"done ok={r1['ok']} sec={r1.get('sec')} cost=${r1.get('cost', 0):.3f}"
          + (f" err={r1['error']}" if not r1["ok"] else ""), flush=True)
    json.dump(r1, open("/tmp/opus_v2_step1.json", "w"), ensure_ascii=False, indent=1)
    await asyncio.sleep(45)

    print("STEP 2/3 — fix verification...", flush=True)
    r2 = await call(_msg(CHUNK2))
    print(f"done ok={r2['ok']} sec={r2.get('sec')} cost=${r2.get('cost', 0):.3f}"
          + (f" err={r2['error']}" if not r2["ok"] else ""), flush=True)
    json.dump(r2, open("/tmp/opus_v2_step2.json", "w"), ensure_ascii=False, indent=1)
    await asyncio.sleep(45)

    print("STEP 3/3 — synthesis...", flush=True)
    synth = ("You reviewed (1) the closure report and (2) the fix diffs. Synthesize: "
             "FINAL verdict on FINAL-GO v2 — AGREE / CONDITIONAL / DISAGREE with the "
             "2-3 most important remaining risks (if any). Then rank the 7 user-side "
             "launch actions (Zarinpal merchant, Kavehnegar key, zayche.io domain, "
             "real-phone test, push, Search Console, brand) by dependency and risk. "
             "Under 300 words.\n\nSTEP1 summary:\n" + r1["text"][:3000] +
             "\n\nSTEP2 summary:\n" + r2["text"][:3000])
    r3 = await call(_msg(synth))
    print(f"done ok={r3['ok']} sec={r3.get('sec')} cost=${r3.get('cost', 0):.3f}"
          + (f" err={r3['error']}" if not r3["ok"] else ""), flush=True)
    json.dump(r3, open("/tmp/opus_v2_step3.json", "w"), ensure_ascii=False, indent=1)
    total = r1.get("cost", 0) + r2.get("cost", 0) + r3.get("cost", 0)
    print(f"\n=== ALL DONE — total cost ${total:.3f} ===")


if __name__ == "__main__":
    asyncio.run(main())