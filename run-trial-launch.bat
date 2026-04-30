@echo off
cd /d "C:\Users\Rainer\Shopify_Analytics_Engine"
if exist ".git\index.lock" del /f ".git\index.lock"
git add backend/app/db/models.py ^
        backend/app/db/init_db.py ^
        backend/app/main.py ^
        backend/app/services/auth.py ^
        backend/app/api/routes/auth.py ^
        frontend/components/waitlist-form.tsx ^
        frontend/components/pricing-button.tsx ^
        frontend/app/page.tsx ^
        frontend/app/blog/page.tsx ^
        frontend/app/vs-spreadsheet/page.tsx ^
        frontend/app/goodbye-stocky/page.tsx ^
        frontend/app/goodbye-genie/page.tsx
git commit -m "feat: launch 14-day free trial (replace waitlist gate)

- User.trial_ends_at: new column, set to now+14d on first signup
- init_db: run_safe_migrations() adds column to existing Railway DB
- main.py: lifespan handler runs init_db on startup (no manual step)
- auth service: new users get trial_ends_at = now + 14 days
- /auth/me: exposes trial_ends_at + in_trial fields
- WaitlistForm: now calls /auth/magic-link/request instead of /waitlist/signup
  success message: 'Check your email for your sign-in link'
- Homepage: remove 'private beta', replace with '14-day free trial. No credit card'
- PricingButton: fallback goes to /login instead of /#waitlist
- All CTAs updated from 'Get early access' to 'Start free trial'"
git push origin HEAD
echo.
echo Done. Exit: %ERRORLEVEL%
pause
