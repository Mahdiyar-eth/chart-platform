"""P5 v2 — personalization comparison (PRODUCTION context via _retrieve).

v1 was invalid: the thin hand-made context lacked houses/domains/insights,
so models hallucinated houses and the judge scored genericness. v2 uses the
real production context builder (app.chat.service._retrieve) exactly like
phase 2 — comparable numbers. pro-thinking uses phase-4 parsing.
"""
import asyncio, json, sys, time
sys.path.insert(0, "/root/chart-platform")
import httpx

from scripts.ai_benchmark_v4 import make_chart, rubric_eval
from app.chat.service import _retrieve
from app.chat.retrieval import CHAT_SYSTEM_PROMPT
from app.core.llm import OmniProvider, build_go_pool

QUESTIONS = [
    "در زندگی عاطفی‌ام چه چالش‌هایی دارم و چطور با آنها کنار بیایم؟",
    "بهترین مسیر شغلی برای من چیست؟",
]

API_BASE = "https://opencode.ai/zen/go/v1"
envk = open("/root/chart-platform/.env").read()
GO_KEY = ""
for ln in envk.splitlines():
    if ln.startswith("GO_API_KEYS="):
        GO_KEY = ln.split("=", 1)[1].split(",")[-1].split("@")[0].strip().strip("\"'")
        break


async def call_go_thinking(user: str, sysp: str) -> dict:
    payload = {"model": "deepseek-v4-pro", "messages": [
        {"role": "system", "content": sysp}, {"role": "user", "content": user}],
        "max_tokens": 1024, "temperature": 0.7,
        "thinking": {"type": "enabled"}}
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=300) as c:
        r = await c.post(f"{API_BASE}/chat/completions", json=payload,
                         headers={"Authorization": f"Bearer {GO_KEY}"})
    dt = time.monotonic() - t0
    j = r.json() if r.status_code == 200 else {}
    msg = (j.get("choices") or [{}])[0].get("message") or {}
    text = msg.get("content") or msg.get("reasoning_content") or ""
    u = j.get("usage") or {}
    cost = (u.get("prompt_tokens", 0) * 0.435 + u.get("completion_tokens", 0) * 0.87) / 1e6
    return {"ok": r.status_code == 200 and bool(text.strip()),
            "text": text[:2500], "cost": cost, "latency_ms": int(dt * 1000),
            "error": (r.text[:150] if r.status_code != 200 else "")}


async def main():
    pools = {k: build_go_pool(model=m) for k, m in
             (("flash-go", "deepseek-v4-flash"), ("pro-go", "deepseek-v4-pro"))}
    omni_gemini = OmniProvider(model="antigravity/gemini-3.6-flash-high")
    MODELS = [("gemini-high", "omni"), ("flash-go", "go"), ("pro-go", "go"),
              ("pro-thinking", "gothink")]
    rows = []
    for tag, kind in MODELS:
        for i in range(6):
            chart = make_chart(i + 30)
            for q in QUESTIONS:
                _, ctx, prompt = _retrieve(q, chart, None, None, None)
                if kind == "omni":
                    r = await omni_gemini.complete(prompt, system=CHAT_SYSTEM_PROMPT,
                                                   max_tokens=700, temperature=0.7)
                elif kind == "gothink":
                    _d = await call_go_thinking(prompt, CHAT_SYSTEM_PROMPT)
                    r = type("R", (), {"ok": _d["ok"], "text": _d["text"],
                                       "cost": _d["cost"],
                                       "latency_ms": _d["latency_ms"],
                                       "error": _d["error"]})()
                else:
                    r = await pools[tag].complete(prompt, system=CHAT_SYSTEM_PROMPT,
                                                  max_tokens=700, temperature=0.7)
                row = {"tag": tag, "chart": i, "q": q, "ok": r.ok,
                       "text": (r.text or "")[:2500], "cost": getattr(r, "cost", 0),
                       "latency_ms": int(getattr(r, "latency_ms", 0) or 0),
                       "error": (getattr(r, "error", "") or "")[:150]}
                rows.append(row)
                print(f"{tag} chart{i} ok={row['ok']} lat={row['latency_ms']}ms "
                      f"cost=${row['cost']:.5f}", flush=True)
    json.dump(rows, open("/tmp/p5v2_rows.json", "w"), ensure_ascii=False, indent=1)

    judge = OmniProvider(model="antigravity/gemini-3.6-flash-high")
    scores = {}
    for row in rows:
        if not row["ok"]:
            continue
        ev = await rubric_eval(make_chart(row["chart"]), row["text"], judge)
        row["rubric"] = ev
        if ev:
            scores.setdefault(row["tag"], []).append(ev)
        await asyncio.sleep(0.4)  # gentle pace — don't saturate the gateway
    json.dump(rows, open("/tmp/p5v2_rows.json", "w"), ensure_ascii=False, indent=1)

    print("\n=== PERSONALIZATION P5 v2 — production-context rubric (avg) ===")
    for tag, kind in MODELS:
        lst = scores.get(tag, [])
        if not lst:
            print(f"{tag}: NO VALID EVALS")
            continue
        a = {k: round(sum(r[k] for r in lst) / len(lst), 2) for k in lst[0]}
        cost = sum(r["cost"] for r in rows if r["tag"] == tag)
        lats = sorted(r["latency_ms"] for r in rows if r["tag"] == tag and r["ok"])
        print(f"{tag}: {a} | n={len(lst)} | cost=${cost:.4f} | "
              f"p50={lats[len(lats)//2] if lats else 0}ms")
    total = sum(r["cost"] for r in rows)
    print("TOTAL COST: %.4f" % total)


if __name__ == "__main__":
    asyncio.run(main())