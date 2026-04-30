@echo off
cd /d "C:\Users\Rainer\Shopify_Analytics_Engine"
if exist ".git\index.lock" del /f ".git\index.lock"
git add "frontend/app/blog/stocky-alternatives-2026/page.tsx" ^
        "frontend/app/blog/why-six-month-moving-average-overstocks-you/page.tsx" ^
        "frontend/app/goodbye-stocky/page.tsx" ^
        "frontend/app/goodbye-genie/page.tsx"
git commit -m "fix: blog title suffixes, add /blog to goodbye-stocky + goodbye-genie footers"
git push origin HEAD
echo.
echo Done. Exit: %ERRORLEVEL%
pause
