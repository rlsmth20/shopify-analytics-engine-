# Changelog

## 2026-04-17

- scaffolded FastAPI backend and Next.js frontend
- added mock SKU data and the first inventory decision engine
- created `GET /actions`, `GET /skus`, and `GET /skus/{sku_id}`
- refined action scoring into urgent, optimize, and dead outputs
- added urgency levels, days-until-stockout messaging, and status-specific action fields
- added lead-time hierarchy with SKU, vendor, category, and global fallback inputs
- connected the homepage to the live backend `/actions` feed
- added and aligned product, process, and engineering docs to the implemented system
