"""
Golden charts — reference charts with expected positions + engine config snapshot.
Every engine/prompt/renderer change must pass ALL golden charts (plan v3.1 §5.4).

Chart 1 = MaHDi's verified chart (expert agreement within 1 arc-minute,
cross-checked against manual DST-offset computation 2026-08-12).
"""

GOLDEN_CHARTS = [
    {
        "id": "chart-1-mahdi",
        "name": "چارت مرجع — مهدی (تطبیق با متخصص، تلرانس ۱ دقیقه قوس)",
        "birth": {
            "lat": 35.6892, "lon": 51.3890,
            "year": 1994, "month": 8, "day": 23, "hour": 6, "minute": 10,
            "time_known": True, "jalali": False, "tz_name": "Asia/Tehran",
        },
        "engine_config": {
            "house_system": "P", "zodiac": "tropical", "ayanamsa": None,
            "orb_rules": {"conjunction": 8.0, "sextile": 6.0, "square": 7.0,
                          "trine": 8.0, "opposition": 8.0},
            "node_type": "mean", "lilith": "mean", "chiron": True,
        },
        "expected": {  # degrees — tolerance 1 arc-minute (0.0167°)
            "Sun": 149.717, "Moon": 351.0, "ASC": 144.933, "MC": 49.967,
            "asc_deg": 24.933, "mc_deg": 19.967,
            "sun_sign": 4, "moon_sign": 11,
            "sun_house": 1, "moon_house": 8,
            "moon_phase": "Waning",
            "moon_phase_deg": 201.3,
            "saturn_retrograde": True, "saturn_house": 7,
            "verify_utc": "1994-08-23 01:40:00",  # 06:10 +4:30 DST → UTC
        },
    },
    {
        "id": "chart-2-no-time",
        "name": "بدون ساعت تولد (ساعت نامعلوم)",
        "birth": {"lat": 35.6892, "lon": 51.3890, "year": 1994, "month": 8, "day": 23,
                  "hour": 12, "minute": 0, "time_known": False, "jalali": False,
                  "tz_name": "Asia/Tehran"},
        "engine_config": None,
        "expected": {"sun_sign": 4, "sun_deg_min": 29.0, "sun_deg_max": 30.0},
    },
    {
        "id": "chart-3-no-dst-1400s",
        "name": "بعد از لغو DST (تولد ۱۴۰۲ — همیشه +3:30)",
        "birth": {"lat": 35.6892, "lon": 51.3890, "year": 2023, "month": 8, "day": 23,
                  "hour": 6, "minute": 10, "time_known": True, "jalali": False,
                  "tz_name": "Asia/Tehran"},
        "engine_config": None,
        "expected": {"verify_utc": "2023-08-23 02:40:00"},
    },
    {
        "id": "chart-4-pre-1977",
        "name": "قبل از آزمایش +4:00 (تولد ۱۳۵۵ — پایه +3:30)",
        "birth": {"lat": 35.6892, "lon": 51.3890, "year": 1976, "month": 8, "day": 23,
                  "hour": 6, "minute": 10, "time_known": True, "jalali": False,
                  "tz_name": "Asia/Tehran"},
        "engine_config": None,
        "expected": {"verify_utc": "1976-08-23 02:40:00"},  # +3:30 base (pre-1977)
    },
    {
        "id": "chart-5-dst-era1",
        "name": "DST دوره اول (تولد ۱۳۵۸ تابستان — +4:30)",
        "birth": {"lat": 35.6892, "lon": 51.3890, "year": 1979, "month": 8, "day": 23,
                  "hour": 6, "minute": 10, "time_known": True, "jalali": False,
                  "tz_name": "Asia/Tehran"},
        "engine_config": None,
        "expected": {"verify_utc": "1979-08-23 01:40:00"},  # DST May27-Sep19 1979
    },
    {
        "id": "chart-6-foreign-city",
        "name": "شهر خارجی (استانبول — UTC+3)",
        "birth": {"lat": 41.0082, "lon": 28.9784, "year": 1994, "month": 8, "day": 23,
                  "hour": 6, "minute": 10, "time_known": True, "jalali": False,
                  "tz_name": "Europe/Istanbul"},
        "engine_config": None,
        "expected": {"verify_utc": "1994-08-23 03:10:00"},
    },
    {
        "id": "chart-7-leap-jalali",
        "name": "سال کبیسه شمسی (تولد ۱ اسفند ۱۳۹۹ — تبدیل جلالی)",
        "birth": {"lat": 35.6892, "lon": 51.3890, "year": 1399, "month": 12, "day": 1,
                  "hour": 6, "minute": 10, "time_known": True, "jalali": True,
                  "tz_name": "Asia/Tehran"},
        "engine_config": None,
        "expected": {"verify_utc": "2021-02-19 02:40:00"},
    },
    {
        "id": "chart-8-house-boundary",
        "name": "مرز خانه (سیاره روی کاسپ) + رتروگرید",
        "birth": {"lat": 35.6892, "lon": 51.3890, "year": 2020, "month": 5, "day": 15,
                  "hour": 14, "minute": 30, "time_known": True, "jalali": False,
                  "tz_name": "Asia/Tehran"},
        "engine_config": None,
        "expected": {"has_retrograde": True,
                     "verify_utc": "2020-05-15 10:00:00"},  # 14:30 +4:30 DST → UTC
    },
    {
        "id": "chart-7-sidereal-lahiri",
        "name": "سایدریال لاهیری — همان تولد مهدی (audit r3: انتخاب سیستم زودیاک)",
        "birth": {
            "lat": 35.6892, "lon": 51.3890,
            "year": 1994, "month": 8, "day": 23, "hour": 6, "minute": 10,
            "time_known": True, "jalali": False, "tz_name": "Asia/Tehran",
        },
        "engine_config": {
            "house_system": "P", "zodiac": "sidereal", "ayanamsa": None,
            "orb_rules": {"conjunction": 8.0, "sextile": 6.0, "square": 7.0,
                          "trine": 8.0, "opposition": 8.0},
            "node_type": "mean", "lilith": "mean", "chiron": True,
        },
        "expected": {  # degrees — Lahiri ayanamsa ≈ 23.78° (tropical − sidereal)
            "Sun": 125.934, "Moon": 327.220, "ASC": 121.156, "MC": 26.180,
            "sun_sign": 4, "moon_sign": 10,       # Leo stays, Pisces→Aquarius
            "sun_house": 1, "moon_house": 8,
            "moon_phase": "Waning",
            "moon_phase_deg": 201.286,
            "saturn_retrograde": True, "saturn_house": 7,
            "verify_utc": "1994-08-23 01:40:00",  # 06:10 +4:30 DST → UTC
        },
    },
    # ── H0.1 (HARDENING): world DST coverage — london/newyork summer vs winter,
    # dubai fixed offset ──
    {
        "id": "chart-9-london-summer",
        "name": "لندن تابستان ۱۹۹۴ (BST +1 → UTC)",
        "birth": {"lat": 51.5074, "lon": -0.1278, "year": 1994, "month": 7, "day": 10,
                  "hour": 12, "minute": 30, "time_known": True, "jalali": False,
                  "tz_name": "Europe/London"},
        "engine_config": None,
        "expected": {"verify_utc": "1994-07-10 11:30:00"},  # independent zoneinfo
    },
    {
        "id": "chart-10-london-winter",
        "name": "لندن زمستان ۱۹۹۴ (GMT +0 → UTC)",
        "birth": {"lat": 51.5074, "lon": -0.1278, "year": 1994, "month": 1, "day": 10,
                  "hour": 12, "minute": 30, "time_known": True, "jalali": False,
                  "tz_name": "Europe/London"},
        "engine_config": None,
        "expected": {"verify_utc": "1994-01-10 12:30:00"},
    },
    {
        "id": "chart-11-newyork-summer",
        "name": "نیویورک تابستان ۱۹۹۴ (EDT −4 → UTC)",
        "birth": {"lat": 40.7128, "lon": -74.0060, "year": 1994, "month": 7, "day": 10,
                  "hour": 12, "minute": 30, "time_known": True, "jalali": False,
                  "tz_name": "America/New_York"},
        "engine_config": None,
        "expected": {"verify_utc": "1994-07-10 16:30:00"},
    },
    {
        "id": "chart-12-newyork-winter",
        "name": "نیویورک زمستان ۱۹۹۴ (EST −5 → UTC)",
        "birth": {"lat": 40.7128, "lon": -74.0060, "year": 1994, "month": 1, "day": 10,
                  "hour": 12, "minute": 30, "time_known": True, "jalali": False,
                  "tz_name": "America/New_York"},
        "engine_config": None,
        "expected": {"verify_utc": "1994-01-10 17:30:00"},
    },
    {
        "id": "chart-13-dubai",
        "name": "دبی (بدون DST — آفست ثابت +4)",
        "birth": {"lat": 25.2048, "lon": 55.2708, "year": 2024, "month": 7, "day": 10,
                  "hour": 12, "minute": 30, "time_known": True, "jalali": False,
                  "tz_name": "Asia/Dubai"},
        "engine_config": None,
        "expected": {"verify_utc": "2024-07-10 08:30:00"},
    },
]
