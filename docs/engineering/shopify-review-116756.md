# Shopify review 116756: installation, sync, and analytics

## Evidence and scope

The reviewer reports a prolonged OAuth loop followed by inability to sync. The
recording ends with an Internal Server Error after approving Shopify access;
earlier frames show a website login and an unconnected workspace.

An isolated reproduction identified a matching callback failure: reconnecting an
already installed Shopify domain from a separate website workspace attempted to
assign the same unique domain to a second Shop. Production logs are still needed
to confirm that this was the exact exception in the recording.

These changes are local. They have not been deployed or submitted to Shopify.
This document records a targeted repair and product improvement pass, not a
completed audit of every App Store requirement.

## Installation and sync repairs

- Verified Shopify session tokens can establish the configured managed
  installation through token exchange, including expiring offline tokens.
- Callback and token exchange resolve the canonical workspace for the verified
  shop. Reinstall reuses it without moving an unrelated website account.
- Per-shop locking prevents concurrent connection provisioning and token refresh.
  PostgreSQL uses transaction advisory locks; local SQLite uses process locks.
- JWT signature, audience, time claims, issuer, destination, and subject are
  validated before provisioning. Invalid bearer tokens cannot fall back to a
  website cookie. Shopify staff do not inherit application-wide administrator
  privileges or restart the workspace trial.
- Browser installation navigation redirects even when a website cookie exists;
  authenticated callers can explicitly request JSON with `format=json`.
- Embedded requests omit website cookies. Authentication errors show recovery
  controls instead of automatically restarting OAuth. Only the read-only
  `/auth/me` request receives one fresh-token retry when instructed by the API.
- App Bridge uses a conditional `beforeInteractive` script, shared loading,
  bounded waits, and recoverable loading failures. Store Sync distinguishes
  loading, connection errors, disconnection, and sync errors.
- Shopify queries use smaller initial pages and exhaust nested variant and order
  line-item pages. Throttled requests receive bounded retries. Failed database
  work rolls back before updating run status; duration uses a monotonic clock.

## Product improvements

- Inventory history offers 7, 30, 90, and 365 calendar-day views; cost, retail,
  and unit measures; available-history change; exact point values; a keyboard
  accessible chart; a data table; and CSV export.
- History respects calendar dates and preserves gaps. The 30-day summary uses
  a snapshot at or before the actual baseline date, returning no comparison when
  there is insufficient history. Empty history explains how to create it.
- Action Queue supports product/SKU/supplier search, confidence, stockout-window
  filters, and priority/impact/coverage sorting. Filters persist in the URL.
  Large result sets display incrementally; exports include every matching row.
- Exposure links open the corresponding filtered actions. Zero-value bars no
  longer imply a positive value. Dashboard and connection errors offer retries.
- Sample history is explicitly labeled, never substitutes for failed live data,
  and remains consistent when changing the selected period.

## Verification performed

From `backend/`, install test dependencies with
`python -m pip install -r requirements-dev.txt`, then run:

```powershell
python -m unittest discover -s tests -v
```

17 tests passed, using synthetic credentials, mocked Shopify responses, and
isolated in-memory SQLite. Coverage includes fresh install, reinstall, expiry,
parallel first requests, failed grants, callback workspace isolation, malformed
tokens, staff privileges, nested pagination, repeat-sync idempotence, throttling,
and calendar history with tenant isolation. No application database was modified.

From `frontend/`:

```powershell
node --test tests/*.test.cjs
npm run typecheck
npm run build
```

15 frontend tests, type checking, and the production build passed. All four sync
GraphQL queries passed Shopify plugin validation against its bundled 2026-04
Admin schema. Browser checks of the local production build confirmed chart
period/measure controls, consistent latest values, the data table, exposure
navigation, and stockout filtering. No warnings or errors were captured in the
final analytics browser check. Earlier error-path checks confirmed connection
failures present recovery controls.

These checks do not exercise Shopify's live authorization, production PostgreSQL
locking, hosting timeouts, or the App Store automated checks.

## Deployment notes and remaining verification

Deploy frontend and backend together. No schema migration or new production
environment variable is required. Existing Shopify client ID/secret, redirect
URLs, backend URL, and CORS configuration must agree with the Partner app.

The root layout now reads a middleware-derived embedded request header so App
Bridge is present before hydration only for embedded entry requests. This opts
pages using that root layout into dynamic rendering, including marketing pages;
allow for the increased server rendering load. A later split into independent
marketing and embedded root layouts can recover marketing prerendering. Verify
App Bridge initialization and Shopify's script detection in the deployed iframe.

Before resubmission, use a development store to verify:

1. Fresh managed install reaches the embedded dashboard without repeated OAuth.
2. Sync imports known products, variants, orders, and line items; a second sync
   creates no duplicates and the dashboard shows the imported inventory.
3. Reinstall, staff access, and an existing unrelated website login resolve the
   correct store. Test with third-party storage restricted.
4. Expired-token recovery and temporary API/network failures have working retry
   paths. Check deployed logs for callback errors or repeated redirects.
5. Test a realistically large catalog and order history within hosting limits.
6. Complete the remaining App Store checklist, then submit the tested release.

## Follow-up priorities identified

- Move large syncs to durable background jobs with progress, cancellation, and
  resumable checkpoints. Sync is still synchronous and can exceed host limits.
- Review privacy webhook data deletion and retention end to end; clearing a
  connection token alone does not establish that all requested data was removed.
- Carry store currency through API responses and formatting. Existing money
  displays use USD; non-USD stores need consistent currency-aware reporting.

References: [Shopify token exchange](https://shopify.dev/docs/apps/build/authentication-authorization/implement-token-exchange),
[access tokens](https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens),
and [App Bridge](https://shopify.dev/docs/api/app-bridge-library).
