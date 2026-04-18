# Sprint 2

## Goal

Define and begin the persistence-first path from mock data to Shopify-backed inventory inputs without breaking the current `/actions` contract.

## Tasks

- [ ] finalize Shopify ingestion design and integration plan
- [ ] define persisted normalized SKU model and supporting tables
- [ ] add backend modules for ingestion, normalization, and repository access
- [ ] implement first stored data path for variants, inventory, and recent sales aggregates
- [ ] add tests around ingestion normalization and engine compatibility

## Definition Of Done

- Shopify integration plan is documented and actionable
- persistence model for normalized engine inputs is defined
- first backend implementation path exists for loading stored normalized SKU rows into the engine
- current frontend and `/actions` response shape remain intact
