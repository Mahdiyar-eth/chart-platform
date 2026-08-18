"""P5 v4 — personalization before/after prompt v3 (gemini + flash only)."""
import asyncio, json, sys
sys.path.insert(0, "/root/chart-platform")
import httpx, time
from scripts.ai_benchmark_v4 import make_chart, rubric_eval
from app.chat.service import _retrieve
from app.chat.retrieval import CHAT_SYSTEM_PROMPT
from app.core.llm import OmniProvider, build_go_pool

QUESTIONS = [
    "در زندگی عاطفی‌ام چه چالش‌هایی دارم و چطور با آنها کنار بیایم؟",
    "بهترین مسیر شغلی برای من چیست؟",
]

async def main():
    pools = {k: build_go_pool(model=m) for k, m in
             (("flash-go", "deepseek-v4-flash"),)}
    omni = OmniProvider(model="antigravity/gemini-3.6-flash-high")
    judge_pro = build_go_pool(model="deepseek-v4-pro")
    rows = []
    for tag, kind, prov in [("gemini-v3", "omni", omni), ("flash-v3", "go", pools["flash-go"])]:
        for i in range(6):
            chart = make_chart(i + 30)
            for q in QUESTIONS:
                _, ctx, prompt = _retrieve(q, chart, None, None, None)
                r = await prov.complete(prompt, system=CHAT_SYSTEM_PROMPT,
                                        max_tokens=700, temperature=0.7)
                rows.append({"tag": tag, "chart": i, "text": (r.text or "")[:2500],
                             "ok": r.ok, "cost": r.cost,
                             "latency_ms": int(getattr(r, "latency_ms", 0) or 0)})
                print(f"{tag} chart{i} ok={r.ok}", flush=True)
    json.dump(rows, open("/tmp/p5v4_rows.json", "w"), ensure_ascii=False, indent=1)
    scores = {}
    for row in rows:
        if not row["ok"]:
            continue
        ev = await rubric_eval(make_chart(row["chart"]), row["text"], judge_pro)
        if ev:
            scores.setdefault(row["tag"], []).append(ev)
        await asyncio.sleep(0.3)
    print("\n=== P5 v4 — prompt v3 before/after (GO-pro judge) ===")
    for tag in ["gemini-v3", "flash-v3"]:
        lst = [r for r in scores.get(tag, [])]
        if lst:
            a = {k: round(sum(r[k] for r in lst) / len(lst), 2) for k in lst[0]}
            print(f"{tag}: {a} | n={len(lst)}")


if __name__ == "__main__":
    asyncio.run(main())