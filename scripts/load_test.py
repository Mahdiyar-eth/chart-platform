#!/usr/bin/env python3
"""G14 (master-spec §61/Capacity) — lightweight capacity probe.

Fires concurrent requests at the key public endpoints and reports
latency/throughput/error rate. Safe against prod (GET-only, small N, no
state mutation). Run:  venv/bin/python scripts/load_test.py [url] [concurrency] [total]

Exit code 0 = all targets healthy (p95 < 800ms, 0 errors).
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
CONC = int(sys.argv[2]) if len(sys.argv) > 2 else 20
TOTAL = int(sys.argv[3]) if len(sys.argv) > 3 else 200

TARGETS = ["/", "/plans", "/synastry", "/learn", "/birth-chart/tehran", "/sitemap.xml"]


def hit(url: str, i: int) -> tuple[float, int]:
    t0 = time.perf_counter()
    try:
        req = Request(url, headers={"X-Forwarded-For": f"10.0.{i // 250}.{i % 250}"})
        with urlopen(req, timeout=10) as r:
            return time.perf_counter() - t0, r.status
    except Exception as e:  # noqa: BLE001
        return time.perf_counter() - t0, getattr(e, "code", 599)


def main() -> int:
    fails = []
    for path in TARGETS:
        url = BASE + path
        lat, codes = [], []
        with ThreadPoolExecutor(max_workers=CONC) as ex:
            for dur, status in ex.map(lambda x: hit(x[0], x[1]), ((url, i) for i in range(TOTAL))):
                lat.append(dur)
                codes.append(status)
        lat.sort()
        p50 = lat[TOTAL // 2] * 1000
        p95 = lat[int(TOTAL * 0.95)] * 1000
        errs = sum(1 for c in codes if c >= 400)
        print(f"{path:26s} p50={p50:6.1f}ms  p95={p95:7.1f}ms  err={errs}/{TOTAL}")
        if p95 > 800 or errs:
            fails.append(path)
    if fails:
        print(f"LOAD-TEST: UNHEALTHY → {fails}")
        return 1
    print("LOAD-TEST: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
