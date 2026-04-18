# Shopify Ingestion

This document describes the Shopify data needed to replace the current mock SKU rows without changing the existing inventory engine contract.

## Current Engine Input

The backend consumes one normalized row per sellable SKU, which should map to a Shopify variant.

Required normalized fields:

- `sku_id`
- `name`
- `vendor`
- `category`
- `price`
- `cost`
- `inventory`
- `last_30_day_sales`
- `last_7_day_sales`
- `days_since_last_sale`
- optional `sku_lead_time_days`

## Required Shopify Data For MVP

### Catalog

- Shopify variant id
- product title
- variant title or option values
- vendor
- product type or equivalent category signal
- current selling price
- unit cost if available

### Inventory

- current sellable quantity for each included variant
- location inclusion rules for the MVP inventory total

### Sales History

- order timestamp
- order cancellation state
- line item variant id
- line item quantity

This is enough to derive the fields the current engine needs.

## Optional Data

- merchant SKU string
- barcode
- compare-at price
- product tags or collections
- location-level inventory detail
- refund and return detail
- variant creation date

Useful later, but not required to run the current engine.

## Data That Must Come From Merchant Settings

Shopify is not the system of record for the current lead-time model.

These inputs should come from settings:

- global default lead time
- global safety buffer
- vendor lead times
- category lead times
- SKU-specific lead time overrides

Reason:

- Shopify does not reliably provide supplier planning data
- these values need merchant control and fallback behavior

## Normalized Internal SKU Model

```ts
type NormalizedSku = {
  sku_id: string;
  name: string;
  vendor: string;
  category: string;
  price: number;
  cost: number;
  inventory: number;
  last_30_day_sales: number;
  last_7_day_sales: number;
  days_since_last_sale: number;
  sku_lead_time_days?: number | null;
};
```

Guidance:

- use Shopify variant id as `sku_id`
- build `name` from product title plus variant title or options
- normalize vendor and category strings before the engine sees them

## Derivations

### `last_30_day_sales`

Sum units sold for the variant over the trailing 30 days, excluding cancelled orders.

### `last_7_day_sales`

Sum units sold for the variant over the trailing 7 days, excluding cancelled orders.

### `days_since_last_sale`

Find the most recent qualifying sale for the variant and compute whole days since that timestamp.

If no qualifying sale exists in the available history:

- use a high sentinel such as `999` for now

### `current inventory`

Sum included sellable quantity across the locations counted by the MVP rules.

## Lead Time In Current Design

Lead time does not come from Shopify today.

The engine resolves it in this order:

1. SKU override
2. vendor lead time
3. category lead time
4. global default

The engine also adds the global safety buffer to derive `target_coverage_days`.

## Likely Data Quality Issues And Shopify Limits

- variant SKU strings may be blank or duplicated, so use variant id as the stable key
- vendor and category values are merchant-managed text and require normalization
- unit cost may be missing or stale
- multi-location inventory can be misleading if some stock is not truly available
- incomplete order history will distort `days_since_last_sale`
- refunds, edits, and bundles can complicate simple unit-based sales aggregation
- Shopify does not directly solve lead times, buffers, or supplier planning inputs
