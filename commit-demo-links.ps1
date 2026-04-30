Set-Location "C:\Users\Rainer\Shopify_Analytics_Engine"

Write-Host "Staging changes..."
git add frontend/app/page.tsx `
         frontend/app/not-found.tsx `
         frontend/app/goodbye-genie/page.tsx `
         frontend/app/goodbye-stocky/page.tsx `
         frontend/app/pricing/page.tsx

Write-Host "Committing..."
git commit -m "fix: add ?demo=1 to all demo entry points; fix trial copy; fix pricing footer

- homepage: all 6 'See in demo' pillar links and hero 'See a live demo'
  link now include ?demo=1 so cold visitors land in demo mode
- not-found.tsx: 'Open the demo' button now goes to /dashboard?demo=1
- goodbye-genie: '30-day trial' -> '14-day trial' (BUG-006)
- goodbye-stocky: 'Free during first 30 days' -> '14-day trial' (BUG-007)
- pricing footer: add Stocky migration, Genie migration, vs. spreadsheet
  links to match homepage footer (BUG-010)"

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
