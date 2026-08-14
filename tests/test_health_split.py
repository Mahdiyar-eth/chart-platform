"""C5 (audit r4): split health endpoints — /liveness (process only) vs
/readiness (DB + Redis + worker + R2 + disk); /health stays as a compat alias.

Regression: the single /health probe mixed liveness and readiness — an
orchestrator restarting on it would also kill the app during a Redis blip.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.main import app as main_app


def test_liveness_always_200_no_deps():
    c = TestClient(main_app)
    r = c.get("/liveness")
    assert r.status_code == 200
    assert r.json() == {"status": "alive"}


def test_readiness_reports_all_components(monkeypatch):
    c = TestClient(main_app)
    r = c.get("/readiness")
    j = r.json()
    assert r.status_code == 200
    for key in ("db", "redis", "worker", "r2", "disk", "status"):
        assert key in j, f"readiness must report {key}"


def test_health_is_alias_of_readiness():
    c = TestClient(main_app)
    h = c.get("/health")
    rd = c.get("/readiness")
    assert h.status_code == rd.status_code
    assert h.json() == rd.json()


def test_readiness_degrades_when_db_down(monkeypatch):

    class _Dead:
        def connect(self):
            raise RuntimeError("db down")

    monkeypatch.setattr("app.main.engine", _Dead())
    c = TestClient(main_app)
    r = c.get("/readiness")
    assert r.status_code == 503
    assert r.json()["db"] == "down"
    assert r.json()["status"] == "degraded"
    # liveness still answers — process is alive even though deps are down
    assert c.get("/liveness").status_code == 200
