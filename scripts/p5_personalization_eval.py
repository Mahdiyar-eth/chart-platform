"""P5 — personalization push: 4-model comparison on the OFFICIAL 5-dim rubric.

Models: gemini-3.6-flash-high (omni) · deepseek-v4-flash (GO) ·
deepseek-v4-pro (GO) · deepseek-v4-pro thinking-ON (GO direct).
6 charts x 3 personalization-probing questions = 18 answers/model.
Rubric judge: gemini (as in phase 2). Output: scores + cost + latency.
"""
import asyncio, json, os, re, sys, time
sys.path.insert(0, "/root/chart-platform")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import httpx
from app.core.llm import build_go_pool, OmniProvider
from scripts.ai_benchmark_v4 import make_chart, rubric_eval
from app.chat.retrieval import CHAT_SYSTEM_PROMPT

QUESTIONS = [
    "در زندگی عاطفی‌ام چه چالش‌هایی دارم و چطور می‌توانم از آنها عبور کنم؟",
    "بهترین مسیر شغلی برای من با توجه به چارتم چیست؟",
    "چه نقاط قوتی دارم که خودم متوجهشان نیستم؟",
]
MODELS = [
    ("gemini-high", "omni", "antigravity/gemini-3.6-flash-high"),
    ("flash-go", "go", "deepseek-v4-flash"),
    ("pro-go", "go", "deepseek-v4-pro"),
    ("pro-thinking", "gothink", "deepseek-v4-pro"),
]

GO_KEY = ""
for k in open("/root/chart-platform/.env").read().splitlines():
    if k.startswith("GO_API_KEYS="):
        slots = k.split("=", 1)[1].split(",")
        GO_KEY = slots[-1].split("@")[0].strip().strip('"').strip("'")
        break
GO_API = "https://opencode.ai/zen/go/v1"


async def call_go_thinking(prompt: str, sysp: str, model: str) -> object:
    payload = {"model": model, "messages": [
        {"role": "system", "content": sysp}, {"role": "user", "content": prompt}],
        "max_tokens": 1400, "temperature": 0.7,
        "thinking": {"type": "enabled"}}
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=300) as c:
        r = await c.post(f"{GO_API}/chat/completions", json=payload,
                         headers={"Authorization": f"Bearer {GO_KEY}"})
    dt = time.monotonic() - t0
    if r.status_code != 200:
        return type("R", (), {"ok": False, "text": "", "cost": 0.0,
                              "latency_ms": int(dt * 1000), "error": r.text[:150]})()
    j = r.json()
    u = j.get("usage") or {}
    text = j["choices"][0]["message"].get("content") or ""
    cost = 0.435 * u.get("prompt_tokens", 0) / 1e6 + 0.87 * u.get("completion_tokens", 0) / 1e6
    return type("R", (), {"ok": True, "text": text, "cost": cost,
                          "latency_ms": int(dt * 1000), "error": ""})()


def chart_ctx(i: int) -> str:
    c = make_chart(i)
    p = c["planets"]; a = c["angles"]

    def pf(name):
        d = p.get(name) or {}
        lon = d.get("longitude", 0)
        return f"{name} {int(lon//30)%12+1}-{int(lon%30)}"
    asc = int(a["ASC"]["longitude"]//30) % 12 + 1
    return (f"chart_{i} — Sun:{pf('Sun')} Moon:{pf('Moon')} ASC sign:{asc} | " +
            " ".join(pf(n) for n in ["Mercury", "Venus", "Mars", "Jupiter",
                                     "Saturn", "Uranus", "Neptune", "Pluto"]))


async def main():
    pools = {k: build_go_pool(model=m) for k, m in
             (("flash-go", "deepseek-v4-flash"), ("pro-go", "deepseek-v4-pro"))}
    omni_gemini = OmniProvider(model="antigravity/gemini-3.6-flash-high")
    rows = []
    for tag, kind, model in MODELS:
        for i in range(6):
            for q in QUESTIONS:
                user = f"خلاصهٔ چارت: {chart_ctx(i)}\n\nسؤال کاربر: {q}"
                if kind == "omni":
                    r = await omni_gemini.complete(user, system=CHAT_SYSTEM_PROMPT,
                                                   max_tokens=700, temperature=0.7)
                elif kind == "gothink":
                    r = await call_go_thinking(user, CHAT_SYSTEM_PROMPT, "deepseek-v4-pro")
                else:
                    r = await pools[tag].complete(user, system=CHAT_SYSTEM_PROMPT,
                                                  max_tokens=700, temperature=0.7)
                rows.append({"tag": tag, "chart": i, "q": q, "ok": r.ok,
                             "text": r.text[:2500] if r.ok else "", "cost": r.cost,
                             "latency_ms": getattr(r, "latency_ms", 0),
                             "error": (r.error or "")[:180], "model": model})
                print(f"{tag} chart{i} q{q[:18]}... ok={r.ok} "
                      f"lat={getattr(r,'latency_ms',0)}ms cost=${r.cost:.5f}", flush=True)
    json.dump(rows, open("/tmp/p5_rows.json", "w"), ensure_ascii=False, indent=1)

    judge = OmniProvider(model="antigravity/gemini-3.6-flash-high")
    scores = {m[0]: [] for m in MODELS}
    for row in rows:
        if not row["ok"]:
            continue
        ev = await rubric_eval(make_chart(row["chart"]), row["text"], judge)
        row["rubric"] = ev
        if ev:
            scores[row["tag"]].append(ev)
    json.dump(rows, open("/tmp/p5_rows.json", "w"), ensure_ascii=False, indent=1)

    print("\n=== PERSONALIZATION P5 — 5-dim rubric (avg) ===")
    for tag, lst in scores.items():
        if not lst:
            print(f"{tag}: NO VALID EVALS")
            continue
        a = {k: round(sum(r[k] for r in lst) / len(lst), 2) for k in lst[0]}
        cost = sum(r["cost"] for r in rows if r["tag"] == tag)
        lats = [r["latency_ms"] for r in rows if r["tag"] == tag and r["ok"]]
        print(f"{tag}: {a} | n={len(lst)} | cost=${cost:.4f} | "
              f"p50={sorted(lats)[len(lats)//2] if lats else 0}ms")
    print("TOTAL COST:", round(sum(r["cost"] for r in rows), 4))


if __name__ == "__main__":
    asyncio.run(main())