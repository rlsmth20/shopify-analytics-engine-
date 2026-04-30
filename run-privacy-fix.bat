@echo off
cd /d "C:\Users\Rainer\Shopify_Analytics_Engine"
if exist ".git\index.lock" del /f ".git\index.lock"
git add frontend/app/privacy/page.tsx
git commit -m "fix: update privacy page from waitlist-era to trial-era language

- 'sign up for the waitlist or create an account' -> 'start a free trial or create an account'
- Resend: 'planned' -> 'magic-link sign-in'
- Stripe: 'when paid plans launch' -> 'for paid subscriptions'"
git push origin HEAD
echo.
echo Done. Exit: %ERRORLEVEL%
pause
