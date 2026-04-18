# Shopify Integration Plan

## Goal

Replace in-memory mock SKU inputs with persisted, normalized Shopify-backed data while keeping the current `/actions` contract stable.

## Recommended Direction

Use a persistence-first approach.

Why:

- the engine should read stable normalized rows, not raw API responses
- persistence makes backfills, reprocessing, and debugging easier
- the action feed stays decoupled from Shopify request timing

## Proposed Flow

1. fetch Shopify catalog, inventory, and recent order data
2. normalize Shopify records into the internal SKU model
3. persist normalized rows and supporting raw or aggregate tables
4. load persisted normalized SKU rows into the existing engine
5. keep `/actions` response shape unchanged

## Likely Backend Modules

- `services/shopify_client`
  - API fetches and pagination
- `services/shopify_normalizer`
  - converts Shopify records into the internal SKU model
- `repositories/sku_repository`
  - loads normalized rows for the engine
- `repositories/settings_repository`
  - loads lead-time settings and buffers
- `services/ingestion_runner`
  - coordinates fetch, normalize, and persist steps

The exact folder layout can stay flexible, but these responsibilities should be separated.

## First Implementation Steps

- define persisted tables for:
  - normalized SKUs
  - inventory snapshots or current inventory state
  - recent sales aggregates or order-line facts
  - settings for lead times and buffers
- build a normalization path from Shopify variant + inventory + order data into the current SKU model
- add repository-backed loading for the engine
- keep `mock_data.py` available until the stored path is verified

## Risks

- vendor and category normalization may be messy and merchant-specific
- unit cost may be unavailable or low quality
- multi-location inventory rules need explicit decisions
- limited history windows can make dead-stock signals noisy for new products
- refunds and edited orders can distort sales aggregates if handled too simply

## Unresolved Questions

- what locations count toward sellable inventory in the first live version?
- how far back should the initial order ingest go?
- should sales aggregates be stored directly, or recomputed from persisted order-line facts?
- where should merchant-maintained lead-time settings live first: file-backed config or database tables?

## Definition Of Success

- engine reads persisted normalized SKU rows instead of mock data
- `/actions` stays compatible with the current frontend
- Shopify-specific complexity is isolated from the scoring service layer
