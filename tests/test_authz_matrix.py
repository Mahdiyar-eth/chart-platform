"""C8 (audit r4): authorization matrix — every registered route MUST be listed
in docs/AUTHORIZATION-MATRIX.md (single source of truth for access levels).

Structural test: parse the app's route table and cross-check against the
matrix's route column; any route missing from the matrix fails the build.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.main import app as main_app

MATRIX = Path(__file__).resolve().parent.parent / "docs" / "AUTHORIZATION-MATRIX.md"

# infra/static routes that don't need matrix entries
SKIP = {"/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect", "/static"}


def _route_pattern(route: str) -> str:
    """FastAPI {param} → regex placeholder for matching matrix rows."""
    return re.sub(r"\{[^}]+\}", "{x}", route)


def _matrix_routes() -> set[str]:
    rows = set()
    for line in MATRIX.read_text().splitlines():
        # rows carry one or more `METHOD /path` entries inside backticks
        for m in re.finditer(r"`((?:GET|POST|PUT|DELETE) [^`]+)`", line):
            rows.add(_route_pattern(m.group(1).split(" ", 1)[1]))
    return rows


def test_every_route_is_in_matrix():
    rows = _matrix_routes()

    missing = []
    for r in main_app.routes:
        path = getattr(r, "path", None)
        if not path or path in SKIP:
            continue
        for method in getattr(r, "methods", set()) or {"GET"}:
            if method in {"HEAD", "OPTIONS"}:
                continue
            if _route_pattern(path) not in rows:
                missing.append(f"{method} {path}")
    assert not missing, (
        f"routes missing from docs/AUTHORIZATION-MATRIX.md: {missing}\n"
        "Add them to the matrix (single source of truth) — this gate keeps "
        "new endpoints from silently skipping authorization documentation."
    )


def test_matrix_rows_are_real_routes():
    """Reverse check: every matrix row must correspond to an actual route."""
    registered = {_route_pattern(getattr(r, "path", "")) for r in main_app.routes}
    fake = []
    for line in MATRIX.read_text().splitlines():
        m = re.match(r"\| `(GET|POST|PUT|DELETE) (/[^`]*)` \|", line)
        if m and _route_pattern(m.group(2)) not in registered:
            fake.append(m.group(2))
    assert not fake, f"matrix rows with no matching route: {fake}"


def test_authz_core_guards_work():
    """Spot checks that matrix levels are enforced in code, not just docs."""
    c = TestClient(main_app)
    # anonymous cannot read admin stats
    assert c.get("/api/admin/stats").status_code == 403
    # anonymous cannot order (no chart → 404, not 200)
    r = c.post("/api/orders", data={"plan_key": "gold", "chart_id": "nonexistent"})
    assert r.status_code == 404
    # anonymous cannot see account
    r = c.get("/account", follow_redirects=False)
    assert r.status_code == 303
    # public endpoints answer
    assert c.get("/api/plans").status_code == 200
    assert c.get("/liveness").status_code == 200
    assert c.get("/privacy").status_code == 200
