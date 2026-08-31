"""Links on the chart page must work for the people who receive them.

Two dead ends, both invisible to the owner and both fatal to someone else:

  * the yearly-transit <img> was the only request on the page that did not
    append the capability token. Every fetch() did. So a shared /chart/{id}?t=
    link rendered for the recipient with a broken image, because _owns_chart
    found neither cookie nor query token and returned 403.
  * the "free exploration" onboarding card linked to /explore with no chart.
    page_explore only finds charts by BirthProfile.user_id, so a guest got
    charts=[] and the page toasted "make a chart first" at somebody who had
    just made one. The funnel link two rows above always passed ?chart=.
"""
from __future__ import annotations

import re
from pathlib import Path

CHART = (Path(__file__).resolve().parent.parent
         / "app" / "templates" / "chart.html").read_text(encoding="utf-8")


def test_every_chart_scoped_api_url_carries_the_token():
    """Anything under /api/charts/{id}/ is ownership-gated."""
    missing = []
    for m in re.finditer(r"/api/charts/\{\{\s*chart\.id\s*\}\}/[A-Za-z0-9_.\-]+", CHART):
        tail = CHART[m.end():m.end() + 30]
        if not tail.lstrip().startswith("?t=") and "access_token" not in tail:
            missing.append(m.group(0) + tail[:20])
    assert not missing, (
        "chart-scoped URL(s) without the capability token — these 403 for "
        f"anyone the chart was shared with: {missing}"
    )


def test_explore_links_carry_the_chart():
    for m in re.finditer(r'href="/explore([^"]*)"', CHART):
        assert "chart=" in m.group(1), (
            "an /explore link on the chart page omits ?chart=, so a guest who "
            "just built a chart is told to build one"
        )
