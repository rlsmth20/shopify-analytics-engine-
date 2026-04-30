@echo off
cd /d "C:\Users\Rainer\Shopify_Analytics_Engine"
if exist ".git\index.lock" del /f ".git\index.lock"
git add "frontend/app/(app-shell)/billing/page.tsx" ^
        "frontend/app/(app-shell)/account/page.tsx" ^
        frontend/app/about/page.tsx ^
        frontend/app/changelog/page.tsx ^
        frontend/app/blog/page.tsx ^
        "frontend/app/blog/why-six-month-moving-average-overstocks-you/page.tsx" ^
        frontend/app/blog/stocky-alternatives-2026/page.tsx ^
        frontend/app/blog/inventory-planner-alternative/page.tsx
git commit -m "feat: trial-era copy + billing/account trial awareness

Billing & account pages:
- billing/page.tsx: trial status card when in_trial + no sub; plan card
  shows 'Free Trial', badge and copy adapt to trial state
- account/page.tsx: plan card shows 'Free Trial — Xd left' when in_trial;
  badge/copy/button adapt to trial vs active vs expired

Marketing copy cleanup (waitlist → trial era):
- about: CTA section: 'private beta / get on the list' → trial CTA
- changelog: add v0.5.0 entry for trial launch; CTA → 'Start free trial'
- blog index: CTA section → trial copy
- why-six-month-moving-average: 'Get early access' → 'Start free trial'
- stocky-alternatives-2026: 'Get early access' → 'Start free trial'
- inventory-planner-alternative: 'early access' → trial language"
git push origin HEAD
echo.
echo Done. Exit: %ERRORLEVEL%
pause
