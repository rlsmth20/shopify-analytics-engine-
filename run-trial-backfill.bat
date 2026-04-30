@echo off
cd /d "C:\Users\Rainer\Shopify_Analytics_Engine"
if exist ".git\index.lock" del /f ".git\index.lock"
git add backend/app/services/auth.py
git commit -m "fix: back-fill trial for existing waitlist users on first magic-link sign-in

Existing users (created before trial launch) have trial_ends_at = NULL.
Without this fix they'd hit the 402 paywall immediately on first login
since require_active_access() sees no trial and no subscription.

Now: if user.trial_ends_at is None at login time, set it to now + 14d.
New users created after trial launch already get trial_ends_at at creation."
git push origin HEAD
echo.
echo Done. Exit: %ERRORLEVEL%
pause
