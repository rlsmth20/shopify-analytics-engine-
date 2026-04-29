@echo off
cd /d "C:\Users\Rainer\Shopify_Analytics_Engine"

REM Remove helper scripts from repo and push
git rm --cached run-commit.bat commit-bugfixes.ps1 2>nul
del run-commit.bat 2>nul
del commit-bugfixes.ps1 2>nul
git add -A
git commit -m "Remove helper commit scripts (cleanup)" 2>nul

echo.
echo Pushing to GitHub...
git push origin HEAD
echo.
if %errorlevel%==0 (
    echo SUCCESS - changes pushed to GitHub
    echo Trigger a Vercel redeploy to go live.
) else (
    echo PUSH FAILED - check your GitHub credentials
)
pause
