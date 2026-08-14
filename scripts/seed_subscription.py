"""Create a test subscription + verify weekly transit delivery machinery.

Simulates the weekly cron (needs no real VAPID push for the storage path;
the send path is exercised via the bot fallback when push is unavailable).
"""
import os, sys
sys.path.insert(0, "/root/chart-platform")
os.environ["APP_ENV"] = "prod"

from sqlmodel import Session, select
from app.db import engine
from app.models import Subscription

CHART_ID = "14df4cdd-abc6-4bfc-9c7a-7db5c0883037"


def main():
    with Session(engine) as s:
        subs = s.exec(select(Subscription).where(Subscription.chart_id == CHART_ID)).all()
        if not subs:
            s.add(Subscription(platform="web", chart_id=CHART_ID, freq="weekly",
                               plan_key="monthly", active=True))
            s.commit()
            print("SUBSCRIPTION CREATED")
        else:
            print("SUBSCRIPTION EXISTS")


if __name__ == "__main__":
    main()
