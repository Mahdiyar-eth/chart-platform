"""Phase 2 'after': top-3 models x 10 charts with NEW chat prompt (v2)."""
import asyncio, json, sys
sys.path.insert(0, "/root/chart-platform")
import httpx
from scripts.model_cmp import make_chart, build_prompt, get_sysprompt, OMNI, OMNI_KEY, QUESTIONS

MODELS = [
    ("pro-go-direct", None, "deepseek-v4-pro"),
    ("gemini-3.6-high", "antigravity/gemini-3.6-flash-high", None),
    ("claude-sonnet-4-6", "antigravity/claude-sonnet-4-6", None),
]
SYS_V2 = get_sysprompt()  # NOW the v2 prompt (imported after patch)

async def call_omni(client, model, prompt, sysp):
    t0 = __import__("time").monotonic()
    r = await client.post(OMNI, json={"model": model,
        "messages": [{"role": "system", "content": sysp}, {"role": "user", "content": prompt}],
        "max_tokens": 1024, "temperature": 0.7, "stream": False},
        headers={"Authorization": f"Bearer {OMNI_KEY}"}, timeout=180)
    dt = __import__("time").monotonic() - t0
    if r.status_code != 200:
        return {"ok": False, "err": r.text[:200], "latency": dt, "status": r.status_code}
    j = r.json(); u = j.get("usage") or {}
    return {"ok": True, "text": j["choices"][0]["message"]["content"], "in": u.get("prompt_tokens", 0),
            "out": u.get("completion_tokens", 0), "latency": dt, "status": 200}

async def main():
    sem = asyncio.Semaphore(4)
    out = []
    open("/tmp/model_cmp_after.jsonl", "w", encoding="utf-8").close()
    for key, om_model, _ in MODELS:
        for i in range(10):
            chart = make_chart(i + 5); chart["_i"] = i
            route, ctx, prompt = build_prompt(chart, QUESTIONS[i])
            async with sem:
                if om_model is None:
                    from app.core.llm import build_go_pool
                    pool = build_go_pool(model="deepseek-v4-pro")
                    t0 = __import__("time").monotonic()
                    res = await pool.complete(prompt, system=SYS_V2, max_tokens=1024, temperature=0.7)
                    dt = __import__("time").monotonic() - t0
                    rec = {"key": key, "i": i, "ok": bool(res.text), "text": res.text or "",
                           "in": getattr(res.usage, "prompt_tokens", 0), "out": getattr(res.usage, "completion_tokens", 0),
                           "latency": dt, "status": 200 if res.text else 500}
                else:
                    async with httpx.AsyncClient() as c:
                        r = await call_omni(c, om_model, prompt, SYS_V2)
                    rec = {"key": key, "i": i, "ok": r["ok"], "text": r.get("text", ""),
                           "in": r.get("in", 0), "out": r.get("out", 0), "latency": r.get("latency", 0), "status": r.get("status")}
                out.append(rec)
                with open("/tmp/model_cmp_after.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("DONE", len(out))

asyncio.run(main())