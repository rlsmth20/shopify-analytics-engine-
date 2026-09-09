param(
    [ValidateSet('review-export', 'review-import', 'outreach-status', 'outreach-reserve', 'outreach-authorize', 'outreach-complete', 'outreach-backfill', 'outreach-reconcile', 'operator-export', 'operator-enqueue', 'operator-claim', 'operator-complete', 'operator-state', 'operator-assess', 'operator-monitor', 'operator-monitor-start')][string]$Action = 'review-export',
    [string]$File,
    [string]$Model = 'codex'
)
$ErrorActionPreference = 'Stop'
$growthRepo = Split-Path -Parent $PSScriptRoot
$growthPriorDatabase = $env:DATABASE_URL
Push-Location $growthRepo
try {
    $growthProject = railway status --json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $growthProject.id -ne '15ef1e57-3759-4e47-a921-fc4814883839') {
        throw 'Expected the linked Skubase Railway project. No database action taken.'
    }
    $growthVariables = railway variables --service '947d9147-d2c6-4aa6-a0cf-6fbb5bf2e2e7' --environment 'd338b7ed-d399-4cfe-bac3-28fda380037e' --json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or -not $growthVariables.DATABASE_PUBLIC_URL) {
        throw 'Skubase database connection unavailable.'
    }
    $env:DATABASE_URL = $growthVariables.DATABASE_PUBLIC_URL
    $growthArguments = @('-m', 'app.growth.control', $Action)
    if ($Action -eq 'review-import') {
        if (-not $File) { throw 'A reviewed JSON file is required.' }
        $growthArguments += @('--file', (Resolve-Path -LiteralPath $File).Path, '--model', $Model)
    }
    if ($Action -in @('outreach-reserve', 'outreach-authorize', 'outreach-complete', 'outreach-reconcile', 'operator-enqueue', 'operator-claim', 'operator-complete', 'operator-assess', 'operator-monitor', 'operator-monitor-start')) {
        if (-not $File) { throw 'An exact reviewed JSON payload is required.' }
        $growthArguments += @('--file', (Resolve-Path -LiteralPath $File).Path)
    }
    Set-Location (Join-Path $growthRepo 'backend')
    python @growthArguments
    if ($LASTEXITCODE -ne 0) { throw 'Executive operation failed.' }
} finally {
    $env:DATABASE_URL = $growthPriorDatabase
    $growthVariables = $null
    Pop-Location
}
