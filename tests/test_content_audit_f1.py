"""F1 — ZAYCHE content audit GATE (R.6 launch work).

The review flagged F1 as the one never-audited workstream: 50 articles exist, but
quality thresholds were never *measured*. This is the durable gate version of the
`scripts/content_audit_f1.py` diagnostic — it turns the audit's findings into
hard assertions so content rot can't slip in silently.

Covers the plan's B-3 criteria:
  * word count floor (>=300; 500+ is "rich")
  * unique title + meta (no empties, no duplicates)
  * each article gets >=2 topic-related sibling links (B-3 «۲-۳ مقاله مرتبط»)
  * Article + BreadcrumbList schema present (article.html) and FAQPage (faq.html)
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = json.load(open(ROOT / "app" / "content" / "articles.json", encoding="utf-8"))

WORD_FLOOR = 300   # below this = thin content (fail)
WORD_RICH = 500    # at/above this = good
MIN_RELATED = 2    # B-3: at least 2 topic-related sibling links


def _body_text(a) -> str:
    parts = []
    for block in a.get("body", []) or []:
        if isinstance(block, dict):
            parts.append(block.get("h2", "") or "")
            parts.append(block.get("p", "") or "")
            for li in block.get("li", []) or []:
                parts.append(li)
    return " ".join(parts)


def _related(a, arts):
    """Mirror the B-3 route logic (app/routes/seo.py page_article)."""
    slug, cat = a.get("slug", ""), a.get("category", "")
    others = [o for o in arts if o.get("slug") != slug and o.get("category") == cat]
    if len(others) < 3:
        others += [o for o in arts if o.get("slug") != slug and o.get("category") != cat]
    return others[:6]


def test_articles_count():
    assert len(ARTICLES) == 50


def test_all_articles_have_word_count_at_or_above_floor():
    thin = []
    for a in ARTICLES:
        wc = len(re.findall(r"\S+", _body_text(a)))
        if wc < WORD_FLOOR:
            thin.append((a.get("slug"), wc))
    assert not thin, f"thin articles (<{WORD_FLOOR} words): {thin}"


def test_most_articles_rich():
    rich = sum(1 for a in ARTICLES if len(re.findall(r"\S+", _body_text(a))) >= WORD_RICH)
    # at least 90% should be "rich" (500+); the diagnostic shows 46/50 today.
    assert rich >= int(len(ARTICLES) * 0.9), f"only {rich}/{len(ARTICLES)} are rich"


def test_unique_and_present_title_and_meta():
    titles, metas = {}, {}
    for a in ARTICLES:
        t = (a.get("title") or "").strip()
        m = (a.get("meta") or "").strip()
        assert t, f"empty title: {a.get('slug')}"
        assert m, f"empty meta: {a.get('slug')}"
        titles[t] = titles.get(t, 0) + 1
        metas[m] = metas.get(m, 0) + 1
    assert all(c == 1 for c in titles.values()), [t for t, c in titles.items() if c > 1]
    assert all(c == 1 for c in metas.values()), [m for m, c in metas.items() if c > 1]


def test_every_article_has_topic_related_links():
    """B-3 «۲-۳ مقاله مرتبط» — every article gets >=2 total related links, and
    TOPIC-matched siblings whenever the category has any. Categories with only a
    couple of articles (e.g. «خانه‌ها» = 2) can't supply 2 same-category siblings,
    so the honest invariant is: total >= 2 AND same-category >= min(2, siblings_available)."""
    bad = []
    for a in ARTICLES:
        cat = a.get("category", "")
        siblings = sum(1 for o in ARTICLES if o.get("slug") != a["slug"] and o.get("category") == cat)
        others = _related(a, ARTICLES)
        same = sum(1 for o in others if o.get("category") == cat)
        need_same = min(MIN_RELATED, siblings)
        if len(others) < MIN_RELATED or same < need_same:
            bad.append((a.get("slug"), len(others), same, need_same))
    assert not bad, f"articles lacking required topic-related links: {bad}"


def test_article_schema_present():
    art_tpl = (ROOT / "app" / "templates" / "article.html").read_text(encoding="utf-8")
    assert "application/ld+json" in art_tpl
    assert '"Article"' in art_tpl
    assert '"BreadcrumbList"' in art_tpl
    faq = (ROOT / "app" / "templates" / "faq.html").read_text(encoding="utf-8")
    assert '"FAQPage"' in faq


def test_no_untranslated_foreign_terms_without_gloss():
    """A foreign abbreviation (MC, ASC, Aspect…) must be glossed inline with its
    Persian term (e.g. «میانه آسمان یا MC») at its FIRST mention; later mentions
    are fine. Bare usage with no Persian gloss at the first occurrence fails."""
    glossed = re.compile(r"(?:میانه\s+آسمان|زاویه|خلق|بالارو\b)")
    for a in ARTICLES:
        body = _body_text(a)
        for term in ("MC", "ASC", "Aspect"):
            first = body.find(term)
            if first == -1:
                continue
            ctx = body[max(0, first - 80):first + 40]
            assert glossed.search(ctx) or "یا MC" in ctx or "یا ASC" in ctx or "یا Aspect" in ctx, \
                f"{a.get('slug')}: foreign term '{term}' first used without a Persian gloss: {ctx[:120]!r}"
