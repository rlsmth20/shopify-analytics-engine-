# Vision

## Who This Is For

- Shopify merchants with enough SKU count that inventory decisions are no longer obvious
- operators who need to know what to do next, not just what happened
- small teams that do not have dedicated supply chain tooling

## Product Direction

This product is a prioritized inventory action feed, not a dashboard.

The main interface should answer:

- what to reorder
- what is overstocked
- what is dead stock
- what to do first

## Jobs To Be Done

- surface SKUs that are about to stock out
- surface SKUs tying up cash in excess inventory
- surface SKUs that have gone stale and need markdown or liquidation decisions
- rank actions so the merchant can work the feed from top to bottom

## Differentiation

- focused on supply-chain-style decisions, not generic commerce analytics
- explains recommended action, urgency, and lead-time context in the same view
- optimized for execution, not reporting

## Current Product State

- FastAPI backend generates prioritized actions from mock SKU data
- Next.js homepage fetches the live `/actions` feed
- no Shopify integration, database, or auth yet
