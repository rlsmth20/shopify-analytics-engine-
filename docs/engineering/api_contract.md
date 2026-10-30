# API Contract

## `GET /actions`

Returns the prioritized inventory action feed used by the homepage.

Rules:

- sorted by `priority_score` descending
- only actionable statuses are returned
- `healthy` items are excluded
- source is DB-backed by default
- mock data is used only when the DB has no usable shop/product catalog or the DB read fails and `allow_mock_fallback` is `true`
- if mock fallback is disabled and DB-backed data is unusable, the endpoint returns `503`

Response shape:

- `data_source: "db" | "mock"`
- `actions: InventoryAction[]`

Example response:

```json
{
  "data_source": "db",
  "actions": [
    {
      "sku_id": "store-name.myshopify.com:SKU-001",
      "name": "Core Hoodie / Black / M",
      "status": "urgent",
      "recommended_action": "Reorder 24 units -> restores inventory to ~21 days (target ~21 days). Reorder within 2 days.",
      "explanation": "Stockout in 4.2 days; estimated profit at risk $960.",
      "days_of_inventory": 4.2,
      "lead_time_days_used": 14,
      "safety_buffer_days": 7,
      "lead_time_source": "global_default",
      "target_coverage_days": 21,
      "priority_score": 1228.5,
      "data_quality_confidence": "medium",
      "data_quality_warnings": [
        "Missing vendor; vendor lead-time overrides unavailable."
      ],
      "urgency_level": "high",
      "days_until_stockout": 4.2,
      "estimated_profit_impact": 960.0
    }
  ]
}
```

## `GET /actions/debug-summary`

Returns a minimal QA/debug view of persisted action-input coverage.

Response body:

- `shops: number`
- `products: number`
- `inventory_rows: number`
- `order_line_items: number`
- `distinct_skus_with_usable_action_data: number`

Example response:

```json
{
  "shops": 1,
  "products": 42,
  "inventory_rows": 42,
  "order_line_items": 118,
  "distinct_skus_with_usable_action_data": 42
}
```

## Shared Fields

Every action includes:

- `sku_id: string`
- `name: string`
- `status: "urgent" | "optimize" | "dead"`
- `recommended_action: string`
- `explanation: string`
- `days_of_inventory: number`
- `lead_time_days_used: number`
- `safety_buffer_days: number`
- `lead_time_source: "sku_override" | "vendor" | "category" | "global_default"`
- `target_coverage_days: number`
- `priority_score: number`
- `data_quality_confidence: "high" | "medium" | "low"`
- `data_quality_warnings: string[]`

## Urgent Fields

- `urgency_level: "critical" | "high" | "medium"`
- `days_until_stockout: number`
- `estimated_profit_impact: number`

## Optimize And Dead Fields

- `excess_units: number`
- `cash_tied_up: number`

## `POST /integrations/shopify/sync`

Queues a sync of the caller's connected Shopify store. Requires an active
session with access (`require_active_access`).

Side effect:

- creates a `shopify_sync_runs` record with status `queued` and returns at once
- a background thread marks the run `running`, imports products, inventory, and recent orders, then stores the outcome on the run
- only one run per shop may be `queued` or `running` at a time

Response body (`202`):

- `run_id: number`
- `status: "queued"`
- `triggered_by: "manual" | "scheduled"`
- `started_at: string`
- `finished_at: null`
- `error_message: null`
- `result: null`

Errors:

- `400` when the workspace has no active Shopify connection
- `409` when a run for this shop is already queued or running (poll the status route)

## `GET /integrations/shopify/sync/status`

Returns one sync run, or the latest, for the caller's shop only.

Query params:

- `run_id: number` (optional; omit for the latest run)

Response body:

- `run_id: number`
- `status: "queued" | "running" | "succeeded" | "partial" | "failed"`
- `triggered_by: string`
- `started_at: string | null`
- `finished_at: string | null`
- `error_message: string | null`
- `result: object | null` (the sync summary rendered by the Store Sync page; present once the run finished)

Errors:

- `404` when the run does not exist or belongs to another shop

## `GET /shop-settings`

Returns effective shop settings for a `shopify_domain`.

Query params:

- `shopify_domain: string`

Response body:

- `shop_id: number | null`
- `shopify_domain: string`
- `global_default_lead_time_days: number`
- `global_safety_buffer_days: number`
- `allow_mock_fallback: boolean`
- `is_persisted: boolean`

If no settings row exists yet, the endpoint returns file defaults for that domain with `is_persisted: false`.

## `PUT /shop-settings`

Upserts shop settings for a `shopify_domain`.

Request body:

- `shopify_domain: string`
- `global_default_lead_time_days: number`
- `global_safety_buffer_days: number`
- `allow_mock_fallback: boolean`

Returns the persisted settings row in the same shape as `GET /shop-settings`.

## `GET /shop-settings/vendor-lead-times`

Returns shop-scoped vendor lead-time overrides for a `shopify_domain`.

Query params:

- `shopify_domain: string`

Response body:

- `shop_id: number | null`
- `shopify_domain: string`
- `items: Array<{ vendor: string, lead_time_days: number }>`

## `PUT /shop-settings/vendor-lead-times`

Replaces the full vendor lead-time override list for a `shopify_domain`.

Request body:

- `shopify_domain: string`
- `items: Array<{ vendor: string, lead_time_days: number }>`

## `GET /shop-settings/category-lead-times`

Returns shop-scoped category lead-time overrides for a `shopify_domain`.

Query params:

- `shopify_domain: string`

Response body:

- `shop_id: number | null`
- `shopify_domain: string`
- `items: Array<{ category: string, lead_time_days: number }>`

## `PUT /shop-settings/category-lead-times`

Replaces the full category lead-time override list for a `shopify_domain`.

Request body:

- `shopify_domain: string`
- `items: Array<{ category: string, lead_time_days: number }>`

Lead-time resolution order for DB-backed actions:

- SKU override
- vendor lead time from `vendor_lead_times`
- category lead time from `category_lead_times`
- shop global default from `shop_settings`
- file-config fallback only when the shop has no DB lead-time settings yet

## Example: urgent

```json
{
  "sku_id": "sku_crop-hoodie-rose-s",
  "name": "Crop Hoodie / Rose / S",
  "status": "urgent",
  "recommended_action": "Reorder 52 units -> restores inventory to ~26 days (target ~26 days). Reorder within 1 day.",
  "explanation": "Stockout in 2.7 days; estimated profit at risk $2,048.",
  "days_of_inventory": 2.7,
  "lead_time_days_used": 19,
  "safety_buffer_days": 7,
  "lead_time_source": "vendor",
  "target_coverage_days": 26,
  "priority_score": 1439.47,
  "data_quality_confidence": "high",
  "data_quality_warnings": [],
  "urgency_level": "critical",
  "days_until_stockout": 2.7,
  "estimated_profit_impact": 2048.0
}
```

## Example: optimize

```json
{
  "sku_id": "sku_longline-tee-white-xl",
  "name": "Longline Tee / White / XL",
  "status": "optimize",
  "recommended_action": "Slow purchasing and work down roughly 145 excess units before placing the next replenishment order.",
  "explanation": "Cash tied up $1,740; inventory cover is far above the 21-day target.",
  "days_of_inventory": 800.0,
  "lead_time_days_used": 14,
  "safety_buffer_days": 7,
  "lead_time_source": "global_default",
  "target_coverage_days": 21,
  "priority_score": 603.5,
  "data_quality_confidence": "medium",
  "data_quality_warnings": [
    "Missing vendor; vendor lead-time overrides unavailable."
  ],
  "excess_units": 145,
  "cash_tied_up": 1740.0
}
```

## Example: dead

```json
{
  "sku_id": "sku_archived-crew-sage-xs",
  "name": "Archived Crew / Sage / XS",
  "status": "dead",
  "recommended_action": "Pause reorders and clear 74 stale units with a markdown, bundle, or liquidation plan.",
  "explanation": "No recent sales; capital tied up $1,554 in stale inventory.",
  "days_of_inventory": 999.0,
  "lead_time_days_used": 14,
  "safety_buffer_days": 7,
  "lead_time_source": "global_default",
  "target_coverage_days": 21,
  "priority_score": 322.5,
  "data_quality_confidence": "low",
  "data_quality_warnings": [
    "Missing category; category lead-time overrides unavailable.",
    "Missing price; profitability estimates may be unreliable."
  ],
  "excess_units": 74,
  "cash_tied_up": 1554.0
}
```

## Example: manual ingest response

```json
{
  "shops": {
    "processed": 1,
    "inserted": 1,
    "updated": 0,
    "skipped": 0
  },
  "products": {
    "processed": 42,
    "inserted": 42,
    "updated": 0,
    "skipped": 0
  },
  "inventory_rows": {
    "processed": 42,
    "inserted": 42,
    "updated": 0,
    "skipped": 0
  },
  "order_line_items": {
    "processed": 118,
    "inserted": 118,
    "updated": 0,
    "skipped": 0
  }
}
```

## Example: shop settings response

```json
{
  "shop_id": 1,
  "shopify_domain": "store-name.myshopify.com",
  "global_default_lead_time_days": 21,
  "global_safety_buffer_days": 10,
  "allow_mock_fallback": false,
  "is_persisted": true
}
```

## Example: vendor lead times response

```json
{
  "shop_id": 1,
  "shopify_domain": "store-name.myshopify.com",
  "items": [
    {
      "vendor": "Summit Sportswear",
      "lead_time_days": 19
    },
    {
      "vendor": "Trailhead Accessories",
      "lead_time_days": 22
    }
  ]
}
```

## Example: category lead times response

```json
{
  "shop_id": 1,
  "shopify_domain": "store-name.myshopify.com",
  "items": [
    {
      "category": "outerwear",
      "lead_time_days": 18
    },
    {
      "category": "tops",
      "lead_time_days": 12
    }
  ]
}
```
