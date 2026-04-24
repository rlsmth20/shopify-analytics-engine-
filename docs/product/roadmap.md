# Roadmap

## Phase 1: Mock-Data MVP And Action Feed

Completed or in place now:

- backend action engine with urgent, optimize, and dead outputs
- lead-time hierarchy and safety buffer handling
- frontend homepage connected to live `/actions`
- lean product and engineering documentation

Still useful within Phase 1:

- backend tests for scoring and lead-time resolution
- simple ingest path for mock or CSV inventory data
- editable config path for lead-time settings

## Phase 2: Shopify Integration And Persistence

Near-term target:

- define persistence model for normalized SKU rows and sales aggregates
- ingest Shopify variants, inventory, and order history into stored tables
- swap the engine input from in-memory mock data to persisted normalized data
- keep the current `/actions` contract stable while changing the data source

## Phase 2.5: Intelligence Surface (Shipped 2026-04-23, v0.2.0)

Additive layer on top of v1. All surfaces use deterministic mock data until Shopify
ingestion is wired; every route is already public and typed end-to-end.

- forecasting: Holt double-exponential smoothing, weekly seasonality, stockout prob
- classification: ABC by revenue, XYZ by demand CV, combined scorecards
- replenishment: safety-stock / reorder-point / EOQ, service-level segmented control
- supplier scorecards and tiering (preferred / acceptable / at-risk)
- bundle / kit bottleneck analysis
- multi-location transfer recommendations
- dead-stock liquidation plans (markdown / bundle / wholesale / write-off)
- alert rule engine with email, SMS, Slack, and webhook delivery
- redesigned dashboard with chart library and "What should I do today?" rail

## Later Phases

- persist alert rules and channel config (currently in-memory)
- Shopify ingestion swap — feed real history into the forecasting/reorder pipeline
- lead times informed by observed restock history, not merchant input alone
- approval / send flow for draft purchase orders
- audit log + snapshot history for decision explainability
- workspace roles, SSO, and multi-store account model
