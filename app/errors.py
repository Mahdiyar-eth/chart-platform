"""G5 (master-spec §169/170) — user-facing error taxonomy.

Every error surfaced to the user carries a stable code `ZAY-<DOMAIN>-<NNN>`
so support can locate the root cause from a single code (RUNBOOK §taxonomy).
The detail message stays Persian, friendly and specific — never a stack
trace. Codes are also the contract for the frontend error handling.
"""

ZAY_ERRORS: dict[str, dict] = {
    # AUTH
    "ZAY-AUTH-001": {"detail": "کد تأیید منقضی شده یا درست نیست؛ دوباره درخواست بده."},
    "ZAY-AUTH-002": {"detail": "تلاش بیش از حد؛ چند دقیقه بعد دوباره امتحان کن."},
    "ZAY-AUTH-003": {"detail": "نشست منقضی شده؛ دوباره وارد شو."},
    "ZAY-AUTH-004": {"detail": "ارسال پیامک موقتاً در دسترس نیست؛ کمی بعد دوباره تلاش کن."},
    # PAYMENT
    "ZAY-PAY-001": {"detail": "ساخت سفارش ناموفق بود؛ دوباره تلاش کن."},
    "ZAY-PAY-002": {"detail": "تأیید پرداخت با درگاه ناموفق بود؛ دوباره تلاش کن."},
    "ZAY-PAY-003": {"detail": "پرداخت نامعتبر است؛ برای پیگیری با پشتیبانی تماس بگیر."},
    "ZAY-PAY-004": {"detail": "کد تخفیف نامعتبر یا منقضی است."},
    # REPORT
    "ZAY-REPORT-001": {"detail": "تولید گزارش با خطا مواجه شد؛ دوباره تلاش میکنیم."},
    "ZAY-REPORT-002": {"detail": "گزارش هنوز در صف تولید است؛ کمی صبر کن."},
    "ZAY-REPORT-003": {"detail": "این گزارش متعلق به حساب تو نیست."},
    # AI
    "ZAY-AI-001": {"detail": "سرویس هوش مصنوعی فعلاً در دسترس نیست؛ دوباره تلاش کن."},
    "ZAY-AI-002": {"detail": "سهمیه پرسش امروز تمام شده."},
    # PUSH / SMS / STORAGE
    "ZAY-PUSH-001": {"detail": "اشتراک اعلان نامعتبر است؛ دوباره فعالش کن."},
    "ZAY-SMS-001": {"detail": "ارسال پیامک ناموفق بود؛ کمی بعد دوباره تلاش کن."},
    "ZAY-R2-001": {"detail": "دریافت فایل ناموفق بود؛ دوباره تلاش کن."},
    # INFRA
    "ZAY-DB-001": {"detail": "خطای موقت سرویس؛ دوباره تلاش کن."},
    "ZAY-FRONT-001": {"detail": "خطای پیشبینینشده؛ دوباره تلاش کن."},
}


def err(code: str, status: int = 400) -> dict:
    """HTTPException kwargs for the given code (fail-safe fallback text)."""
    entry = ZAY_ERRORS.get(code, ZAY_ERRORS["ZAY-FRONT-001"])
    return {"status_code": status, "detail": f"[{code}] {entry['detail']}"}
