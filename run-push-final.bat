@echo off
cd /d "C:\Users\Rainer\Shopify_Analytics_Engine"
if exist ".git\index.lock" del /f ".git\index.lock"
git add frontend/app/page.tsx frontend/app/goodbye-genie/page.tsx frontend/app/goodbye-stocky/page.tsx
git commit -m "fix: restore complete files with correct encoding"
git push origin HEAD
echo.
echo Done. Exit code: %ERRORLEVEL%
pause
