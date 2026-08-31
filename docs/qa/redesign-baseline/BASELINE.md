# ZAYCHE UI REDESIGN — BASELINE REPORT

**Date:** ۱۴۰۵/۰۶/۰۴
**Source:** live `https://chart.negar.io`
**Scope:** ۲۷ public routes × ۲ viewport = ۵۴ browser visits
**Mode:** read-only; no production code changed during baseline

## Automated baseline result

| Check | Result |
|---|---:|
| Browser visits | ۵۴ |
| HTTP 200 | ۵۲ |
| HTTP 404 | ۲ visits / ۱ unique route |
| Console page errors | ۰ |
| Failed network requests | ۰ |
| Document horizontal overflow | ۰ |
| Screenshots | ۵۴ |

## Missing public page

- `/signs/leo` returned 404 in both viewports. This is a real route/data gap, not a styling issue. The redesign plan keeps this as a required SEO/page-completeness item.
- `/birth-chart/tehran` returned 200; its presence is confirmed.

## Screenshot set

Saved in `docs/qa/redesign-baseline/`:

- each route at 390×844 mobile
- each route at 1280×844 desktop
- machine-readable `baseline.json`

## Page groups to redesign

1. Public acquisition: home, plans, birth form, synastry, rectify
2. Daily/product: today, sky, sky-today, transit, solar, relocation
3. Content/SEO: articles, learn, glossary, FAQ, guide, city/sign/moon clusters
4. User workspace: dashboard, chart, reports, chats, credits, orders, account, settings
5. Commerce: product choice, checkout, payment result, refund and all failure states
6. Admin/CMS: overview, health, money, users, sales, content, settings, LLM and media

## Important interpretation

This baseline proves only that the public pages currently load without browser-level errors or horizontal overflow. It does **not** prove that the pages are visually good, that protected pages work, or that every button has a working destination. Those are separate gates in the approved execution plan.

## Next gate

Build the shared foundation and dashboard reference first, then rerun screenshots and browser checks before extending the visual system to every page group.
