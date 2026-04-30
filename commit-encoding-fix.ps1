Set-Location "C:\Users\Rainer\Shopify_Analytics_Engine"

# Remove stale lock if present
$lockFile = ".git\index.lock"
if (Test-Path $lockFile) {
    Remove-Item $lockFile -Force
    Write-Host "Removed stale index.lock"
}

git add frontend/app/page.tsx frontend/app/goodbye-genie/page.tsx frontend/app/goodbye-stocky/page.tsx

git commit -m "fix: correct mojibake encoding in marketing pages

Em dash, right arrow, middle dot, copyright, and double apostrophes
were stored as mis-decoded Windows-1252 sequences after a previous
PowerShell script captured git output with the wrong console encoding.
Fixed with Python: replaced the bad Unicode sequences with the correct
UTF-8 characters and wrote back without BOM."

Write-Host ""
Write-Host "Pushing..."
git push origin HEAD

if ($LASTEXITCODE -eq 0) {
    Write-Host "SUCCESS - Vercel will redeploy."
} else {
    Write-Host "PUSH FAILED - exit code $LASTEXITCODE"
}

pause
