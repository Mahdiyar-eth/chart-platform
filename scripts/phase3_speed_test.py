"""Phase 3 — worker section speed test: deepseek-v4-pro vs gemini-3.6-high.
Runs the REAL generate_sections_async pipeline (5 core sections) on 2 charts.
"""
import asyncio, json, sys, time
sys.path.insert(0, "/root/chart-platform")
from scripts.ai_benchmark_v4 import make_chart
from app.core.llm import build_section_router
from app.report.worker import generate_sections_async


def full_chart(i: int) -> dict:
    c = make_chart(i)
    c["birth"] = {"date": "2000-01-01", "time": "10:30", "time_known": True,
                  "city": "تهران", "lat": 35.7, "lon": 51.4}
    c["moon_phase"] = "نیمه‌اول"
    return c


async def run(name: str, model: str, charts: list[dict]) -> dict:
    print(f"### {name} ({model})", flush=True)
    router = build_section_router("identity", model)
    t0 = time.monotonic()
    total_tokens = 0
    fails = 0
    for i, ch in enumerate(charts):
        sections, metrics = await generate_sections_async(ch, router=router)
        total_tokens += metrics["total_tokens"]
        ok_count = sum(1 for v in sections.values() if v.get("ok"))
        print(f"  chart{i}: sections={len(sections)} ok={ok_count} "
              f"calls={metrics['calls']} retries={metrics['retries']} "
              f"qa_fail={metrics['qa_failures']} cost=${metrics['cost_usd']:.4f}", flush=True)
        fails += len(sections) - ok_count
    dt = time.monotonic() - t0
    print(f"  TOTAL: {dt:.1f}s tokens={total_tokens} failed_sections={fails}", flush=True)
    return {"name": name, "model": model, "wall_s": round(dt, 1),
            "tokens": total_tokens, "failed": fails,
            "charts": len(charts)}


def main():
    charts = [full_chart(5), full_chart(11)]
    results = []
    results.append(asyncio.run(run("pro-current", "deepseek-v4-pro", charts)))
    results.append(asyncio.run(run("gemini-high", "antigravity/gemini-3.6-flash-high", charts)))
    json.dump(results, open("/tmp/phase3_speed.json", "w"), ensure_ascii=False, indent=1)
    print("SAVED")


if __name__ == "__main__":
    main()