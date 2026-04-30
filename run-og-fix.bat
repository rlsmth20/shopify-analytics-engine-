@echo off
cd /d "C:\Users\Rainer\Shopify_Analytics_Engine"
if exist ".git\index.lock" del /f ".git\index.lock"
git add frontend/app/opengraph-image.tsx
git commit -m "fix: OG image brand mark 'sf' -> 'sb'"
git push origin HEAD
echo.
echo Done. Exit: %ERRORLEVEL%
pause
