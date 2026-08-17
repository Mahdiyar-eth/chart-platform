#!/usr/bin/env python3
"""opus-4.6-thinking full audit of ZAYCHE code bundle via OmniRoute.

Chunks the bundle into 5 dimension groups + 1 synthesis call. Saves each
dim-N.md + opus-final.md under docs/audit/opus/. Prints cost summary.
"""
import json, re, sys, time
from pathlib import Path
import urllib.request

ROOT = Path("/root/chart-platform")
BUNDLE = ROOT / "docs" / "audit" / "ZAYCHE-CODEBUNDLE.md"
OUTDIR = ROOT / "docs" / "audit" / "opus"
OUTDIR.mkdir(parents=True, exist_ok=True)
KEY = Path("/root/backups/omniroute-api-key.txt").read_text().strip()
BASE = "http://127.0.0.1:20128/v1"
MODEL = "antigravity/claude-opus-4-6-thinking"

HDR = {
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
}

def ask(prompt: str, system: str, max_tokens: int = 14000) -> dict:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "stream": False,
    }
    req = urllib.request.Request(
        f"{BASE}/chat/completions", data=json.dumps(payload).encode(),
        headers=HDR, method="POST")
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.loads(r.read().decode())
    dt = time.monotonic() - t0
    msg = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    return {"text": msg, "secs": round(dt, 1),
            "in": usage.get("prompt_tokens", 0), "out": usage.get("completion_tokens", 0)}

SYS = (
    "You are a ruthless senior staff engineer + security architect + astrologer-systems "
    "reviewer. Audit the provided ZAYCHE (Persian astrology SaaS) code for: correctness, "
    "security (OWASP), data race, cost leaks, astrology math errors, RAG/LLM pipeline "
    "defects, UX (mobile RTL), business logic, and launch readiness. "
    "Reply in English. Structure: FINDINGS (numbered, each with [SEV: critical/major/mod: P0/P1/P2], file:line, evidence, fix), "
    "then VERDICT for the chunk dimensions. Be specific; quote code. "
    "Do NOT invent issues — if a section is correct, say so."
)

DIMENSIONS = [
    ("1-backend-core", None), ("2-report-chat", None), ("3-security-payment", None),
    ("4-ui-bots-seo", None), ("5-tests-deploy", None),
]

def split_bundle() -> list[tuple[str, str]]:
    text = BUNDLE.read_text(encoding="utf-8")
    secs = re.split(r"\n## ", text)
    # map section titles to chunks
    def find(n: str) -> str:
        for s in secs:
            if s.startswith(n):
                return s
        return ""
    chunks = {
        "1-backend-core": find("۱)") + find("۲)") + find("۴)"),
        "2-report-chat": find("۵)") + find("۶)") + find("۱۰)"),
        "3-security-payment": find("۳)") + find("۷)") + find("۸)"),
        "4-ui-bots-seo": find("۱۱)") + find("۹)") + find("۱۵)"),
        "5-tests-deploy": find("۱۲)") + find("۱۳)") + find("۱۴)") + find("۱۶)") + find("۱۷)") + find("۱۸)"),
    }
    return [(k, v if v else "SECTION MISSING IN BUNDLE") for k, v in chunks.items()]

def main() -> None:
    if not BUNDLE.exists():
        print("BUNDLE NOT READY — run gen_codebundle.py first"); sys.exit(1)
    total_in = total_out = 0
    chunk_size = BUNDLE.stat().st_size / 1024
    print(f"BUNDLE: {chunk_size:.0f} KB — running {len(DIMENSIONS)} dims + synthesis")
    results = {}
    for name, _ in DIMENSIONS:
        blob = next(c for n, c in split_bundle() if n == name)
        prompt = (
            f"AUDIT CHUNK ({name}).\n"
            "This is part of a full Persian-astrology SaaS (ZAYCHE). "
            "Review this chunk ONLY. Report findings with file:line + evidence + fix.\n\n"
            f"===== CHUNK START =====\n{blob[:190000]}\n===== CHUNK END =====\n"
        )
        try:
            r = ask(prompt, SYS, max_tokens=14000)
        except Exception as e:
            print(f"  {name}: ERROR {e}")
            results[name] = {"text": f"ERROR: {e}", "secs": 0, "in": 0, "out": 0}
            continue
        total_in += r["in"]; total_out += r["out"]
        results[name] = r
        (OUTDIR / f"dim-{name}.md").write_text(r["text"], encoding="utf-8")
        print(f"  {name}: {r['secs']}s | in={r['in']} out={r['out']} | {len(r['text'])} chars")

    # synthesis
    all_findings = "\n\n".join(f"### {n}\n{r['text']}\n" for n, r in results.items())
    print("synthesis call…")
    syn = ask(
        "SYNTHESIS: merge all five dimension reviews below into ONE final audit report:\n"
        "1) Consolidated FINDINGS table (dedupe across dims; keep P0/P1; drop duplicates).\n"
        "2) Per-dimension verdicts (architecture, backend, astrology, report/chat/RAG, "
        "security, payment, UI/UX, bots, SEO, tests/deploy, cost).\n"
        "3) TOP 10 CRITICAL issues ranked.\n"
        "4) FINAL VERDICT: is ZAYCHE launch-ready? YES / CONDITIONAL / NO with the exact "
        "blocking items.\n"
        "5) Best-quality/AI recommendations (model routing, personalization).\n\n"
        "DIMMED: this is the final audited artifact — be decisive.\n\n"
        + all_findings,
        SYS, max_tokens=18000,
    )
    total_in += syn["in"]; total_out += syn["out"]
    (OUTDIR / "opus-final.md").write_text(syn["text"], encoding="utf-8")
    print(f"  synthesis: {syn['secs']}s | in={syn['in']} out={syn['out']}")
    cost = (total_in / 1e6 * 5.0) + (total_out / 1e6 * 25.0)
    print(f"DONE. total in={total_in} out={total_out} | est cost ${cost:.2f}")
    (OUTDIR / "cost.txt").write_text(f"{cost:.2f}", encoding="utf-8")

if __name__ == "__main__":
    main()