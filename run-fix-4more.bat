@echo off
cd /d "C:\Users\Rainer\Shopify_Analytics_Engine"
if exist ".git\index.lock" del /f ".git\index.lock"
git add frontend/app/pricing/page.tsx ^
        frontend/app/privacy/page.tsx ^
        frontend/app/terms/page.tsx ^
        frontend/app/vs-spreadsheet/page.tsx
git commit -m "fix: restore 4 more pages truncated by WSL cache bug (pricing, privacy, terms, vs-spreadsheet)"
git push origin HEAD
echo.
echo Done. Exit: %ERRORLEVEL%
pause
