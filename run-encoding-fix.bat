@echo off
cd /d "C:\Users\Rainer\Shopify_Analytics_Engine"
if exist ".git\index.lock" del /f ".git\index.lock"
git add frontend/app/about/page.tsx ^
        frontend/app/changelog/page.tsx ^
        frontend/app/blog/page.tsx ^
        "frontend/app/blog/stocky-alternatives-2026/page.tsx" ^
        "frontend/app/blog/why-six-month-moving-average-overstocks-you/page.tsx"
git commit -m "fix: restore 5 pages truncated/broken by WSL cache bug

- about/page.tsx: restore from pre-truncation commit, fix mojibake
- changelog/page.tsx: restore from pre-truncation commit, fix mojibake
- blog/page.tsx: reconstruct with all 5 posts + complete footer
- blog/stocky-alternatives-2026/page.tsx: restore complete, fix mojibake
- blog/why-six-month.../page.tsx: restore from pre-truncation commit, fix mojibake

Root cause: Python in-place read used WSL stale cache (truncated content).
Fix: read from git object store via subprocess git show <commit>:<path>."
git push origin HEAD
echo.
echo Done. Exit: %ERRORLEVEL%
pause
