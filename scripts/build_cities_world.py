#!/usr/bin/env python3
"""Build app/astrology/data/cities_world_seed.json from geonames cities5000.

Keeps the largest ~1100 world cities (population >= 250k, top by pop) with
their official IANA timezone (geonames field 18) — used for correct chart
computation outside Iran (HARDENING H0.1). Deterministic; run manually when
the dataset needs refresh. Source: geonames.org (CC-BY-4.0).
"""
from __future__ import annotations

import json
from pathlib import Path

SRC = Path("/tmp/cities5000.txt")
OUT = Path(__file__).resolve().parent.parent / "app" / "astrology" / "data" / "cities_world_seed.json"
FA_OUT = Path(__file__).resolve().parent.parent / "app" / "astrology" / "data" / "cities_fa_world.json"

# ~120 well-known cities Persian -> geonames name (lowercased for match)
FA = {
    "استانبول": "istanbul", "آنکارا": "ankara", "ازمیر": "izmir", "آنتالیا": "antalya",
    "دبی": "dubai", "ابوظبی": "abu dhabi", "شارجه": "sharjah",
    "نیویورک": "new york city", "لوس آنجلس": "los angeles", "شیکاگو": "chicago",
    "هیوستون": "houston", "سان فرانسیسکو": "san francisco", "بوستون": "boston",
    "واشنگتن": "washington d.c.", "میامی": "miami", "تورنتو": "toronto",
    "ونکوور": "vancouver", "مونترال": "montreal",
    "لندن": "london", "منچستر": "manchester", "بیرمنگام": "birmingham", "ادینبورگ": "edinburgh",
    "پاریس": "paris", "لیون": "lyon", "مارسی": "marseille", "نیس": "nice",
    "برلین": "berlin", "هامبورگ": "hamburg", "مونیخ": "munich", "فرانکفورت": "frankfurt",
    "کلن": "cologne", "اشتوتگارت": "stuttgart",
    "رم": "rome", "میلان": "milan", "ناپل": "naples", "تورین": "turin", "ونیز": "venice",
    "فلورانس": "florence", "بولوینا": "bologna",
    "مادرید": "madrid", "بارسلون": "barcelona", "والنسیا": "valencia", "سویل": "seville",
    "لیسبون": "lisbon", "پورتو": "porto",
    "بروکسل": "brussels", "روتردام": "rotterdam", "لاهه": "the hague",
    "ژنو": "geneva", "زوریخ": "zurich", "آنتورپ": "antwerp",
    "وین": "vienna", "سالزبورگ": "salzburg", "پرگ": "prague", "بوداپست": "budapest",
    "ورشو": "warsaw", "کراکوف": "krakow", "مسکو": "moscow", "سن پترزبورگ": "saint petersburg",
    "کیف": "kyiv", "آتن": "athens", "سالونیک": "thessaloniki",
    "استکهلم": "stockholm", "اسلو": "oslo", "کپنهاگ": "copenhagen", "هلسینکی": "helsinki",
    "دوبلین": "dublin", "ریکیاویک": "reykjavik", "باکو": "baku", "تفلیس": "tbilisi",
    "ایروان": "yerevan", "بغداد": "baghdad", "کویت": "kuwait city", "ریاض": "riyadh",
    "جده": "jeddah", "مکه": "mecca", "مدینه": "medina", "دوحه": "doha", "مسقط": "muscat",
    "بیروت": "beirut", "دمشق": "damascus", "امان": "amman", "تل آویو": "tel aviv",
    "قاهره": "cairo", "اسکندریه": "alexandria", "الجزیره": "algiers", "تونس": "tunis",
    "رباط": "rabat", "کازابلانکا": "casablanca", "نایروبی": "nairobi", "آدیس آبابا": "addis ababa",
    "ژوهانسبورگ": "johannesburg", "کیپ تاون": "cape town", "دوربان": "durban",
    "دهلی": "delhi", "دهلی نو": "new delhi", "بمبئی": "mumbai", "پونا": "pune",
    "بنگلور": "bangalore", "حیدرآباد": "hyderabad", "چنای": "chennai", "کلکته": "kolkata",
    "کراچی": "karachi", "لاهور": "lahore", "اسلامآباد": "islamabad", "کابل": "kabul",
    "تاشکند": "tashkent", "آلماتی": "almaty", "بیشکک": "bishkek", "عشقآباد": "ashgabat",
    "دوشنبه": "dushanbe", "پکن": "beijing", "شانگهای": "shanghai", "گوانگژو": "guangzhou",
    "شنژن": "shenzhen", "هنگ کنگ": "hong kong", "ماکائو": "macau", "تایپه": "taipei",
    "سئول": "seoul", "توکیو": "tokyo", "اوساکا": "osaka", "کیوتو": "kyoto",
    "هیروشیما": "hiroshima", "سنگاپور": "singapore", "بانکوک": "bangkok", "پوکت": "phuket",
    "کوالالامپور": "kuala lumpur", "جاکارتا": "jakarta", "بالی": "denpasar",
    "مانیل": "manila", "هانوی": "hanoi", "هوشیمین": "ho chi minh city",
    "سیدنی": "sydney", "ملبورن": "melbourne", "بریزبن": "brisbane", "پرت": "perth",
    "آوکلند": "auckland", "ولینگتون": "wellington",
    "بوئنوس آیرس": "buenos aires", "سائوپائولو": "sao paulo", "ریودوژانیرو": "rio de janeiro",
    "برازیلیا": "brasilia", "سانتیاگو": "santiago", "لیما": "lima", "بوگوتا": "bogota",
    "کاراکاس": "caracas", "مکزیکو سیتی": "mexico city", "مونتری": "monterrey",
    "آتلانتا": "atlanta", "دالاس": "dallas", "دنور": "denver", "سیاتل": "seattle",
    "لاس وگاس": "las vegas", "اورلاندو": "orlando", "فینیکس": "phoenix", "فیلادلفیا": "philadelphia",
    "سان دیگو": "san diego", "پورتلند": "portland", "مینیاپولیس": "minneapolis",
    "دیترویت": "detroit", "کلیولند": "cleveland", "پیتسبرگ": "pittsburgh",
}


def build() -> None:
    rows = []
    with SRC.open(encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 19:
                continue
            try:
                pop = int(p[14])
            except ValueError:
                continue
            if pop < 250_000:
                continue
            rows.append({
                "id": int(p[0]), "name": p[1], "ascii": p[2], "lat": float(p[4]),
                "lon": float(p[5]), "country": p[8], "tz": p[17], "pop": pop,
            })
    rows.sort(key=lambda r: -r["pop"])
    rows = rows[:1100]
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
    FA_OUT.write_text(json.dumps(FA, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE {len(rows)} cities -> {OUT}")


if __name__ == "__main__":
    build()
