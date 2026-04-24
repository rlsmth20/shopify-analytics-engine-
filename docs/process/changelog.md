# Changelog

## 2026-04-23 — Inventory Command API v0.2.0

Ships the v2 intelligence surface alongside the existing v1 action feed. Nothing from
v1 is removed; all additions are additive.

### Backend

- added Holt double-exponential demand forecasting with weekly seasonality detection
  and erf-based stockout probability (`services/forecasting.py`)
- added ABC/XYZ scorecards with 80/95 revenue cutoffs and CV-based volatility
  classification (`services/abc_analysis.py`)
- added reorder optimizer: safety stock, reorder point, and EOQ with per-service-level
  z-scores (`services/reorder_optimizer.py`)
- added supplier scoring (on-time / fill / lead variance / cost stability) with
  preferred / acceptable / at-risk tiering (`services/supplier_scoring.py`)
- added multi-channel notifications with Twilio, SMTP, Slack webhook, and generic
  webhook drivers, plus an in-memory dev sink fallback (`services/notifications.py`)
- added alert rule engine with stockout-risk, dead-stock, overstock, forecast-miss,
  and supplier-slip triggers (`services/alerts.py`)
- added bundle/kit bottleneck analyzer (`services/bundle_analyzer.py`)
- added vendor-grouped PO drafts with expected arrival dates (`services/purchase_orders.py`)
- added dead-stock liquidation plan with markdown / bundle / wholesale / write-off
  tactics (`services/dead_stock.py`)
- added multi-location transfer recommender targeting 30-day cover
  (`services/transfers.py`)
- added dashboard aggregator with KPIs, trend, health breakdown, top movers, ABC mix,
  cash by vendor, and forecast-vs-actual (`services/dashboard.py`)
- added nine new routers: `/dashboard`, `/forecast`, `/analytics/scorecards`,
  `/reorder`, `/suppliers`, `/bundles`, `/transfers`, `/liquidation`, `/alerts/*`
- bumped app title to "Inventory Command API" and version to 0.2.0

### Frontend

- rebuilt the dashboard as a command center with sparklines, donut, area, diverging,
  and horizontal bar charts plus a "What should I do today?" action strip
- added pages for forecast detail, ABC/XYZ analytics, suppliers, purchase orders (with
  service-level segmented control), inter-location transfers, bundle health, dead-stock
  liquidation, and alerts/rules/channels/history
- added a dependency-free SVG chart library (`components/charts.tsx`)
- grouped sidebar nav into Command / Intelligence / Operations / Settings sections
- extended the design system (`app/globals.css`) with chart palette tokens, KPI card
  tones, score rings, tier boxes, tactic pills, and responsive layout rules

## 2026-04-17

- scaffolded FastAPI backend and Next.js frontend
- added mock SKU data and the first inventory decision engine
- created `GET /actions`, `GET /skus`, and `GET /skus/{sku_id}`
- refined action scoring into urgent, optimize, and dead outputs
- added urgency levels, days-until-stockout messaging, and status-specific action fields
- added lead-time hierarchy with SKU, vendor, category, and global fallback inputs
- connected the homepage to the live backend `/actions` feed
- added and aligned product, process, and engineering docs to the implemented system
