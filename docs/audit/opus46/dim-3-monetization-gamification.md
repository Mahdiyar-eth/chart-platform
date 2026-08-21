# AUDIT: Monetization Model — ZAYCHE Platform

**Auditor:** Senior Staff Engineer / Product Architect
**Date:** 2026-08-18
**Scope:** `app/models.py`, `app/db.py` (seed_plans), `app/payment/orders.py`, credit/subscription/order lifecycle
**Verdict:** The current model is **functional but confusing** — three overlapping value-exchange mechanisms with unclear user-facing boundaries. Below is the evidence-based analysis and a principled recommendation.

---

## 1. CURRENT STATE: What Actually Exists (Evidence)

### 1.1 Three Monetization Primitives

| Primitive | Model / Table | How user pays | What user gets | Code evidence |
|-----------|--------------|---------------|----------------|---------------|
| **One-off Report** | `Plan` (key ∈ `{basic, full, gold, synastry}`) → `Order` → `Report` | Zarinpal or wallet balance | PDF report (5/13/13+ sections) | `orders.py:REPORT_PLANS = {"basic", "full", "gold"}` (line ~170) |
| **Credit Pack** | `Plan` (key ∈ `{credit3, credit6, credit12}`) → `Order` → `User.credits` | Zarinpal or wallet balance | N exploration credits | `orders.py:CREDIT_PACKS = {"credit3", "credit6", "credit12"}` (line ~171) — **but these plans are NOT in `seed_plans()`** |
| **Subscription** | `Plan` (key ∈ `{monthly, yearly}`) → `Order` → `Subscription` | Zarinpal or wallet balance | Daily/weekly reflections + 5 credits/month + transit alerts | `orders.py:SUBSCRIPTION_PLANS = {"monthly", "yearly"}` (line ~172) |

### 1.2 Credit Economy

| Mechanism | Code location | Amount |
|-----------|--------------|--------|
| Free first exploration | `User.free_exploration_used` (models.py:19) | 1 free, then blocked |
| Subscription monthly grant | `grant_subscription_credits()` (orders.py:~185) | 5 credits/month |
| Credit pack purchase | `grant_credits()` (orders.py:~220) | `Plan.credits_grant` — **but no credit packs are seeded** |
| Referral bonus (buyer) | `reward_referral()` (orders.py:~270) | 1 credit on first paid order |
| Exploration cost | `Exploration.credits_cost` (models.py:~120) | 1 credit per card |
| Refund on failure | `Exploration.refunded` (models.py:~122) | 1 credit back |

### 1.3 Wallet (Rial balance)

| Mechanism | Code | Amount |
|-----------|------|--------|
| Referral reward (referrer) | `reward_referral()` → `User.balance_rial` | 10% of referred order |
| Wallet payment | `pay_order_with_balance()` | Full order amount only (no mixed) |
| Withdrawal | `withdraw_request()` | Min 500k rial (50k toman) |

---

## 2. PROBLEMS IDENTIFIED (Ranked)

### P0 — Credit Packs Referenced But Never Seeded

**Evidence:** `orders.py:171` defines `CREDIT_PACKS = {"credit3", "credit6", "credit12"}` and `grant_credits()` (line ~220) reads `Plan.credits_grant`. But `db.py:seed_plans()` (lines 32-67) seeds only `basic`, `full`, `gold`, `synastry`, `monthly`, `yearly`. No `credit3/6/12` plans exist.

**Impact:** If a user somehow reaches a credit-pack purchase flow, `create_order()` will raise `LookupError("plan not found")`. The feature is **dead code** — or there's an unseeded migration adding these plans that I don't see.

**Acceptance criteria:** Either (a) add credit pack plans to `seed_plans()` with `credits_grant > 0`, or (b) remove `CREDIT_PACKS` and `grant_credits()` if the product decision is credit-via-subscription-only.

### P1 — User Confusion: Three Mental Models

The user encounters:
1. **"Buy a report"** — one-time, 149k–699k toman, gets a PDF
2. **"Buy credits"** — (dead, but implied by the Exploration UI) to unlock individual insight cards
3. **"Subscribe"** — 99k/month or 890k/year, gets daily content + 5 credits/month

**The confusion:** A Gold report buyer (699k toman) gets AI chat (5 questions/day) but only through the report — no exploration credits. A subscriber (99k/month) gets 5 credits but no report. To get BOTH, the user pays twice with no bundle discount. The value proposition of "credits" is never explained relative to "reports."

### P2 — `Plan.credits_grant` Has `server_default="0"` But Is Never Set

**Evidence:** `models.py:~195` — `credits_grant: int = Field(default=0, sa_column=Column(Integer, default=0, server_default="0"))`. The `seed_plans()` catalog dicts never include `credits_grant`, so every seeded plan has `credits_grant=0`. Even if credit packs were seeded, the grant amount would need to be explicitly set.

### P3 — Gold Plan Includes Chat But Not Credits

**Evidence:** `seed_plans()` Gold features include "گفتوگو با هوش مصنوعی دربارهی چارت (۵ سوال در روز)" but `credits_grant=0`. The Gold buyer cannot do explorations without separately buying credits or subscribing. This is a **value gap** — the most expensive one-off product doesn't include the self-discovery feature.

### P4 — Subscription Credits Are Chart-Bound, Not User-Bound

**Evidence:** `grant_subscription_credits()` (orders.py:~185) resolves the user through `sub.chart_id → Chart → BirthProfile → user_id`. If a user has multiple charts, they could theoretically have multiple subscriptions and get 5 credits × N per month. Conversely, credits are on `User.credits` (user-level), so they're spendable on ANY chart — the binding is asymmetric.

### P5 — No Gamification Infrastructure Beyond Free-First-Exploration

The only "gamification" is:
- `User.free_exploration_used` — one free card, ever
- `DailyReflection` with unique constraint — streak-trackable but **no streak counter, no reward**
- Referral gives 1 credit (buyer) + 10% rial (referrer) — but no tiered rewards

There is no:
- Streak reward system
- Loyalty tier
- Achievement/badge system
- Seasonal/event credits
- Social proof mechanics

---

## 3. RECOMMENDATION: Credit-Centric Hybrid Model

### 3.1 Principle

**Credits should be the universal internal currency.** Reports cost credits. Explorations cost credits. Chat questions cost credits. Subscriptions grant credits monthly. One-off purchases grant credits. This eliminates the "report vs credit vs subscription" confusion.

**Why not pure subscription?** Persian astrology is event-driven (birth, marriage, new year). Most users want one report and leave. Forcing subscription creates churn anxiety. Credits let casual users buy what they need.

**Why not pure one-off?** Subscribers are 10× more valuable (recurring revenue, daily engagement, referral source). The subscription should exist as the "best deal" wrapper around credits.

### 3.2 Proposed Pricing / Credits Table

| Plan Key | Name (FA) | Price (Toman) | Credits Granted | What It Unlocks | Notes |
|----------|-----------|---------------|-----------------|-----------------|-------|
| `starter` | شروع | 0 (free) | 3 | 1 free basic report (auto-spent) + 2 explorations | Replaces `free_exploration_used` flag |
| `basic` | گزارش پایه | 149,000 | 15 | Basic report costs 10 credits; 5 leftover for explorations | User sees "۱۵ اعتبار" not "گزارش پایه" |
| `full` | گزارش کامل | 349,000 | 40 | Full report costs 30 credits; 10 leftover | Best value for one-time deep analysis |
| `gold` | گزارش طلایی | 699,000 | 90 | Gold report costs 50 credits; 40 leftover for chat + explorations | Premium users get weeks of engagement |
| `synastry` | سیناستری | 499,000 | 50 | Synastry costs 40 credits; 10 leftover | |
| `credit10` | ۱۰ اعتبار | 99,000 | 10 | Pure top-up | Replaces dead `credit3/6/12` |
| `credit30` | ۳۰ اعتبار | 249,000 | 30 | Pure top-up (17% bonus vs credit10) | |
| `credit60` | ۶۰ اعتبار | 449,000 | 60 | Pure top-up (33% bonus) | |
| `monthly` | همراه ماهانه | 99,000/mo | 20/month | Daily insight + weekly reflection + transit alerts | Was 5 credits — too stingy for 99k |
| `yearly` | همراه سالانه | 890,000/yr | 25/month | Same + 2 months free + priority queue | 25 > 20 rewards commitment |

**Credit costs for actions:**

| Action | Credit Cost | Rationale |
|--------|------------|-----------|
| Basic report generation | 10 | ~15k toman per report section |
| Full report generation | 30 | 13 sections, heavier LLM |
| Gold report generation | 50 | 13 sections + chat + transit |
| Synastry report | 40 | Two charts, complex analysis |
| Exploration card | 1 | Impulse-friendly |
| AI chat question | 1 | Was "5/day" — now metered fairly |
| Daily reflection (read) | 0 | Free — engagement driver |
| Weekly reflection (read) | 0 | Free — engagement driver |

### 3.3 User-Facing Copy (FA)

**Dashboard wallet section:**
```
اعتبار شما: ۴۲ ⭐
[خرید اعتبار]  [تاریخچه]

هر اعتبار = یک کاوش یا یک سوال از هوش مصنوعی
گزارش پایه = ۱۰ اعتبار | گزارش کامل = ۳۰ اعتبار
```

**Pricing page header:**
```
همه چیز با اعتبار کار میکند ⭐
گزارش بخواهید، سوال بپرسید، کاوش کنید — همه با یک حساب اعتبار.
```

**Subscription pitch:**
```
همراه زایچه شوید 🌙
هر ماه ۲۰ اعتبار + بینش روزانه + هشدار گذرها
فقط ۹۹,۰۰۰ تومان/ماه — ارزانتر از خرید تکی اعتبار
```

**Empty state (0 credits):**
```
اعتباری ندارید ⭐
برای ادامهی کاوش، اعتبار بخرید یا همراه ماهانه شوید.
[خرید اعتبار]  [اشتراک ماهانه — ۲۰ اعتبار/ماه]
```

### 3.4 Gamification Mechanics

#### A. Free Credits (Onboarding Funnel)

| Trigger | Credits | Implementation |
|---------|---------|----------------|
| Account creation | 3 | `CreditTransaction(reason="signup_gift")` — replaces `free_exploration_used` |
| Complete birth profile | 2 | `CreditTransaction(reason="profile_complete")` — incentivizes full data entry |
| First share (OG card) | 1 | `CreditTransaction(reason="first_share")` — viral loop |
| **Total free:** | **6** | Enough for 1 basic report preview + 1 exploration — hooks without giving away the product |

#### B. Referral Program (Enhanced)

| Event | Referrer Gets | Referred Gets | Current code |
|-------|--------------|---------------|--------------|
| Referred user signs up | 2 credits | 3 credits (signup gift, as above) | Extend `reward_referral()` |
| Referred user's first paid order | 10% rial to wallet + 3 credits | 1 credit (existing) | Already in `reward_referral()` — add credit grant for referrer |
| Referrer hits 5 successful referrals | "سفیر زایچه" badge + 10 bonus credits | — | New: `ReferralEvent` count check |
| Referrer hits 20 referrals | 15% commission (up from 10%) | — | Tiered `REFERRAL_REWARD_PERCENT` |

#### C. Streak System (Leverage Existing `DailyReflection`)

**Evidence:** `DailyReflection` already has `UniqueConstraint("chart_id", "day_local")` — streak detection is a query, not a schema change.

| Streak Length | Reward | Implementation |
|--------------|--------|----------------|
| 3 days | 1 credit | Query: `SELECT COUNT(*) FROM daily_reflections WHERE chart_id=? AND day_local >= ?` with consecutive-day check |
| 7 days | 3 credits + "هفتهی درخشان" badge | |
| 30 days | 10 credits + "ماه کامل" badge | |
| 90 days | 30 credits + "فصل ستارگان" badge | |

**New model needed:**
```python
class Achievement(SQLModel, table=True):
    __tablename__ = "achievements"
    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    key: str = Field(index=True)  # streak_7, streak_30, ambassador, ...
    title_fa: str = Field(default="")
    credits_awarded: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_achievement_user_key"),)
```

#### D. Loyalty Program (Spend-Based)

| Lifetime Credits Purchased | Tier | Benefit |
|---------------------------|------|---------|
| 0–49 | ستاره (Star) | Base pricing |
| 50–149 | ماه (Moon) | 5% bonus credits on every purchase |
| 150–499 | خورشید (Sun) | 10% bonus + priority report queue |
| 500+ | کهکشان (Galaxy) | 15% bonus + early access to new features + direct support |

**Implementation:** `SUM(amount) FROM credit_transactions WHERE user_id=? AND amount > 0 AND reason IN ('purchase', 'subscription')` — no new table, just a computed tier.

#### E. Seasonal / Event Credits

| Event | Mechanic | Frequency |
|-------|----------|-----------|
| Nowruz (نوروز) | Double credits on all purchases for 13 days | Annual |
| Yalda (یلدا) | Free 5 credits to all active users | Annual |
| Mercury retrograde | 1 free exploration card (themed) | ~3×/year |
| User's solar return (birthday) | 3 free credits + personalized message | Per-user annual |

---

## 4. MIGRATION PATH (What Changes in Code)

### 4.1 Schema Changes

| File | Change | Priority |
|------|--------|----------|
| `models.py:Plan` | Add `credits_cost: int` field (how many credits a report/action costs) | P0 |
| `models.py:User` | Remove `free_exploration_used` — replaced by signup credit grant | P1 |
| `models.py` | Add `Achievement` table (see §3.4.C) | P2 |
| `db.py:seed_plans()` | Update catalog with new credit values; add `credit10/30/60` packs | P0 |

### 4.2 Logic Changes

| File | Change | Priority |
|------|--------|----------|
| `orders.py:create_order()` | Report purchase should deduct credits (or purchase credits then auto-deduct) | P0 |
| `orders.py:grant_credits()` | Must work — currently dead (no seeded credit packs) | P0 |
| `orders.py:CREDIT_PACKS` | Update to `{"credit10", "credit30", "credit60"}` | P0 |
| New: `app/gamification/streaks.py` | Streak detection + reward granting after `DailyReflection` creation | P2 |
| New: `app/gamification/loyalty.py` | Tier computation from `CreditTransaction` aggregates | P2 |

### 4.3 What NOT to Change

- **Zarinpal integration** — works correctly, keep as-is
- **Wallet (balance_rial)** — keep for referral payouts; it's real money, not credits
- **Subscription model** — keep, but increase `SUBSCRIPTION_MONTHLY_CREDITS` from 5 to 20
- **Coupon system** — works, keep as-is (apply to credit purchases too)
- **Atomic debit patterns** — `F-02`, `F-11`, `F-15` are correct and battle-tested

---

## 5. WHAT IS CORRECT (No Issues Found)

| Area | Verdict |
|------|---------|
| `CreditTransaction` ledger pattern | ✅ Correct — append-only, links reason + ref_id, enables audit trail |
| Atomic balance operations | ✅ `UPDATE ... WHERE balance >= amount` pattern is race-safe |
| Referral cycle detection | ✅ 8-hop chain walk with cycle detection (orders.py:~280) |
| Self-referral guard | ✅ Double-layer: creation-time + reward-time (H1.4) |
| Subscription renewal extension | ✅ `max(current_expiry, now) + days` preserves prepaid time (A9) |
| Withdrawal one-pending constraint | ✅ Partial unique index + atomic CAS (F-11, F-15) |
| Coupon atomic reservation | ✅ `UPDATE ... WHERE used_count < max_uses RETURNING id` (A10) |

---

## 6. SUMMARY DECISION MATRIX

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **Status quo** (report + dead credits + subscription) | No migration work | Users confused; credit packs broken; no gamification | ❌ Reject |
| **Pure subscription** | Simple mental model | Kills casual buyers (majority of Persian astrology market); high churn | ❌ Reject |
| **Pure one-off** | Simple; no recurring billing | No engagement loop; no LTV growth | ❌ Reject |
| **Credit-centric hybrid** (recommended) | One currency; casual + committed users served; gamification-ready; existing code 80% reusable | Migration effort (~2 sprints); needs credit-cost tuning post-launch | ✅ **Accept** |

---

**Bottom line:** The codebase is 80% ready for a credit-centric model. The `CreditTransaction` ledger, atomic operations, and subscription infrastructure are solid. The gap is product-level: seed the credit packs, set `credits_grant` on every plan, add `credits_cost` to actions, kill the `free_exploration_used` flag in favor of signup credits, and layer gamification on top of the existing `DailyReflection` streak data. Two sprints to code-complete; one more for copy/UX polish before launch-accepted.