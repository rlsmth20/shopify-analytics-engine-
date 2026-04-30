@echo off
cd /d "C:\Users\Rainer\Shopify_Analytics_Engine"
if exist ".git\index.lock" del /f ".git\index.lock"
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
        frontend/app/login/page.tsx ^
        frontend/app/goodbye-stocky/page.tsx
git commit -m "feat: trial paywall enforcement — frontend + backend

Backend (access gating):
- deps.py: require_active_access() checks trial or active subscription
- All 15 gated routes use require_active_access (402 when expired)
- Admins always pass; billing/auth/health routes unchanged

Frontend (paywall UX):
- auth-guard: AuthUser gets trial_ends_at + in_trial fields
- app-shell: countdown banner at 7 days left, urgent at 2
- api-v2: redirects to /pricing?trial_expired=1 on any 402
- login: remove stale waitlist copy
- goodbye-stocky: step 1 uses trial language"
git push origin HEAD
echo.
echo Done. Exit: %ERRORLEVEL%
pause
