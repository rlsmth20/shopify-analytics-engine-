# Sprint 1

## Goal

Ship a usable mock-data MVP that proves the product as an inventory action feed.

## Completed

- [x] scaffold FastAPI backend
- [x] scaffold Next.js frontend
- [x] create mock SKU dataset
- [x] implement inventory decision engine
- [x] add urgent, optimize, and dead action outputs
- [x] add urgency levels and stockout messaging
- [x] add lead-time hierarchy and safety buffer handling
- [x] connect homepage to live `GET /actions`
- [x] document current API contract and engineering shape

## Remaining Outside Sprint 1

- backend automated tests
- persistence-backed ingestion
- Shopify integration planning and first implementation work

## Definition Of Done

- `/actions` returns a useful prioritized feed
- frontend renders that feed clearly
- docs describe the current system accurately
