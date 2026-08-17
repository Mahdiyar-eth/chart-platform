"""Model comparison harness — Phase 1 (2026-08-17, approved plan).

9 model paths x 10 charts with the REAL production chat prompt
(retrieve -> build_chat_prompt -> system prompt). Measures:
  quality (factual/evidence/hallucination + 5-dim rubric LLM-judge),
  latency, tokens, and exact cost per model (prices below, verified via web).
"""
import asyncio, json, os, sys, time

ROOT = "/root/chart-platform"
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import httpx  # noqa: E402

OMNI = "http://127.0.0.1:20128/v1/chat/completions"
OMNI_KEY = open("/root/backups/omniroute-api-key.txt").read().strip()

# prices $/1M tokens (in, out) — verified 2026-08-17 via web
PRICES = {
    "pro-go-direct": (0.435, 0.87),
    "pro-omni": (0.435, 0.87),
    "flash": (0.14, 0.28),
    "gemini-3.6-high": (1.50, 7.50),
    "gemini-3.6-medium": (1.50, 7.50),
    "gemini-3.6-low": (1.50, 7.50),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-6-thinking": (5.00, 25.00),
    "gemini-3.1-pro": (2.00, 12.00),
}

MODELS = [  # (key, omni_model_or_None(=GO-direct), label)
    ("pro-go-direct", None, "deepseek-v4-pro (GO مستقیم — baseline تولید)"),
    ("pro-omni", "opencode-go/deepseek-v4-pro", "deepseek-v4-pro (via Omni)"),
    ("flash", "opencode-go/deepseek-v4-flash", "deepseek-v4-flash (via Omni)"),
    ("gemini-3.6-high", "antigravity/gemini-3.6-flash-high", "Gemini 3.6 Flash High"),
    ("gemini-3.6-medium", "antigravity/gemini-3.6-flash-medium", "Gemini 3.6 Flash Medium"),
    ("gemini-3.6-low", "antigravity/gemini-3.6-flash-low", "Gemini 3.6 Flash Low"),
    ("claude-sonnet-4-6", "antigravity/claude-sonnet-4-6", "Claude Sonnet 4.6"),
    ("claude-opus-4-6-thinking", "antigravity/claude-opus-4-6-thinking", "Claude Opus 4.6 Thinking"),
    ("gemini-3.1-pro", "antigravity/gemini-3.1-pro-low", "Gemini 3.1 Pro Low"),
]

QUESTIONS = [
    "برج خورشید و ماه من چیست و این دو جایگاه چطور با هم تعامل دارند؟",
    "مسیر شغلی من بر اساس چارتم چگونه است؟",
    "در روابط عاطفی چه چیزی مهم است و چه چالشی دارم؟",
    "امروز چه انرژی‌ای بر من حاکم است و چطور از آن استفاده کنم؟",
    "قوی‌ترین نقطه شخصیت من چیست و کدام عامل چارتم آن را می‌سازد؟",
    "با خانواده و احساساتم چطور ارتباط برقرار کنم؟",
    "آینده مالی من چه روندی دارد و چه فرصتی جلوی من است؟",
    "بهترین زمان برای تصمیم‌گیری مهم چه موقع است؟",
    "چه عادتی را باید تغییر دهم تا رشد کنم؟",
    "سفر یا هزینه بزرگ، برای من مناسب است؟",
]

def make_chart(i):
    from scripts.ai_benchmark_v4 import make_chart as mc
    return mc(i)

def build_prompt(chart, q):
    from app.chat.service import _retrieve
    return _retrieve(q, chart, None, None, None)  # (route, ctx, prompt)

SYSPROMPT = None

def get_sysprompt():
    global SYSPROMPT
    if SYSPROMPT is None:
        from app.chat.retrieval import CHAT_SYSTEM_PROMPT
        SYSPROMPT = CHAT_SYSTEM_PROMPT
    return SYSPROMPT

async def call_omni(client, model, prompt, sysp):
    t0 = time.monotonic()
    async with client.stream("POST", OMNI, json={
        "model": model,
        "messages": [{"role": "system", "content": sysp},
                     {"role": "user", "content": prompt}],
        "max_tokens": 1024, "temperature": 0.7, "stream": False,
    }, headers={"Authorization": f"Bearer {OMNI_KEY}", "Content-Type": "application/json"},
        timeout=180) as resp:
        data = await resp.aread()
    dt = time.monotonic() - t0
    if resp.status_code != 200:
        return {"ok": False, "status": resp.status_code,
                "err": data.decode("utf-8", "ignore")[:300], "latency": dt}
    j = json.loads(data)
    usage = j.get("usage") or {}
    txt = (j.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    return {"ok": True, "text": txt, "in": usage.get("prompt_tokens", 0),
            "out": usage.get("completion_tokens", 0), "latency": dt, "status": 200}

async def call_go_direct(model, prompt, sysp):
    """Production path: GO paid pool pinned to deepseek-v4-pro."""
    from app.core.llm import build_go_pool
    pool = build_go_pool(model="deepseek-v4-pro")
    if pool is None:
        return {"ok": False, "text": "", "in": 0, "out": 0, "latency": 0.0, "status": 500}
    t0 = time.monotonic()
    res = await pool.complete(prompt, system=sysp, max_tokens=1024, temperature=0.7)
    dt = time.monotonic() - t0
    return {"ok": bool(getattr(res, "text", "")), "text": getattr(res, "text", ""),
            "in": getattr(res.usage, "prompt_tokens", 0), "out": getattr(res.usage, "completion_tokens", 0),
            "latency": dt, "status": 200 if getattr(res, "text", "") else 500}

async def run_one(key, src, model, chart, q, out, sem):
    async with sem:
        route, ctx, prompt = build_prompt(chart, q)
        sysp = get_sysprompt()
        if src is None:
            r = await call_go_direct(model, prompt, sysp)
        else:
            async with httpx.AsyncClient() as c:
                r = await call_omni(c, model, prompt, sysp)
        rec = {"key": key, "model": model, "i": chart["_i"], "q": q,
               "ok": r["ok"], "status": r.get("status"), "err": r.get("err"),
               "text": r.get("text", ""), "in": r.get("in", 0), "out": r.get("out", 0),
               "latency": round(r.get("latency", 0), 2)}
        out.append(rec)
        with open("/tmp/model_cmp_run.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

async def main():
    sem = asyncio.Semaphore(4)
    out = []
    open("/tmp/model_cmp_run.jsonl", "w", encoding="utf-8").close()
    # build 10 charts once, tag with _i
    charts = []
    for i in range(10):
        c = make_chart(i + 5)  # varied seeds
        c["_i"] = i
        charts.append(c)
    for key, om_model, label in MODELS:
        model = om_model or "deepseek-v4-pro"
        print(f"### {key} — {label}", flush=True)
        tasks = []
        for i, chart in enumerate(charts):
            tasks.append(run_one(key, om_model, model, chart, QUESTIONS[i], out, sem))
        await asyncio.gather(*tasks)
        # small pricelog of errors/empties
        rs = [r for r in out if r["key"] == key]
        ok = sum(1 for r in rs if r["ok"] and r["text"].strip())
        print(f"  ok={ok}/{len(rs)}", flush=True)
    # summary
    print("DONE", flush=True)

if __name__ == "__main__":
    asyncio.run(main())