# AGENTS

## Repo Structure

- `frontend/`
  - Next.js App Router app
  - UI, routing, API fetch helpers, and presentation components
- `backend/`
  - FastAPI app
  - API routes, services, SQLAlchemy models, ingestion, and inventory engine
- `docs/`
  - product, engineering, and process docs

The repo is a monorepo, but frontend and backend stay cleanly separated. Do not introduce direct imports across those boundaries.

## Run Commands

### Backend

From `backend/`:

```powershell
python -m pip install -r requirements.txt
python -m app.db.init_db
uvicorn app.main:app --reload --port 8000
```

### Frontend

From `frontend/`:

```powershell
npm install
npm run dev
npm run build
npm run typecheck
```

## Rules

- Do not modify backend logic unless explicitly requested.
- Frontend changes should not break existing API contracts.
- Keep changes minimal, clean, and easy to review.
- Keep FastAPI route files thin; business logic belongs in services.
- Keep frontend/backend separation intact; use HTTP contracts, not shared runtime imports.
- Prefer small documentation updates when changing developer workflow, environment variables, or deployment behavior.
