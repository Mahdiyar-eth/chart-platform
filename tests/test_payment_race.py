"""Payment callback race — audit r3: concurrent duplicate Zarinpal callbacks
must process an order exactly ONCE (single verify, single coupon increment,
single report row)."""
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.db import engine
from app.models import Chart, Coupon, Order, Report


class FakeZarinpalClient:
    verify_calls = 0
    lock = threading.Lock()

    def __init__(self):
        pass

    def verify(self, authority, amount_rial):
        with self.lock:
            FakeZarinpalClient.verify_calls += 1  # class attr — assert reads it
        time.sleep(0.05)  # widen the window between claim and commit
        return {"ref_id": "100000000099", "card_pan": "621986****0000"}


@pytest.fixture
def paid_order(monkeypatch):
    monkeypatch.setattr("app.main.ZarinpalClient", FakeZarinpalClient)
    FakeZarinpalClient.verify_calls = 0
    auth = f"S{int(time.time())}{'R' * 20}"
    with Session(engine) as s:
        ch = Chart(chart_json={"planets": {}, "engine_config": {"zodiac": "tropical"}})
        s.add(ch)
        s.flush()
        c = Coupon(code=f"RACE{int(time.time())}", percent=50, max_uses=5, used_count=0)
        s.add(c)
        s.flush()
        o = Order(plan_key="full", amount_rial=1_490_000, status="pending",
                  authority=auth, chart_id=ch.id, coupon_id=c.id)
        s.add(o)
        s.commit()
        yield {"order_id": o.id, "coupon_id": c.id, "auth": auth}


def test_concurrent_verify_processes_once(paid_order):
    barrier = threading.Barrier(5)

    def hit(_):
        barrier.wait()
        # fresh client per thread — starlette TestClient is not thread-safe
        url = f"/api/payments/verify?Authority={paid_order['auth']}&Status=OK"
        with TestClient(app) as tc:
            return tc.get(url, follow_redirects=False).status_code

    with ThreadPoolExecutor(max_workers=5) as ex:
        codes = list(ex.map(hit, range(5)))

    assert all(code in (302, 303) for code in codes), codes
    with Session(engine) as s:
        o = s.get(Order, paid_order["order_id"])
        coupon = s.get(Coupon, paid_order["coupon_id"])
        reports = s.exec(select(Report).where(Report.chart_id == o.chart_id)).all()
    assert FakeZarinpalClient.verify_calls == 1, f"verify called {FakeZarinpalClient.verify_calls}x"
    assert o.status == "paid"
    # audit r4 A10: coupon consumption moved to order CREATION (reservation);
    # a raw-DB fixture order never reserved → used_count stays 0
    assert coupon.used_count == 0, f"coupon consumed {coupon.used_count}x"
    assert len(reports) == 1, f"{len(reports)} reports created (expected 1)"
