#!/usr/bin/env python3
"""Transit digests for bot subscribers (plan v3.0 §7) — daily 07:00 + weekly.

AI-INDEPENDENT (system crontab):
  - daily:  0 7 * * *     → freq=daily
  - weekly: 0 7 * * 6     → freq=weekly (Saturday morning, richer digest)

Only ACTIVE, non-expired subscriptions receive digests. Silent when nobody.
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/root/chart-platform")
from dotenv import load_dotenv  # noqa: E402

load_dotenv("/root/chart-platform/.env")

from app.db import Session, engine  # noqa: E402
from sqlmodel import select  # noqa: E402
from app.models import Chart, Subscription  # noqa: E402
from app.astrology.transits import compute_transits  # noqa: E402

TOKENS = {
    "telegram": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    "bale": os.getenv("BALE_BOT_TOKEN", ""),
}
_API = {
    "telegram": f"https://api.telegram.org/bot{TOKENS['telegram']}",
    "bale": f"https://tapi.bale.ai/bot{TOKENS['bale']}",
}


def _send(platform: str, chat_id: str, text: str) -> bool:
    import requests
    try:
        r = requests.post(f"{_API[platform]}/sendMessage",
                          json={"chat_id": int(chat_id), "text": text,
                                "parse_mode": "HTML"}, timeout=20)
        return r.status_code == 200 and r.json().get("ok", False)
    except Exception:
        return False


def _format_digest(transits: list[dict], weekly: bool = False) -> str:
    if not transits:
        return "🌠 امروز گذر مهمی روی چارت تولدت فعال نیست — روز آرامی داری."
    lines = []
    for t in transits[: (7 if weekly else 5)]:
        target = {"Sun": "خورشید", "Moon": "ماه", "ASC": "طالع"}.get(t["target"], t["target"])
        lines.append(f"• {t['planet_fa']} ({t['sign_fa']}) — {t['aspect']} با <b>{target}</b> (اورب {t['orb']}°)")
    if weekly:
        return "📅 <b>گذرهای هفتهی پیشِ روی چارت تو</b>\n\n" + "\n".join(lines) + \
               "\n\nاین هفته: مراقب فرصتهای شغلی و گفتوگوهای مهم باش."
    return "🌠 <b>گذرهای امروز چارت تو</b>\n\n" + "\n".join(lines)


def main(weekly: bool = False) -> None:
    now = datetime.now(timezone.utc)
    with Session(engine) as s:
        subs = s.exec(select(Subscription).where(
            Subscription.active == True)).all()  # noqa: E712
        if not subs:
            return
        sent = 0
        for sub in subs:
            if weekly and sub.freq != "weekly":
                continue
            if sub.expires_at and sub.expires_at < now:
                sub.active = False  # auto-expire unpaid renewals
                continue
            chart = s.get(Chart, sub.chart_id)
            if not chart or not chart.chart_json:
                continue
            transits = compute_transits(chart.chart_json)
            text = _format_digest(transits, weekly=weekly)
            if _send(sub.platform, sub.chat_id, text):
                sub.last_sent_at = now
                sent += 1
        s.commit()
    print(f"transit digests sent: {sent}") if sent else None


if __name__ == "__main__":
    main(weekly=("--weekly" in sys.argv))
