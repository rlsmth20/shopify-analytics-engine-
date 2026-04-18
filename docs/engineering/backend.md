# Backend

## Purpose

The backend owns the action-feed contract, manual Shopify ingest, and the inventory decision logic.

## Layers

### Route Layer

- location: `backend/app/api/routes`
- purpose: expose HTTP endpoints
- rule: keep route files thin

Current routes:

- `GET /health`
- `GET /actions`
- `GET /actions/debug-summary`
- `POST /integrations/shopify/ingest`
- `GET /integrations/shopify/sync-status`
- `GET /shop-settings`
- `PUT /shop-settings`
- `GET /shop-settings/vendor-lead-times`
- `PUT /shop-settings/vendor-lead-times`
- `GET /shop-settings/category-lead-times`
- `PUT /shop-settings/category-lead-times`
- `GET /skus`
- `GET /skus/{sku_id}`

### Schema Layer

- location: `backend/app/schemas.py`
- purpose: define strict request and response shapes plus the normalized SKU input model consumed by the engine

### Service Layer

- `backend/app/services/action_feed.py`
  - loads persisted product, inventory, and order data into normalized engine rows
  - applies per-shop lead-time settings
  - makes the DB-vs-mock fallback explicit
  - adds lightweight data-quality warnings to action output
- `backend/app/services/inventory_engine.py`
  - resolves lead times, calculates metrics, scores actions, and builds the action feed
- `backend/app/services/shopify_ingestion.py`
  - orchestrates manual Shopify ingest, creates a sync-run record, and returns processing counts
  - resolves the latest recorded sync status for one shop
- `backend/app/services/shop_settings.py`
  - resolves persisted shop settings or file defaults
  - upserts settings by `shopify_domain`
  - loads and saves shop-scoped vendor/category lead-time overrides

### Integration Layer

- location: `backend/app/integrations`
- purpose: wrap Shopify fetches and map Shopify payloads into internal records

### DB Layer

- location: `backend/app/db`
- purpose: define persisted `shops`, `shop_settings`, `vendor_lead_times`, `category_lead_times`, `shopify_sync_runs`, `products`, `inventory`, and `order_line_items` plus database session setup

### Config Layer

- location: `backend/app/config/lead_time.py`
- purpose: hold default lead-time inputs, vendor/category lead-time maps, and the default mock-fallback flag used when DB settings do not exist

### Mock Data Layer

- location: `backend/app/mock_data.py`
- purpose: provide fallback normalized SKU rows when the DB is empty or unavailable

## Current Behavior

- `POST /integrations/shopify/ingest` manually ingests one shop into PostgreSQL
- each manual ingest creates a `shopify_sync_runs` row, marks it `running`, then updates it to `succeeded` or `failed`
- `GET /integrations/shopify/sync-status` returns the latest recorded sync run for one `shopify_domain`
- `GET /shop-settings` returns persisted shop settings when they exist, otherwise file defaults for that domain
- `PUT /shop-settings` upserts persistent shop settings scoped by `shop_id`
- `GET /shop-settings/vendor-lead-times` and `PUT /shop-settings/vendor-lead-times` manage shop-scoped vendor lead-time overrides
- `GET /shop-settings/category-lead-times` and `PUT /shop-settings/category-lead-times` manage shop-scoped category lead-time overrides
- `GET /actions` prefers DB-backed SKU rows when a persisted shop catalog exists
- DB-backed lead-time resolution order is:
  - SKU override
  - DB vendor lead time
  - DB category lead time
  - shop-scoped global default from `shop_settings`
  - file-config fallback only when no DB lead-time settings exist for that shop
- action output includes `data_quality_confidence` and `data_quality_warnings` for weak DB inputs
- mock fallback is controlled by `allow_mock_fallback`
- if mock fallback is disabled and DB-backed data is not usable, `GET /actions` returns `503` instead of mock actions
- service layer computes:
  - velocity
  - days of inventory
  - resolved lead time
  - target coverage
  - urgency level
  - excess units
  - cash tied up
- healthy items are filtered out before `/actions` returns

## Near-Term Backend Work

- add tests
- store product cost from live data or settings
- replace manual ingest with persistent shop configuration
- add scheduled or webhook-triggered sync
