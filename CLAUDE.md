# chart-platform (زایچه) — Project Context

FastAPI + PostgreSQL + Jinja2 astrology / natal-chart web app. Prod: https://chart.negar.io (systemd → 127.0.0.1:8767).

## Architecture
- `app/main.py` — FastAPI app + routes (138 routes / 127 API). Auth, reports, synastry, transit, explore, chat, today, content, share, payment.
- `app/astrology/` — **engine (natal chart math + transits) = GOLDEN, DO NOT MODIFY**; `golden_data.py` + `tests/test_golden_charts.py` = correctness reference.
- `app/explore/` — credit-gated self-knowledge cards (10) — atomic credit spend at `service.py:214-258`.
- `app/report/` — report generator (basic/full/gold) + `qa.py` (hallucination/QA gate).
- `app/chat/` — chart chat (gold/monthly plan, daily limit).
- `app/today/` — آسمان امروز / هفته / transit.
- `app/payment/` — Zarinpal + Order + coupon (atomic reservation, refund cycle).
- `app/secret_store.py` — encrypted secret catalog (`SECRETS_MASTER_KEY`).
- `app/storage.py` — Cloudflare R2 object storage (presigned).
- `app/security.py` — rate limiting (Redis in prod; memory only in dev/QA).
- `app/content/`, `app/seo/` — CMS articles + sitemap + SEO.
- `app/bots/` — Telegram (`@Voice_clone_real_bot`) + Bale (`@VoieAiToolsbot`).
- `app/models*.py`, `alembic/` — models + migrations (29).

## Common commands
- Tests: `venv/bin/python -m pytest tests/ -q`
- Full CI gate (coverage>=60, alembic drift, ruff, bandit, pip-audit, secret + brand-language scans): `bash scripts/ci.sh`
- Alembic: `venv/bin/alembic revision --autogenerate -m "..."` then `venv/bin/alembic upgrade head` then `venv/bin/alembic check`
- QA instance (isolated): uvicorn `127.0.0.1:8798`, DB `chart_platform_qa`, env `OTP_DEV_MODE=true ENRICH_INSIGHTS=0 RATE_LIMIT_BACKEND=memory CREATE_ALL_ON_BOOT=1`
- Prod restart (Jinja cached until restart — REQUIRED after any template/UI change): `systemctl restart chart-web chart-worker`

## Red lines (never violate)
1. Astronomical engine (`app/astrology/engine.py`), `app/astrology/golden_data.py`, `tests/test_golden_charts.py` — golden-tested to 1′ arc, do not touch.
2. Never delete/skip an existing test to make CI green (563 baseline must stay green or grow).
3. Never change existing تُمن prices without owner approval.
4. Never commit/write secrets or real keys in code/docs (CI secret-scan fails).
5. Never use «فال / پیش‌بینی / طالع‌بینی» promotional language in content (CI brand-language scan fails).

## Working rules (from HERMES-PLAN-v1)
- **One task (one `[ID]`) per commit**, each commit `[<ID>] <summary>`.
- **Test-first**: write a RED test → run (show red) → code → run (show green) → `bash scripts/ci.sh` green.
- Keep each diff < ~250 lines; split larger tasks and note the split in the report.
- If a task needs a real external key/account (Zarinpal merchant, Kavenegar SMS, FCM, domain) → mark **BLOCKED**, ask the owner, never invent.
- **Cost control**: never fire paid LLM endpoints in tests/validation. Cover validation/404/history/read-only only. Enrichment: `ENRICH_INSIGHTS=0`.

## Docs / plans
- `docs/plans/` — execution plans (`HERMES-PLAN-v1.md` = current). `docs/reports/` — Hermes round reports (`HERMES-ROUND-<n>.md`, commit+push to the working branch). `docs/audit/opus46/` — audit plan/review. `docs/workflow/` — workflow.

## Key env vars
`APP_ENV` (dev|prod; both `prod` and `production` activate prod), `DATABASE_URL`, `AUTH_SECRET`, `ADMIN_SECRET`, `SECRETS_MASTER_KEY`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `OTP_DEV_MODE`, `ENRICH_INSIGHTS`, `CREATE_ALL_ON_BOOT`, `RATE_LIMIT_BACKEND`. `.env` at `/root/chart-platform/.env` (never commit).
