# Inventory Command

Inventory Command is a monorepo for a Shopify-focused inventory action product. The backend ingests one shop at a time, persists normalized Shopify data plus shop-scoped settings, and generates prioritized inventory actions. The frontend is a multi-page Next.js app shell for operations: dashboard, actions, store sync, and lead-time settings.

## Repo Structure

- `frontend/`
  - Next.js App Router app
  - multi-page SaaS shell
  - fetches the backend over HTTP only
- `backend/`
  - FastAPI app
  - SQLAlchemy models and DB setup
  - inventory action engine, Shopify ingestion, and settings services
- `docs/`
  - product, process, and engineering docs

There are no cross-imports between `frontend/` and `backend/`. They are separate deployable apps in one repo.

## Local Backend

From `backend/`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m app.db.init_db
uvicorn app.main:app --reload --port 8000
```

Default local database:

- `DATABASE_URL=sqlite:///./shopify_analytics_engine.db`

That default now works locally without PostgreSQL. If you want PostgreSQL instead, set `DATABASE_URL` before running `init_db` or `uvicorn`.

Backend entry point:

- `uvicorn app.main:app --reload --port 8000`

Useful backend endpoints:

- `GET /health`
- `GET /actions`
- `GET /actions/debug-summary`
- `POST /integrations/shopify/ingest`
- `GET /integrations/shopify/sync-status`
- `GET /shop-settings`
- `PUT /shop-settings`
- `GET /shop-settings/vendor-lead-times`
- `PUT /shop-settings/vendor-lead-times`
- `GET /shop-settings/category-lead-times`
- `PUT /shop-settings/category-lead-times`

## Local Frontend

From `frontend/`:

```powershell
npm install
npm run dev
```

Open `http://localhost:3000`.

Frontend API base URL behavior:

- uses `NEXT_PUBLIC_API_BASE_URL` when set
- otherwise falls back to `http://localhost:8000`

## Environment Variables

### Backend

- `DATABASE_URL`
  - optional for local development
  - default: `sqlite:///./shopify_analytics_engine.db`
  - required on Railway if using managed Postgres
- `FRONTEND_ORIGIN`
  - optional locally
  - default: `http://localhost:3000`
  - set this to the deployed frontend origin in production
- `SQLALCHEMY_ECHO`
  - optional
  - default: `false`

### Frontend

- `NEXT_PUBLIC_API_BASE_URL`
  - optional locally
  - default: `http://localhost:8000`
  - required on Vercel so the frontend points at the deployed backend

### Not Environment Variables

These are intentionally not stored as app env vars today:

- Shopify `shopify_domain`
- Shopify `access_token`

They are entered manually in the UI for the current MVP ingest flow.

## Architecture

Current action flow:

1. Frontend page loads through the App Router shell in `frontend/app/`
2. Frontend fetch helpers in `frontend/lib/api.ts` call the FastAPI backend
3. `GET /actions` goes through thin routes in `backend/app/api/routes/`
4. `backend/app/services/action_feed.py` prefers persisted DB data
5. `backend/app/services/inventory_engine.py` ranks urgent, optimize, and dead actions
6. If DB data is unusable and allowed by settings, the backend falls back to mock data

Current sync flow:

1. User submits Shopify domain and access token from the Store Sync page
2. `POST /integrations/shopify/ingest` calls the ingestion service
3. Backend persists shops, products, inventory, order line items, settings-related data, and sync-run status

## Deployment Notes

### Frontend

- deploy from `frontend/`
- works on Vercel
- required env var on Vercel:
  - `NEXT_PUBLIC_API_BASE_URL`

### Backend

- deploy from `backend/`
- works on Railway
- required env vars on Railway:
  - `DATABASE_URL`
  - `FRONTEND_ORIGIN`

If Railway provides `DATABASE_URL`, the backend will use it automatically. Local SQLite is for development convenience, not the recommended production database.

## Additional Docs

- [docs/engineering/architecture.md](docs/engineering/architecture.md)
- [docs/process/decisions.md](docs/process/decisions.md)
- [docs/engineering/api_contract.md](docs/engineering/api_contract.md)
