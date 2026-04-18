# Decisions

## Action Feed Instead Of Dashboard

Decision:

- the core product is a prioritized action feed

Why:

- the current user problem is operational prioritization, not analytics browsing
- a feed forces the product to recommend action, not just display metrics

## Thin Routes, Logic In Services

Decision:

- FastAPI route files stay thin

Why:

- scoring, lead-time resolution, and action generation need to stay testable and reusable
- route files should only handle HTTP wiring

## Lead-Time Hierarchy Outside Shopify

Decision:

- lead times and safety buffers come from settings, not Shopify

Why:

- Shopify is not a reliable source of supplier planning inputs
- merchants need explicit override control at SKU, vendor, category, and global levels

## Persistence-First Direction For Shopify Data

Decision:

- live Shopify integration should persist normalized data before the engine consumes it

Why:

- it gives the engine stable inputs
- it makes reprocessing, debugging, and testing easier
- it avoids coupling action generation directly to API fetch timing

## Mock First, Shopify Later

Decision:

- stabilize the engine and feed contract before wiring live commerce data

Why:

- it reduces moving parts while the product definition is still settling

## Use All Shopify Locations In V1

Decision:

- use all Shopify locations for initial inventory calculations

Why:

- it keeps the first live inventory path simple
- location-specific inclusion rules can be added later when real merchant needs are clearer

## Use 60 Days Of Order History

Decision:

- ingest the last 60 days of order data for the first live velocity path

Why:

- it covers the current 7-day and 30-day calculations with some buffer
- it keeps the first ingest smaller than a full historical backfill

## Persist Raw Order Line Items

Decision:

- persist raw order line items and compute 7-day and 30-day sales dynamically

Why:

- raw facts are easier to reprocess if aggregation rules change
- it avoids locking the first integration into one precomputed rollup shape

## Persist Shop Settings In The Database

Decision:

- persist shop settings, vendor lead times, and category lead times in the database

Why:

- lead times need to be scoped per shop once live ingestion is in place
- persisted settings make live action generation deterministic and easier to debug

## Ignore Refunds And Bundle Decomposition In V1

Decision:

- ignore refunds and bundle decomposition in V1 and treat line items as-is

Why:

- it reduces first-pass ingestion complexity
- the current goal is to get a stable live input path before handling harder commerce edge cases

## Multi-Page Frontend Shell

Decision:

- move from a single-page UI to a multi-page app shell

Why:

- dashboard, actions, store sync, and settings are different operational jobs
- separating them improves scanability without changing the backend contract
