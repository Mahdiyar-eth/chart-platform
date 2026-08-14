"""Build final cities_ir seed: merge Persian-names dataset (337 cities) with
simplemaps precise coordinates (156 cities). Precision wins for the same city.

Output: app/astrology/data/cities_seed.json  (deterministic, auditable)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.astrology.cities_ir import load_cities  # noqa: E402

ROOT = Path(__file__).parent.parent
FA_DATA = ROOT / "app" / "astrology" / "data" / "iran_cities_with_coordinates.json"
SIMPLEMAPS = Path("/tmp/ir_cities.csv")
OUT = ROOT / "app" / "astrology" / "data" / "cities_seed.json"

# precise coords from simplemaps (city transliterated → Persian name map)
# simplemaps uses English names; Persian from FA dataset by best-effort mapping below
SIMPLE_TO_FA = {
    # diacritic variants (simplemaps uses ā ī ū etc.)
    "Shīrāz": "شیراز", "Tabrīz": "تبریز", "Kermānshāh": "کرمانشاه",
    "Kermān": "کرمان", "Sārī": "ساری", "Qazvīn": "قزوین", "Hamadān": "همدان",
    "Eşfahān": "اصفهان", "Bandar ‘Abbās": "بندرعباس", "Bandar ʻAbbās": "بندرعباس",
    "Ahvāz": "اهواز", "Gorgān": "گرگان", "Arāk": "اراک", "Ardabīl": "اردبیل",
    "Orūmīyeh": "ارومیه", "Zāhedān": "زاهدان", "Āzādshahr": "آزادشهر",
    "Torbat-e Ḩeydarīyeh": "تربت حیدریه", "Neyshābūr": "نیشابور", "Kāshān": "کاشان",
    "Būshehr": "بوشهر", "Īlām": "ایلام", "Bojnūrd": "بجنورد", "Bīrjand": "بیرجند",
    "Sanandaj": "سنندج", "Khorramābād": "خرم‌آباد", "Yāsūj": "یاسوج",
    "Semnān": "سمنان", "Marāgheh": "مراغه", "Sabzevār": "سبزوار",
    "Rafsanjān": "رفسنجان", "Sīrjān": "سیرجان", "Jīroft": "جیرفت",
    "Marv Dasht": "مرودشت", "Īzeh": "ایذه", "Shūshtar": "شوشتر",
    "Abādān": "آبادان", "Khorramshahr": "خرمشهر", "Dezfūl": "دزفول",
    "Mashhad": "مشهد", "Tehran": "تهران", "Isfahan": "اصفهان", "Karaj": "کرج",
    "Qom": "قم", "Ahvaz": "اهواز", "Rasht": "رشت", "Yazd": "یزد",
    "Kerman": "کرمان", "Hamadan": "همدان", "Urmia": "ارومیه", "Zahedan": "زاهدان",
    "Ardabil": "اردبیل", "Bandar Abbas": "بندرعباس", "Arak": "اراک",
    "Eslamshahr": "اسلامشهر", "Zanjan": "زنجان",
    "Qazvin": "قزوین", "Khorramabad": "خرم‌آباد", "Gorgan": "گرگان", "Sari": "ساری",
    "Kashan": "کاشان", "Shahriar": "شهریار", "Dezful": "دزفول", "Borujerd": "بروجرد",
    "Ilam": "ایلام", "Bojnurd": "بجنورد", "Birjand": "بیرجند", "Yasuj": "یاسوج",
    "Semnan": "سمنان", "Bushehr": "بوشهر", "Bam": "بم", "Bandar-e Lengeh": "بندرلنگه",
    "Kish": "کیش", "Qeshm": "قشم", "Chabahar": "چابهار", "Maragheh": "مراغه",
    "Neyshabur": "نیشابور", "Sabzevar": "سبزوار", "Torbat-e Heydarieh": "تربت حیدریه",
    "Kashmar": "کاشمر", "Gonabad": "گناباد", "Rafsanjan": "رفسنجان",
    "Sirjan": "سیرجان", "Jiroft": "جیرفت", "Marvdasht": "مرودشت", "Fasa": "فسا",
    "Lar": "لار", "Kazeroon": "کازرون", "Abadan": "آبادان", "Shushtar": "شوشتر",
    "Andimeshk": "اندیمشک", "Masjed Soleyman": "مسجدسلیمان", "Izeh": "ایذه",
    "Shahrekord": "شهرکرد", "Falavarjan": "فلاورجان", "Khomeyni Shahr": "خمینی‌شهر",
    "Najafabad": "نجف‌آباد", "Shahin Shahr": "شاهین‌شهر", "Mobarakeh": "مبارکه",
    "Tonekabon": "تنکابن", "Amol": "آمل", "Babol": "بابل", "Babol Sar": "بابلسر",
    "Qaemshahr": "قائم‌شهر", "Behshahr": "بهشهر", "Neka": "نکا", "Chalus": "چالوس",
    "Nowshahr": "نوشهر", "Ramsar": "رامسر", "Lahijan": "لاهیجان", "Astara": "آستارا",
    "Anzali": "بندر انزلی", "Langarud": "لنگرود", "Talesh": "تالش", "Fuman": "فومن",
    "Sowme'eh Sara": "صومعه‌سرا", "Malayer": "ملایر", "Tuyserkan": "تویسرکان",
    "Nahavand": "نهاوند", "Asadabad": "اسدآباد", "Kangavar": "کنگاور", "Sonqor": "سنقر",
    "Marivan": "مریوان", "Saqqez": "سقز", "Baneh": "بانه", "Divandarreh": "دیواندره",
    "Piranshahr": "پیرانشهر", "Mahabad": "مهاباد", "Bukan": "بوکان", "Naqadeh": "نقده",
    "Shahindej": "شاهیندژ", "Takab": "تکاب", "Sardasht": "سردشت", "Khoy": "خوی",
    "Salmas": "سلماس", "Maku": "ماکو", "Chaldoran": "چالدران", "Poldasht": "پلدشت",
    "Showt": "شوط", "Parsabad": "پارس‌آباد", "Germi": "گرمی", "Meshgin Shahr": "مشگین‌شهر",
    "Khalkhal": "خلخال", "Namin": "نمین", "Sarab": "سراب", "Mianeh": "میانه",
    "Bonab": "بناب", "Ajab Shir": "عجب‌شیر", "Azarshahr": "آذرشهر", "Sahand": "سهند",
    "Osku": "اسکو", "Heris": "هریس", "Varzaqan": "ورزقان", "Kaleybar": "کلیبر",
    "Jolfa": "جلفا", "Marand": "مرند", "Shabestar": "شبستر", "Zarrin Shahr": "زرین‌شهر",
    "Daran": "داران", "Golpayegan": "گلپایگان", "Natanz": "نطنز", "Ardestan": "اردستان",
    "Meybod": "میبد", "Ardakan": "اردکان", "Taft": "تفت", "Mehriz": "مهریز",
    "Ashkezar": "اشکذر", "Bafq": "بافق", "Shahreza": "شهرضا", "Abadeh": "آباده",
    "Eqlid": "اقلید", "Neyriz": "نی‌ریز", "Darab": "داراب", "Jahrom": "جهرم",
    "Firuzabad": "فیروزآباد", "Zarqan": "زرقان", "Kavar": "کوار", "Sepidan": "سپیدان",
    "Arsanjan": "ارسنجان", "Estahban": "استهبان", "Lamerd": "لامرد", "Mohr": "مهر",
    "Khafr": "خفر", "Sarvestan": "سروستان", "Gonbad-e Kavus": "گنبد کاووس",
    "Minudasht": "مینودشت", "Kalaleh": "کلاله", "Aliabad": "علی‌آباد",
    "Bandar Torkaman": "بندر ترکمن", "Aq Qala": "آق‌قلا", "Kordkuy": "کردکوی",
    "Bandar-e Gaz": "بندر گز", "Galugah": "گلوگاه", "Fereydunkenar": "فریدونکنار",
    "Mahmudabad": "محمودآباد", "Nur": "نور", "Royan": "رویان", "Kojur": "کجور",
    "Shahre Kord": "شهرکرد", "Farrokhshahr": "فرخ‌شهر", "Hafshejan": "هفشجان",
    "Ben": "بن", "Saman": "سامان", "Borujen": "بروجن", "Lordan": "لردگان",
    "Farsan": "فارسان", "Ardal": "اردل", "Naghan": "ناغان", "Kiar": "کیار",
    "Gahru": "گهرو", "Sudejan": "سودجان", "Astaneh-ye Ashrafiyeh": "آستانه اشرفیه",
    "Rudsar": "رودسر", "Amlash": "املش", "Rezvanshahr": "رضوانشهر", "Masal": "ماسال",
    "Shaft": "شفت", "Kuchesfahan": "کوچصفهان", "Khvoresh Rostam": "خورش رستم",
    "Khoshk-e Bijar": "خشکبیجار",
}


def _norm(s: str) -> str:
    """Normalize Arabic yeh/keheh to Persian variants + ZWNJ handling."""
    return s.replace("\u064a", "\u06cc").replace("\u0643", "\u06a9").strip()


def main() -> None:
    fa_cities = load_cities()

    # read simplemaps
    precise: dict[str, dict] = {}
    if SIMPLEMAPS.exists():
        with open(SIMPLEMAPS, newline="") as f:
            for row in csv.DictReader(f):
                fa = SIMPLE_TO_FA.get(row["city"])
                if fa:
                    precise[_norm(fa)] = {"lat": float(row["lat"]), "lon": float(row["lng"])}

    out = []
    for c in fa_cities:
        name = c["city_fa"]
        p = precise.get(_norm(name))
        out.append({
            "city_fa": name,
            "province_fa": c["province_fa"],
            "lat": p["lat"] if p else c["lat"],
            "lon": p["lon"] if p else c["lon"],
            "precise": bool(p),
        })

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"seed written: {len(out)} cities → {OUT}")
    teh = next(c for c in out if c["city_fa"] == "تهران")
    print("Tehran:", teh)
    print("precise-coord cities:", sum(1 for c in out if c["precise"]))


if __name__ == "__main__":
    main()
