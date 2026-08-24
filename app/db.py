"""DB session + init (Postgres). For tests: override engine with temp SQLite."""
import os

from sqlalchemy import create_engine, text
from sqlmodel import Session, SQLModel

from app.env import IS_PROD

_DEV_DEFAULT = "postgresql://chart_app:***@127.0.0.1:5432/chart_platform"
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    if IS_PROD:
        raise RuntimeError("DATABASE_URL is required in production (APP_ENV=prod|production)")
    DATABASE_URL = _DEV_DEFAULT

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def init_db() -> None:
    # import models so they register on metadata
    import app.models  # noqa: F401
    # audit P1 (round 3): production schema is Alembic-managed ONLY — create_all
    # would silently ignore drift. It runs only when explicitly enabled
    # (tests / fresh dev DBs), never on a normal production boot.
    if os.getenv("CREATE_ALL_ON_BOOT", "0") == "1":
        # R4/W5: ensure the pgvector extension exists before create_all (models
        # use VECTOR(384)). Idempotent + guarded: in CI the service POSTGRES_USER
        # is a superuser so this succeeds; locally it's a no-op if already present.
        # Never raise on privilege failure — the drift gate/migrations own DDL.
        try:
            with engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:  # noqa: BLE001 — best-effort; schema may already be ready
            pass
        SQLModel.metadata.create_all(engine)
    seed_plans()
    seed_credit_prices()


def seed_plans() -> None:
    """Idempotent plan catalog (plan v3.0 §12 — prices in toman; price_rial = ×10)."""
    from sqlmodel import select
    from app.models import Plan

    catalog: list[dict] = [
        dict(key="basic", name_fa="پایه", subtitle_fa="آشنایی اولیه با چارت تولد — برای شروع شناخت", price_toman=149_000,
             features=["چارت تولد تعاملی + SVG اختصاصی", "سه‌گانه‌ی اصلی (خورشید، ماه، طالع) با تفسیر",
                       "۵ بخش اصلی گزارش (شخصیت، ذهن، احساسات، رابطه، مسیر)",
                       "پیش‌نمایش رایگان قبل از خرید", "دانلود PDF"], sort=1),
        dict(key="full", name_fa="کامل", subtitle_fa="گزارش کامل ۱۳ بخشی با شواهد نجومی — پرفروش‌ترین", price_toman=349_000,
             features=["همه‌ی امکانات پلن پایه", "گزارش کامل هر ۱۳ حوزه‌ی زندگی (شخصیت، عشق، شغل، خانواده، مالی، سلامت و…)",
                       "تحلیل کامل جنبه‌ها و خانه‌ها", "هر بینش با شاهد نجومی (کدام سیاره، کدام خانه، کدام زاویه)",
                       "دانلود PDF ۲۵+ صفحه + Word قابل ویرایش", "نمودارهای SVG اختصاصی"], sort=2),
        dict(key="gold", name_fa="طلایی", subtitle_fa="شناخت عمیق + گفت‌وگوی شخصی با هوش مصنوعی + ترانزیت", price_toman=699_000,
             features=["همه‌ی امکانات پلن کامل", "گفت‌وگو با هوش مصنوعی درباره‌ی چارت (۵ سوال در روز)",
                       "فصل فرهنگی-اسلامی", "نقشه‌ی گذرهای ۴ ماه آینده نسبت به چارت",
                       "اولویت در صف تولید گزارش", "به‌روزرسانی‌های آینده رایگان"], sort=3),
        dict(key="synastry", name_fa="سیناستری", subtitle_fa="سنجش سازگاری دو چارت — برای رابطه، ازدواج و شراکت", price_toman=499_000,
             features=["نمره‌ی سازگاری ۴ حوزه‌ای (عشق، ذهن، کار، معنا)",
                       "۲۵+ ارتباط سیاره‌ای میان دو چارت",
                       "تفسیر اختصاصی و عمیق رابطه", "پیش‌نمایش رایگان نمره‌ی کلی"],
             sort=4),
        dict(key="credit3", name_fa="۳ اعتبار", subtitle_fa="سه کاوش خودشناسی", price_toman=180_000,
             credits_grant=3, features=["هر کاوش = ۱ اعتبار", "بدون تاریخ انقضا"],
             sort=5),
        dict(key="credit6", name_fa="۶ اعتبار", subtitle_fa="شش کاوش خودشناسی", price_toman=330_000,
             credits_grant=6, features=["ارزش ۲۰٪ بیشتر از پک ۳تایی", "بدون تاریخ انقضا"],
             sort=6),
        dict(key="credit12", name_fa="۱۲ اعتبار", subtitle_fa="دوازده کاوش خودشناسی", price_toman=600_000,
             credits_grant=12, features=["بهترین ارزش", "بدون تاریخ انقضا"],
             sort=7),
        dict(key="monthly", name_fa="اشتراک ماهانه", subtitle_fa="همراه ماهانه‌ی زایچه — برای دنبال‌کنندگان آسمان", price_toman=99_000,
             features=["نگاهی به آسمان امروز (Today) — هر روز", "تأمل هفتگی کوتاه در ربات و سایت",
                       "اعلان گذرهای مهم سیاره‌ای", "۵ اعتبار کاوش در ماه"],
             sort=5),
        dict(key="yearly", name_fa="اشتراک سالانه", subtitle_fa="همراه سالانه — دو ماه رایگان نسبت به ماهانه", price_toman=890_000,
             features=["همه‌ی امکانات اشتراک ماهانه", "معادل ۱۰ ماه برای ۱۲ ماه (دو ماه رایگان)",
                       "۵ اعتبار کاوش در ماه", "اولویت در صف تولید گزارش"],
             sort=8),
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
    # §13 — launch coupon LANCH20: 20% off the FIRST deep report, 1 use/phone
    # F-11 (opus-audit verified): the old code used `s` AFTER its `with Session`
    # block closed — SQLAlchemy raised on the closed session and the exception
    # was swallowed, so the coupon silently NEVER seeded. Use a fresh session.
    from app.models import Coupon
    with Session(engine) as s2:
        c = s2.exec(select(Coupon).where(Coupon.code == "LANCH20")).first()
        if not c:
            # atomic insert — two startup workers may race here
            from sqlalchemy import text as _text
            try:
                s2.exec(_text(
                    "INSERT INTO coupons (id, code, percent, max_uses, used_count, "
                    "active, report_only, created_at) VALUES "
                    "(gen_random_uuid()::text, 'LANCH20', 20, 10000, 0, true, true, now()) "
                    "ON CONFLICT (code) DO NOTHING"))
                s2.commit()
            except Exception:  # noqa: BLE001 — another worker won the race
                s2.rollback()




def seed_credit_prices() -> None:
    """A1 — idempotent credit-price catalog (HERMES-PLAN-v1 section 3.2).
    Unit-of-money = credit; admin-editable (never hard-coded in gates)."""
    from sqlmodel import select
    from app.models import CreditPrice

    catalog: list[dict] = [
        # MASTER W4 (§6): result-oriented names — the product is named by the
        # sentence in the user's head, not by astrological jargon.
        dict(action_key="explore_card",  title_fa="یک سؤال، یک جواب",                            credits=1),
        dict(action_key="report_basic",  title_fa="آشنایی (۵ بخش) — شروعِ سریع",                  credits=3),
        dict(action_key="report_full",   title_fa="شناخت کامل (۱۳ بخش)",                          credits=7),
        dict(action_key="report_gold",   title_fa="شناخت + همراهی (۱۳بخش + چت ۳۰روزه + ۱۲ماهه)",   credits=14),
        dict(action_key="synastry_full", title_fa="سازگاری دو نفر — ما به هم می‌خوریم؟",           credits=10),
        dict(action_key="transit_3m",    title_fa="۳ ماه آیندهٔ من",                              credits=2),
        dict(action_key="transit_12m",   title_fa="۱۲ ماه آیندهٔ من",                             credits=5),
        dict(action_key="rectify",       title_fa="ساعت تولدم را نمی‌دانم",                       credits=2, active=False),  # Z8: free (Y15), keep row inactive for correct admin financial report
        dict(action_key="chat_pack_20",  title_fa="از چارتت بپرس — ۲۰ پیام (۳۰ روزه)",             credits=2),
        dict(action_key="report_audio",  title_fa="گزارشت را گوش کن (نسخهٔ صوتی)",                 credits=1),
    ]
    with Session(engine) as s:
        for item in catalog:
            existing = s.exec(select(CreditPrice).where(
                CreditPrice.action_key == item["action_key"])).first()
            if existing:
                existing.title_fa = item["title_fa"]
                existing.credits = item["credits"]
                existing.active = item.get("active", True)  # Z8: honor inactive (rectify)
                s.add(existing)
            else:
                s.add(CreditPrice(**item))
        s.commit()

def get_session():
    with Session(engine) as s:
        yield s
