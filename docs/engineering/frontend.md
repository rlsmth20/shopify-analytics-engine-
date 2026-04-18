# Frontend

## Purpose

The frontend renders the prioritized action feed from the backend.

## Current Fetch Flow

1. homepage mounts
2. `frontend/lib/api.ts` calls `GET /actions`
3. backend response is typed as a union of urgent, optimize, and dead actions
4. homepage groups items by status and renders each section

## Configuration

- backend base URL comes from `NEXT_PUBLIC_API_BASE_URL`
- fallback default is `http://localhost:8000`

## Current UI Behavior

- loading state while fetching `/actions`
- error state if the request fails
- empty state if no actionable items are returned
- grouped sections for:
  - urgent
  - optimize
  - dead

## Current Scope

- one page: the homepage action feed
- no charts
- no auth
- no extra pages

## Near-Term Frontend Work

- keep API typings aligned with the backend contract
- add lightweight refresh behavior only if it helps operational use
