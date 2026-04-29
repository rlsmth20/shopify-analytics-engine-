Set-Location "C:\Users\Rainer\Shopify_Analytics_Engine"

# Remove stale git lock if present
$lock = ".git\index.lock"
if (Test-Path $lock) { Remove-Item $lock -Force; Write-Host "Removed stale index.lock" }

git add -A
git commit -m "Fix bug-report issues: shared MarketingNav, demo mode, subscribe button, login demo link

BUG-001/003: Add demo mode to AuthGuard via ?demo=1 param + sessionStorage.
Visitors who click 'View demo' land on the app with a synthetic demo user
and sample data. No login required. Circular redirect eliminated.

BUG-002: Fix PricingButton to handle network/CORS errors gracefully.
Falls back to /login redirect instead of silent failure. 503 (billing not
wired) now routes to /#waitlist instead of alerting.

BUG-003: Add 'view the demo' link to login page pointing to /dashboard?demo=1.

BUG-004/005/008: Extract shared MarketingNav component with consistent
'View demo' + 'Sign in' CTAs. Applied to all 12 marketing pages: home,
pricing, about, blog index, both blog posts, goodbye-stocky, goodbye-genie,
vs-spreadsheet, changelog, privacy, terms.

AppShell: Demo banner when user.id === 0. Sign out replaced with Sign up
free for demo visitors."

Write-Host "`nDone. Run: git push" -ForegroundColor Green
