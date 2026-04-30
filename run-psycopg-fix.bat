@echo off
cd /d "C:\Users\Rainer\Shopify_Analytics_Engine"
if exist ".git\index.lock" del /f ".git\index.lock"
git add backend/app/db/session.py
git commit -m "fix: use postgresql+psycopg:// dialect for psycopg v3 compatibility"
git push origin HEAD
echo.
echo Done. Exit: %ERRORLEVEL%
pause
