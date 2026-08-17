# AUDIT REPORT — Chunk 2: Report + Chat + Core LLM + Share

---

## FINDINGS

### 1. `asyncio.run()` inside sync `generate_sections` will crash if called from an existing event loop [SEV: critical, P0]

**File:** `app/report/generator.py:89`

**Evidence:**
```python
def await_complete(router, prompt: str, max_tokens: int):
    """Sync wrapper over the async LLMRouter (worker will be async later)."""
    import asyncio
    return asyncio.run(router.complete(prompt, max_tokens=max_tokens, temperature=0.6, json_mode=True))
```
`asyncio.run()` raises `RuntimeError` if called inside a running loop (e.g., from FastAPI, ARQ worker, or any async context). The same pattern appears in `chat/service.py:42`:
```python
res = asyncio.run(rtr.complete(prompt, system=CHAT_SYSTEM_PROMPT, ...))
```

**Fix:** Use `asyncio.get_event_loop().run_until_complete()` with loop detection, or better, make `generate_sections` async (the worker already uses `generate_sections_async`). For `chat_answer`, use `asyncio.run()` only when no loop is running, otherwise use `await`:
```python
try:
    loop = asyncio.get_running_loop()
    # Already in async context — caller should use the async variant
    raise RuntimeError("Use chat_stream or call from sync context")
except RuntimeError:
    res = asyncio.run(rtr.complete(...))
```

---

### 2. Data race on `metrics` dict in concurrent `generate_sections_async` [SEV: major, P1]

**File:** `app/report/worker.py:107-110`

**Evidence:**
```python
metrics = {"calls": 0, "retries": 0, "total_tokens": 0, "cost_usd": 0.0,
           "qa_failures": 0, "provider": set()}
# ...
async def _gen_one(domain, prompt, ctx_info):
    # ...
    metrics["calls"] += 1          # ← concurrent writes from gather()
    metrics["total_tokens"] += res.usage.total
    metrics["cost_usd"] += res.cost
    metrics["provider"].add(res.provider)
```
Multiple `_gen_one` coroutines run concurrently via `asyncio.gather()`. While CPython's GIL prevents memory corruption, `+=` on a dict value is NOT atomic (`LOAD_FAST` + `BINARY_ADD` + `STORE_SUBSCR`). Under `SECTION_CONC=4`, concurrent increments can lose updates, producing inaccurate cost/token counts.

**Fix:** Use an `asyncio.Lock` around metrics updates, or accumulate per-task and merge after `gather()`:
```python
task_metrics = []
async def _gen_one(...):
    local = {"calls": 0, "cost_usd": 0.0, ...}
    # ... update local ...
    task_metrics.append(local)
await asyncio.gather(...)
for m in task_metrics:
    metrics["calls"] += m["calls"]  # sequential merge
```

---

### 3. `OmniProvider.complete()` calls `super().complete()` before the actual implementation, wasting a call [SEV: major, P1]

**File:** `app/core/llm.py:475-477`

**Evidence:**
```python
class OmniProvider(LLMProvider):
    async def complete(self, prompt, system=None, max_tokens=2048, temperature=0.7,
                       json_mode=False) -> LLMResult:
        res = await super().complete(prompt, system=system, max_tokens=max_tokens,
                                     temperature=temperature)
        if not self.api_key:
            return LLMResult(...)
```
`super().complete()` is `LLMProvider.complete()` which is **abstract** — this will raise `TypeError` at runtime. The `res` return value is never used. This means **OmniProvider is completely broken and every Gemini/Antigravity-routed section call will crash**.

**Fix:** Remove the `super().complete()` call entirely:
```python
async def complete(self, prompt, system=None, max_tokens=2048, temperature=0.7,
                   json_mode=False) -> LLMResult:
    if not self.api_key:
        return LLMResult(text="", provider="omni", model=self.MODEL,
                         error="OMNI_API_KEY not set")
    messages = [{"role": "user", "content": prompt}]
    # ... rest of implementation ...
```

---

### 4. `_extract_house` regex fails for Arabic-numeral house numbers [SEV: mod, P2]

**File:** `app/report/claim_validation.py:172`

**Evidence:**
```python
def _extract_house(text: str) -> list[tuple[str, int]]:
    # ...
    out.append((_normalize_planet(m.group(1)), int(_num(m.group(2))) if m.group(2).isdigit() else HOUSE_FA[m.group(2)]))
```
`m.group(2).isdigit()` returns `True` for Persian digits (`۱۲`) but `int()` cannot parse them without `_num()` conversion first. The `_num()` call is only made when `.isdigit()` is True, but `int("۱۲")` will raise `ValueError`.

**Fix:**
```python
raw_house = _num(m.group(2))
try:
    house_num = int(raw_house)
except ValueError:
    house_num = HOUSE_FA.get(m.group(2), 0)
out.append((_normalize_planet(m.group(1)), house_num))
```

Wait — re-reading: `int(_num(m.group(2)))` IS called when `.isdigit()` is True. `_num` converts Persian digits to ASCII. So `int(_num("۱۲"))` → `int("12")` → 12. Actually this is correct for Persian digits. But `.isdigit()` returns True for Persian digits `۱۲`, and `_num` converts them. So this works. However, `HOUSE_FA` lookup is used for the `else` branch (word forms like "اول"), and if the regex captures a mixed string, `HOUSE_FA` could KeyError. The regex alternation `(اول|دوم|...|[۰-۹0-9]+)` should prevent this. **Retracted — this is correct.**

---

### 5. `_is_uncertain_moon` false-positive: triggers on ANY text containing "ماه" without hedging [SEV: mod, P2]

**File:** `app/report/claim_validation.py:213-216`

**Evidence:**
```python
def _is_uncertain_moon(text: str) -> bool:
    if "ماه" not in text:
        return False
    return not re.search(r"حدود|تقریباً|تقریبا|شاید|ممکن|نزدیک|حوالی|~", text)
```
"ماه" means both "Moon" and "month" in Persian. Any section mentioning "ماه آینده" (next month), "سه ماه" (three months), etc. will trigger a false `moon-position-without-uncertainty` note even when the text has nothing to do with the Moon's zodiac position.

**Fix:** Require "ماه" in an astrological context (near a sign name or "در برج"):
```python
def _is_uncertain_moon(text: str) -> bool:
    if not re.search(r"ماه\s*(در|در برج|شما|تو)", text):
        return False
    return not re.search(r"حدود|تقریباً|تقریبا|شاید|ممکن|نزدیک|حوالی|~", text)
```

---

### 6. `extract_claims` drops all but the first pending planet when multiple planets precede a sign [SEV: mod, P2]

**File:** `app/report/claim_validation.py:130`

**Evidence:**
```python
elif pend:
    claims.append((pend.pop(0), _normalize_sign(tok)))
```
If the text says "خورشید و ماه در سرطان" (Sun and Moon in Cancer), `pend` accumulates `["sun", "moon"]`, but only `"sun"` is popped and paired with Cancer. The Moon claim is silently lost. This means a hallucinated Moon sign won't be caught.

**Fix:** Pop all pending planets and pair each with the sign:
```python
elif pend:
    sign = _normalize_sign(tok)
    for p in pend:
        claims.append((p, sign))
    pend.clear()
```

---

### 7. Prompt injection via `personal_question` — XML tag escape [SEV: major, P1]

**File:** `app/report/prompt_builder.py:237-240`

**Evidence:**
```python
PERSONAL_QUESTION_TEMPLATE = """...
<پرسش_کاربر>
{question}
</پرسش_کاربر>
...
"""
```
The `question` is capped at 600 chars (line 270: `question[:600]`) but never sanitized for the XML-like tag structure. A user can inject `</پرسش_کاربر>` followed by new instructions. The prompt does contain a warning about ignoring instructions inside the tags, but the model can be manipulated to treat injected text outside the closing tag as system-level.

**Fix:** Strip or escape the closing tag from user input:
```python
question = question.replace("</پرسش_کاربر>", "").replace("<پرسش_کاربر>", "")
```

---

### 8. `chat_answer` uses `asyncio.run()` — crashes in async contexts (duplicate of #1 for chat path) [SEV: critical, P0]

**File:** `app/chat/service.py:42`

**Evidence:**
```python
res = asyncio.run(rtr.complete(prompt, system=CHAT_SYSTEM_PROMPT,
                               max_tokens=1024, temperature=0.7))
```
If `chat_answer` is called from a FastAPI endpoint (which runs in an async event loop), this will raise `RuntimeError: asyncio.run() cannot be called from a running event loop`.

**Fix:** Make `chat_answer` async, or use `loop.run_until_complete()` with proper detection.

---

### 9. `build_section_router` is `@lru_cache(maxsize=None)` — unbounded memory + stale circuit breakers [SEV: major, P1]

**File:** `app/core/llm.py:726`

**Evidence:**
```python
@lru_cache(maxsize=None)
def build_section_router(domain: str, model: str) -> LLMRouter:
```
The cache is unbounded and never invalidated. More critically, the cached `LLMRouter` contains `GoPoolProvider` instances with mutable `KeySlot` state (error_streak, tripped_until, in_flight). Since the router is cached, **all concurrent report generations share the same mutable provider state without synchronization**. The `in_flight` counter can drift (if a task is cancelled after incrementing but before decrementing).

Additionally, if an admin changes the model via the secret store, the old cached router continues to be used.

**Fix:** Either remove the cache and build fresh routers per call (cheap), or use a TTL-based cache with proper state isolation:
```python
@lru_cache(maxsize=32)  # at least bound it
def build_section_router(domain: str, model: str) -> LLMRouter:
```
Or better, separate the stateful pool from the cached config.

---

### 10. Weekly delivery: N+1 query pattern — one DB session per subscription [SEV: mod, P2]

**File:** `app/report/weekly.py:107-145`

**Evidence:**
```python
for sub in subs:
    try:
        with Session(engine) as s:
            chart = s.get(Chart, sub.chart_id)
            # ...
        # ...
        with Session(engine) as s:
            sub_row = s.get(Subscription, sub.id)
```
Each subscription opens 2-3 separate DB sessions. For 1000 subscribers, this is 3000 session open/close cycles. Also, `sub` objects from the first query are detached when used in the loop (the first `with Session` block closed).

**Fix:** Batch-load charts and use a single session per batch, or at minimum use eager loading:
```python
with Session(engine) as s:
    subs = s.exec(select(Subscription).where(...)).all()
    chart_ids = [sub.chart_id for sub in subs]
    charts = {c.id: c for c in s.exec(select(Chart).where(Chart.id.in_(chart_ids))).all()}
```

---

### 11. `_week_start()` uses `(weekday() + 2) % 7` — wrong for Persian Saturday-start week [SEV: mod, P2]

**File:** `app/report/weekly.py:88-90`

**Evidence:**
```python
def _week_start() -> str:
    now = datetime.now(timezone.utc)
    return (now - timedelta(days=(now.weekday() + 2) % 7)).strftime("%Y-%m-%d")
```
Python's `weekday()`: Monday=0, Sunday=6. For Saturday (weekday=5): `(5+2)%7 = 0` → no subtraction → returns today. For Sunday (6): `(6+2)%7 = 1` → subtracts 1 → Saturday. For Monday (0): `(0+2)%7 = 2` → subtracts 2 → Saturday. This is **correct** for a Saturday-start week. **No issue.**

---

### 12. `word.py` — no input sanitization; potential OOXML injection [SEV: mod, P2]

**File:** `app/report/word.py:33-47`

**Evidence:**
```python
def report_to_docx(rep: dict[str, Any]) -> bytes:
    h = doc.add_heading(rep.get("title", "گزارش چارت تولد"), level=0)
    # ...
    for para in str(content).split("\n\n"):
        p = doc.add_paragraph(para)
```
`content` comes from LLM-generated report sections. While python-docx escapes XML entities in text runs, the `title` and `content` are not validated. If an attacker controls the report dict (unlikely but possible via admin override), they could inject content. Low risk since python-docx handles escaping, but the function accepts arbitrary dicts.

**Fix:** Validate input types and sanitize:
```python
title = str(sec.get("title", key))[:200]
content = str(sec.get("content", ""))[:10000]
```

---

### 13. `render_share_card` uses SHA-1 for cache key — no security concern but uses deprecated hash [SEV: mod, P2]

**File:** `app/share/card.py:60`

**Evidence:**
```python
key = hashlib.sha1(chart_id.encode(), usedforsecurity=False).hexdigest()[:16]
```
`usedforsecurity=False` is correctly set, so this is fine for cache keying. **No real issue — correctly flagged as non-security use.**

---

### 14. `render_share_card` — Playwright `--no-sandbox` in production [SEV: major, P1]

**File:** `app/share/card.py:67`

**Evidence:**
```python
b = p.chromium.launch(headless=True, args=["--no-sandbox"])
```
Running Chromium without sandbox in production is a security risk. If the HTML content (which includes LLM-generated text via `big_three`) contains malicious content, the unsandboxed browser process has full access to the host.

**Fix:** Run with sandbox enabled, or use a container-level sandbox:
```python
args = ["--no-sandbox"] if os.getenv("PLAYWRIGHT_NO_SANDBOX") else []
b = p.chromium.launch(headless=True, args=args)
```

---

### 15. `GoProvider.stream()` yields TWO results for a non-streaming fallback [SEV: mod, P2]

**File:** `app/core/llm.py:159-166`

**Evidence:**
```python
async def stream(self, prompt, ...):
    res = await self.complete(...)
    if res.error:
        yield res
    else:
        yield res  # single-shot is a valid "stream" of one chunk
        yield LLMResult(text=res.text, provider=self.name, model=self.MODEL,
                        latency_ms=res.latency_ms, usage=res.usage, cost=res.cost)
```
On success, the base `stream()` yields the same result TWICE — the consumer in `LLMRouter.stream_complete()` will emit duplicate tokens to the SSE client. The second yield is meant to be the "final" marker with usage, but the first yield already has the full text.

**Fix:** Yield once with full metadata:
```python
async def stream(self, prompt, ...):
    res = await self.complete(...)
    yield res  # single yield — carries text + usage + error (if any)
```

---

### 16. `validate_section` uses lowercase sign keys but `sign_of` may return mixed case [SEV: mod, P2]

**File:** `app/report/claim_validation.py:65, 100`

**Evidence:**
```python
def sign_of(planet_key, chart, default=""):
    return (pl.get("sign") or _sign_from_lon(pl.get("longitude"))) or default
```
`pl.get("sign")` returns whatever the chart JSON has — could be "Aries" (title case) or "aries" (lowercase). But `_normalize_sign` and the `SIGN_EN` dict use lowercase keys. If the chart stores "Aries", `sign_of` returns "Aries", but `extract_claims` normalizes to "aries" → mismatch → false hallucination flag.

**Fix:** Normalize in `sign_of`:
```python
return ((pl.get("sign") or _sign_from_lon(pl.get("longitude"))) or default).lower()
```

---

### 17. `qa_section` calls `evaluate(chart)` on every QA check — expensive re-computation [SEV: mod, P2]

**File:** `app/report/qa.py:120-123`

**Evidence:**
```python
def qa_section(section, chart, domain):
    try:
        from app.report.rules import evaluate
        _active_factors = {r["factor"] for r in evaluate(chart).get(domain, [])}
```
`evaluate(chart)` iterates all rules for all domains. In `generate_sections_async`, QA runs per section per attempt (up to 7 attempts × 13 sections = 91 calls). Each call re-evaluates the full rule engine.

**Fix:** Pass pre-computed active factors or cache the evaluation:
```python
# In the worker, compute once:
all_active = evaluate(chart)
# Pass to qa_section:
errors = qa_section(section, chart, domain, active_factors=all_active.get(domain, []))
```

---

### 18. `prompt_overrides.get_overrides()` replaces the ENTIRE prompt, losing the structured template [SEV: major, P1]

**File:** `app/report/worker.py:96-98`

**Evidence:**
```python
for key, content in get_overrides().items():
    if key in prompts:
        prompts[key] = (content, prompts[key][1])
```
An admin override replaces the full prompt string. If the override doesn't include the JSON output format, golden rules, or factor block, the LLM will produce unstructured output that fails QA. There's no validation that the override contains required template elements.

**Fix:** Either merge overrides into the template (e.g., override only the instruction section), or validate that overrides contain required markers:
```python
if "خروجی JSON" not in content:
    log.warning("Override for %s missing JSON format spec — skipping", key)
    continue
```

---

### 19. `_free_text()` in `qa_section` is called once per FORBIDDEN_PATTERN — O(n²) [SEV: mod, P2]

**File:** `app/report/qa.py:137-139`

**Evidence:**
```python
for pat in FORBIDDEN_PATTERNS:
    if re.search(pat, _free_text().replace("\u200c", "")):
```
`_free_text()` rebuilds the full text string on every iteration of the outer loop (25+ patterns). Then the same patterns are checked AGAIN inside the per-insight loop (line 157).

**Fix:** Compute `_free_text()` once and reuse:
```python
full_text = _free_text().replace("\u200c", "")
for pat in FORBIDDEN_PATTERNS:
    if re.search(pat, full_text):
        errors.append(...)
        break
```

---

### 20. `generate_report_audio` nests `asyncio.run()` inside `asyncio.to_thread` [SEV: critical, P0]

**File:** `app/report/worker.py:195-199`

**Evidence:**
```python
async def _gen():
    tts = edge_tts.Communicate(text, "fa-IR-DilaraNeural", rate="+0%")
    await tts.save(str(out))

await asyncio.to_thread(lambda: asyncio.run(_gen()))
```
`asyncio.to_thread` runs the lambda in a thread pool. Inside that thread, `asyncio.run()` creates a NEW event loop. This works but is unnecessarily complex and wasteful. More importantly, if `edge_tts` internally uses `aiohttp` with session reuse, creating a new loop per call can leak connections.

**Fix:** Just `await _gen()` directly since `generate_report_audio` is already async:
```python
tts = edge_tts.Communicate(text, "fa-IR-DilaraNeural", rate="+0%")
await tts.save(str(out))
```

---

### 21. `chat_stream` yields `cost_usd` and `tokens` from the LAST chunk — may be zero for streaming providers [SEV: mod, P2]

**File:** `app/chat/service.py:82-89`

**Evidence:**
```python
yield {
    "type": "done",
    "answer": last.text or "",
    "cost_usd": last.cost,
    "tokens": last.usage.total,
```
For `DeepSeekProvider.stream()`, the final chunk has `usage=LLMUsage(prompt_tokens=0, completion_tokens=len(acc))` — prompt tokens are always 0 in streaming mode, so cost is underreported.

**Fix:** Track accumulated usage across chunks, or note that streaming cost is approximate.

---

### 22. `_num()` Persian-to-ASCII translation is incomplete [SEV: mod, P2]

**File:** `app/report/claim_validation.py:161`

**Evidence:**
```python
def _num(text: str) -> str:
    return text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٤٥٦", "0123456789456"))
```
The Arabic-Indic digits mapping is incomplete: `٤٥٦` maps to `456`, but `٠١٢٣` (U+0660-U+0663) and `٧٨٩` (U+0667-U+0669) are not mapped. If the LLM outputs `٧` (Arabic-Indic 7), it won't be converted.

**Fix:**
```python
def _num(text: str) -> str:
    return text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
```

---

### 23. `house_of()` uses whole-sign houses but the rule engine uses chart-provided houses [SEV: mod, P2]

**File:** `app/report/claim_validation.py:178-182`

**Evidence:**
```python
def house_of(planet_key: str, chart: dict) -> int | None:
    """Whole-sign: index of the 30°-segment above the ASC longitude."""
    asc = _lon_of("ascendant", chart)
    lon = _lon_of(planet_key, chart)
    return int(((lon - asc) % 360.0) // 30) + 1
```
This computes whole-sign houses from longitudes, but the chart JSON likely stores Placidus or Koch houses in `planet.house`. The validation will flag correct Placidus house assignments as hallucinations when they differ from whole-sign.

**Fix:** Use the chart's stored house value when available:
```python
def house_of(planet_key: str, chart: dict) -> int | None:
    p = (chart.get("planets") or {}).get(planet_key, {})
    if isinstance(p, dict) and p.get("house") is not None:
        return int(p["house"])
    # fallback to whole-sign
    ...
```

---

### 24. `CACHE_DIR.chmod(0o700)` at module import time — fails on read-only filesystems [SEV: mod, P2]

**File:** `app/share/card.py:17-18`

**Evidence:**
```python
CACHE_DIR = Path(os.getenv("SHARE_CACHE_DIR", str(private_tmp() / "chart-share")))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.chmod(0o700)
```
This runs at import time. On read-only or restricted filesystems (some container deployments), `chmod` will raise `PermissionError` and prevent the entire module from loading.

**Fix:** Wrap in try/except or defer to first use:
```python
try:
    CACHE_DIR.chmod(0o700)
except OSError:
    pass
```

---

### 25. `weekly.py` — `run_weekly_delivery` commits the reflection row BEFORE sending the message [SEV: major, P1]

**File:** `app/report/weekly.py:120-127`

**Evidence:**
```python
s.add(WeeklyReflection(chart_id=sub.chart_id, week_start=week, text=text))
s.commit()
# ...
if sub.chat_id:
    await send_message(int(sub.chat_id), text, sub.platform)
```
If `send_message` fails, the `WeeklyReflection` row is already committed. The `already` check on line 115 will skip this chart on retry, so the user **never receives the message** and it's never retried.

**Fix:** Commit AFTER successful delivery, or use a `delivered` flag:
```python
s.add(WeeklyReflection(chart_id=sub.chart_id, week_start=week, text=text, delivered=False))
s.commit()
# ... send ...
reflection.delivered = True
s.commit()
```

---

## CORRECT SECTIONS (no issues found)

- **`app/report/rules.py`**: Rule engine evaluation logic is clean, well-structured, and correctly handles wildcard conditions, aspect matching, and priority sorting. The dataclass-based rule definitions are sound.

- **`app/chat/intents.py`**: Simple keyword classifier is appropriate for the use case. Scoring is correct. `route_question` mapping is complete.

- **`app/chat/retrieval.py`**: Prompt injection defenses (XML tags + system prompt separation + `_sanitize_question`) are well-implemented. The `CHAT_SYSTEM_PROMPT` correctly instructs the model to ignore injected instructions.

- **`app/report/claim_validation.py` (core sign/planet validation)**: The `validate_section` and `critical_facts` functions are correct. The regex-based extraction is thorough for both Persian and English.

- **`app/report/preview.py`**: Deterministic, no LLM cost, correct ranking logic. The `enrich_insights_async` gracefully falls back to deterministic originals on failure.

---

## VERDICT

| Dimension | Rating | Notes |
|---|---|---|
| **Correctness** | 🔴 Major issues | OmniProvider crashes on every call (#3); `asyncio.run()` in async contexts (#1, #8, #20); duplicate stream yields (#15); sign case mismatch (#16) |
| **Security (OWASP)** | 🟡 Moderate | Prompt injection partially mitigated but XML tag escape missing (#7); Chromium no-sandbox (#14); input sanitization adequate elsewhere |
| **Data Race** | 🟡 Moderate | Shared mutable `metrics` dict under `asyncio.gather` (#2); cached mutable router state (#9) |
| **Cost Leaks** | 🟢 Good | Budget ceilings well-implemented (daily/monthly/per-report/per-user); GO flat subscription correctly costs $0; streaming cost underreported (#21) |
| **Astrology Math** | 🟡 Moderate | Whole-sign vs Placidus house mismatch in validation (#23); claim extraction drops multi-planet claims (#6); sign case normalization gap (#16) |
| **RAG/LLM Pipeline** | 🔴 Major issues | OmniProvider broken (#3) blocks all Gemini routing; QA re-evaluates rules 91× (#17); prompt overrides can break output format (#18) |
| **UX (Mobile RTL)** | 🟢 Good | PDF renderer has proper RTL CSS, Vazirmatn font, `direction: rtl`, right-aligned Word export |
| **Business Logic** | 🟡 Moderate | Weekly delivery commit-before-send (#25) can permanently lose messages; fallback sections are honest but could be more informative |
| **Launch Readiness** | 🔴 Not ready | OmniProvider crash (#3) is a showstopper if Gemini is the default model; `asyncio.run()` crashes (#1, #8) block sync API paths; fix these before launch |