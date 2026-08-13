"""
PDF renderer — WeasyPrint + Vazirmatn (RTL Persian report, plan v3.1 §6.5).

Deterministic: same report JSON → same PDF. No JS, no network fonts.
"""
from __future__ import annotations

import html
from pathlib import Path

from weasyprint import HTML

from app.astrology.big_three import big_three
from app.astrology.engine import fmt_lon
from app.report.rules import DOMAINS

FONT_DIR = Path(__file__).parent.parent / "static" / "fonts"

CSS = """
@page {
  size: A4;
  margin: 2cm 1.8cm;
  @bottom-center { content: counter(page) " / " counter(pages); font-family: Vazirmatn; font-size: 8pt; color: #999; }
}
@font-face { font-family: Vazirmatn; src: url("Vazirmatn-Regular.ttf"); font-weight: 400; }
@font-face { font-family: Vazirmatn; src: url("Vazirmatn-Medium.ttf"); font-weight: 500; }
@font-face { font-family: Vazirmatn; src: url("Vazirmatn-Bold.ttf"); font-weight: 700; }
@font-face { font-family: Vazirmatn; src: url("Vazirmatn-ExtraBold.ttf"); font-weight: 800; }
* { box-sizing: border-box; }
body { font-family: Vazirmatn; font-size: 10.5pt; line-height: 2; color: #1a1a2e; direction: rtl; }
.cover { text-align: center; padding-top: 38%; }
.cover .title { font-size: 30pt; font-weight: 800; color: #3b2f80; margin-bottom: 8px; }
.cover .sub { font-size: 13pt; color: #666; margin-bottom: 30px; }
.cover .badge { display: inline-block; background: #efeaff; color: #2b2170; border-radius: 99px; padding: 4px 18px; font-size: 10pt; margin: 4px; font-weight: 600; }
h1.section { font-size: 17pt; font-weight: 800; color: #3b2f80; border-bottom: 2px solid #d5c9ff; padding-bottom: 6px; margin: 28px 0 12px; page-break-after: avoid; }
h2.insight { font-size: 12.5pt; font-weight: 700; color: #2a9d8f; margin: 16px 0 4px; page-break-after: avoid; }
.block { page-break-inside: avoid; margin: 8px 0; }
p { margin: 6px 0; text-align: justify; orphans: 3; widows: 3; }
.evidence { font-size: 8.5pt; color: #888; background: #f6f6fb; border-radius: 8px; padding: 4px 10px; margin: 4px 0; }
ul { margin: 4px 0; padding-right: 18px; list-style-position: inside; }
li { margin: 2px 0; }
li::marker { unicode-bidi: plaintext; }
.advice { background: #eefaf5; border-right: 4px solid #2a9d8f; padding: 8px 12px; border-radius: 8px; margin: 8px 0; }
table.transit { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 9.5pt; }
table.transit th { background: #2a3555; color: #fff; padding: 6px 8px; text-align: right; }
table.transit td { border-bottom: 1px solid #e3e6f0; padding: 6px 8px; }
.bigthree { text-align: center; margin: 18px 0; }
.bigthree .bt { display: inline-block; background: #f0edff; border-radius: 14px; padding: 10px 22px; margin: 6px; }
.bigthree .bt .k { font-size: 9pt; color: #888; }
.bigthree .bt .v { font-size: 12.5pt; font-weight: 700; color: #3b2f80; }
.meta { font-size: 9pt; color: #777; text-align: center; margin-top: 10px; }
.footer-note { margin-top: 30px; font-size: 8.5pt; color: #aaa; text-align: center; border-top: 1px solid #eee; padding-top: 10px; }
"""


def _esc(s: str) -> str:
    return html.escape(str(s or ""))


def render_report_pdf(report: dict, out_path: str | Path, plan_key: str | None = None) -> Path:
    """report JSON (build_report_json output) → PDF file."""
    chart = report["chart"]
    sections = report["sections"]
    metrics = report.get("metrics", {})
    bt = big_three(chart)
    birth = chart["birth"]

    parts = [f'<div class="cover">',
             f'<div class="title">گزارش چارت تولد</div>',
             f'<div class="sub">آینهی خودشناسی — تفسیر اختصاصی بر اساس محاسبهی نجومی دقیق</div>',
             f'<div class="badge">تاریخ و ساعت تولد: {_esc(birth.get("local_time", ""))}</div>',
             f'<div class="badge">مکان: {_esc(birth.get("city_fa", "")) or "—"}</div>',
             "</div>"]

    # Big Three box
    parts.append('<div class="bigthree">')
    for key, label in (("sun", "خورشید"), ("moon", "ماه"), ("asc", "طالع")):
        v = bt.get(key, {})
        parts.append(f'<div class="bt"><div class="k">{label}</div><div class="v">'
                     f'{_esc(v.get("sign_fa", ""))}</div></div>')
    parts.append("</div>")
    asc = chart.get("angles", {}).get("ASC", {})
    parts.append(f'<p class="meta">فاز ماه: {_esc(chart.get("moon_phase", ""))} — '
                 f'طالع {_esc(bt.get("asc", {}).get("sign_fa", asc.get("sign_fa", "")))}</p>')

    # Sections (iterate actual generated sections — plan-based subsets + islamic)
    for domain_key, sec in sections.items():
        title_fa = DOMAINS.get(domain_key, "فرهنگ و باورها — از منظر خودشناسی")
        parts.append(f'<h1 class="section">{_esc(sec.get("title_fa", title_fa))}</h1>')
        if sec.get("intro"):
            parts.append(f"<p>{_esc(sec['intro'])}</p>")
        for ins in sec.get("insights", []):
            parts.append('<div class="block">')
            title = ins.get("insight", "")[:70]
            parts.append(f'<h2 class="insight">◈ {_esc(title)}{"…" if len(ins.get("insight", "")) > 70 else ""}</h2>')
            body = ins.get("insight", "")
            parts.append(f"<p>{_esc(body)}</p>")
            evs = ins.get("evidence", [])
            if evs:
                ev_txt = "شواهد نجومی: " + " | ".join(
                    f"{_esc(e.get('factor'))} در {_esc(e.get('sign', ''))} {_esc(e.get('house', ''))}".strip()
                    for e in evs)
                parts.append(f'<div class="evidence">{ev_txt}</div>')
            strengths = ins.get("strengths", [])
            if strengths:
                parts.append("<ul>" + "".join(f"<li>✔ {_esc(s)}</li>" for s in strengths) + "</ul>")
            challenges = ins.get("challenges", [])
            if challenges:
                parts.append("<ul>" + "".join(f"<li>• {_esc(c)}</li>" for c in challenges) + "</ul>")
            if ins.get("practical_advice"):
                parts.append(f'<div class="advice">💡 پیشنهاد عملی: {_esc(ins["practical_advice"])}</div>')
            parts.append("</div>")

    # ── Gold bonus: upcoming-transit chapter (plan §10 — deterministic, no LLM) ──
    if plan_key == "gold":
        try:
            from app.astrology.svg_widgets import transit_timeline_svg
            from app.astrology.transits import upcoming_transits
            events = upcoming_transits(chart, days=120)[:10]
            parts.append('<h1 class="section">گذرهای پیشِ رو — نقشهی ۴ ماه آینده</h1>')
            if events:
                parts.append('<table class="transit">')
                parts.append('<tr><th>از تاریخ</th><th>سیارهی گذرنده</th><th>با</th><th>نوع</th></tr>')
                for e in events:
                    tgt = {"Sun": "خورشید", "Moon": "ماه", "ASC": "طالع", "Venus": "ناهید",
                           "Mars": "مریخ", "Mercury": "عطارد"}.get(e["target"], e["target"])
                    parts.append(f"<tr><td>{_esc(e['start'])}</td><td>{_esc(e['planet_fa'])} "
                                 f"({_esc(e['sign_fa'])})</td><td>{_esc(tgt)}</td>"
                                 f"<td>{_esc(e['aspect'])} (اورب {e['orb']}°)</td></tr>")
                parts.append("</table>")
            parts.append(f'<div class="advice">🌠 این جدول از روی محاسبهی مستقیم نجومی ساخته شده '
                         f'و نشان میدهد کدام گذرهای مهم روی چارت تو فعال میشوند.</div>')
            try:
                svg = transit_timeline_svg(chart, months=12).replace('width="100%"', 'width="680"')
                parts.append(f'<div style="page-break-inside:avoid;">{svg}</div>')
            except Exception:  # noqa: BLE001 — widget must never break the PDF
                pass
        except Exception:  # noqa: BLE001
            pass

    parts.append(f'<div class="footer-note">این گزارش با محاسبه‌ی دقیق نجومی (Swiss Ephemeris) تهیه شده است. '
                 f'نقشه‌ی نجومی است، نه پیش‌گویی — برای خودشناسی و تأمل؛ '
                 f'تصمیم‌های مهم زندگی را با عقل و اختیار خودت بگیر. '
                 f'تولید: {metrics.get("generated_at", "")}</div>')

    html_doc = f"""<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
    <style>{CSS}</style></head><body>{"".join(parts)}</body></html>"""

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_doc, base_url=str(FONT_DIR)).write_pdf(str(out))
    return out
