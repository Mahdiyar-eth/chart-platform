"""B5 — every promise in the UI must point to a REAL product (broken-promise gate)."""
import os, re
os.environ["DATABASE_URL"] = "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test"

from fastapi.testclient import TestClient
import app.main as m

_ROUTES = None


def _paths():
    global _ROUTES
    if _ROUTES is None:
        c = TestClient(m.app)
        _ROUTES = set()
        for r in m.app.routes:
            _ROUTES.add(getattr(r, "path", ""))
            # mounted sub-apps / routers expose their own routes
            for sub in getattr(r, "routes", []) or []:
                _ROUTES.add(getattr(sub, "path", ""))
        _ROUTES.discard("")
    return _ROUTES


def test_transit_page_promises_the_real_forecast_product():
    """transit.html must link to the B3 forecast product, not vague plan marketing."""
    src = open("app/templates/transit.html", encoding="utf-8").read()
    assert "/plans" not in src, "transit page must not send users to plans — product exists now"
    assert '/transits/{{ chart_id }}' in src


def test_payment_result_promise_has_a_followup_path():
    """«گزارش در صف است» must be paired with a link to track it."""
    src = open("app/templates/payment_result.html", encoding="utf-8").read()
    assert "در صف تولید" in src
    assert '/chart/{{ order.chart_id }}' in src


def _norm(p: str) -> str:
    p = p.split("#")[0].split("?")[0].rstrip("/")
    p = re.sub(r"\{[^}]*?\}", "V", p)               # {param} or {{expr}} → V (keep slashes)
    return re.sub(r"/\d+", "/V", p)                  # literal digits → /V


def test_all_internal_template_links_resolve():
    """Every internal href in templates must map to an existing route (no dead promises)."""
    bad = []
    norm_routes = {_norm(pt) for pt in _paths()}
    for f in os.listdir("app/templates"):
        if not f.endswith(".html"):
            continue
        src = open(f"app/templates/{f}", encoding="utf-8").read()
        for href in re.findall(r'href="/([^"{][^"]*)"', src):
            cand = _norm("/" + href)
            if cand.startswith("/static") or cand.startswith("/api"):
                continue
            # every dynamic segment of the candidate must be matched by some route
            ok = False
            for rt in norm_routes:
                c_segs, r_segs = cand.split("/"), rt.split("/")
                if len(c_segs) != len(r_segs):
                    continue
                if all(cs == rs or rs.endswith("V") and len(rs) <= 2 or cs == rs
                       for cs, rs in zip(c_segs, r_segs)):
                    ok = True
                    break
            if not ok and cand != "":
                bad.append((f, href))
    assert not bad, f"dead template links: {bad[:8]}"
