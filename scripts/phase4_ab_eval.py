"""Phase 4 eval — rubric comparison thinking-ON vs OFF (uses the proven benchmark rubric)."""
import asyncio, json, re, sys
sys.path.insert(0, "/root/chart-platform")
import app.config
from app.core.llm import build_go_pool
from scripts.ai_benchmark_v4 import make_chart, RUBRIC_PROMPT, rubric_eval

RB = ["personalization", "coherence", "persian", "tone", "contradiction"]

async def main():
    pool = build_go_pool(model="deepseek-v4-pro")
    if pool is None:
        print("pool unavailable"); return
    # reuse the benchmark's own router wrapper so the rubric is unit-identical
    class Router:
        async def complete(self, prompt, system, max_tokens=120, temperature=0.0, json_mode=False):
            res = await pool.complete(prompt, system=system, max_tokens=max_tokens, temperature=temperature)
            return res
    router = Router()
    data = json.load(open("/tmp/phase4_ab.json"))
    charts = {i: make_chart(i + 5) for i in range(20)}
    agg = {m: {k: [] for k in RB} for m in ("on", "off")}
    fails = {m: 0 for m in ("on", "off")}
    for row in data:
        rb = await rubric_eval(charts[row["i"]], row["text"], router)
        if not rb:
            fails[row["mode"]] += 1
            continue
        for k in RB:
            try:
                agg[row["mode"]][k].append(int(rb.get(k, 0)))
            except Exception:
                pass
    res = {}
    for m in ("on", "off"):
        res[m] = {k: round(sum(v) / len(v), 2) if v else None for k, v in agg[m].items()}
        res[m]["n"] = len(agg[m]["personalization"])
        res[m]["rubric_fails"] = fails[m]
    print(json.dumps(res, ensure_ascii=False, indent=1))

asyncio.run(main())