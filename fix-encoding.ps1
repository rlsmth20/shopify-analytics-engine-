Set-Location "C:\Users\Rainer\Shopify_Analytics_Engine"

# Files that have mojibake special characters from the previous WSL/PowerShell encoding issue.
# The problem: git show output was captured with Windows-1252 console encoding,
# so UTF-8 multi-byte sequences got mis-decoded into Latin-1 lookalikes.
# This script fixes: em dash (—), right arrow (→), middle dot (·), and double apostrophes.

$filesToFix = @(
    "frontend\app\page.tsx",
    "frontend\app\goodbye-genie\page.tsx",
    "frontend\app\goodbye-stocky\page.tsx"
)

function Fix-Encoding($path) {
    Write-Host "Fixing: $path"
    $content = [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)

    # Em dash mojibake: the bytes 0xE2 0x80 0x94 (UTF-8 em dash) were read as
    # Windows-1252: 0xE2=â (U+00E2), 0x80=€ (U+20AC), 0x94=" (U+201D)
    # Then re-encoded to UTF-8 producing â€" visually.
    $emDashBad  = [char]0x00E2 + [char]0x20AC + [char]0x201D
    $emDash     = [char]0x2014
    $content = $content.Replace($emDashBad, $emDash)

    # Right arrow mojibake: 0xE2 0x86 0x92 (UTF-8 →) read as
    # 0xE2=â (U+00E2), 0x86=† (U+2020), 0x92=' (U+2019) → â†'
    $arrowBad   = [char]0x00E2 + [char]0x2020 + [char]0x2019
    $arrow      = [char]0x2192
    $content = $content.Replace($arrowBad, $arrow)

    # Middle dot mojibake: 0xC2 0xB7 (UTF-8 ·) read as
    # 0xC2=Â (U+00C2), 0xB7=· (U+00B7) → Â·
    $midDotBad  = [char]0x00C2 + [char]0x00B7
    $midDot     = [char]0x00B7
    $content = $content.Replace($midDotBad, $midDot)

    # Registered trademark / copyright mojibake if present
    # 0xC2 0xA9 (©) → Â©
    $copyBad    = [char]0x00C2 + [char]0x00A9
    $copy       = [char]0x00A9
    $content = $content.Replace($copyBad, $copy)

    # Double apostrophes from SQL-style escaping
    $content = $content.Replace("''", "'")

    # Write back as UTF-8 without BOM
    [System.IO.File]::WriteAllText($path, $content, [System.Text.UTF8Encoding]::new($false))
    Write-Host "  Done."
}

foreach ($f in $filesToFix) {
    $fullPath = "C:\Users\Rainer\Shopify_Analytics_Engine\$f"
    Fix-Encoding $fullPath
}

Write-Host ""
Write-Host "Verifying page.tsx has no mojibake..."
$check = [System.IO.File]::ReadAllText("C:\Users\Rainer\Shopify_Analytics_Engine\frontend\app\page.tsx", [System.Text.Encoding]::UTF8)
if ($check -match "â€") {
    Write-Host "WARNING: still has mojibake (â€)"
} elseif ($check -match "Â·") {
    Write-Host "WARNING: still has mojibake (Â·)"
} else {
    Write-Host "OK: no mojibake found"
}

Write-Host ""
Write-Host "Committing..."
git add frontend/app/page.tsx frontend/app/goodbye-genie/page.tsx frontend/app/goodbye-stocky/page.tsx
git commit -m "fix: decode mojibake special chars in marketing pages

Previous PowerShell script captured git output with Windows-1252 console
encoding, causing UTF-8 multi-byte sequences to be double-encoded:
  — (em dash U+2014)  showed as: â€"
  → (right arrow)     showed as: â†'
  · (middle dot)      showed as: Â·

Fixed by reading file as UTF-8, replacing the mis-decoded Unicode sequences
with their correct counterparts, and writing back as UTF-8-no-BOM.
Also fixed double apostrophes (don''t -> don't)."

Write-Host ""
Write-Host "Pushing..."
git push origin HEAD

if ($LASTEXITCODE -eq 0) {
    Write-Host "SUCCESS - Vercel will redeploy."
} else {
    Write-Host "PUSH FAILED"
}

pause
