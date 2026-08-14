"""Health endpoint + degraded banner — audit r3 (P2-18): /health must report
degraded + 503 when Redis/DB is down (the UI banner keys off this)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.main import app


def test_health_ok():
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_degraded_when_redis_down(monkeypatch):
    # point at a dead redis port → ping fails → degraded
    monkeypatch.setattr("app.main._REDIS_URL", "redis://127.0.0.1:59999/0")
    r = TestClient(app).get("/health")
    assert r.status_code == 503
    j = r.json()
    assert j["status"] == "degraded"
    assert j["redis"] == "down"


def test_health_degraded_when_db_down(monkeypatch):
    class DeadEngine:
        def connect(self):
            raise ConnectionError("db down")
    monkeypatch.setattr("app.main.engine", DeadEngine())
    r = TestClient(app).get("/health")
    assert r.status_code == 503
    j = r.json()
    assert j["status"] == "degraded"
    assert j["db"] == "down"
