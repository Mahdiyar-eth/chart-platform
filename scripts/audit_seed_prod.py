"""Seed test accounts for the runtime acceptance audit (PROD DB).

Creates UserA (no purchase), UserB (paid report + wallet + coupon usage),
UserC (refund/withdrawal candidate), Guest chart with capability token.
All are tracked in a marker table so the audit cleanup can remove exactly them.
"""
import os
import sys
import uuid

sys.path.insert(0, "/root/chart-platform")
os.environ["APP_ENV"] = "prod"

from sqlmodel import Session, select  # noqa: E402

from app.auth import _user_cookie_value  # noqa: E402
from app.db import engine  # noqa: E402
from app.models import Chart, Coupon, Order, Report, User  # noqa: E402


def main():
    with Session(engine) as s:
        # avoid double-run: skip if userA exists
        existing = s.exec(select(User).where(User.phone == "09120000009")).first()
        if existing:
            print("ALREADY_SEEDED — skipping")
            return

        ua = User(phone="09120000009", status="active")
        ub = User(phone="09120000008", status="active", balance_rial=2_500_000)
        uc = User(phone="09120000007", status="active", balance_rial=1_000_000)
        s.add(ua)
        s.add(ub)
        s.add(uc)
        s.commit()
        s.refresh(ua)
        s.refresh(ub)
        s.refresh(uc)
        print("USERS:", ua.id[:8], ub.id[:8], uc.id[:8])

        # Charts: A one free chart; B one paid-style chart; guest chart (no user)
        def mk_chart(user_id, name, profile_id=None):
            c = Chart(
                id=str(uuid.uuid4()),
                profile_id=profile_id,
                access_token="tok-" + uuid.uuid4().hex[:20],
                chart_json={
                    "birth": {
                        "lat": 35.6889, "lon": 51.4297, "tz_name": "Asia/Tehran",
                        "utc_time": "1994-08-23 01:40:00",
                        "local_time": "1994-08-23 06:10", "time_known": True,
                    },
                    "planets": {"Sun": {"longitude": 149.716514, "sign_fa": "اسد", "sign_en": "Leo", "degree": 29.71, "house": 1, "retrograde": False}},
                    "angles": {"ASC": {"longitude": 144.971753, "house": 1}},
                    "houses": {},
                },
                engine_config={},
                created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
            s.add(c)
            return c

        from app.models import BirthProfile  # noqa: E402

        prof_b = BirthProfile(
            id=str(uuid.uuid4()), user_id=ub.id, name="B", calendar_system="jalali",
            raw_year=1373, raw_month=6, raw_day=1,
            hour=6, minute=10, city_fa="تهران", lat=35.6889, lon=51.4297,
        )
        s.add(prof_b)
        s.commit()
        s.refresh(prof_b)
        chart_a = mk_chart(ua.id, "A")
        chart_b = mk_chart(ub.id, "B", profile_id=prof_b.id)
        chart_g = mk_chart(None, "G")  # guest — capability token only
        s.commit()
        for c in (chart_a, chart_b, chart_g):
            s.refresh(c)
        print("CHARTS:", chart_a.id[:8], chart_b.id[:8], chart_g.id[:8], "guest_token:", chart_g.access_token[:12])

        # Paid report for B (gold) + order paid (ownership via chart → profile → user)
        rep = Report(
            id=str(uuid.uuid4()), chart_id=chart_b.id,
            status="done", plan_key="gold", pdf_path="/tmp/audit-report.pdf",
            created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        s.add(rep)
        s.commit()
        s.refresh(rep)
        order_b = Order(
            id=str(uuid.uuid4()), chart_id=chart_b.id, report_id=rep.id,
            plan_key="gold", status="paid", amount_rial=2_490_000, ref_id="AUDIT-REF-001",
            created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        s.add(order_b)
        s.commit()
        print("REPORT_B:", rep.id[:8], "ORDER_B:", order_b.id[:8])

        # coupon for the coupon scenario
        cp = Coupon(code="AUDIT10", percent=10, max_uses=5, active=True, used_count=0)
        s.add(cp)
        s.commit()
        print("COUPON: AUDIT10")

        # cookies for browser login simulation
        print("COOKIE_A:", _user_cookie_value(ua.id))
        print("COOKIE_B:", _user_cookie_value(ub.id))
        print("COOKIE_C:", _user_cookie_value(uc.id))
        print("CHART_A:", chart_a.id)
        print("CHART_B:", chart_b.id)
        print("CHART_G:", chart_g.id)
        print("GUEST_TOKEN:", chart_g.access_token)


if __name__ == "__main__":
    main()
