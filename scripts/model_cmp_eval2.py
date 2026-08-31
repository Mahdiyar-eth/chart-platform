"""Phase 1 eval v2: per-planet grounding + hallucination + 5-dim rubric (fixed judge)."""
import asyncio, json, re, sys
sys.path.insert(0, "/root/chart-platform")
from scripts.ai_benchmark_v4 import SIGNS_FA
from app.core.llm import build_go_pool

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

def sign_fa(lon):
    return SIGNS_FA[int(lon // 30) % 12]

def norm(t):
    return t.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ").replace("ِ", "").replace("ْ", "")

PLANET_FA = {"خورشید": "Sun", "ماه": "Moon", "عطارد": "Mercury", "زهره": "Venus",
             "مریخ": "Mars", "مشتری": "Jupiter", "زحل": "Saturn", "اورانوس": "Uranus",
             "نپتون": "Neptune", "پلوتو": "Pluto", "طالع": "ASC"}
SIGN_PAT = "|".join(SIGNS_FA)

def planet_sign_pairs(text):
    """Find (planet, sign_index) pairs from phrases like 'X در برج Y' / 'X در Y'."""
    t = norm(text)
    pairs = []
    for pfa, pen in PLANET_FA.items():
        for m in re.finditer(rf"{pfa}\s*(?:شما|تان|ت|تو)?\s*(?:در\s*)?(?:برج|نشان|منطقه)?\s*({SIGN_PAT})", t):
            sfa = m.group(1).strip()
            pairs.append((pen, SIGNS_FA.index(sfa)))
    return pairs

def eval_row(chart, text):
    t = norm(text)
    real = {}
    for pen, p in chart["planets"].items():
        real[pen] = int(p["longitude"] // 30) % 12
    real["ASC"] = int(chart["angles"]["ASC"]["longitude"] // 30) % 12
    pairs = planet_sign_pairs(t)
    if not pairs:
        return {"grounded": False, "halluc": False, "pairs": 0}
    ok = sum(1 for p, s in pairs if real.get(p) == s)
    bad = sum(1 for p, s in pairs if p in real and real[p] != s)
    return {"grounded": ok >= 1, "halluc": bad == 0, "pairs": len(pairs), "ok_pairs": ok, "bad_pairs": bad}

RUBRIC = """تو یک ارزیاب کیفیت متن فارسی هستی. یک پاسخ نجومی (بر اساس چارت تولد) را با ۵ معیار از ۰ تا ۱۰ امتیاز بده. فقط خروجی JSON بده:
{{"personalization": n, "coherence": n, "persian": n, "tone": n, "contradiction": n}}
- personalization: چقدر به جزئیات اختصاصی همین چارت اشاره دارد (نه متن عمومی/تکراری)؛ هرچه واقعیتهای عینی بیشتری از همین چارت ذکر کند و تفسیر با «تو/شما» باشد، بالاتر
- coherence: ساختار منطقی، پیوسته، بدون قطعهقطعهبودن
- persian: روانی، دستور زبان، رسمالخط درست فارسی
- tone: لحن مناسب (آگاهیبخش، محترمانه، بدون ترساندن یا اغراق)
- contradiction: ۱۰ = بدون تناقض داخلی، ۰ = تناقض آشکار
چارت: {chart}
پاسخ: {answer}"""

def main():
    rows = [json.loads(l) for l in open("/tmp/model_cmp_run.jsonl", encoding="utf-8")]
    from scripts.ai_benchmark_v4 import make_chart
    charts = {i: make_chart(i + 5) for i in range(10)}
    summary = {}
    for key in sorted(set(r["key"] for r in rows)):
        rs = [r for r in rows if r["key"] == key]
        grounded = 0; halluc = 0; lats = []; tin = 0; tout = 0
        rb = {"personalization": [], "coherence": [], "persian": [], "tone": [], "contradiction": []}
        for r in rs:
            c = charts[r["i"]]
            if not r["ok"] or not r["text"].strip():
                continue
            e = eval_row(c, r["text"])
            grounded += e["grounded"]; halluc += (not e["halluc"])
            lats.append(r["latency"]); tin += r["in"]; tout += r["out"]
        n = len(rs)
        pin, pout = PRICES[key]
        lats.sort()
        summary[key] = {"n": n, "grounded": grounded, "halluc_answers": halluc,
                        "p50": lats[len(lats)//2], "max": max(lats), "t_in": tin, "t_out": tout,
                        "cost": round((tin*pin + tout*pout)/1e6, 5)}
    # rubric judge — run only for models that matter (fixed judge = GO pro)
    pool = build_go_pool(model="deepseek-v4-pro")
    async def judge():
        sem = asyncio.Semaphore(6)
        results = {}
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
                    return {k: int(d.get(k, 0)) for k in rb}
                except Exception:
                    return None
        for key in summary:
            results[key] = []
            rs = [r for r in rows if r["key"] == key]
            for res in await asyncio.gather(*[one(r) for r in rs[:6]]):
                if res: results[key].append(res)
        return results
    rb_results = asyncio.run(judge())
    print(f"{'مدل':32s} grounded halluc  p50(s)  cost$   | pers  coh  tone  contra  persn")
    for k, v in summary.items():
        rr = rb_results.get(k, [])
        def avg(f):
            xs = [r[f] for r in rr]
            return round(sum(xs)/len(xs), 1) if xs else 0
        print(f"{LABELS[k]:32s} {v['grounded']:2d}/10  {v['halluc_answers']:2d}/10  {v['p50']:5.1f}  {v['cost']:8.5f} | "
              f"{avg('persian')}  {avg('coherence')}  {avg('tone')}  {avg('contradiction')}  {avg('personalization')}")
    json.dump({"summary": summary, "rubric": {k: v for k, v in rb_results.items()}},
              open("/tmp/model_cmp_eval2.json", "w"), ensure_ascii=False, indent=1)

main()