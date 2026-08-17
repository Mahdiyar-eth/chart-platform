"""Phase 1 evaluation: facts + evidence + 5-dim rubric + cost per model."""
import asyncio, json, re, sys
sys.path.insert(0, "/root/chart-platform")
from scripts.ai_benchmark_v4 import SIGNS, SIGNS_FA
from app.core.llm import build_go_pool

SUN = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]

def sign_fa(lon):
    return SIGNS_FA[int(lon // 30) % 12]

def norm(t):
    return t.replace("ي", "ی").replace("ك", "ک")

def check_factual(chart, text):
    sun_lon = chart["planets"]["Sun"]["longitude"]
    sun_fa = sign_fa(sun_lon)
    t = norm(text)
    return sun_fa in t or SUN[int(sun_lon // 30) % 12].lower() in t.lower()

def sign_mentions(text):
    t = norm(text)
    out = set()
    for i, s in enumerate(SIGNS_FA):
        if s in t:
            out.add(i)
        if SIGNS[i].lower() in t.lower():
            out.add(i)
    return out

def check_evidence(chart, text):
    real = {int(p["longitude"] // 30) % 12 for p in chart["planets"].values()}
    real.add(int(chart["angles"]["ASC"]["longitude"] // 30) % 12)
    mentioned = sign_mentions(text)
    return mentioned <= real, sorted(mentioned - real)

PRICES = {
    "pro-go-direct": (0.435, 0.87), "pro-omni": (0.435, 0.87), "flash": (0.14, 0.28),
    "gemini-3.6-high": (1.50, 7.50), "gemini-3.6-medium": (1.50, 7.50), "gemini-3.6-low": (1.50, 7.50),
    "claude-sonnet-4-6": (3.00, 15.00), "claude-opus-4-6-thinking": (5.00, 25.00), "gemini-3.1-pro": (2.00, 12.00),
}
LABELS = {
    "pro-go-direct": "deepseek-v4-pro (GO مستقیم)", "pro-omni": "deepseek-v4-pro (Omni)",
    "flash": "deepseek-v4-flash (Omni)", "gemini-3.6-high": "Gemini 3.6 Flash High",
    "gemini-3.6-medium": "Gemini 3.6 Flash Medium", "gemini-3.6-low": "Gemini 3.6 Flash Low",
    "claude-sonnet-4-6": "Claude Sonnet 4.6", "claude-opus-4-6-thinking": "Claude Opus 4.6 Thinking",
    "gemini-3.1-pro": "Gemini 3.1 Pro Low",
}

def main():
    rows = [json.loads(l) for l in open("/tmp/model_cmp_run.jsonl", encoding="utf-8")]
    from scripts.ai_benchmark_v4 import make_chart
    charts = {}
    for i in range(10):
        c = make_chart(i + 5); c["_i"] = i
        charts[i] = c
    summary = {}
    for key in set(r["key"] for r in rows):
        rs = [r for r in rows if r["key"] == key]
        facts = 0; evids = 0; empty = 0; lats = []; tin = 0; tout = 0
        badfact = []
        for r in rs:
            c = charts[r["i"]]
            if not r["ok"] or not r["text"].strip():
                empty += 1; continue
            f = check_factual(c, r["text"])
            e, extra = check_evidence(c, r["text"])
            facts += f; evids += e
            if not f or not e:
                badfact.append((r["i"], f, e, extra, r["text"][:100]))
            lats.append(r["latency"]); tin += r["in"]; tout += r["out"]
        n = len(rs) - empty
        pin, pout = PRICES[key]
        cost = (tin * pin + tout * pout) / 1e6
        lats.sort()
        summary[key] = {"n": n, "empty": empty, "factual": round(100 * facts / max(n,1), 1),
                        "evidence": round(100 * evids / max(n,1), 1),
                        "lat_p50": round(lats[len(lats)//2], 1), "lat_max": round(max(lats), 1),
                        "t_in": tin, "t_out": tout, "cost": round(cost, 4), "bad": badfact[:2]}
    for k, v in summary.items():
        print(f"{LABELS[k]:32s} n={v['n']:2d} factual={v['factual']:5.1f}% evid={v['evidence']:5.1f}% "
              f"p50={v['lat_p50']:6.1f}s max={v['lat_max']:6.1f}s tok={v['t_in']+v['t_out']:6d} cost=${v['cost']:.4f}")
        for b in v["bad"]:
            print("   bad:", b)
    json.dump(summary, open("/tmp/model_cmp_eval.json", "w"), ensure_ascii=False, indent=1)

main()