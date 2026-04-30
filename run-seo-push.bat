@echo off
cd /d "C:\Users\Rainer\Shopify_Analytics_Engine"
if exist ".git\index.lock" del /f ".git\index.lock"
git add frontend/app/about/page.tsx ^
        frontend/app/blog/page.tsx ^
        frontend/app/blog/stocky-alternatives-2026/page.tsx ^
        frontend/app/blog/why-six-month-moving-average-overstocks-you/page.tsx ^
        frontend/app/blog/inventory-planner-alternative/page.tsx ^
        frontend/app/blog/shopify-safety-stock-formula/page.tsx ^
        frontend/app/blog/how-to-clear-dead-stock-shopify/page.tsx ^
        frontend/app/changelog/page.tsx ^
        frontend/app/pricing/page.tsx ^
        frontend/app/privacy/page.tsx ^
        frontend/app/terms/page.tsx ^
        frontend/app/vs-spreadsheet/page.tsx ^
        frontend/app/sitemap.ts
git commit -m "seo: fix encoding on all remaining pages; add 3 targeted blog posts

- Fix mojibake (em dash, apostrophe, middle dot) in about, blog, changelog,
  pricing, privacy, terms, vs-spreadsheet, and both existing blog posts
- New post: Inventory Planner alternative (high commercial intent)
- New post: Shopify safety stock formula (how-to, lower competition)
- New post: How to clear dead stock on Shopify (problem-aware query)
- Add all 3 new posts to sitemap.ts and blog index"
git push origin HEAD
echo.
echo Done. Exit: %ERRORLEVEL%
pause
