"""Phase 2: evaluate the AFTER (v2 prompt) run — grounding + rubric vs BEFORE."""
import asyncio, json, re, sys
sys.path.insert(0, "/root/chart-platform")
from scripts.ai_benchmark_v4 import SIGNS_FA, make_chart
from scripts.model_cmp_eval2 import planet_sign_pairs, norm, RUBRIC
from app.core.llm import build_go_pool

rows = [json.loads(l) for l in open("/tmp/model_cmp_after.jsonl", encoding="utf-8")]
charts = [make_chart(i + 5) for i in range(10)]
PRICE = {"pro-go-direct": (0.435, 0.87), "gemini-3.6-high": (1.50, 7.50), "claude-sonnet-4-6": (3.0, 15.0)}

def eval_row(chart, text):
    t = norm(text)
    real = {}
    for pen, p in chart["planets"].items():
        real[pen] = int(p["longitude"] // 30) % 12
    if chart.get("ascendant"):
        real["ASC"] = int(chart["ascendant"]["longitude"] // 30) % 12
    pairs = planet_sign_pairs(t)
    if not pairs:
        return {"grounded": False, "halluc": False, "npairs": 0}
    ok = sum(1 for p, s in pairs if real.get(p) == s)
    bad = sum(1 for p, s in pairs if p in real and real[p] != s)
    return {"grounded": ok >= 1, "halluc": bad > 0, "npairs": len(pairs)}

summary = {}
for key in sorted(set(r["key"] for r in rows)):
    rs = [r for r in rows if r["key"] == key]
    g = sum(eval_row(charts[r["i"]], r["text"])["grounded"] for r in rs)
    h = sum(eval_row(charts[r["i"]], r["text"])["halluc"] for r in rs)
    lats = sorted(r["latency"] for r in rs)
    tin = sum(r["in"] for r in rs); tout = sum(r["out"] for r in rs)
    pin, pout = PRICE[key]
    cost = round((tin * pin + tout * pout) / 1e6, 5)
    summary[key] = {"n": len(rs), "grounded": g, "halluc": h,
                    "p50": round(lats[len(lats)//2], 2), "max": round(max(lats), 2),
                    "t_in": tin, "t_out": tout, "cost": cost}

pool = build_go_pool(model="deepseek-v4-pro")
async def judge_run():
    sem = asyncio.Semaphore(6)
    results = {k: [] for k in summary}
    async def one(r):
        async with sem:
            c = charts[r["i"]]
            try:
                chart = json.dumps({k: {"longitude": v["longitude"], "sign": SIGNS_FA[int(v["longitude"] // 30) % 12]}
                                    for k, v in c["planets"].items()}, ensure_ascii=False)
            except Exception:
                chart = "chart"
            res = await pool.complete(RUBRIC.format(chart=chart, answer=r["text"]), max_tokens=160, temperature=0)
            txt = res.text or ""
            try:
                m = re.search(r"\{.*\}", txt, re.S)
                d = json.loads(m.group(0))
                return {k: int(d.get(k, 0)) for k in ("persian","coherence","tone","contradiction","personalization")}
            except Exception:
                return None
    for key in summary:
        rs = [r for r in rows if r["key"] == key]
        for res in await asyncio.gather(*[one(r) for r in rs[:6]]):
            if res: results[key].append(res)
    return results

rubric = asyncio.run(judge_run())
agg = {}
for key, list_of_dicts in rubric.items():
    if not list_of_dicts:
        agg[key] = {}
        continue
    agg[key] = {k: round(sum(d[k] for d in list_of_dicts) / len(list_of_dicts), 2) for k in list_of_dicts[0]}

print("MODEL                          grounded halluc p50(s)  cost$   | pers  coh  tone  contra  persn")
for key, s in summary.items():
    a = agg.get(key, {})
    print(f"{key:30s} {s['grounded']:>3}/{s['n']:<2} {s['halluc']:>5} {s['p50']:>6.1f} {s['cost']:>7.5f} | "
          f"{a.get('persian','-'):>4} {a.get('coherence','-'):>4} {a.get('tone','-'):>4} {a.get('contradiction','-'):>5} {a.get('personalization','-'):>4}")
json.dump({"summary": summary, "rubric": agg}, open("/tmp/model_cmp_after_eval.json", "w"), ensure_ascii=False, indent=1)
print("saved /tmp/model_cmp_after_eval.json")