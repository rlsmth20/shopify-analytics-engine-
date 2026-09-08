param([string]$CodexPath)
$ErrorActionPreference = 'Stop'
$growthRepo = Split-Path -Parent $PSScriptRoot
if (-not $CodexPath) {
    $growthBins = Get-ChildItem -LiteralPath "$env:LOCALAPPDATA/OpenAI/Codex/bin" -Directory | Sort-Object LastWriteTime -Descending
    $CodexPath = $growthBins | ForEach-Object { Join-Path $_.FullName 'codex.exe' } | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $CodexPath) { throw 'Installed desktop Codex executable unavailable.' }
Push-Location $growthRepo
$growthPriorDatabase = $env:DATABASE_URL
try {
    $growthProject = railway status --json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $growthProject.id -ne '15ef1e57-3759-4e47-a921-fc4814883839') { throw 'Expected Skubase project.' }
    $growthVariables = railway variables --service '947d9147-d2c6-4aa6-a0cf-6fbb5bf2e2e7' --environment 'd338b7ed-d399-4cfe-bac3-28fda380037e' --json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or -not $growthVariables.DATABASE_PUBLIC_URL) { throw 'Production database unavailable.' }
    $env:DATABASE_URL = $growthVariables.DATABASE_PUBLIC_URL
    $growthVariables = $null
    Set-Location (Join-Path $growthRepo 'backend')
    python -m app.growth.browser_executor --codex $CodexPath --repo $growthRepo
    if ($LASTEXITCODE -ne 0) { throw 'Acquisition executor stopped.' }
} finally {
    $env:DATABASE_URL = $growthPriorDatabase
    Pop-Location
}
