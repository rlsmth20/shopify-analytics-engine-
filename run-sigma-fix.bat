@echo off
cd /d "C:\Users\Rainer\Shopify_Analytics_Engine"
if exist ".git\index.lock" del /f ".git\index.lock"
git add "frontend/app/blog/why-six-month-moving-average-overstocks-you/page.tsx"
git commit -m "fix: restore sigma (sigma) in why-six-month blog post"
git push origin HEAD
echo.
echo Done. Exit: %ERRORLEVEL%
pause
