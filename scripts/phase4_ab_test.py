"""Phase 4 — A/B: deepseek-v4-pro thinking OFF vs ON on 20 charts (chat prompt v2).
Direct GO call, same key, same model; only the thinking flag differs.
"""
import asyncio, json, sys, time
sys.path.insert(0, "/root/chart-platform")
import httpx
from scripts.ai_benchmark_v4 import make_chart
from scripts.model_cmp import build_prompt, get_sysprompt, QUESTIONS

API_BASE = "https://opencode.ai/zen/go/v1"
KEY = ""  # filled from .env GO_API_KEYS third slot
for k in open("/root/chart-platform/.env").read().splitlines():
    if k.startswith("GO_API_KEYS="):
        slots = k.split("=", 1)[1].split(",")
        KEY = slots[-1].split("@")[0].strip().strip('"').strip("'")

SYSV2 = get_sysprompt()
PRICE = (0.435, 0.87)

async def call(mode: str, prompt: str, sysp: str) -> dict:
    payload = {"model": "deepseek-v4-pro", "messages": [
        {"role": "system", "content": sysp}, {"role": "user", "content": prompt}],
        "max_tokens": 1024, "temperature": 0.7,
        "thinking": {"type": "enabled" if mode == "on" else "disabled"}}
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=300) as c:
        r = await c.post(f"{API_BASE}/chat/completions", json=payload,
                         headers={"Authorization": f"Bearer {KEY}"})
    dt = time.monotonic() - t0
    if r.status_code != 200:
        return {"ok": False, "text": "", "err": r.text[:150], "latency": dt}
    j = r.json()
    u = j.get("usage") or {}
    return {"ok": True, "text": j["choices"][0]["message"].get("content") or "",
            "in": u.get("prompt_tokens", 0), "out": u.get("completion_tokens", 0), "latency": dt}

async def run_mode(mode: str, charts, prompts) -> list:
    sem = asyncio.Semaphore(3)
    rows = []
    async def one(i, prompt):
        async with sem:
            r = await call(mode, prompt, SYSV2)
            return {"mode": mode, "i": i, **r}
    for res in await asyncio.gather(*[one(i, p) for i, p in enumerate(prompts)]):
        rows.append(res)
    return rows

def main():
    charts = [make_chart(i + 20) for i in range(20)]
    prompts = []
    for i, c in enumerate(charts):
        c["_i"] = i
        _, _, p = build_prompt(c, QUESTIONS[i % 10])
        prompts.append(p)
    rows = []
    for mode in ("on", "off"):
        print(f"--- thinking {mode} ---", flush=True)
        rr = asyncio.run(run_mode(mode, charts, prompts))
        ok = sum(1 for r in rr if r["ok"])
        lats = sorted(r["latency"] for r in rr if r["ok"])
        tin = sum(r["in"] for r in rr); tout = sum(r["out"] for r in rr)
        cost = (tin * PRICE[0] + tout * PRICE[1]) / 1e6
        print(f"  ok={ok}/20 p50={lats[len(lats)//2]:.1f}s max={max(lats):.1f}s "
              f"tokens_in={tin} out={tout} cost=${cost:.4f}", flush=True)
        for r in rr:
            r["cost"] = (r["in"] * PRICE[0] + r["out"] * PRICE[1]) / 1e6
        rows.extend(rr)
    json.dump(rows, open("/tmp/phase4_ab.json", "w"), ensure_ascii=False)
    print("SAVED /tmp/phase4_ab.json")

if __name__ == "__main__":
    main()