@echo off
cd /d "C:\Users\Rainer\Shopify_Analytics_Engine"
if exist ".git\index.lock" del /f ".git\index.lock"
git add backend/app/main.py backend/railway.json
git commit -m "fix: decouple init_db from start command — lifespan handles it, health stays up"
git push origin HEAD
echo.
echo Done. Exit: %ERRORLEVEL%
pause
