# Architecture

## Current System

The product is a multi-page inventory operations app with a FastAPI backend and a Next.js frontend. The backend persists Shopify ingestion data plus shop-scoped settings, then builds a prioritized action feed from DB-backed data when available.

## Current Flow

### Actions

1. frontend pages in `frontend/app/` load through the shared app shell
2. frontend fetch helpers in `frontend/lib/api.ts` call `GET /actions`
3. thin FastAPI routes in `backend/app/api/routes/` hand off to services
4. `backend/app/services/action_feed.py` derives engine input rows from persisted `products`, `inventory`, and `order_line_items`
5. `backend/app/services/inventory_engine.py` ranks `urgent`, `optimize`, and `dead` actions
6. if DB data is unusable and shop settings allow it, the backend falls back to `backend/app/mock_data.py`

### Store Sync

1. user submits `shopify_domain` and `access_token` from the Store Sync page
2. `POST /integrations/shopify/ingest` calls the ingestion service
3. Shopify payloads are fetched through `backend/app/integrations/shopify_client.py`
4. mapped records are persisted through `backend/app/services/shopify_ingestion.py`
5. sync-run status is stored in `shopify_sync_runs`

### Settings

1. frontend settings pages call `GET/PUT /shop-settings` and lead-time override endpoints
2. backend persists shop-scoped settings, vendor lead times, and category lead times
3. action generation resolves lead times from SKU override, DB vendor, DB category, shop default, then file fallback

## Current Components

- `frontend/app/`
  - App Router pages for dashboard, actions, analytics, store sync, lead-time settings, billing, and account
- `frontend/components/`
  - shell, feed, KPI, sync, and reusable UI components
- `frontend/lib/`
  - typed API client plus lightweight client-side hooks
- `backend/app/api/routes/`
  - thin route layer
- `backend/app/services/`
  - action generation, scoring, ingestion, and settings logic
- `backend/app/integrations/`
  - Shopify client and mapping layer
- `backend/app/db/`
  - SQLAlchemy models, sessions, and table initialization

## Current Limits

- no real auth
- no background jobs or webhooks
- no merchant-managed Shopify connection flow
- local development defaults to SQLite; production should use managed Postgres

## Deployment Shape

- deploy frontend from `frontend/`
- deploy backend from `backend/`
- set `NEXT_PUBLIC_API_BASE_URL` on the frontend
- set `DATABASE_URL` and `FRONTEND_ORIGIN` on the backend
