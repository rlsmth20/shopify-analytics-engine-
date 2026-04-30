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
        backend/app/api/routes/transfers.py
git commit -m "feat: enforce trial/subscription access gate on all protected routes

- deps.py: add require_active_access() dependency
  - Passes if user is in trial (trial_ends_at in the future) OR
  - Passes if shop has active Stripe subscription
  - Admins always pass (support access)
  - Returns HTTP 402 with message if neither condition is met
- All 15 gated routes now use require_active_access instead of get_current_user
  (actions, alerts, analytics, bundles, dashboard, forecast, liquidation,
   reorder, shipstation_import, shop_settings, shopify_ingestion, skus,
   stocky_import, suppliers, transfers)
- auth, billing, admin, health, waitlist routes unchanged"
git push origin HEAD
echo.
echo Done. Exit: %ERRORLEVEL%
pause
