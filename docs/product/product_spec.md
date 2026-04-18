# Product Spec

## Current MVP

The MVP is a working inventory action feed backed by a FastAPI decision engine and rendered on a Next.js homepage.

### In Scope Now

- homepage action feed grouped into:
  - `urgent`
  - `optimize`
  - `dead`
- backend `GET /actions` endpoint with prioritized output
- mock SKU dataset and mock lead-time configuration
- lead-time resolution by hierarchy:
  - SKU override
  - vendor
  - category
  - global default
- frontend loading, error, and empty states

### Current Action Fields

Shared fields:

- `sku_id`
- `name`
- `status`
- `recommended_action`
- `days_of_inventory`
- `lead_time_days_used`
- `safety_buffer_days`
- `lead_time_source`
- `target_coverage_days`
- `priority_score`

Urgent fields:

- `urgency_level`
- `days_until_stockout`
- `estimated_profit_impact`

Optimize and dead concepts:

- `excess_units`
- `cash_tied_up`

### Current Feed Behavior

- healthy items are excluded from the homepage feed
- urgent items are ranked highest
- optimize and dead actions are ranked using tied-up capital and inventory severity
- recommendation copy is action-oriented rather than descriptive

## Not Implemented Yet

- Shopify auth
- Shopify data sync
- persisted inventory or settings storage
- editable settings UI
- SKU detail page
- charts or dashboard views
- background jobs or scheduled refresh

## Future Ideas

- persisted settings for lead times and buffers
- first-class ingest pipeline for mock and CSV data
- improved forecasting beyond trailing sales windows
- multi-location inventory handling
- lead times derived partly from historical restock behavior
