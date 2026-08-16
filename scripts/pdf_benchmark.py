#!/usr/bin/env python3
"""G16 (master-spec §61/Performance) — PDF render benchmark.

Renders a representative report body through the real PDF pipeline and
reports wall time + size. Guards against slow regressions (>15s => fail).

Run:  venv/bin/python scripts/pdf_benchmark.py
"""
import sys
import time


def build_sample_report() -> dict:
    """A realistic report JSON (mirrors build_report_json output)."""
    sections = {}
    for i in range(13):
        sections[f"domain_{i}"] = {
            "title_fa": f"بخش {i+1} — تحلیل اختصاصی",
            "intro": "بر اساس جایگاه سیاره‌ها و خانه‌های چارت، این بخش به بررسی دقیق می‌پردازد.",
            "insights": [
                {"insight": "خورشید در برج اسد با درجه‌ی ۲۹ به معنای اراده‌ی قوی و مرکز توجه بودن است.",
                 "evidence": [{"factor": "خورشید", "sign": "اسد", "house": "خانه ۱"}],
                 "strengths": ["تعادل میان احساس و منطق"]},
                {"insight": "ماه در حوت بیانگر حساسیت و همدلی عمیق است.",
                 "evidence": [{"factor": "ماه", "sign": "حوت", "house": "خانه ۸"}]},
                {"insight": "طالع اسد چهره‌ی اجتماعی و پرانرژی را می‌سازد."},
            ],
        }
    return {
        "chart": {
            "planets": {"Sun": {"longitude": 120.0}, "Moon": {"longitude": 350.0}},
            "angles": {"ASC": {"longitude": 130.0}},
            "moon_phase": "نزولی",
            "birth": {"local_time": "۱۳۷۳/۰۶/۰۱ ۰۶:۱۰", "city_fa": "تهران"},
        },
        "sections": sections,
        "metrics": {},
    }


def main() -> int:
    report = build_sample_report()
    try:
        from app.report.renderer import render_report_pdf  # real pipeline
        import tempfile
        out = tempfile.mktemp(suffix=".pdf")
        t0 = time.perf_counter()
        render_report_pdf(report, out, plan_key="full")
        pdf_bytes = open(out, "rb").read()
    except Exception as e:  # noqa: BLE001 — bench must never crash silently
        print(f"PDF-BENCH: FAILED — {e}")
        return 1
    dt = time.perf_counter() - t0
    print(f"PDF-BENCH: {dt*1000:7.1f}ms  {len(pdf_bytes)/1024:7.1f} KiB  (13 sections, RTL)")
    if dt > 15.0:
        print("PDF-BENCH: TOO SLOW (>15s)")
        return 1
    print("PDF-BENCH: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
