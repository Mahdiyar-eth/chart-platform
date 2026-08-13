"""DB session + init (Postgres). For tests: override engine with temp SQLite."""
import os

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

_DEV_DEFAULT = "postgresql://chart_app:CHANGE_ME@127.0.0.1:5432/chart_platform"
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    if os.getenv("APP_ENV", "dev") == "prod":
        raise RuntimeError("DATABASE_URL is required (set APP_ENV=prod)")
    DATABASE_URL = _DEV_DEFAULT

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def init_db() -> None:
    # import models so they register on metadata
    import app.models  # noqa: F401
    SQLModel.metadata.create_all(engine)
    seed_plans()


def seed_plans() -> None:
    """Idempotent plan catalog (plan v3.0 §12 — prices in toman; price_rial = ×10)."""
    from sqlmodel import select
    from app.models import Plan

    catalog: list[dict] = [
        dict(key="basic", name_fa="پایه", subtitle_fa="شناخت سریع خودت", price_toman=149_000,
             features=["چارت تولد تعاملی + SVG", "سه‌گانه‌ی اصلی (خورشید، ماه، طالع)",
                       "۵ بخش اصلی گزارش", "دانلود PDF"], sort=1),
        dict(key="full", name_fa="کامل", subtitle_fa="گزارش عمیق شخصیت، رابطه و مسیر شغلی", price_toman=349_000,
             features=["همه‌ی امکانات پایه", "هر ۱۳ حوزه‌ی تفسیر با شواهد نجومی",
                       "گزارش PDF + Word", "نمودارهای SVG اختصاصی", "استعلام سیناستری"], sort=2),
        dict(key="gold", name_fa="طلایی", subtitle_fa="گزارش کامل + گفت‌وگوی شخصی + ترانزیت", price_toman=699_000,
             features=["همه‌ی امکانات کامل", "فصل فرهنگی-اسلامی", "نقشه‌ی گذرهای ۴ ماه آینده",
                       "هوش مصنوعی چت سوال‌پاسخ", "اولویت تولید"], sort=3),
        dict(key="synastry", name_fa="سیناستری", subtitle_fa="شناخت عمق رابطه و سازگاری", price_toman=499_000,
             features=["نمره‌ی سازگاری ۴ حوزه‌ای", "۲۵+ ارتباط سیاره‌ای", "تفسیر اختصاصی"],
             sort=4),
        dict(key="monthly", name_fa="اشتراک ماهانه", subtitle_fa="نگاهی به آسمان هفته", price_toman=399_000,
             features=["نگاهی به آسمان هفته (هر هفته، خودکار)", "تأمل هفتگی کوتاه در ربات و سایت", "تمدید خودکار ۳۰ روزه"],
             sort=5),
    ]
    with Session(engine) as s:
        for item in catalog:
            existing = s.exec(select(Plan).where(Plan.key == item["key"])).first()
            if existing:
                # only update display fields, never overwrite runtime price edits
                existing.name_fa = item["name_fa"]
                existing.subtitle_fa = item["subtitle_fa"]
                existing.features = item["features"]
                existing.sort = item["sort"]
                s.add(existing)
            else:
                s.add(Plan(**item))
        s.commit()


def get_session():
    with Session(engine) as s:
        yield s
