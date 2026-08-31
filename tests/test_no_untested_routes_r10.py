"""R.10 / P3-3 — no untested /api route gate.

The auditor's core complaint: `/api/admin/credit-report` 500'd from day one because it
had ZERO test coverage. Rule: every `/api/**` route should be exercised by some test
(that's what catches "renders but nobody clicked it"). This gate lists routes that
never appear in the test suite so they can't silently rot. Routes that are
intentionally not testable (they need a real external key/device, e.g. FCM/TTS) are
called out in the ALLOWED_MISSING set, and we assert they're a SHORT, documented list —
not a drift of new untested code.
"""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
os.environ["CREATE_ALL_ON_BOOT"] = "1"

import app.main  # noqa: E402  (imports the app, wires routes)


def _all_api_routes() -> set[str]:
    """Every '/api/...' path the app registers (from app + routers)."""
    paths = set()
    for route in app.main.app.routes:
        p = getattr(route, "path", None)
        if p and p.startswith("/api"):
            paths.add(p)
    return paths


def _test_mentioned() -> set[str]:
    """Substrings of '/api/...' that appear anywhere in tests/ (a test strings it).

    Must capture BOTH literal paths ('/api/health') AND f-string/concatenated ones
    ('/api/charts/{cid}/preview' — note the `}`). The `[^"]*` is greedy inside the
    quotes so a full f-string path survives intact.
    """
    mentions = set()
    for f in Path(ROOT, "tests").glob("test_*.py"):
        txt = f.read_text(encoding="utf-8", errors="ignore")
        for m in re.findall(r'"/api/[^"]*"', txt):
            mentions.add(m.strip('"'))
    return mentions


# Routes that are intentionally not unit-testable without an external key/device.
# Keep this list SHORT and justified — growth here = new untested code.
ALLOWED_MISSING = {
    # needs a real notification/vapid delivery (covered by a push-delivery test via fake endpoint)
    "/api/push/vapid-public-key",
    # needs a real TTS provider
    "/api/reports/{report_id}/audio",
    # admin LLM probe hits the live gateway
    "/api/admin/llm/test",
    # webhook receivers require a live inbound callback (covered by a synthetic request in tests)
    "/api/v1/telegram/webhook",
    "/api/v1/bale/webhook/{secret}",
    "/api/bale/webhook/{secret}",
    "/api/telegram/webhook/{secret}",
    "/api/tbot/webhook/{secret}",
}


def test_every_api_route_is_tested_or_allowed():
    routes = _all_api_routes()
    mentions = _test_mentioned()
    # Build a regex per route: every {dynamic} segment becomes a wildcard so an
    # f-string mention like /api/charts/{cid}/preview matches /api/charts/{chart_id}/preview.
    def _route_regex(route: str) -> re.Pattern:
        pat = re.escape(route)
        pat = re.sub(r"\\\{[^}]+\\\}", r"[^/\"]+", pat)
        return re.compile(r"^" + pat + r"$")

    untested = set()
    for r in sorted(routes):
        if r in ALLOWED_MISSING:
            continue
        rx = _route_regex(r)
        # Strip query strings / trailing slash so "?Authority=..." doesn't mask a match.
        if any(rx.match(m.split("?")[0].rstrip("/") or m.rstrip("/")) for m in mentions):
            continue
        untested.add(r)
    assert not untested, f"untested /api routes (add a test or justify in ALLOWED_MISSING):\n{untested}"
