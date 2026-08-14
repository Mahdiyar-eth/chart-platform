"""Chart-platform bot handler — Telegram + Bale, fully button-driven.

Flow: /start → «ساخت چارت» → birth date → birth time (optional) → city →
chart computed → share card + chart link + action buttons.
Uses Bot API over httpx; tokens from env. parse_mode=HTML everywhere
(pitfall: Markdown breaks on _ in ids — none here, but stay safe).
"""
from __future__ import annotations

import html as _html
import logging
import os
import re
import secrets
import traceback

import httpx

import app.config  # noqa: F401 — load .env FIRST
from app.astrology.big_three import big_three
from app.astrology.cities_ir import search_cities
from app.astrology.engine import compute_from_fields, validate_birth_fields
from app.bots.state import clear_chat_state, get_chat_state, set_chat_state
from sqlmodel import select

logger = logging.getLogger("chart.bots")

from app.secret_store import get_secret

TELEGRAM_TOKEN = get_secret("telegram_bot_token", "TELEGRAM_BOT_TOKEN", "")
BALE_TOKEN = get_secret("bale_bot_token", "BALE_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_SECRET = get_secret("telegram_webhook_secret", "TELEGRAM_WEBHOOK_SECRET", "")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
BALE_API = f"https://tapi.bale.ai/bot{BALE_TOKEN}"


async def api_call(method: str, payload: dict, platform: str) -> dict:
    token = TELEGRAM_TOKEN if platform == "telegram" else BALE_TOKEN
    if not token:
        return {"ok": False, "description": "token not configured"}
    base = TELEGRAM_API if platform == "telegram" else BALE_API
    try:
        async with httpx.AsyncClient(timeout=30) as cl:
            r = await cl.post(f"{base}/{method}", json=payload)
            data = r.json()
            if not data.get("ok"):
                logger.warning("BotAPI %s/%s -> %s", platform, method, data.get("description"))
            return data
    except Exception as e:  # noqa: BLE001
        logger.error("BotAPI %s/%s error: %s", platform, method, e)
        return {"ok": False, "description": str(e)}


def _fmt_html(text: str) -> str:
    escaped = _html.escape(text, quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)


async def send_message(chat_id: int, text: str, platform: str, reply_markup: dict | None = None) -> dict:
    payload = {"chat_id": chat_id, "text": _fmt_html(text), "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await api_call("sendMessage", payload, platform)


async def send_photo(chat_id: int, photo_url: str, caption: str, platform: str, reply_markup: dict | None = None) -> dict:
    payload = {"chat_id": chat_id, "photo": photo_url, "caption": _fmt_html(caption), "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await api_call("sendPhoto", payload, platform)


async def answer_callback(cb_id: str, text: str = "", platform: str = "telegram") -> None:
    await api_call("answerCallbackQuery", {"callback_query_id": cb_id, "text": text}, platform)


def cancel_keyboard() -> dict:
    return {"inline_keyboard": [[{"text": "❌ لغو", "callback_data": "cancel"}]]}


def start_keyboard() -> dict:
    return {"inline_keyboard": [[{"text": "✨ ساخت چارت تولد من", "callback_data": "chart_start"}]]}


def chart_actions_keyboard(chart_id: str, tok: str = "") -> dict:
    base = os.getenv("PUBLIC_BASE_URL", "https://chart.negar.io").rstrip("/")
    q = f"?t={tok}" if tok else ""  # audit r4 A6: bot charts carry capability token
    sep = "&" if q else ""          # keep the query string well-formed
    return {
        "inline_keyboard": [
            [{"text": "📄 مشاهده چارت", "url": f"{base}/chart/{chart_id}{q}"}],
            [{"text": "✨ خرید گزارش کامل", "url": f"{base}/plans?chart={chart_id}{sep}{q.lstrip('?')}"}],
            [{"text": "🌠 گذرهای کنونی", "url": f"{base}/transit/{chart_id}{q}"}],
            [{"text": "🌌 نگاهی به آسمان هفته", "callback_data": f"sub_{chart_id}"}],
        ]
    }


# ─────────────────────────── commands ───────────────────────────

async def _cmd_start(chat_id: int, platform: str) -> None:
    await send_message(
        chat_id,
        "🌟 به ربات چارت تولد خوش آمدی!\n\n"
        "با چند اطلاعات ساده، چارت نجومی دقیق تو را محاسبه می‌کنم و از آن یک گزارش اختصاصی می‌سازم.\n\n"
        "👇 شروع کنیم؟",
        platform, reply_markup=start_keyboard(),
    )


# ─────────────────────────── state routing ───────────────────────────

_DATE_RE = re.compile(r"^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})$")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


async def _route_by_state(chat_id: int, platform: str, text: str) -> bool:
    st = get_chat_state(chat_id, platform)
    if not st:
        return False
    state, payload = st["state"], st["payload"]

    if state == "waiting_birth_date":
        m = _DATE_RE.match(text.strip())
        if not m:
            await send_message(chat_id, "⛔ قالب تاریخ درست نیست.\n📅 تاریخ را به شکل **روز/ماه/سال** بفرست؛ مثال: **23/08/1994**", platform)
            return True
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        ok, err = validate_birth_fields(y, mo, d)
        if not ok:
            await send_message(chat_id, f"⛔ {err}", platform)
            return True
        set_chat_state(chat_id, platform, "waiting_birth_time", {**payload, "day": d, "month": mo, "year": y})
        await send_message(
            chat_id,
            "🕐 **ساعت تولد** را بفرست (مثال: 06:10).\n\n"
            "اگر ساعت دقیق را نمی‌دانی، فقط **صفر** یا **خالی** بفرست — نیمه‌شب در نظر گرفته می‌شود.",
            platform, reply_markup=cancel_keyboard(),
        )
        return True

    if state == "waiting_birth_time":
        t = text.strip()
        hour, minute = 12, 0
        if t and t not in ("0", "صفر"):
            m = _TIME_RE.match(t)
            if not m:
                await send_message(chat_id, "⛔ قالب ساعت درست نیست.\n🕐 ساعت را به شکل **ساعت:دقیقه** بفرست؛ مثال: **06:10**", platform)
                return True
            hour, minute = int(m.group(1)), int(m.group(2))
            if hour > 23 or minute > 59:
                await send_message(chat_id, "⛔ ساعت نامعتبر است. بین 00:00 تا 23:59", platform)
                return True
        set_chat_state(chat_id, platform, "waiting_birth_city", {**payload, "hour": hour, "minute": minute})
        await send_message(
            chat_id,
            "🏙️ **شهر تولد** را بفرست (مثال: تهران، شیراز، مشهد...)",
            platform, reply_markup=cancel_keyboard(),
        )
        return True

    if state == "waiting_birth_city":
        city = text.strip()
        hits = search_cities(city) if city else []
        if not hits:
            await send_message(
                chat_id,
                "⛔ شهری با این نام پیدا نکردم. نام شهر را دوباره بفرست (مثلاً: تهران، اصفهان، تبریز، کرج...)",
                platform,
            )
            return True
        best = hits[0]
        # audit r3: zodiac system is a choice → buttons, before computing
        set_chat_state(chat_id, platform, "waiting_zodiac",
                       {**payload, "city_fa": city, "lat": best["lat"], "lon": best["lon"]})
        await send_message(
            chat_id,
            "🌗 **سیستم نجومی** چارت را انتخاب کن:\n\n"
            "**تروپیکال** — برج‌های خورشیدی رایج (پیش‌فرض)\n"
            "**سایدریال لاهیری** — سیستم ودیک/هندی",
            platform,
            reply_markup={"inline_keyboard": [[
                {"text": "🌞 تروپیکال (پیش‌فرض)", "callback_data": "zodiac_tropical"},
                {"text": "🕉 سایدریال لاهیری", "callback_data": "zodiac_sidereal"},
            ]]},
        )
        return True

    if state == "waiting_zodiac":
        # should not arrive as free text (buttons only) — remind
        await send_message(
            chat_id, "روی یکی از دو دکمه‌ی بالا بزن: 🌞 تروپیکال یا 🕉 سایدریال لاهیری", platform)
        return True

    return False


async def _compute_and_send_chart(chat_id: int, platform: str, payload: dict, zodiac: str) -> None:
    """Compute chart from payload + chosen zodiac system, persist, send card."""
    try:
        from app.astrology.cities_world import is_iran_coords, tz_from_coords
        tz_name = tz_from_coords(payload["lat"], payload["lon"])
        # F-06: Tehran fallback only for Iran; bot asks for a city otherwise
        if tz_name is None and not is_iran_coords(payload["lat"], payload["lon"]):
            await send_message(chat_id, "⛔ برای این موقعیت، شهر را انتخاب کن تا منطقهٔ زمانی درست شود.", platform)
            return
        chart = compute_from_fields(
            payload["lat"], payload["lon"], payload["year"], payload["month"],
            payload["day"], payload["hour"], payload["minute"], zodiac=zodiac,
            tz_name=tz_name or "Asia/Tehran",
        )
    except Exception as e:  # noqa: BLE001
        logger.error("compute failed: %s", e)
        await send_message(chat_id, "⛔ مشکلی در محاسبه پیش آمد؛ دوباره تلاش کن.", platform)
        return

    from app.db import engine
    from sqlmodel import Session
    from app.models import Chart
    with Session(engine) as s:
        row = Chart(chart_json=chart.chart_json,
                    access_token=secrets.token_urlsafe(32))  # A6: capability token
        s.add(row)
        s.commit()
        chart_id = row.id

    bt = big_three(chart.chart_json)
    base = os.getenv("PUBLIC_BASE_URL", "https://chart.negar.io").rstrip("/")
    caption = (
        f"🌟 **چارت تولد تو آماده شد!**\n\n"
        f"☀️ خورشید: **{bt.get('Sun', {}).get('sign_fa', '')}**\n"
        f"🌙 ماه: **{bt.get('Moon', {}).get('sign_fa', '')}**\n"
        f"⬆️ طالع: **{bt.get('ASC', {}).get('sign_fa', '')}**\n\n"
        f"سیستم: {'سایدریال لاهیری' if zodiac == 'sidereal' else 'تروپیکال'}\n"
        f"برای مشاهده و خرید گزارش اختصاصی، دکمه‌های زیر را بزن:"
    )
    await send_photo(chat_id, f"{base}/api/share/{chart_id}.png", caption,
                     platform, reply_markup=chart_actions_keyboard(chart_id, row.access_token or ""))


# ─────────────────────────── update dispatch ───────────────────────────

async def handle_update(update: dict, platform: str) -> dict:
    try:
        msg = update.get("message") or {}
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        text = msg.get("text") or ""
        entities = msg.get("entities") or []
        is_command = bool(entities and entities[0].get("type") == "bot_command") or text.startswith("/")

        if msg.get("photo") and chat_id:
            return await _route_photo(chat_id, platform, msg)

        if chat_id:
            if is_command and text.startswith("/start"):
                await _cmd_start(chat_id, platform)
                return {"ok": True}
            if is_command and text.startswith("/cancel_sub"):
                try:
                    from app.db import Session as _Session
                    from app.db import engine as _engine
                    from app.models import Subscription
                    with _Session(_engine) as s:
                        subs = s.exec(select(Subscription).where(
                            Subscription.chat_id == str(chat_id),
                            Subscription.active == True,
                        )).all()
                        for sub in subs:
                            sub.active = False
                        s.commit()
                    await send_message(chat_id, "اشتراک گذرها لغو شد. 😔\nهر وقت خواستی دوباره فعالش کن.", platform)
                except Exception as e:  # noqa: BLE001
                    logger.error("cancel_sub error: %s", e)
                    await send_message(chat_id, "مشکلی پیش آمد؛ دوباره تلاش کن.", platform)
                return {"ok": True}
            if not is_command and text:
                handled = await _route_by_state(chat_id, platform, text)
                if handled:
                    return {"ok": True}
                await send_message(chat_id, "برای شروع دکمه‌ی «✨ ساخت چارت تولد من» را بزن.", platform)
                return {"ok": True}

        cb = update.get("callback_query")
        if cb:
            await _handle_callback(cb, platform)
            return {"ok": True}

        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        logger.error("handle_update(%s) error: %s\n%s", platform, e, traceback.format_exc())
        return {"ok": True}


async def _route_photo(chat_id: int, platform: str, msg: dict) -> dict:
    """No photo flow in chart bot — but keep state machine sane."""
    st = get_chat_state(chat_id, platform)
    if st:
        await send_message(chat_id, "این بخش نیاز به متن دارد — لطفاً اطلاعات خواسته‌شده را بنویس.", platform)
    return {"ok": True}


async def _handle_callback(cb: dict, platform: str) -> None:
    cb_id = cb.get("id")
    chat_id = cb.get("message", {}).get("chat", {}).get("id")
    data = cb.get("data") or ""
    if not chat_id:
        if cb_id:
            await answer_callback(cb_id, platform=platform)
        return
    if data == "chart_start":
        set_chat_state(chat_id, platform, "waiting_birth_date", {})
        await send_message(
            chat_id,
            "📅 **تاریخ تولد** را بفرست؛ مثال: **23/08/1994**",
            platform, reply_markup=cancel_keyboard(),
        )
    elif data == "cancel":
        clear_chat_state(chat_id, platform)
        await send_message(chat_id, "لغو شد. هر وقت خواستی دوباره شروع کن 👇", platform, reply_markup=start_keyboard())
    elif data.startswith("zodiac_"):
        # audit r3: tropical|sidereal choice — compute the chart with the chosen system
        zodiac = data.split("_", 1)[1]
        if zodiac not in ("tropical", "sidereal"):
            await answer_callback(cb_id, "گزینه نامعتبر", platform=platform)
            return
        st = get_chat_state(chat_id, platform)
        if not st or st.get("state") != "waiting_zodiac":
            await answer_callback(cb_id, "ابتدا چارت بساز", platform=platform)
            return
        payload = st.get("payload") or {}
        clear_chat_state(chat_id, platform)
        await answer_callback(cb_id, platform=platform)
        await _compute_and_send_chart(chat_id, platform, payload, zodiac)
    elif data.startswith("sub_"):
        chart_id = data[4:]
        try:
            from app.db import Session as _Session
            from app.db import engine as _engine
            from app.models import Chart, Subscription
            with _Session(_engine) as s:
                chart = s.get(Chart, chart_id)
                if not chart:
                    await send_message(chat_id, "چارت پیدا نشد؛ اول یک چارت بساز.", platform)
                    return
                # existing active subscription → just show status
                from datetime import datetime as _dt, timezone as _tz
                sub = s.exec(select(Subscription).where(
                    Subscription.chat_id == str(chat_id),
                    Subscription.chart_id == chart_id, Subscription.active == True,  # noqa: E712
                )).first()
                if sub and sub.expires_at and sub.expires_at > _dt.now(_tz.utc):
                    expires = sub.expires_at.strftime("%Y-%m-%d") if sub.expires_at else "نامحدود"
                    await send_message(
                        chat_id,
                        f"🌌 اشتراک «نگاهی به آسمان هفته» فعال است (تا {expires}).\nبرای لغو: /cancel_sub",
                        platform,
                    )
                    return
                elif sub and (not sub.expires_at or sub.expires_at <= _dt.now(_tz.utc)):
                    sub.active = False  # auto-expire (audit r4 A9)
                    s.add(sub)
                    s.commit()
            # paid flow: monthly plan order → zarinpal link (plan v3.0 §7)
            from app.payment.orders import create_order
            with _Session(_engine) as s:
                order, pay_url = create_order(
                    s, "monthly", chart_id, chat_id=str(chat_id), platform=platform,
                    new_user_id=str(chat_id),
                )
            markup = {"inline_keyboard": [
                [{"text": "💳 پرداخت ۳۹۹ هزار تومان", "url": pay_url}],
            ]}
            await send_message(
                chat_id,
                "🌌 اشتراک «نگاهی به آسمان هفته» — ۳۹۹ هزار تومان در ماه\n\n"
                "هر هفته، نگاهی تأملی به گذرهای سیارهای چارتت را اینجا میفرستم.\n"
                "نقشه‌ی موقعیت‌های آسمان — نه تقدیر. پس از پرداخت، ۳۰ روز فعال می‌شود.",
                platform,
                reply_markup=markup,
            )
        except Exception as e:  # noqa: BLE001
            logger.error("subscription error: %s", e)
            await send_message(chat_id, "مشکلی در ایجاد اشتراک پیش آمد؛ دوباره تلاش کن.", platform)
    if cb_id:
        await answer_callback(cb_id, platform=platform)
