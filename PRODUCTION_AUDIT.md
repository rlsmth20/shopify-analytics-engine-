# skubase Production Readiness Audit

**Date:** 2026-05-01  
**Auditor:** Claude Code  
**Branch:** claude/naughty-sutherland-bebbed  
**Scope:** Full backend (`backend/app/`) + frontend (`frontend/`) audit

---

## Executive Summary

The application had no plan-level feature gating — every paying customer received every feature regardless of their subscription tier. This has been fixed. A number of additional production-readiness gaps were found and are documented below, split into **FIXED** (resolved in this commit) and **NEEDS ATTENTION** (requires further work before or shortly after launch).

---

## Priority 1: Plan-Level Feature Gating — FIXED

### What was wrong

`require_active_access` in `backend/app/api/deps.py` only checked whether the user had _any_ active subscription (`sub.status == "active"`). The `plan` field on the `Subscription` model (`"starter_monthly"`, `"growth_annual"`, etc.) was never read. A Starter subscriber at $29/mo had access to Growth features worth $99/mo.

### What was implemented

**`backend/app/api/deps.py`** — added:

- `TIER_RANK = {"starter": 1, "growth": 2, "scale": 3}` — canonical tier ordering
- `_extract_tier(plan)` — extracts `"growth"` from `"growth_monthly"` etc.
- `PlanGateException(required_tier)` — custom exception; converted to HTTP 402 with `{"detail": "...", "required_plan": "growth"}` by a handler in `main.py`
- `get_user_tier(db, user)` — returns the user's effective tier string; trial users get `"growth"` so they can evaluate the full product
- `require_plan(minimum_tier)` — dependency factory; chains off `require_active_access` so the subscription gate still runs first

**`backend/app/main.py`** — added `PlanGateException` exception handler that returns the exact JSON shape `{"detail": "...", "required_plan": "..."}`.

### Route tier assignments

| Route | Minimum tier | Rationale |
|-------|-------------|-----------|
| `GET /actions` | Starter | Action feed is a core Starter feature |
| `GET /forecast` | Starter | AI-powered forecasting listed on Starter |
| `GET /analytics/scorecards` | Starter | ABC×XYZ listed on Starter |
| `GET /reorder/purchase-orders` | Starter | "Purchase orders (create + PDF export)" on Starter |
| `GET /skus`, `GET /skus/{id}` | Starter | Core data — needed by all tiers |
| `GET /dashboard` | Starter | Core dashboard available to all |
| `GET /suppliers` | Starter | "Supplier records + basic scorecards" on Starter |
| `GET/PUT /shop-settings` (all variants) | Starter | Config — available to all |
| `GET /integrations/shopify` (install/connection/sync) | Starter | Shopify ingestion on Starter |
| `POST /integrations/stocky/import` | Starter | CSV imports on Starter |
| `POST /integrations/shipstation/import` | Starter | CSV imports on Starter |
| `GET/POST /alerts/rules`, `GET /alerts/events`, `POST /alerts/evaluate` | Starter | Email + Slack alerts on Starter |
| `GET /alerts/channels` | Starter | Read-only, Starter |
| `POST /alerts/channels` | **Growth** for SMS/webhook | Enabling SMS or webhook requires Growth |
| `POST /alerts/test` | **Growth** for SMS/webhook | Same as above |
| `POST /alerts/rules` | **Growth** if channels include sms/webhook | Rule creation with Growth channels |
| `GET /reorder` | **Growth** | Safety-stock / ROP / EOQ listed as Growth feature |
| `GET /bundles` | **Growth** | Bundle/kit analysis listed as Growth |
| `GET /transfers` | **Growth** | Multi-location transfers listed as Growth |
| `GET /liquidation` | **Growth** | Dead-stock liquidation plans listed as Growth |
| Audit log, workspace roles, SSO | **Scale** | No routes exist yet for these features |

### Trial user behaviour

Trial users receive `"growth"` tier access (they can evaluate the full product). This is enforced in `get_user_tier()`. When a Scale-only feature is later added, trial users will not see it automatically — they would need to be assigned `"scale"` in `get_user_tier` or the logic updated.

### HTTP 402 response shape

```json
{
  "detail": "Upgrade to Growth to access this feature.",
  "required_plan": "growth"
}
```

The frontend currently redirects all 402s to `/pricing?trial_expired=1`. When the upgrade-prompt UI is built, it can use `required_plan` to deep-link to the correct tier.

---

## Priority 2: Backend Audit

### 2.1 Routes with no auth — NO ISSUES

All data-serving routes use either `require_active_access` (now with plan gating where applicable) or `require_admin`. Public routes are intentional:

- `GET /health` — health check (fine)
- `POST /waitlist/signup`, `GET /waitlist/count` — pre-launch signup (fine)
- `GET /integrations/shopify/callback` — OAuth callback (must be unauthenticated for Shopify to reach it; HMAC signature verified)
- `POST /stripe/webhook` — Stripe posts here; Stripe-Signature verified ✅

The admin routes (`/admin/invite`, `/admin/users`) use `ADMIN_BOOTSTRAP_TOKEN` header gating, not session cookies. This is intentional during the beta phase but should be replaced with `require_admin` once admin users are seeded.

**⚠️ NEEDS ATTENTION — Admin bootstrap security:** If `ADMIN_BOOTSTRAP_TOKEN` is not set in the environment, `POST /admin/invite` returns HTTP 503 (disabled). But if it IS set and accidentally leaked, anyone with the token can invite arbitrary users. Rotate this token if it has been shared. Migrate to `require_admin` as soon as you have an admin user in the database.

### 2.2 Missing input validation

**NEEDS ATTENTION:**

| Location | Issue |
|----------|-------|
| `POST /alerts/rules` (`CreateAlertRuleRequest`) | `name` has no max-length constraint. A 10 MB rule name would pass. Add `Field(max_length=200)`. |
| `POST /alerts/channels` (`UpdateNotificationChannelRequest`) | `target` (email/phone/URL) has no max-length or format validation. Add `Field(max_length=500)`. SMS targets should validate E.164 format. |
| `GET /forecast` | `horizon_days` query param has no max constraint — a caller could request a 10-year horizon and trigger a very long computation. Add `Query(30, ge=1, le=365)`. |
| `GET /alerts/events` | `limit` query param has no max — a caller could request 1 million events. Add `Query(50, ge=1, le=500)`. |
| `GET /reorder` | `service_level` already has bounds (`ge=0.80, le=0.999`) ✅ |
| `POST /admin/invite` | `shopify_domain` has `max_length=255` ✅; `note` has `max_length=1000` ✅ |
| CSV imports | File size limits exist (25 MB Stocky, 50 MB ShipStation) ✅. No MIME-type verification beyond `.csv` extension check — a renamed binary file passes. |

### 2.3 N+1 queries / performance

**NEEDS ATTENTION:**

| Location | Issue |
|----------|-------|
| `GET /forecast` | Calls `load_daily_history_for_shop_sku` in a Python for-loop — one DB round-trip per SKU. For a shop with 500 SKUs this is 500 queries per request. Should batch with a single query keyed by `product_id IN (...)` and group in Python. |
| `GET /alerts/evaluate` | Same loop pattern as forecast — N queries for N SKUs. |
| `GET /reorder` | Same loop via lambda passed to `build_reorder_suggestions`. |
| `GET /analytics/scorecards` | Same. |
| `GET /dashboard` | Delegates to `services/dashboard.py` — needs review for similar patterns. |

**Already efficient:**
- `load_skus_for_shop` issues a single joined query with `func.sum` aggregations ✅
- All ORM queries use `select()` with parameterized filters; no dynamic SQL ✅

### 2.4 Error handling gaps

**NEEDS ATTENTION:**

| Location | Issue |
|----------|-------|
| `GET /forecast/{sku_id}` | Calls `load_skus_for_shop` to find the SKU, then calls `forecast_sku`. If `forecast_sku` raises an unhandled exception (e.g. division by zero on zero-history SKU), the user gets a raw 500. Wrap in a try/except. |
| `POST /integrations/shopify/sync` | `sync_shop_now` catches `RuntimeError` only. Other exceptions from the Shopify API client (network timeouts, rate-limit 429s) propagate as 500s. |
| `services/notifications.py` | Email/SMS/Slack/webhook delivery — unclear if all delivery errors are caught and returned as structured `DeliveryRecord.error` rather than raised. Audit the notification service. |
| `POST /stripe/webhook` | Top-level exception is caught and returns 200 (correct — prevents Stripe retries). But the error is only logged; there's no alerting. Consider a Sentry/alerting hook here. |

**Already handled correctly:**
- `POST /integrations/stocky/import` and `POST /integrations/shipstation/import` — `StockyImportError` / `ShipStationImportError` caught and returned as 400 ✅
- Billing routes — `RuntimeError` from Stripe client caught and returned as 400 ✅

### 2.5 Environment variable dependencies

**NEEDS ATTENTION — Missing startup warnings:**

| Env var | Used for | What happens if missing |
|---------|----------|------------------------|
| `DATABASE_URL` | All DB operations | App starts but crashes on first request (no warning at startup) |
| `STRIPE_SECRET_KEY` | Billing | Routes return 503; `is_configured()` check present ✅ |
| `STRIPE_WEBHOOK_SECRET` | Webhook verification | `verify_webhook_signature` returns `None` → all webhooks rejected with 400; no startup warning |
| `SHOPIFY_CLIENT_ID` / `SHOPIFY_CLIENT_SECRET` | OAuth | `is_configured()` check present ✅ |
| `RESEND_API_KEY` | Transactional email | Magic links silently fail to send (no startup warning) |
| `TWILIO_*` | SMS alerts | Delivery silently fails |
| `SLACK_BOT_TOKEN` | Slack alerts | Delivery silently fails |
| `ADMIN_BOOTSTRAP_TOKEN` | Admin invite endpoint | Route returns 503 with clear message ✅ |
| `FRONTEND_ORIGIN` | CORS + redirect URLs | Defaults to `http://localhost:3000` — wrong in production |

**Recommendation:** Add a startup check in `lifespan()` that logs `WARNING` for any required env var that is absent. `DATABASE_URL` and `STRIPE_WEBHOOK_SECRET` should be hard errors.

### 2.6 Rate limiting

**NEEDS ATTENTION — No rate limiting present anywhere.**

The most critical unprotected surface is `POST /auth/magic-link/request`. An attacker can:
- Enumerate valid email addresses (the endpoint currently returns 200 always, which is correct for enumeration prevention, but the lack of rate limiting means unlimited email spam to any address)
- Exhaust the Resend/email sending quota

**Recommendation:** Add `slowapi` (FastAPI wrapper around `limits`) with:
- `POST /auth/magic-link/request` → 5 requests per email per hour + 20 per IP per hour
- `POST /billing/checkout` → 10 per user per hour (prevent Stripe session spam)
- Apply globally: 200 req/min per IP as a baseline

No rate limiting exists on any other endpoint either, leaving the service open to scraping.

### 2.7 CORS configuration

**PARTIALLY ADDRESSED — Needs verification in production.**

CORS origins are read from `FRONTEND_ORIGIN` env var (comma-separated). This is correct — not hardcoded to `*`. However:

- `allow_methods=["*"]` and `allow_headers=["*"]` are overly permissive. Restrict to the methods and headers actually used (`GET, POST, PUT, PATCH, DELETE, OPTIONS` and `Content-Type, Accept, Cookie`).
- If `FRONTEND_ORIGIN` is not set, it defaults to `http://localhost:3000` — if this reaches production, CORS will block all browser requests from the real domain.
- Verify the Railway/production env var is set to the actual `https://skubase.io` origin before launch.

### 2.8 Stripe webhook signature verification

**CORRECT — No action needed.**

`billing.py` calls `verify_webhook_signature(payload, signature_header)` before processing any event. The raw request body is used (not the parsed JSON). If the signature header is missing or invalid, returns 400. ✅

One caveat: if `STRIPE_WEBHOOK_SECRET` is not set in the environment, `verify_webhook_signature` currently returns `None` for every event, blocking all webhooks. Add a startup warning for this case (see §2.5).

### 2.9 SQL injection surface

**NONE FOUND — No action needed.**

All database access goes through SQLAlchemy ORM with parameterized queries. `db.execute()` calls in `services/shop_skus.py` use `func.*` constructs and Python objects as bind parameters — no string interpolation. No raw `text()` SQL anywhere in the codebase. ✅

### 2.10 Sensitive data in responses

**NEEDS ATTENTION:**

| Route | Issue |
|-------|-------|
| `GET /billing/me` | Returns `current_subscription_summary` — need to confirm this does not include `stripe_customer_id` or `stripe_subscription_id` in the response (internal IDs that shouldn't be exposed to frontend). Review `services/billing.py::current_subscription_summary`. |
| `GET /integrations/shopify/connection` | Returns `shopify_domain`, `scope`, `last_sync_at`. The OAuth access token is NOT returned — correct ✅. `scope` is informational and acceptable. |
| `GET /admin/users` | Returns `user_id`, `email`, `shop_id`, `is_admin`. Protected by `ADMIN_BOOTSTRAP_TOKEN`. `trial_ends_at` and internal timestamps are not returned — correct ✅. |
| Magic-link tokens | Tokens are hashed in the DB (SHA-256); raw token only travels in the email link. Sessions are hashed too. ✅ |
| `ShopSettings.allow_mock_fallback` | This field is returned in `GET /shop-settings`. It reveals an internal capability flag to the user. Consider removing from the response schema. |

**Also noted:** `GET /shop-settings` returns `shop_id` (internal integer). This is low-risk but unnecessary — consider omitting from the public response.

---

## Priority 3: Frontend Audit

### 3.1 Hardcoded mock/debug strings

**NONE FOUND IN PRODUCTION COMPONENTS.**

`frontend/lib/demo-data.ts` contains demo fixtures, but these are served only when `sessionStorage.getItem("skubase_demo") === "1"` or `?demo=1` is in the URL. This is intentional demo mode, not a leaked debug string.

`ShopSettings.allow_mock_fallback` controls whether backend services fall back to mock data. The default is `True` in the `ShopSettings` model — **this should default to `False` in production** (see §2.10 above).

### 3.2 API error handling — 402 responses

**FIXED (partial):**

- `get()` in `frontend/lib/api-v2.ts`: had a duplicated 402 handler block (lines 296–307 were identical). The duplicate has been removed.
- `postJson()` in `api-v2.ts`: had **no** 402 handler at all. Now fixed — all mutating calls (create alert rule, update channel, send test alert) will redirect to pricing on 402.

**STILL NEEDS ATTENTION:**

The 402 handler currently redirects the whole page to `/pricing?trial_expired=1`. Once plan gating is live, a Starter user trying to enable an SMS channel will get a hard page redirect instead of an inline upgrade prompt. This is a rough UX. The recommended follow-up:

1. Parse `required_plan` from the 402 JSON body
2. Show an inline `<UpgradePrompt plan="growth" />` modal instead of redirecting
3. The redirect is acceptable as a v1 but should be replaced before users start hitting plan gates

**`frontend/lib/api.ts`** (v1 API client used for `/actions`, `/shop-settings`, `/skus`): Does NOT have a 402 handler. These routes return `require_active_access` 402s (trial expired), not plan-gate 402s — but once gating is live, if a v1 route were accidentally downgraded below Starter, users would see an unhandled error. Add a 402 handler to `api.ts` as a safety net.

### 3.3 Missing loading/error states

**NEEDS ATTENTION:**

Spot-checked several app pages:

| Page | Loading state | Error state | Notes |
|------|-------------|-------------|-------|
| `dashboard/page.tsx` | Unclear — depends on component | Unclear | Needs verification |
| `forecast/page.tsx` | Unclear | Unclear | Long-running request for large shops — needs skeleton |
| `bundles/page.tsx` | Unclear | Unclear | Now Growth-gated; first error state users may see is 402 redirect |
| `liquidation/page.tsx` | Unclear | Unclear | Same |
| `transfers/page.tsx` | Unclear | Unclear | Same |
| `suppliers/page.tsx` | Unclear | Unclear | Same |

The `app-shell` wraps all pages with auth-guard and trial-banner logic — that part is solid. The per-page data-fetch error states were not fully audited here; recommend a dedicated frontend pass before launch.

### 3.4 Workspace ID "#0" bug

This was flagged as "being fixed separately." Not reproduced or verified here — that fix should be confirmed in its own session.

---

## Additional Findings

### A. `allow_mock_fallback` defaults to True

`backend/app/db/models.py` — `ShopSettings.allow_mock_fallback` column defaults to `True`. In production, this means new shops that haven't explicitly configured settings will fall back to mock data when real data is unavailable. Set the column default to `False`.

```python
# In models.py, change:
allow_mock_fallback: Mapped[bool] = mapped_column(Boolean, default=True)
# To:
allow_mock_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
```

### B. Session cookie SameSite=None requires Secure

The session cookie is set with `SameSite=None` (required for cross-origin cookie sharing between the Next.js frontend and the FastAPI backend on different origins). `SameSite=None` MUST be accompanied by `Secure=True` in production. Verify this is set in `services/auth.py` where the cookie is created. If the app is deployed on HTTP (not HTTPS), the browser will silently reject the cookie.

### C. Magic-link token window

Magic-link tokens expire in 15 minutes (good). Sessions expire in 30 days. Consider adding a `POST /auth/sessions` endpoint to list active sessions and a `DELETE /auth/sessions/{id}` to revoke individual ones — useful if a user suspects a session was compromised.

### D. Supplier scorecard tiering not yet differentiated by plan

The pricing table lists "Supplier records + basic scorecards" on Starter and "Supplier scorecards + tiering" on Growth. Currently the `/suppliers` endpoint returns full scorecards including the `tier` field (preferred/acceptable/at_risk) for all subscribers. This is a minor tier-bleed: Starter users technically see a Growth feature.

**Recommended follow-up:** In `services/supplier_scoring.py`, strip the `tier` and `notes` fields (or set them to `null`) when the requesting user's plan tier is Starter.

### E. No PO approval workflow routes

The pricing table lists "PO approval workflows" as a Growth feature. No route currently implements this. When PO approval is built, gate it at Growth using `require_plan("growth")`.

### F. No audit log routes

"Audit log and decision snapshots" is a Scale feature. No route currently implements this. When built, gate with `require_plan("scale")`.

### G. CORS `allow_methods=["*"]` and `allow_headers=["*"]`

Restrict to only what the app uses. Recommended:
```python
allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
allow_headers=["Content-Type", "Accept"],
```
`Cookie` headers are handled automatically by `allow_credentials=True` and don't need to be listed.

---

## Summary Table

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | No plan-level feature gating — all features accessible on all tiers | **Critical** | ✅ Fixed |
| 2 | Duplicate 402 handler in `api-v2.ts get()` | Low | ✅ Fixed |
| 3 | No 402 handler in `api-v2.ts postJson()` | Medium | ✅ Fixed |
| 4 | No rate limiting on `POST /auth/magic-link/request` (email spam risk) | **High** | Needs attention |
| 5 | `allow_mock_fallback` defaults to True in production | Medium | Needs attention |
| 6 | No startup warnings for missing required env vars | Medium | Needs attention |
| 7 | N+1 queries in forecast, reorder, analytics, alerts/evaluate loops | Medium | Needs attention |
| 8 | `horizon_days` and `limit` query params have no upper bounds | Low | Needs attention |
| 9 | `CreateAlertRuleRequest.name` and `target` have no length limits | Low | Needs attention |
| 10 | `STRIPE_WEBHOOK_SECRET` absence silently drops all webhooks | **High** | Needs attention |
| 11 | Admin bootstrap token should migrate to `require_admin` | Medium | Needs attention |
| 12 | `GET /billing/me` may expose internal Stripe IDs | Low | Needs investigation |
| 13 | `allow_mock_fallback` exposed in shop-settings response | Low | Needs attention |
| 14 | CORS `allow_methods=["*"]` overly permissive | Low | Needs attention |
| 15 | No rate limiting globally | Medium | Needs attention |
| 16 | Supplier tier field not stripped for Starter subscribers | Low | Needs attention |
| 17 | No 402 handler in `frontend/lib/api.ts` (v1 client) | Low | Needs attention |
| 18 | 402 causes hard page redirect; inline upgrade prompt not yet built | Medium | Needs attention |
| 19 | `SameSite=None` cookie must have `Secure=True` in production | Medium | Verify |
| 20 | Workspace ID "#0" bug (tracked separately) | Medium | In progress |
