#!/usr/bin/env python3
"""Resume opus audit: dim-5 + synthesis only, slow pace (45s gaps)."""
import json, re, time
from pathlib import Path
import urllib.request

ROOT = Path("/root/chart-platform")
OUTDIR = ROOT / "docs" / "audit" / "opus"
KEY = Path("/root/backups/omniroute-api-key.txt").read_text().strip()
BASE = "http://127.0.0.1:20128/v1"
MODEL = "antigravity/claude-opus-4-6-thinking"
HDR = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

def ask(prompt, system, max_tokens=14000):
    payload = {"model": MODEL,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": prompt}],
               "max_tokens": max_tokens, "temperature": 0.3, "stream": False}
    req = urllib.request.Request(f"{BASE}/chat/completions",
        data=json.dumps(payload).encode(), headers=HDR, method="POST")
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=900) as r:
        data = json.loads(r.read().decode())
    dt = time.monotonic() - t0
    msg = data["choices"][0]["message"]["content"]
    u = data.get("usage") or {}
    return {"text": msg, "secs": round(dt, 1), "in": u.get("prompt_tokens", 0), "out": u.get("completion_tokens", 0)}

SYS = ("You are a ruthless senior staff engineer + security architect + astrologer-systems reviewer. "
       "Audit the provided ZAYCHE code for correctness, security, cost leaks, astrology math errors, "
       "RAG/LLM pipeline defects, UX (mobile RTL), business logic, launch readiness. "
       "Reply in English. Structure: FINDINGS (numbered, each with [SEV P0/P1/P2], file:line, evidence, fix) then VERDICT. "
       "Be specific; quote code. Do NOT invent issues — if a section is correct, say so.")

bundle = (ROOT / "docs" / "audit" / "ZAYCHE-CODEBUNDLE.md").read_text(encoding="utf-8")
secs = re.split(r"\n## ", bundle)
def find(n):
    return next((s for s in secs if s.startswith(n)), "")
dim5 = find("۱۲)") + find("۱۳)") + find("۱۴)") + find("۱۶)") + find("۱۷)") + find("۱۸)")
r5 = ask(f"AUDIT CHUNK (5-tests-deploy). Part of a Persian-astrology SaaS (ZAYCHE). Review ONLY this chunk. "
         f"Report findings with file:line + evidence + fix.\n===== CHUNK =====\n{dim5[:190000]}\n===== END =====\n", SYS, 14000)
(OUTDIR / "dim-5-tests-deploy.md").write_text(r5["text"], encoding="utf-8")
print(f"dim5: {r5['secs']}s in={r5['in']} out={r5['out']}")
time.sleep(45)

all_findings = "".join(
    f"### {p.name}\n{p.read_text(encoding='utf-8')}\n"
    for p in sorted(OUTDIR.glob("dim-*.md")))
syn = ask(
    "SYNTHESIS: merge ALL dimension reviews into ONE final audit report:\n"
    "1) Consolidated FINDINGS table (dedupe; keep P0/P1; drop duplicates).\n"
    "2) Per-dimension verdicts (architecture, backend, astrology, report/chat/RAG, security, payment, UI/UX, bots, SEO, tests/deploy, cost).\n"
    "3) TOP 10 critical issues ranked.\n4) FINAL VERDICT: launch-ready? YES/CONDITIONAL/NO + exact blockers.\n"
    "5) AI recommendations (model routing, personalization). Be decisive.\n\n" + all_findings,
    SYS, 16000)
(OUTDIR / "opus-final.md").write_text(syn["text"], encoding="utf-8")
print(f"syn: {syn['secs']}s in={syn['in']} out={syn['out']}")
tot_in = sum(json.loads(p.read_text() or '{}').get('i', 0) for p in []) + syn["in"] + r5["in"]
print("DONE")