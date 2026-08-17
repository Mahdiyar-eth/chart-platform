# AUDIT REPORT — CHUNK 5 (tests + deploy)

## FINDINGS

---

### 1. [SEV P0] `tests/conftest.py:12` — Test DATABASE_URL points at a real PostgreSQL, not "temp SQLite per run" as docstring claims

**Evidence:**
```python
"""Pytest fixtures — temp SQLite per run (NEVER prod Postgres).
...
"""
os.environ["DATABASE_URL"] = "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test"
```

The docstring says "temp SQLite per run (NEVER prod Postgres)" but the actual `DATABASE_URL` is a PostgreSQL connection string with hardcoded credentials. This is misleading documentation. More critically, if CI runs without a local Postgres, tests silently fail or — worse — if someone copies this pattern and the env var leaks, the credentials `chart_test:chart_test_pw` are exposed.

**Fix:** Either (a) update the docstring to accurately describe the PostgreSQL test DB, or (b) actually use a temp SQLite (`sqlite:///...`). Also, consider reading credentials from env vars rather than hardcoding them.

---

### 2. [SEV P1] `tests/conftest.py:12` — Hardcoded database password in source code

**Evidence:**
```python
os.environ["DATABASE_URL"] = "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test"
```

This password is repeated in `test_account_delete_rag.py:10`, `test_astrology_edge_a3.py:17`, and several other files. Even for a test DB, hardcoded credentials in version-controlled source are a security smell — especially if the test DB shares a host with production.

**Fix:** Use an env var with a fallback: `os.environ.setdefault("DATABASE_URL", "postgresql://...")` (some files already do this inconsistently). Better: read from a `.env.test` file excluded from VCS.

---

### 3. [SEV P1] `tests/conftest.py:44-50` — `_FakeZarinpal.request()` references `fake_authority` before it's defined

**Evidence:**
```python
class _FakeZarinpal:
    ...
    def request(self, amount_rial, callback_url, description, meta=None):
        return f"S{fake_authority(16)}", "https://sandbox.zarinpal.com/pg/StartPay/S-fake"
```

`fake_authority` is defined at line 53, *after* the class. Python closures resolve names at call time, not definition time, so this works at runtime. However, the second element of the returned tuple is a hardcoded `S-fake` string that doesn't match the dynamically generated authority in the first element. This means the "payment URL" returned by the fake never contains the actual authority — any test that parses the URL to extract the authority will get the wrong value.

**Fix:** Return a consistent tuple:
```python
auth = f"S{fake_authority(16)}"
return auth, f"https://sandbox.zarinpal.com/pg/StartPay/{auth}"
```

---

### 4. [SEV P2] `tests/test_account_delete_rag.py:8-11` — Redundant env var setting that may override conftest

**Evidence:**
```python
os.environ["APP_ENV"] = "development"
os.environ.setdefault("DATABASE_URL", "postgresql://chart_test:chart_test_pw@127.0.0.1:5432/chart_platform_test")
```

`conftest.py` already sets these. Using `os.environ["APP_ENV"] = "development"` (hard set, not `setdefault`) means if a CI matrix intentionally sets `APP_ENV` to something else, this file overrides it. Multiple test files repeat this pattern (`test_astrology_edge_a3.py`, `test_explore_catalog_p3.py`, `test_llm_cost_metering.py`, etc.).

**Fix:** Remove per-file env overrides; rely on `conftest.py` which loads first. If a file truly needs a different env, document why.

---

### 5. [SEV P1] `tests/test_astrology_edge_a3.py:26` — `swe.set_ephe_path` hardcoded to `/usr/share/swisseph`

**Evidence:**
```python
swe.set_ephe_path("/usr/share/swisseph")
```

If the ephemeris files aren't at this path (macOS, different Linux distro, Docker image without them), the cross-check tests silently compute with lower-precision Moshier ephemeris instead of Swiss Ephemeris, making the 0.1° tolerance assertions potentially meaningless. No error is raised — `swe` falls back silently.

**Fix:** Assert the path exists or use an env var: `swe.set_ephe_path(os.environ.get("SWE_EPHE_PATH", "/usr/share/swisseph"))`. Add a guard: `assert Path("/usr/share/swisseph").exists(), "ephemeris files missing"`.

---

### 6. [SEV P2] `tests/test_astrology_edge_a3.py:38-39` — Cross-check uses `FLG_MOSEPH` alongside `FLG_SWIEPH`

**Evidence:**
```python
flag = swe.FLG_SWIEPH | swe.FLG_MOSEPH
```

Combining `FLG_SWIEPH` and `FLG_MOSEPH` is contradictory — they select different ephemeris backends. In practice, `FLG_SWIEPH` takes precedence if the files are found, but this is confusing and fragile. If the Swiss Ephemeris files are missing, `FLG_MOSEPH` kicks in silently, and the "cross-check" is comparing Moshier vs. Moshier (or Moshier vs. Swiss), not a true independent verification.

**Fix:** Use only `swe.FLG_SWIEPH`:
```python
flag = swe.FLG_SWIEPH
```

---

### 7. [SEV P2] `tests/test_bots.py:12-16` — `FakeBotAPI.calls` is a mutable class attribute shared across tests

**Evidence:**
```python
class FakeBotAPI:
    calls: list[dict] = []

    @classmethod
    async def install(cls, monkeypatch):
        cls.calls = []
```

`calls` is a class-level mutable list. While `install()` resets it, if any test forgets to call `install()` or if tests run in parallel, state leaks between tests. This is a classic Python mutable-default-on-class bug.

**Fix:** Always initialize in `install()` (which it does), but also make the class attribute annotation-only: `calls: list[dict]` without `= []`, and set it in `install()`.

---

### 8. [SEV P1] `tests/test_content_sweep_v4.py:22-31` — Hardcoded absolute path `/root/chart-platform`

**Evidence:**
```python
ROOT = Path("/root/chart-platform")
```

This test will fail on any machine where the repo isn't cloned to `/root/chart-platform`. Every other test file uses `Path(__file__).resolve().parent.parent` for the project root.

**Fix:**
```python
ROOT = Path(__file__).resolve().parent.parent
```

---

### 9. [SEV P2] `tests/test_coupon_atomic.py:76-82` — Test creates raw DB orders bypassing the reservation pattern, then asserts `used_count == 0`

**Evidence:**
```python
# legacy raw-DB order (created before reservation): verify must still mark
# it PAID — a paying user never gets a failed order over coupon capacity
r1 = _verify(c, a1)
assert r1.status_code == 303  # paid → redirect to result
...
assert used[0] == 0  # never reserved → never consumed
```

The test intentionally bypasses the reservation pattern (raw INSERT) and then asserts `used_count == 0`. This tests a legacy edge case but the comment "never reserved → never consumed" means the coupon's `used_count` is never incremented for this order — the coupon slot is effectively leaked (used but not counted). If this is intentional legacy behavior, it should be documented more prominently; if not, it's a business logic bug in the verify path.

**Fix:** Clarify whether verify should increment `used_count` for legacy orders. If yes, fix the verify path; if no, add a comment explaining the tradeoff.

---

### 10. [SEV P0] `tests/test_data_lifecycle.py:87-88` — Privacy test asserts `"OpenAI" not in r.text` — brittle and may mask a real provider leak

**Evidence:**
```python
assert "OpenAI" not in r.text
assert "DeepSeek" in r.text and "OpenCode" in r.text
```

If the privacy page ever mentions "OpenAI" in a *negative* context (e.g., "ما از OpenAI استفاده نمیکنیم" — "We do not use OpenAI"), this test fails. More importantly, if the app actually starts using OpenAI as a fallback provider, this test would correctly catch it — but the assertion is too blunt. The real concern is whether the privacy page accurately lists *all* providers.

**Fix:** This is acceptable as a canary test, but add a comment explaining the intent. Consider checking for a structured provider list rather than substring matching.

---

### 11. [SEV P2] `tests/test_cms_p04.py:50-67` — `_req()` builds a fake `Request` with manual cookie header but `_State` class doesn't match real middleware

**Evidence:**
```python
class _State:
    is_admin = admin
    def get(self, k, d=None):
        return d

scope["headers"] = [(b"cookie", f"chart_admin={ck}".encode())]
r.scope["state"] = _State()
```

The test manually injects `is_admin` into the request state, bypassing the real admin authentication middleware. This means the test doesn't actually verify that the cookie-based admin auth works — it only tests that the route checks `state.is_admin`. If the middleware changes how it sets this flag, these tests would still pass while production breaks.

**Fix:** Use `TestClient` with real cookies (as `test_cms_golden_e2e_r1.py` does) for at least one integration test per route.

---

### 12. [SEV P2] `tests/test_chat_quota_atomic.py:73-95` — Concurrent test uses `threading.Barrier(10)` with `TestClient` which is not thread-safe

**Evidence:**
```python
barrier = threading.Barrier(10)
def worker():
    tc = TestClient(main_mod.app)  # TestClient is not thread-safe
    tc.cookies.update(ck)
    barrier.wait()
    r = tc.post("/api/chat", ...)
```

The comment acknowledges `TestClient is not thread-safe`, and each thread creates its own instance, which is the right mitigation. However, the underlying ASGI app may have shared state (DB sessions, Redis connections) that isn't thread-safe. The test could produce false positives or flaky results. The `BrokenBarrierError` is caught in the broad `except Exception`, masking real failures.

**Fix:** This is acceptable for testing atomicity semantics, but add a note that flakiness here may indicate real concurrency bugs, not test infrastructure issues.

---

### 13. [SEV P1] `tests/test_env_prod.py:26-27` — Production boot test uses `sqlite:////tmp/env_prod_test.db` which doesn't test real Postgres behavior

**Evidence:**
```python
env["DATABASE_URL"] = "sqlite:////tmp/env_prod_test.db" if secrets_ok else ""
```

The test verifies that the app *boots* in production mode, but uses SQLite instead of Postgres. If the app has Postgres-specific SQL (e.g., `pgvector`, `RETURNING`, `FOR UPDATE`), this test would pass while production fails. The `CREATE_ALL_ON_BOOT` flag with SQLite may also create a different schema than Alembic migrations on Postgres.

**Fix:** For boot-only tests this is acceptable (testing env validation, not DB schema). Document this limitation.

---

### 14. [SEV P2] `tests/test_explore_catalog_p3.py:60-61` — `GOOD_JSON` insights contain hardcoded Persian text that must match QA rules

**Evidence:**
```python
GOOD_JSON = json.dumps({
    "intro": "پاسخ کلی این است که ...",
    "insights": [{"insight": "خورشید در برج اسد نشان میدهد که ...", ...}]
})
```

If the QA rules (banned words, minimum length, required fields) change, this fixture must be updated manually. The `test_generate_retries_on_banned_words_then_recovers` test modifies `GOOD_JSON` to inject a banned phrase — if the banned word list changes, this test silently stops testing the right thing.

**Fix:** Add a comment linking to the QA rules file. Consider generating `GOOD_JSON` programmatically from the rules.

---

### 15. [SEV P1] `tests/test_owasp_extra_s9.py:168-178` — `test_docs_disabled_in_prod_env` spawns a subprocess with `os.environ['DATABASE_URL']` which may contain production credentials

**Evidence:**
```python
code = (
    "import os; os.environ['APP_ENV']='prod'\n"
    f"os.environ['DATABASE_URL']={os.environ['DATABASE_URL']!r}\n"
    ...
)
r = subprocess.run([sys.executable, "-c", code], ...)
```

The test passes the current process's `DATABASE_URL` (which contains the test DB password) into a subprocess via a Python `-c` command string. If process listing is visible to other users (`ps aux`), the credentials are exposed on the command line.

**Fix:** Pass credentials via environment variables to the subprocess (which `subprocess.run(env=...)` already supports) rather than embedding them in the `-c` code string. Actually, the `env` dict is already being constructed in `test_env_prod.py` — use the same pattern here.

---

### 16. [SEV P2] `tests/test_human_eval_h18.py:25-33` — Test asserts `>= 20` eval charts and `== 13` domain prompts but doesn't validate chart content deeply

**Evidence:**
```python
assert len(charts) >= 20, "plan requires 20 eval charts"
...
assert len(files) == 13, f"{d.name} should have 13 domain prompts"
```

This is a structural test only — it verifies file counts but not that the charts are valid or that prompts match the current domain list. If a domain is added or removed, the hardcoded `13` will break or silently pass.

**Fix:** Import `DOMAINS` from `app.report.rules` and assert `len(files) == len(DOMAINS)`.

---

### 17. [SEV P2] `tests/test_moon_confidence.py:39-42` — Parametrized boundary days are hardcoded for July 2024; may not be stable across ephemeris versions

**Evidence:**
```python
@pytest.mark.parametrize("day,expected", [
    (5, "medium"),   # moon crosses 90° (Gemini→Cancer) during 2024-07-05
    (25, "medium"),  # crosses Aries→Pisces boundary that day
    (2, "medium"),   # Taurus→Gemini boundary day
])
```

The comments claim specific sign boundaries on specific dates. If the ephemeris precision changes or the engine's noon-default shifts, these assertions may break. The test doesn't independently verify that the Moon actually crosses a boundary on these dates.

**Fix:** Add a cross-check: compute Moon longitude at 00:00 and 23:59 UTC for each date and verify the sign actually changes.

---

### 18. [SEV P2] `tests/test_llm_router.py` — File has no module docstring and no imports; relies on implicit conftest path insertion

**Evidence:**
```python
# ───────────────────── R.3 per-slot model override ─────────────────────
def test_pool_slot_model_override():
    """key@model pins ONE key to a model while others keep the pool default."""
    from app.core.llm import GoPoolProvider
```

The file starts with a comment, no docstring, no `sys.path` manipulation. It works because `conftest.py` inserts the parent into `sys.path`, but this is fragile and inconsistent with other test files.

**Fix:** Add `sys.path.insert(0, ...)` or rely on `conftest.py` consistently (document the convention).

---

### 19. [SEV P1] `tests/test_credit_packs_p6.py:100-101` — `test_grant_credits_unknown_pack_raises` uses bare `except` pattern that swallows unexpected errors

**Evidence:**
```python
try:
    with Session(engine) as s:
        grant_credits(s, s.get(Order, oid))
    raise AssertionError("expected ValueError")
except ValueError:
    pass
```

If `grant_credits` raises a *different* exception (e.g., `TypeError`, `IntegrityError`), the test fails with a confusing `AssertionError("expected ValueError")` instead of the actual error. The `finally` block restores state, which is good.

**Fix:** Use `pytest.raises(ValueError)`:
```python
with pytest.raises(ValueError):
    with Session(engine) as s:
        grant_credits(s, s.get(Order, oid))
```

---

### 20. [SEV P2] Multiple files — No test isolation for database state; tests depend on execution order

**Evidence:** Many tests (`test_chat_stream_sse.py`, `test_llm_cost_metering.py`, `test_credit_packs_p6.py`) create DB rows and clean them up in fixtures or finally blocks. If a test fails mid-way, cleanup doesn't run, leaving orphan rows that can cause subsequent tests to fail. The `test_llm_cost_metering.py` explicitly acknowledges this:
```python
# F-P1: this test reads GLOBAL 7d aggregates ... so any LLMRun left behind
# by earlier/heavier tests ... breaks the assertions.
# Purge ALL runs before seeding
```

**Fix:** Use database transactions with rollback per test (SQLAlchemy's `nested` transactions or a session-scoped fixture that rolls back after each test). This is a systemic issue across the test suite.

---

### 21. [SEV P2] `tests/test_ownership_r4.py` — File is truncated at line 113

**Evidence:**
```python
# ---------- A5: order creation -------
```

The file ends abruptly after the section header for A5 (order creation) tests. Either the chunk was cut or the tests are incomplete.

**Fix:** Verify the full file exists and contains the A5 order creation tests.

---

## VERDICT

**Not launch-blocking, but several P0/P1 issues require attention before production confidence is high.**

**Strengths:**
- Excellent coverage breadth: IDOR, OWASP, ownership, CSRF, rate limiting, budget gates, coupon atomicity, LLM circuit breakers, concurrent quota claims, account deletion cascades, astrology cross-checks, and content safety sweeps are all tested.
- The `_FakeZarinpal` autouse fixture correctly prevents real payment gateway calls.
- The `_bypass_rate_limit` autouse fixture prevents cross-test rate limit interference.
- Astrology golden tests with independent `swisseph` cross-checks are solid.
- The authorization matrix structural test (`test_authz_matrix.py`) is an excellent pattern.
- Chat prompt injection sandboxing test (`test_chat_prompt_structured.py:59-66`) correctly verifies policy is in system prompt, not user message.

**Critical fixes needed:**
1. **P0 Finding #1**: Fix the misleading docstring in `conftest.py` — it claims SQLite but uses Postgres. This is a trust/documentation issue.
2. **P1 Finding #2**: Extract hardcoded DB credentials to env vars.
3. **P1 Finding #3**: Fix `_FakeZarinpal.request()` return tuple inconsistency.
4. **P1 Finding #8**: Fix hardcoded `/root/chart-platform` path in `test_content_sweep_v4.py`.
5. **P1 Finding #15**: Don't embed `DATABASE_URL` in subprocess command strings.
6. **P1 Finding #19**: Use `pytest.raises` instead of try/except/AssertionError pattern.

**Systemic improvement needed:**
- Database test isolation via transaction rollback (Finding #20) would eliminate an entire class of flaky test failures.
- Consistent env var handling across test files (some use `setdefault`, some hard-set).