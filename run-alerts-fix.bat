@echo off
cd /d "C:\Users\Rainer\Shopify_Analytics_Engine"
if exist ".git\index.lock" del /f ".git\index.lock"
git add "frontend/app/(app-shell)/alerts/page.tsx" frontend/app/globals.css
git commit -m "fix: alerts toggle label overlapping Delete button"
git push origin HEAD
echo Done. Exit: %ERRORLEVEL%
pause
