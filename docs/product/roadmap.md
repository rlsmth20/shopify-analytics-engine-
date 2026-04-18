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

## Later Phases

- settings persistence and admin flows
- improved forecasting and seasonality handling
- multi-location inventory logic
- lead times informed by restock history in addition to merchant settings
