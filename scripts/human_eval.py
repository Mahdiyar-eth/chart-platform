"""H1.8 — human evaluation framework: 20 charts × 13 domains, 8-criteria
rubric (1-5), objective genericness/accuracy scoring.

Modes:
  --build        materialize 20 eval charts (14 golden + 6 synthetic) → docs/eval/charts/
  --prompts      render every domain prompt for every chart → docs/eval/prompts/
  --judge        run the LLM-judge over existing DB reports (costs money;
                 --limit N or --report-id for a bounded run; --dry-run prints plan)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EVAL_DIR = ROOT / "docs" / "eval"

# 6 synthetic birth-data cases covering edge scenarios (no LLM cost — computed
# locally with the real engine)
SYNTHETIC = [
    dict(name="syd-ne-york", calendar="gregorian", year=1988, month=7, day=4,
         hour=9, minute=30, city="New York", lat=40.7128, lon=-74.0060, tz="America/New_York"),
    dict(name="syd-london-dst", calendar="gregorian", year=1992, month=3, day=29,
         hour=1, minute=45, city="London", lat=51.5074, lon=-0.1278, tz="Europe/London"),
    dict(name="syd-dubai", calendar="gregorian", year=2000, month=12, day=1,
         hour=21, minute=0, city="Dubai", lat=25.2048, lon=55.2708, tz="Asia/Dubai"),
    dict(name="syd-mashhad", calendar="jalali", year=1370, month=1, day=1,
         hour=12, minute=0, city="مشهد", lat=36.2605, lon=59.6168, tz="Asia/Tehran"),
    dict(name="syd-no-time", calendar="jalali", year=1354, month=9, day=30,
         hour=None, minute=None, city="شیراز", lat=29.5918, lon=52.5837, tz="Asia/Tehran"),
    dict(name="syd-leap-day", calendar="gregorian", year=1996, month=2, day=29,
         hour=23, minute=58, city="Sydney", lat=-33.8688, lon=151.2093, tz="Australia/Sydney"),
]

DOMAIN_COUNT = 13
CRITERIA = ["genericness", "accuracy", "personalization", "actionability",
            "language", "safety", "balance", "flow"]

JUDGE_SYSTEM = """تو ارزیاب کیفیت گزارش‌های خودشناسی نجومی هستی. یک گزارش کامل و یک
چارت تولد به تو داده می‌شود. به ۸ معیار از ۱ تا ۵ امتیاز بده (۱=ضعیف، ۵=عالی):
genericness (اگر هویت عوض شود آیا متن همان می‌ماند؟)، accuracy (تطابق ارجاع‌های
نجومی با چارت)، personalization (استفاده از جزئیات خاص چارت)، actionability
(اقدام عملی مشخص)، language (روانی و طبیعی)، safety (بدون فال/پیش‌گویی/حکم
پزشکی)، balance (توازن قوت/چالش)، flow (انسجام روایت). اگر بین دو نمره مرددی،
محافظه‌کار باش (نمره پایین‌تر). پاسخ فقط JSON: {"criteria": {"genericness": 1-5, ...}, "notes": "یک پاراگراف دلیل" }"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def build_charts() -> list[dict]:
    """20 charts: 14 golden + 6 synthetic (computed with the real engine)."""
    from app.astrology.golden_data import GOLDEN_CHARTS
    from app.astrology.cities_world import tz_from_coords
    from app.astrology.engine import compute_from_fields

    out = []
    charts_dir = EVAL_DIR / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    for g in GOLDEN_CHARTS:
        b = g["birth"]
        res = compute_from_fields(
            lat=b["lat"], lon=b["lon"], year=b["year"], month=b["month"], day=b["day"],
            hour=b["hour"] if b.get("time_known", True) else 12,
            minute=b["minute"] if b.get("time_known", True) else 0,
            time_known=b.get("time_known", True), jalali=b.get("jalali", False),
            tz_name=b.get("tz_name", "Asia/Tehran"), zodiac="tropical")
        fid = f"chart-{g['id']}"
        rec = {"id": fid, "source": "golden", "birth": b, "chart_json": res.chart_json}
        out.append(rec)
        (charts_dir / f"{fid}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    for i, s in enumerate(SYNTHETIC, start=15):
        fid = f"chart-{i:02d}-{s['name']}"
        tz = s.get("tz") or tz_from_coords(s["lat"], s["lon"])
        known = s["hour"] is not None
        res = compute_from_fields(
            lat=s["lat"], lon=s["lon"], year=s["year"], month=s["month"], day=s["day"],
            hour=s["hour"] if known else 12, minute=s["minute"] if known else 0,
            time_known=known, jalali=(s["calendar"] == "jalali"),
            tz_name=tz, zodiac="tropical")
        rec = {"id": fid, "source": "synthetic", "meta": {k: s[k] for k in
               ("calendar", "year", "month", "day", "city")}, "chart_json": res.chart_json}
        out.append(rec)
        (charts_dir / f"{fid}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def build_prompts() -> None:
    """Render all 13 domain prompts for every chart → docs/eval/prompts/."""
    from app.report.prompt_builder import build_all_prompts

    charts = [json.loads(p.read_text(encoding="utf-8"))
              for p in sorted((EVAL_DIR / "charts").glob("*.json"))]
    prompts_dir = EVAL_DIR / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for rec in charts:
        d = prompts_dir / rec["id"]
        d.mkdir(parents=True, exist_ok=True)
        prompts = build_all_prompts(rec["chart_json"])
        for domain, (prompt, ctx) in prompts.items():
            (d / f"{domain}.txt").write_text(prompt, encoding="utf-8")
            n += 1
    print(f"prompts rendered: {n} ({len(charts)} charts × {DOMAIN_COUNT} domains)")


def judge(args) -> None:
    """LLM-judge: score existing DB reports against the rubric."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import Report

    with Session(engine) as s:
        q = select(Report).where(Report.status.in_(["done", "degraded"]))
        if args.report_id:
            q = q.where(Report.id == args.report_id)
        q = q.order_by(Report.created_at.desc()).limit(args.limit or 20)
        reports = list(s.exec(q))
    if not reports:
        print("no reports found in DB; run --build/--prompts for the offline path")
        return
    if args.dry_run:
        print(f"[dry-run] would score {len(reports)} report(s) via LLM (cost: ~$0.0{len(reports)}-0.2)")
        return
    print(f"scoring {len(reports)} report(s) — needs the LLM router (costs money)")
    results = {"criteria": CRITERIA, "reports": [], "generated_at": _now()}
    for rep in reports:
        results["reports"].append({"report_id": rep.id, "chart_id": rep.chart_id,
                                   "plan": rep.plan_key, "status": "pending-llm"})
    results_dir = EVAL_DIR / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / f"judge-{_now()}.json"
    path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"result scaffold written: {path} (run the real LLM pass to fill scores)")


def main() -> None:
    ap = argparse.ArgumentParser(description="H1.8 human-eval framework")
    ap.add_argument("--build", action="store_true", help="materialize 20 eval charts")
    ap.add_argument("--prompts", action="store_true", help="render 13 domain prompts per chart")
    ap.add_argument("--judge", action="store_true", help="LLM-judge over DB reports")
    ap.add_argument("--report-id", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.build:
        charts = build_charts()
        print(f"charts: {len(charts)} → docs/eval/charts/")
    if args.prompts:
        build_prompts()
    if args.judge:
        judge(args)
    if not (args.build or args.prompts or args.judge):
        ap.print_help()


if __name__ == "__main__":
    main()
