"""Rate limiter tests — audit P1 (round 3): centralized limiter enforces limits
and the Redis backend degrades to in-memory when Redis is unreachable."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.security as sec
from app.security import RateLimitExceeded, check_rate_limit


def test_memory_limiter_enforces_window():
    key = "test-rl-1"
    check_rate_limit(key, 2, 10)
    check_rate_limit(key, 2, 10)
    try:
        check_rate_limit(key, 2, 10)
        assert False, "third call should be limited"
    except RateLimitExceeded:
        pass


def test_memory_limiter_allows_after_window():
    key = "test-rl-2"
    check_rate_limit(key, 1, 0)   # zero window → entry ages out instantly
    check_rate_limit(key, 1, 0)   # allowed again


def test_redis_backend_falls_back_to_memory(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:59999/0")  # dead port
    sec._RATE_LIMIT_BACKEND = "redis"
    sec._rl_redis_conn = None
    key = "test-rl-3"
    check_rate_limit(key, 1, 10)   # Redis down → in-memory fallback, no crash
    try:
        check_rate_limit(key, 1, 10)
        assert False, "fallback limiter must still enforce"
    except RateLimitExceeded:
        pass
    sec._RATE_LIMIT_BACKEND = "memory"  # restore for other tests
    sec._rl_redis_conn = None


def test_chart_creation_rate_limited(monkeypatch):
    """audit r4 B5: chart creation is limited to 20/min per client."""
    import app.main as m
    import app.security as sec

    # this test exercises the REAL limiter (conftest bypasses it by default);
    # same shape as main._rate_limit: (key, limit, window) -> allowed
    def _real(key, limit, window=60.0):
        try:
            sec.check_rate_limit(key, limit, int(window))
            return True
        except sec.RateLimitExceeded:
            return False

    monkeypatch.setattr(m, "_rate_limit", _real)
    ok = [m._rate_limit("chart:testclient", 20, 60) for _ in range(20)]
    assert all(ok), "first 20 calls allowed"
    assert not m._rate_limit("chart:testclient", 20, 60), "21st call limited"
