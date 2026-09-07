# Growth and merchant product release — September 7, 2026

Shopify Partners showed the Skubase listing as **Submitted**, not published. This release gives merchants a useful inventory diagnostic without requiring app installation, makes the merchant and owner dashboards easier to read, and fixes observed billing and forecast defects. It introduces no advertising spend, new dependencies, database migrations, or increase to the rolling 20-new-merchant ceiling.

## Product behavior

- `/tools/inventory-health-check` accepts up to 1,000 unique SKU summaries in 500 KB of CSV, calculates coverage/reorder triggers/above-target stock, and exports results with currency and planning assumptions. All SKU processing stays in the browser. No-sales and missing-cost values remain unknown; zero sales does not establish dead stock. The tool explains its limited demand assumptions and distinguishes reorder triggers from order quantities.
- Sample runs, invalid data and explicit demo URLs do not generate tool-use evidence. Real use emits only the existing bounded growth event, page and attribution, without SKU entries. Leaving the sample workspace to use the real public health tool no longer inherits a stale telemetry exclusion; DNT and actual sample-workspace exclusions remain intact. A free review handoff preserves the `inventory-health-check-v1` campaign. Review request, thank-you, reorder calculator, demo banner and public footer link to the tool.
- Merchant dashboards have visible chart bars and centered donut totals, actual dates and units, expandable value tables, and KPI descriptions that distinguish recorded order revenue from current catalog-price estimates. Unrelated revenue sparklines no longer appear on inventory KPIs. The demo's forecast variance compares five products, matching production semantics.
- Action Queue adds a comparison table with coverage, lead time, replenishment quantity, financial exposure and confidence. Unknown coverage no longer sorts as an imminent stockout. Narrow screens have a compact app menu and contained table scrolling instead of whole-page horizontal overflow.
- Owner growth dashboard separates mission-period and all-history observations, shows daily contacts versus substantive replies, and compares preserved channel/experiment/ICP/offer/message-version cohorts. Unlinked conversions and missing costs stay unknown. Automated replies and existing stores cannot inflate new customer progress.
- Seven-day forecast variance now sums the actual seven-day prediction points instead of prorating a 30-day projection. An undefined zero prediction is omitted, while observed zero sales against positive demand stays a valid negative variance.
- Billing webhooks acknowledge only successful persistence, safely reconcile replay and ordering, and execute synchronous provider work outside the API event loop. Legacy overdue Stripe accounts can open their existing portal to update payment details. Shopify billing keeps precedence. See the separate billing reliability review for provider reconciliation limits.

## Learning and service fulfillment

New requested-service drafts use the browser health check first, identify Skubase and include its App Store review status. Earlier permitted bodies remain unchanged. A template revision closes enrollment in an older service cohort and starts a separate cohort; it does not mix workflows or resend messages.

Organic experiment attribution uses an explicit campaign or validated experiment page. A different campaign cannot enter through a matching page path. New tool-acquired stores require this campaign's request, verified identity linkage and the first verified connection strictly later than the request. Existing connections/reconnects remain baseline. This is observational attribution, not proof of causation.

After deployment, enroll the new organic experiment using `docs/growth/inventory-health-check-experiment.md` and activate the versioned requested-service skill using retained deployment and validation evidence. These operational actions do not send merchant messages.

## Verification

- Full isolated backend suite: **144 passed**.
- Full frontend suite: **72 passed**; TypeScript check and production build passed.
- Browser checks: sample calculations (3 SKUs, 1 stockout risk, 151 above-target units at $1,208), priority filtering, invalid-negative-stock rejection, demo CTA and request handoff, expandable merchant values/comparison, mobile menu navigation, growth period toggle, synthetic cohort chart, and narrow-screen containment at 390 pixels.
- CSV round trips, formula-safe exports, missing costs, sample detection, planning assumptions, limits, attribution, signed synthetic webhooks, replay, suppression and persistent growth behavior have focused regression coverage.
- Browser fixtures used isolated SQLite and synthetic merchants. No synthetic replies, connections or payments were inserted into production. No real outreach or provider financial actions were performed by these checks.

## Production rollout

Commit `711bf8a` was deployed from an immutable archive. Vercel deployment `dpl_FGzonmHdZRkJT5p8GMVLcyur9Ye3` is ready at `www.skubase.io`; Railway deployment `42b79ff0-7130-4fe6-b7bc-d042ae3d9c77` succeeded. API health, public tool and sitemap returned 200; anonymous access to the growth API returned 401. The live tool loaded and ran synthetic sample inputs.

Retained release evidence is `5151`. Requested-service skill version **3** is active, along with browser-service experiment `97b00298aa2b4c58a7443ddfe727c78a`. Organic experiment `inventory-health-check-v1` is enrolled as `e80c93819dd649a380e33a92c4fc3661`. The worker was running and unpaused after deployment, with no active model call, 13 of 20 first-contact slots used, 7 remaining and no unresolved reservations. Newly qualified users remained 0; this release does not claim customer acquisition from simulated checks.

Preserve the previous immutable release for rollback; no schema downgrade is needed. The audited skill workflow can reactivate version 2 if the service revision needs rollback. Preserve all experiment evidence and original message bodies.
