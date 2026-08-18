"""P5 v5 — personalization on REAL production charts (with engine houses).

make_chart has no houses → models hallucinate them and the judge penalizes.
Real charts from DB carry houses/sign_fa per planet — the honest test.
"""
import asyncio, json, re, subprocess, sys
sys.path.insert(0, "/root/chart-platform")
from scripts.ai_benchmark_v4 import rubric_eval
from app.chat.service import _retrieve
from app.chat.retrieval import CHAT_SYSTEM_PROMPT
from app.core.llm import OmniProvider, build_go_pool

QUESTIONS = [
    "در زندگی عاطفی‌ام چه چالش‌هایی دارم و چطور با آنها کنار بیایم؟",
    "بهترین مسیر شغلی برای من چیست؟",
]

env = open("/root/chart-platform/.env").read()
url = re.search(r'^DATABASE_URL=(.+)$', env, re.M).group(1).strip()
r = subprocess.run(["psql", "-q", url, "-t", "-A", "-c",
                    "SELECT chart_json FROM charts WHERE chart_json ? 'planets' "
                    "ORDER BY created_at DESC LIMIT 8"], capture_output=True, text=True)
CHARTS = [json.loads(l) for l in r.stdout.splitlines() if l.strip()][:6]
print("real charts:", len(CHARTS))


async def main():
    pools = {k: build_go_pool(model=m) for k, m in
             (("flash-go", "deepseek-v4-flash"), ("pro-go", "deepseek-v4-pro"))}
    omni = OmniProvider(model="antigravity/gemini-3.6-flash-high")
    judge_pro = build_go_pool(model="deepseek-v4-pro")
    rows = []
    for tag, prov in [("gemini-real", omni), ("flash-real", pools["flash-go"]),
                      ("pro-real", pools["pro-go"])]:
        for i, chart in enumerate(CHARTS):
            for q in QUESTIONS:
                _, ctx, prompt = _retrieve(q, chart, None, None, None)
                r = await prov.complete(prompt, system=CHAT_SYSTEM_PROMPT,
                                        max_tokens=700, temperature=0.7)
                rows.append({"tag": tag, "chart": i, "text": (r.text or "")[:2500],
                             "ok": r.ok, "cost": r.cost})
                print(f"{tag} chart{i} ok={r.ok}", flush=True)
    json.dump(rows, open("/tmp/p5v5_rows.json", "w"), ensure_ascii=False, indent=1)
    scores = {}
    for row in rows:
        if not row["ok"]:
            continue
        ev = await rubric_eval(CHARTS[row["chart"]], row["text"], judge_pro)
        if ev:
            scores.setdefault(row["tag"], []).append(ev)
        await asyncio.sleep(0.3)
    json.dump(rows, open("/tmp/p5v5_rows.json", "w"), ensure_ascii=False, indent=1)
    print("\n=== P5 v5 — REAL charts (engine houses) — GO-pro judge ===")
    for tag in ["gemini-real", "flash-real", "pro-real"]:
        lst = scores.get(tag, [])
        if lst:
            a = {k: round(sum(r[k] for r in lst) / len(lst), 2) for k in lst[0]}
            print(f"{tag}: {a} | n={len(lst)}")


if __name__ == "__main__":
    asyncio.run(main())