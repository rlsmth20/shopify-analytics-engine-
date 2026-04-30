Set-Location "C:\Users\Rainer\Shopify_Analytics_Engine"

Write-Host "Staging changes..."
git add frontend/lib/demo-data.ts frontend/lib/api-v2.ts frontend/lib/api.ts

Write-Host "Committing..."
git commit -m "fix: demo mode returns mock data instead of hitting backend (401 fix)

- Add frontend/lib/demo-data.ts with realistic mock responses for every
  authenticated endpoint (dashboard, forecast, analytics, suppliers,
  bundles, transfers, liquidation, purchase-orders, alerts, action feed)
- Patch api-v2.ts: isDemo() check in get() and postJson() short-circuits
  to local fixture data when sessionStorage.skubase_demo === '1'
- Patch api.ts: fetchInventoryActions() returns DEMO_ACTION_FEED in demo
  mode so actions and analytics pages also work without a real session
- Fixes: all app-shell tabs showing '/dashboard failed with 401' in demo"

Write-Host ""
Write-Host "Pushing to GitHub..."
git push origin HEAD

Write-Host ""
if ($LASTEXITCODE -eq 0) {
    Write-Host "SUCCESS - pushed. Vercel will redeploy automatically."
} else {
    Write-Host "PUSH FAILED - check credentials."
}

pause
