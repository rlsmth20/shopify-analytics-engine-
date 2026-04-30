Set-Location "C:\Users\Rainer\Shopify_Analytics_Engine"

Write-Host "Reading clean base from git object store..."
# git show bypasses WSL stale cache - this is the known-good content from 0b1f844
$content = git show 0b1f844:frontend/app/page.tsx

# Remove UTF-8 BOM if present
if ($content[0] -eq [char]0xFEFF) {
    $content = $content.Substring(1)
}

Write-Host "Applying demo link fixes..."
# Fix all pillar hrefs to include ?demo=1
$content = $content -replace '(href: "/forecast")', 'href: "/forecast?demo=1"'
$content = $content -replace '(href: "/suppliers")', 'href: "/suppliers?demo=1"'
$content = $content -replace '(href: "/liquidation")', 'href: "/liquidation?demo=1"'
$content = $content -replace '(href: "/bundles")', 'href: "/bundles?demo=1"'
$content = $content -replace 'href: "/dashboard" \}', 'href: "/dashboard?demo=1" }'
$content = $content -replace '(href: "/alerts")', 'href: "/alerts?demo=1"'

# Fix hero "See a live demo" link
$content = $content -replace 'Link href="/dashboard">See a live demo', 'Link href="/dashboard?demo=1">See a live demo'

Write-Host "Writing fixed file (no BOM, no curly quotes)..."
# Write with UTF-8 no BOM encoding
[System.IO.File]::WriteAllText(
    "C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\page.tsx",
    $content,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "Verifying file..."
$verify = Get-Content "C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\page.tsx" | Select-String "demo=1"
Write-Host "Lines with demo=1: $($verify.Count)"
$badQuotes = Get-Content "C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\page.tsx" -Raw | Select-String ([char]0x201C)
if ($badQuotes) {
    Write-Host "WARNING: curly quotes still present!"
} else {
    Write-Host "OK: no curly quote string delimiters found"
}

Write-Host ""
Write-Host "Committing..."
git add frontend/app/page.tsx
git commit -m "fix: rewrite page.tsx with clean ASCII quotes and ?demo=1 on all demo links

The previous commit introduced curly/smart quote characters as JS string
delimiters due to WSL encoding corruption. This rewrites from the known-good
git object (0b1f844) using PowerShell UTF8NoBOM encoding, then applies the
?demo=1 changes cleanly.

- All 6 pillar 'See in demo' links include ?demo=1
- Hero 'See a live demo' link includes ?demo=1
- No BOM, no curly quotes, no doubled apostrophes"

Write-Host ""
Write-Host "Pushing..."
git push origin HEAD

Write-Host ""
if ($LASTEXITCODE -eq 0) {
    Write-Host "SUCCESS"
} else {
    Write-Host "PUSH FAILED"
}

pause
