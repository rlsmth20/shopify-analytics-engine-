@echo off
cd /d "C:\Users\Rainer\Shopify_Analytics_Engine"
if exist ".git\index.lock" del /f ".git\index.lock"

REM ── Commit 1: access gating + trial paywall frontend ──────────────────────
git add backend/app/api/deps.py ^
        backend/app/api/routes/actions.py ^
        backend/app/api/routes/alerts.py ^
        backend/app/api/routes/analytics.py ^
        backend/app/api/routes/bundles.py ^
        backend/app/api/routes/dashboard.py ^
        backend/app/api/routes/forecast.py ^
        backend/app/api/routes/liquidation.py ^
        backend/app/api/routes/reorder.py ^
        backend/app/api/routes/shipstation_import.py ^
        backend/app/api/routes/shop_settings.py ^
        backend/app/api/routes/shopify_ingestion.py ^
        backend/app/api/routes/skus.py ^
        backend/app/api/routes/stocky_import.py ^
        backend/app/api/routes/suppliers.py ^
        backend/app/api/routes/transfers.py ^
        frontend/components/auth-guard.tsx ^
        frontend/components/app-shell.tsx ^
        frontend/lib/api-v2.ts ^
        frontend/app/login/page.tsx
git commit -m "feat: trial/subscription access gating — backend + frontend

- require_active_access() dep: 402 if no trial or active subscription
- All 15 gated routes switched; auth/billing/admin unchanged
- AuthUser type: trial_ends_at + in_trial fields
- AppShell: trial countdown banner at 7 days (urgent at 2)
- api-v2: 402 → redirect to /pricing?trial_expired=1
- login: remove stale waitlist error copy"

REM ── Commit 2: pricing banner + onboarding + copy fixes ────────────────────
git add frontend/components/trial-expired-banner.tsx ^
        frontend/app/pricing/page.tsx ^
        frontend/app/goodbye-genie/page.tsx ^
        frontend/app/goodbye-stocky/page.tsx ^
        "frontend/app/(app-shell)/dashboard/page.tsx" ^
        frontend/app/globals.css
git commit -m "feat: trial-expired pricing banner + onboarding steps + copy

- TrialExpiredBanner: client component reads ?trial_expired=1 on /pricing
- Dashboard empty state: 4-step onboarding (Stocky CSV, ShipStation,
  Shopify store-sync, lead times) with styled step cards
- goodbye-genie step 1: trial language (was waitlist language)
- goodbye-stocky step 1: already fixed, committed for completeness
- CSS: trial-expired-banner + dashboard-empty-step styles"

git push origin HEAD
echo.
echo Done. Exit: %ERRORLEVEL%
pause
