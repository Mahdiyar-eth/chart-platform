#!/usr/bin/env python3
"""opus-4-6-thinking PLAN + audit of ZAYCHE via OmniRoute (PACED, user's 4 dimensions).

Produces MASTER_PLAN.md (the plan) + REVIEW.md (the audit, machine-readable) +
dim-*.md per dimension. Paces heavy calls >=45s so the gateway never saturates
the user's own chat. Reads the (freshly regenerated) ZAYCHE-CODEBUNDLE.md.
"""
import json, re, sys, time
from pathlib import Path
import urllib.request

ROOT = Path("/root/chart-platform")
BUNDLE = ROOT / "docs" / "audit" / "ZAYCHE-CODEBUNDLE.md"
OUTDIR = ROOT / "docs" / "audit" / "opus46"
OUTDIR.mkdir(parents=True, exist_ok=True)
KEY = Path("/root/backups/omniroute-api-key.txt").read_text().strip()
BASE = "http://127.0.0.1:20128/v1"
MODEL = "antigravity/claude-opus-4-6-thinking"
PACE = 45  # seconds between heavy calls
HDR = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

def ask(prompt, system, max_tokens=14000):
    payload = {"model": MODEL,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": prompt}],
               "max_tokens": max_tokens, "temperature": 0.3, "stream": False}
    req = urllib.request.Request(f"{BASE}/chat/completions",
                                 data=json.dumps(payload).encode(), headers=HDR, method="POST")
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.loads(r.read().decode())
    dt = time.monotonic() - t0
    msg = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    return {"text": msg, "secs": round(dt, 1),
            "in": usage.get("prompt_tokens", 0), "out": usage.get("completion_tokens", 0)}

def paced(prev, gap=PACE):
    if prev is not None:
        dt = time.monotonic() - prev
        if dt < gap:
            time.sleep(gap - dt)

SYS = (
    "You are a ruthless senior staff engineer + security architect + astrology-systems "
    "reviewer acting as ARCHITECT / AUDITOR / REVIEWER for ZAYCHE, a Persian astrology SaaS. "
    "You are NOT the implementer: you NEVER write or edit code. Your only deliverables are "
    "a PLAN and an AUDIT (markdown docs, with file:line + evidence + checkable acceptance "
    "criteria). Distinguish 'code-complete' from 'launch-accepted'. Do NOT invent issues - "
    "if code is correct, say so. Be specific, quote code, anticipate what gets overlooked "
    "(security, IDOR, auth, rate limits, mobile breakpoints, empty states, race conditions, "
    "failure paths). Reply in English."
)

# --- the user's 4 audit dimensions (from /tmp/audit_prompt.md) ---
DIMS = [
    ("1-purchase-return-bug",
     "AUDIT DIMENSION - end-to-end purchase flow correctness. A visitor does NOT log in, buys "
     "a plan, and after the payment redirect/return STILL sees the free-chart summary (same as "
     "the free chart page). Analyze the code path: app/payment/*, app/routes/wallet.py, "
     "app/auth.py, the post-payment return/redirect handler, the summary/report generation. "
     "Name likely root causes with file:line. Flag every similar flow where the rendered "
     "end-state could diverge from intent (HTTP 200 != correct view)."),
    ("2-ui-ux-glassmorphism",
     "AUDIT DIMENSION - UI/UX to best possible state. Assess every page/screen against the "
     "mobile-first bar (no confirm(), no opacity-0/group-hover buttons, 44px targets, no "
     "tab-wrap, RTL) and general hierarchy/spacing. For weak screens, SPEC a proper re-design "
     "with a cohesive liquid-glass/glassmorphism aesthetic (translucent blurred panels, subtle "
     "borders, depth, light + professional). Concrete spec per screen (elements, classes, layout)."),
    ("3-monetization-gamification",
     "AUDIT DIMENSION - monetization model, marketing, gamification. The platform mixes 'report' "
     "(one-off), 'credit' (another cost), and 'subscription' - users get confused. Analyze the "
     "actual models: app/models.py (Plan, Order, Subscription, Credit), app/payment/orders.py, "
     "app/routes/wallet.py. Recommend the CLEANEST product model (credit-centric? hybrid?). Give "
     "the exact pricing/credits table + user-facing copy + gamification mechanics (free credits, "
     "referral, loyalty, streaks). Principled recommendation, justified."),
    ("4-astrology-services",
     "AUDIT DIMENSION - diverse personalized services from the birth chart. The platform should "
     "offer services derived from the person's birth chart (e.g. upcoming TRANSITS specific to "
     "that person, with clear full explanations). Audit app/astrology/* (engine.py pyswisseph, "
     "transits.py, synastry.py, rectify.py, big_three.py, sky.py) and app/report/*: what exists "
     "vs what is actually wired into the UI/reports, and what's missing for a full personalized "
     "multi-service offering. Reuse the runtime pattern (Omni gateway via app/core/llm.py). "
     "Give the feature list + build order."),
]

PLAN_DESC = (
    "PLAN REQUEST: produce docs/workflow/MASTER_PLAN.md - a complete phased plan (goal, "
    "architecture, phases, acceptance criteria, order of work) that an implementer (Hermes) "
    "will execute to: (1) fix the purchase/return bug, (2) reach best-possible mobile-first "
    "liquid-glass UI/UX, (3) pick the cleanest monetization/gamification model, (4) wire the "
    "diverse personalized birth-chart services. For every phase give file:line targets, "
    "intended behavior, edge cases, and CHECKABLE acceptance criteria. Distinguish "
    "'code-complete' from 'launch-accepted'. Also note what will need REAL browser or live-DB "
    "verification by Hermes (you cannot run the app)."
)

def split_bundle():
    text = BUNDLE.read_text(encoding="utf-8")
    secs = re.split(r"\n## ", text)
    def find(n):
        for s in secs:
            if s.startswith(n):
                return s
        return ""
    return {
        "1-purchase-return-bug": find("۲)") + find("۳)") + find("۷)") + find("۱۰)"),
        "2-ui-ux-glassmorphism": find("۱۱)") + find("۹)") + find("۱۵)"),
        "3-monetization-gamification": find("۲)") + find("۷)") + find("۱۰)"),
        "4-astrology-services": find("۴)") + find("۵)") + find("۶)"),
    }

def main():
    if not BUNDLE.exists():
        print("BUNDLE NOT READY - run gen_codebundle.py first"); sys.exit(1)
    chunk_size = BUNDLE.stat().st_size / 1024
    print(f"BUNDLE {chunk_size:.0f} KB | {len(DIMS)} dims + plan + synthesis"
          f" | pacing {PACE}s | model {MODEL}")
    chunks = split_bundle()
    total_in = total_out = 0
    results = {}

    # (1) PLAN call
    plan_prompt = (
        "PROJECT OVERVIEW: ZAYCHE = Persian astrology SaaS at chart.negar.io. "
        "FastAPI + HTMX/Alpine (RTL PWA) + Postgres 16 + pgvector (RAG) + OmniRoute LLM gateway "
        "(gemini flash-high default, deepseek-v4-pro for report framing; docs/ROUTING.md is "
        "single source of truth). 551 tests green; up to commit fef0d6e. The external auditor "
        "reads the code bundle; it cannot run the app.\n\n" + PLAN_DESC + "\n\n"
        "This is a PLAN-only request: write the plan (no code)."
    )
    print("PLAN call ...")
    r = ask(plan_prompt, SYS, max_tokens=16000)
    total_in += r["in"]; total_out += r["out"]
    (OUTDIR / "MASTER_PLAN.md").write_text(r["text"], encoding="utf-8")
    print(f"  PLAN: {r['secs']}s | in={r['in']} out={r['out']}")
    results["0-plan"] = r
    last = time.monotonic()

    # (2) per-dimension audit
    for name, desc in DIMS:
        blob = chunks.get(name, "SECTION MISSING IN BUNDLE")
        prompt = f"{desc}\n\n===== CODE (from ZAYCHE-CODEBUNDLE.md) =====\n{blob[:190000]}\n===== END =====\n"
        paced(last)
        print(f"DIM {name} ...")
        r = ask(prompt, SYS, max_tokens=14000)
        total_in += r["in"]; total_out += r["out"]
        results[name] = r
        (OUTDIR / f"dim-{name}.md").write_text(r["text"], encoding="utf-8")
        print(f"  {name}: {r['secs']}s | in={r['in']} out={r['out']}")
        last = time.monotonic()

    # (3) synthesis -> REVIEW.md
    all_f = "\n\n".join(f"### {n}\n{r['text']}\n" for n, r in results.items())
    pace_time = time.monotonic() - last
    if pace_time < PACE:
        time.sleep(PACE - pace_time)
    print("SYNTHESIS -> REVIEW.md ...")
    syn = ask(
        "SYNTHESIS: merge the PLAN and all dimension reviews into ONE machine-readable REVIEW.md:\n"
        "1) STATUS: APPROVED | CHANGES_REQUIRED | CONDITIONAL_AGREE (one-line reason).\n"
        "2) CRITICAL / HIGH / MEDIUM / LOW: every finding as [file:line] + evidence + required fix.\n"
        "3) REQUIRED_FIXES: ordered actionable list.\n"
        "4) ACCEPTANCE_CRITERIA: per item, checkable.\n"
        "5) APPROVAL: verdict + evidence + gates met/not.\n"
        "6) TRUTH-NOTES: what you could NOT verify - say it explicitly, never guess.\n"
        "7) NEW-FEATURES list + PRICING/GAMIFICATION recommendation.\n\n"
        + all_f,
        SYS, max_tokens=18000,
    )
    total_in += syn["in"]; total_out += syn["out"]
    (OUTDIR / "REVIEW.md").write_text(syn["text"], encoding="utf-8")
    print(f"  REVIEW: {syn['secs']}s | in={syn['in']} out={syn['out']}")

    cost = (total_in / 1e6 * 5.0) + (total_out / 1e6 * 25.0)
    (OUTDIR / "cost.txt").write_text(f"{cost:.2f}", encoding="utf-8")
    print(f"DONE. in={total_in} out={total_out} | est cost ${cost:.2f}")

if __name__ == "__main__":
    main()
