"""P5 v3 — re-judge the saved p5v2 answers with the GO-pro rubric judge
(phase-2's judge) to make absolute scores comparable."""
import asyncio, json, sys
sys.path.insert(0, "/root/chart-platform")
from scripts.ai_benchmark_v4 import make_chart, rubric_eval
from app.core.llm import build_go_pool

ROWS = json.load(open("/tmp/p5v2_rows.json"))
CHART_INDEX = {r["chart"]: r for r in ROWS}  # any row carries its chart idx


async def main():
    judge = build_go_pool(model="deepseek-v4-pro")
    scores = {}
    for row in ROWS:
        if not row["ok"] or row.get("rubric_pro"):
            continue
        ev = await rubric_eval(make_chart(row["chart"]), row["text"], judge)
        row["rubric_pro"] = ev
        if ev:
            scores.setdefault(row["tag"], []).append(ev)
        await asyncio.sleep(0.3)
    json.dump(ROWS, open("/tmp/p5v2_rows.json", "w"), ensure_ascii=False, indent=1)
    print("=== P5 v3 — GO-pro judge (phase-2 compatible) ===")
    for tag in ["gemini-high", "flash-go", "pro-go", "pro-thinking"]:
        lst = scores.get(tag, [])
        if not lst:
            print(tag, "NO EVALS")
            continue
        a = {k: round(sum(r[k] for r in lst) / len(lst), 2) for k in lst[0]}
        print(f"{tag}: {a} | n={len(lst)}")


if __name__ == "__main__":
    asyncio.run(main())