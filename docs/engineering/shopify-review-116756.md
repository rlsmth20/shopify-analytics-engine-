# Shopify review 116756: installation, sync, and analytics

## Evidence and scope

The reviewer reports a prolonged OAuth loop followed by inability to sync. The
recording ends with an Internal Server Error after approving Shopify access;
earlier frames show a website login and an unconnected workspace.

An isolated reproduction identified a matching callback failure: reconnecting an
already installed Shopify domain from a separate website workspace attempted to
assign the same unique domain to a second Shop. Production logs are still needed
to confirm that this was the exact exception in the recording.

The repairs were deployed to Vercel and Railway on September 6, 2026, through
commits `c925fcf` and `7c8449f`. Both deployment checks succeeded. They have not
been submitted to Shopify.
The subsequent inventory-trust, support, and pricing pass was deployed as
`359dfa5`; Vercel and Railway both reported success. No migration was required.
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
- App Bridge uses a conditional synchronous CDN script, shared loading,
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
- Complete catalog traversal reconciles planning inventory with active, tracked,
  non-gift-card Shopify variants. Deleted, archived, draft, untracked, prior CSV,
  and superseded location inventory is retired only after every product page is
  validated. Product and order history is retained; other shops are unaffected.
- Sync receipts distinguish eligible planning inventory, newly imported order
  lines, already imported lines, unmatched items, and incomplete order history.
  A valid empty 60-day paid-order window does not tell the merchant to reconnect.
  Invalid order roots/cursor loops fail; order pages commit only after traversal.
- Unknown or insufficient sales history yields a low-confidence monitoring task,
  never liquidation, excess-cash claims, or an overstock alert. Cards and reports
  explain missing history instead of presenting the legacy 999-day sentinel as
  measured cover. Existing demand can still produce a low-confidence reorder
  warning. A prior inventory snapshot becomes zero when the catalog empties.
- Support requests require an actual reply email and acknowledge success only
  after the provider accepts delivery. Synthetic Shopify login identities are
  not prefilled as mailboxes. All automated email tests mock delivery.
- Annual pricing equivalents, feature limits, comparison prices and Stocky
  retirement/migration copy are corrected. Billing amounts are unchanged.

## Verification performed

From `backend/`, install test dependencies with
`python -m pip install -r requirements-dev.txt`, then run:

```powershell
python -m unittest discover -s tests -v
```

61 tests passed, using synthetic credentials, mocked Shopify responses, and
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

25 frontend tests, type checking, and the production build passed. All four sync
GraphQL queries passed Shopify plugin validation against its bundled 2026-04
Admin schema. Browser checks of the local production build confirmed chart
period/measure controls, consistent latest values, the data table, exposure
navigation, and stockout filtering. No warnings or errors were captured in the
final analytics browser check. Earlier error-path checks confirmed connection
failures present recovery controls.

The initial live test reproduced a blocked accounts.shopify.com iframe on the
old deployment. The first repaired deployment exposed App Bridge's rejection of
Next's asynchronous beforeInteractive loader. Commit `7c8449f` replaces it with
a native synchronous CDN script and makes the recovery loader synchronous too.
A production HTML check confirms it is the first blocking external script and
does not appear on the public pricing page. Live uninstall/reinstall on the
development store `skubase_test` then reached the embedded dashboard without
repeated OAuth. The canonical existing workspace and subscription were retained.
Two manual syncs completed at 13:31:29 and 13:32:13 local time on September 6:
17 products, 26 variants, and zero eligible orders. Shopify's newest existing
orders were June 12, outside the 60-day access window, explaining the empty result.

After deploying `359dfa5`, a live sync completed at 13:50:17 with 17 products,
26 scanned variants, 19 eligible planning variants, seven excluded variants and
zero eligible orders. The receipt confirms outdated inventory was retired. The
dashboard now contains 19 current variants instead of 76 combined old/current
rows, and the Action Queue contains only current catalog products. Older retained
orders still support stale-stock signals for those products. The live pricing
toggle shows $24.67/$84.17/$169.17 equivalents with $296/$1,010/$2,030 billed
yearly. A bounded production error-log check returned no matching errors.
Repeating the deployed sync at 13:53:29 returned the same 26 scanned / 19 eligible
variants, seven exclusions, zero eligible orders, and no further retired inventory.

A one-item developer draft was prepared to verify a current paid order. Automatic
approval review initially blocked marking the $749.95 development draft as paid.
The user subsequently authorized completing the test and submission. The old
browser connection then stopped responding; the replacement browser currently
required Shopify Partners login. The user's existing signed-in Chrome window
was subsequently reached with the installed Computer Use plugin. Shopify's
automated checks had expired after 30 days; a new run was started on the App
Store review page. The listing check displayed "Error checking app listing. You
can submit for review without it." Other preliminary configuration and embedded
checks displayed as complete. Before the fresh paid-order test, Computer Use
stopped because it could not confidently determine Chrome's current URL to
enforce policy. No further browser input was issued in that turn. The new checks'
completion, live paid-order test, and resubmission are still unverified.
No charge, invoice, or customer message was issued. Do not
treat automated paid-order tests as a completed live paid-order check or Shopify
approval.

The final code review added transactional privacy deletion, merchant-only customer
access exports, delayed-webhook reinstall protection, and nine privacy tests.
Settings tolerate blocked local storage. Signup and configuration no longer ask
merchants to enter a Shopify domain. Privacy disclosures now describe actual
retained order fields, hosting, billing, email, and optional AI processors.
The retired Stripe webhook now rejects unsigned requests even if Stripe
configuration is missing; five regression tests cover real signature validation
and protection against unauthorized subscription activation.

Commit `5d7cc9a` deployed successfully to Vercel and Railway. The live privacy
page returns HTTP 200 and includes the updated processor and access-request
disclosures. The billing signature repair is included in the subsequent commit.
Both production customer-access list and individual-download endpoints return
HTTP 401 without authentication.

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
- Verify privacy webhook registration and provider backup retention. Production
  database deletion and export handling are implemented and tested; backup
  schedules remain an operational check.
- Carry store currency through API responses and formatting. Existing money
  displays use USD; non-USD stores need consistent currency-aware reporting.
- Reconcile order edits, cancellations and refunds. Existing imported line IDs
  currently skip updates, so a corrected quantity can leave stale demand history.
- Verify saved purchase orders and partial receiving end to end. They already
  exist; harden duplicate/over-quantity receipts, confirm open-order netting, and
  replace the supplier observation loader's assumed 14-day lead-time baseline.

The sales-history guard is intentionally conservative and uses no new database
field: at least 30 days since a recorded positive sale, plus a successful Shopify
sync no older than two days when sync metadata exists. It is a warning heuristic,
not proof of uninterrupted coverage or product age. Established CSV history with
no Shopify sync metadata retains prior behavior. Durable coverage windows and
historical stockout observations are still needed for richer forecasting.

References: [Shopify token exchange](https://shopify.dev/docs/apps/build/authentication-authorization/implement-token-exchange),
[access tokens](https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens),
and [App Bridge](https://shopify.dev/docs/api/app-bridge-library).
