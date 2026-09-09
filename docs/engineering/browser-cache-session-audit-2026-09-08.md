# Browser cache and application recovery audit

Scope: shared API clients, authentication, plan caches, browser storage, back/forward
restoration, error boundaries, dashboard/onboarding state, and the existing backend
and frontend regression suites. Customer inventory and saved purchasing data were
not changed.

The live frontend already returned private/no-store HTML, and the repository had
no service worker. Hashed static assets keep normal caching. API responses lacked
an explicit cache policy; the backend now sets private/no-store on ordinary
responses, including authentication errors, while CORS preflight caching remains.
Authenticated browser requests also use no-store. Reads receive a 30-second bound
combined with caller cancellation; writes are not automatically replayed.

Session read failures now show retry instead of redirecting a still-signed-in
customer to login. Only a confirmed 401 causes that redirect. Invalid successful
session payloads are rejected. Sign-out must be confirmed by the server before
the UI reports completion. A generation fence prevents older authentication
responses from restoring stale state. Cross-tab sign-in/sign-out notifications
and persisted pageshow events recheck the session and invalidate plan memory;
workspace component state remounts when account/shop identity changes.

Plan reads reject unavailable or malformed responses instead of caching an
apparent downgrade or crashing on absent capabilities. Onboarding/checklist and
remembered-domain keys are scoped by user/shop. Old unscoped keys remain stored
but are not assigned to an unknown account. Checklist parsing tolerates corrupt
storage and writes are optional; read hydration no longer overwrites progress.
Real store labels come from the authenticated API rather than global storage.

Page errors offer a full reload for stale JavaScript, and a root error boundary
provides recovery if the root layout fails. No automatic reload loop or global
cache purge is introduced. Network errors avoid exposing internal endpoint URLs.

Verification: the baseline full backend suite passed 421 tests and 211 subtests;
the added cache/CORS middleware test passed separately. The frontend suite passed
236 tests after the changes, including auth failure/retry, failed logout, cross-tab
identity changes, browser restoration, corrupt preferences, cache invalidation,
read cancellation, and no write replay. Typecheck and production build passed;
the final deployment rebuild validates the release snapshot. This audit is not a
claim that every possible browser, merchant dataset, or third-party outage was tested.

Production rollout: code commit `68a62b4`; Railway deployment
`8db1322f-e8a9-49d0-b98e-d740db2d9aa6` SUCCESS; Vercel deployment
`dpl_EUvZzshT75U1nLP193FhhjGpQDo7` READY at `https://www.skubase.io`
(37-second remote build). Live health and unauthenticated auth/entitlement
responses now return `Cache-Control: private, no-store` and `Pragma: no-cache`.
Frontend HTML remains private/no-store; a versioned JavaScript asset retains
`public,max-age=31536000,immutable` caching.

Read-only Chrome checks covered dashboard, account, alerts, actions, analytics,
forecast, reports, purchase orders, Stocky migration, store sync, stock rules,
billing, both CSV import screens, privacy requests, transfers, bundles, dead-stock
recovery, suppliers, and feedback. The signed-in workspace had no inventory;
planning pages finished loading into empty states and setup guidance. No browser
console errors appeared in these checks, and the post-deployment Vercel error-log
query returned no entries. This does not establish coverage for every merchant
dataset or verify sending alerts, making payments, or uploading inventory in
production. Recovery fault cases remain covered by regression fixtures.

Release evidence `12712` preserves the changes and verification limits in the
growth agent's durable history. No growth executor restart was required.
