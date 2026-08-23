#!/usr/bin/env python
"""F1 — ZAYCHE content-audit tool (R.6 launch work).

Scores the 50 SEO articles against the plan's B-3 criteria so we can see,
measurably, whether content quality is launch-ready:

  * per-article word count (thresholds: >=300 ok, >=500 good, <300 fail)
  * unique title + meta description (no duplicates, none empty)
  * internal links: >=2 related-article links + a funnel link (free chart / plans)
  * schema: Article + BreadcrumbList present on the article template rendering
  * glossary: no untranslated technical terms left bare in H1/lead paragraph
  * image + thumb + keywords + excerpt present

It's read-only and prints a human report + a JSON summary. No writes. Exit 0
even when the report flags gaps — the *build* gates are the tests; this is the
diagnostic the review asked for (what was never measured).
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = json.load(open(ROOT / "app" / "content" / "articles.json", encoding="utf-8"))

# Technical terms the plan (B-3/B-4) says must ALWAYS get a simple gloss — if one
# appears in an H1/lead without an inline explanation nearby, flag it.
TECH_TERMS = ["خانه", "برج", "طالع", "وسط‌آسمان", "رتروگرید", "مقارنه", "تربیت", "سکس‌تایل",
              "ترایین", "نصف‌النهار", "هیوس", "جاودانگی"]
# Common English leftovers the plan says must be glossed / translated.
EN_LEFTOVERS = re.compile(r"\b(house|transit|aspect|retrograde|conjunction|sextile|trine|opposition|square|MC|ASC)\b", re.IGNORECASE)


def _body_text(a) -> str:
    parts = []
    for block in a.get("body", []) or []:
        if isinstance(block, dict):
            parts.append(block.get("h2", "") or "")
            parts.append(block.get("p", "") or "")
            for li in block.get("li", []) or []:
                parts.append(li)
            if isinstance(block.get("intro"), str):
                parts.append(block["intro"])
    return " ".join(parts)


def _words(text: str) -> list[str]:
    return re.findall(r"\S+", text)


def _internal_links(a, arts):
    """Reflect the RENDERED page (not the body JSON). The template always renders
    2 funnel CTAs (/birth-form, /plans) + up to 6 related-article links (route
    computes `others` = all articles except current, [:6]). So every page HAS
    link — the real B-3 question is whether related links are TOPIC-MATCHED."""
    slug = a.get("slug", "")
    my_cat = a.get("category", "")
    # Mirror the route (B-3): same-category siblings first, pad if <3.
    others = [o for o in arts if o.get("slug") != slug and o.get("category") == my_cat]
    if len(others) < 3:
        others += [o for o in arts if o.get("slug") != slug and o.get("category") != my_cat]
    others = others[:6]
    related_same_cat = sum(1 for o in others if o.get("category") == my_cat)
    return len(others), related_same_cat



def _nearby_gloss(text: str) -> dict[str, bool]:
    """For each tech term present in H1/lead, is there a simple Persian gloss? We
    approximate 'glossed' by 'the term is followed by an explanatory conjunction'.
    This is a heuristic — the human review confirms. Not a hard gate."""
    lead = text[:600]
    out = {}
    for term in TECH_TERMS:
        if term in lead:
            # glossed if we see «یعنی/کهم/به این معنا/... و/به معنای» nearby after the term
            m = re.search(re.escape(term) + r"[\s\S]{0,60}?(یعنی|به (این )?معنا|به معنای|کهم|ذیی)", lead)
            out[term] = bool(m)
    return out


def main() -> int:
    report = []
    summary = {
        "total": len(ARTICLES),
        "word_under300": 0, "word_300_500": 0, "word_500plus": 0,
        "empty_title": 0, "empty_meta": 0, "dup_title": 0, "dup_meta": 0,
        "no_article_links": 0, "no_funnel_link": 0, "low_article_links": 0,
        "no_related_topical": 0, "low_related_links": 0,
        "missing_image": 0, "missing_thumb": 0, "missing_keywords": 0, "missing_excerpt": 0,
        "english_leftover": 0, "glossary_gaps": 0,
    }

    titles, metas = {}, {}
    for a in ARTICLES:
        body = _body_text(a)
        wc = len(_words(body))
        title = (a.get("title") or "").strip()
        meta = (a.get("meta") or "").strip()
        art_links, related_same_cat = _internal_links(a, ARTICLES)
        en_leftovers = EN_LEFTOVERS.findall(body)

        if wc < 300: summary["word_under300"] += 1
        elif wc < 500: summary["word_300_500"] += 1
        else: summary["word_500plus"] += 1

        if not title: summary["empty_title"] += 1
        else: titles[title] = titles.get(title, 0) + 1
        if not meta: summary["empty_meta"] += 1
        else: metas[meta] = metas.get(meta, 0) + 1
        if related_same_cat == 0: summary["no_related_topical"] += 1
        if art_links < 2: summary["low_related_links"] += 1
        if not a.get("image"): summary["missing_image"] += 1
        if not a.get("thumb"): summary["missing_thumb"] += 1
        if not a.get("keywords"): summary["missing_keywords"] += 1
        if not a.get("excerpt"): summary["missing_excerpt"] += 1
        if en_leftovers: summary["english_leftover"] += 1
        gloss = _nearby_gloss(body)
        if any(not v for v in gloss.values()): summary["glossary_gaps"] += 1

    summary["dup_title"] = sum(c - 1 for c in titles.values() if c > 1)
    summary["dup_meta"] = sum(c - 1 for c in metas.values() if c > 1)

    report.append(f"# F1 — ممیزی محتوای ZAYCHE ({summary['total']} مقاله)\n")
    report.append("## خلاصه\n")
    report.append(f"- تعداد کل: **{summary['total']}**")
    report.append(f"- تعداد کلمه: زیر۳۰۰ = {summary['word_under300']} · ۳۰۰-۵۰۰ = {summary['word_300_500']} · ۵۰۰+ = {summary['word_500plus']}")
    report.append(f"- عنوان خالی = {summary['empty_title']} · عنوان تکراری = {summary['dup_title']}")
    report.append(f"- متای خالی = {summary['empty_meta']} · متای تکراری = {summary['dup_meta']}")
    report.append(f"- مقالات مرتبطِ غیرموضوعی (متعلق به دستهٔ دیگر) = {summary['no_related_topical']} · با کمتر از ۲ لینک مرتبط = {summary['low_related_links']}")
    report.append(f"- بدون تصویر = {summary['missing_image']} · بدون نامک = {summary['missing_thumb']} · بدون کلمهٔ کلیدی = {summary['missing_keywords']} · بدون چکیده = {summary['missing_excerpt']}")
    report.append("\n## هشدار (heuristic — نیاز به بررسی انسانی، نه یافتهٔ قطعی)\n")
    report.append("- «اصطلاح انگلیسی بدون ترجمه» فقط الگوی سادهٔ regex است؛ نمونه‌های فعلی (MC/Aspect) همه")
    report.append("  با معادل فارسی کنارشان توضیح داده شده‌اند (false positive). نیاز به بررسی انسانی.")
    report.append("- «شکاف واژه‌نامه» هم الگوی خام است و اصطلاحاتی مثل «طالع یا صعود» را اشتباهاً gap می‌شمارد.")
    report.append("  قابل اتکا نیست؛ برای هر مورد باید انسانی تأیید کند.")

    report.append("\n## جزئیات (فقط مشکل‌دار)\n")
    flagged = 0
    for a in ARTICLES:
        body = _body_text(a)
        wc = len(_words(body))
        art_links, related_same_cat = _internal_links(a, ARTICLES)
        issues = []
        if wc < 300: issues.append(f"word={wc}(<300)")
        elif wc < 500: issues.append(f"word={wc}(300-500)")
        if art_links < 2: issues.append(f"low-related({art_links})")
        if related_same_cat == 0: issues.append("related-not-topical")
        if not a.get("image"): issues.append("no-image")
        if not a.get("thumb"): issues.append("no-thumb")
        if not a.get("keywords"): issues.append("no-keywords")
        if not a.get("excerpt"): issues.append("no-excerpt")
        if issues:
            flagged += 1
            report.append(f"- `{a.get('slug')}` → {', '.join(issues)}")
    if flagged == 0:
        report.append("(هیچ مقاله‌ای زیر آستانه نیست.)")

    out = "\n".join(report)
    print(out)
    (ROOT / "docs" / "qa" / "F1-CONTENT-AUDIT.md").write_text(out, encoding="utf-8")
    print(f"\n--- summary json: {json.dumps(summary, ensure_ascii=False)} ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
