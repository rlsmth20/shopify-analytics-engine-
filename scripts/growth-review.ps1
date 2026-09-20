param(
    [ValidateSet('warmup-status', 'warmup-prepare', 'warmup-authorize', 'warmup-record', 'review-export', 'review-import', 'outreach-status', 'outreach-reserve', 'outreach-authorize', 'outreach-complete', 'outreach-backfill', 'outreach-reconcile', 'operator-export', 'operator-enqueue', 'operator-claim', 'operator-complete', 'operator-state', 'operator-assess', 'operator-monitor', 'operator-monitor-start', 'community-record', 'community-reply', 'community-export', 'prospect-link', 'prospect-history', 'email-queue', 'email-status', 'email-suppress')][string]$Action = 'review-export',
    [string]$File,
    [string]$Model = 'codex'
)
$ErrorActionPreference = 'Stop'
$growthRepo = Split-Path -Parent $PSScriptRoot
$growthPriorDatabase = $env:DATABASE_URL
$growthPriorEmailVariables = @{}
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
    if ($Action -like 'email-*') {
        $growthBackendVariables = railway variables --service '6b132d29-f6ca-4536-92fb-1dcc0bb1027f' --environment 'd338b7ed-d399-4cfe-bac3-28fda380037e' --json | ConvertFrom-Json
        if ($LASTEXITCODE -ne 0) { throw 'Outreach configuration unavailable.' }
        foreach ($growthEntry in $growthBackendVariables.PSObject.Properties) {
            if ($growthEntry.Name -like 'OUTREACH_*' -or $growthEntry.Name -in @('BUSINESS_NAME', 'BUSINESS_POSTAL_ADDRESS')) {
                $growthPriorEmailVariables[$growthEntry.Name] = [Environment]::GetEnvironmentVariable($growthEntry.Name, 'Process')
                [Environment]::SetEnvironmentVariable($growthEntry.Name, $growthEntry.Value, 'Process')
            }
        }
    }
    $growthArguments = @('-m', 'app.growth.control', $Action)
    if ($Action -eq 'review-import') {
        if (-not $File) { throw 'A reviewed JSON file is required.' }
        $growthArguments += @('--file', (Resolve-Path -LiteralPath $File).Path, '--model', $Model)
    }
    if ($Action -in @('warmup-prepare', 'warmup-authorize', 'warmup-record', 'outreach-reserve', 'outreach-authorize', 'outreach-complete', 'outreach-reconcile', 'operator-enqueue', 'operator-claim', 'operator-complete', 'operator-assess', 'operator-monitor', 'operator-monitor-start', 'community-record', 'community-reply', 'prospect-link', 'prospect-history', 'email-queue', 'email-suppress')) {
        if (-not $File) { throw 'An exact reviewed JSON payload is required.' }
        $growthArguments += @('--file', (Resolve-Path -LiteralPath $File).Path)
    }
    Set-Location (Join-Path $growthRepo 'backend')
    if ($Action -eq 'outreach-reserve') {
        # Retain the exact handoff once; missing tool output must not repeat a mutation.
        $growthReservationOutput = python @growthArguments
        if ($LASTEXITCODE -ne 0) { throw 'Executive operation failed.' }
        $growthReservation = ($growthReservationOutput -join "`n") | ConvertFrom-Json
        if ($growthReservation.reservation_id -notmatch '^[a-f0-9]{32}$') {
            throw 'Reservation response missing a valid ID; reconcile without reserving again.'
        }
        $growthResultDirectory = Join-Path $growthRepo '.growth-deploy'
        New-Item -ItemType Directory -Path $growthResultDirectory -Force | Out-Null
        $growthResultFile = Join-Path $growthResultDirectory ('outreach-reservation-' + $growthReservation.reservation_id + '.json')
        $growthReservation | Add-Member -NotePropertyName result_file -NotePropertyValue $growthResultFile -Force
        $growthReservationJson = $growthReservation | ConvertTo-Json -Depth 30
        Set-Content -LiteralPath $growthResultFile -Value $growthReservationJson -Encoding UTF8
        $growthReservationJson
    } elseif ($Action -eq 'operator-monitor-start') {
        # The check is already created when stdout returns. Preserve its exact
        # ID and expiry instead of making the browser worker repeat the start.
        $growthMonitorOutput = python @growthArguments
        if ($LASTEXITCODE -ne 0) { throw 'Executive operation failed.' }
        $growthMonitor = ($growthMonitorOutput -join "`n") | ConvertFrom-Json
        $growthMonitorInput = Get-Content -LiteralPath $growthArguments[-1] -Raw | ConvertFrom-Json
        if ($growthMonitor.check_id -le 0 -or $growthMonitorInput.lease_token -notmatch '^[a-f0-9]{32}$') {
            throw 'Monitor response missing a valid check ID or lease; inspect retained evidence.'
        }
        $growthResultDirectory = Join-Path $growthRepo '.growth-deploy'
        New-Item -ItemType Directory -Path $growthResultDirectory -Force | Out-Null
        $growthResultFile = Join-Path $growthResultDirectory ('operator-monitor-start-' + $growthMonitorInput.lease_token + '.json')
        $growthMonitor | Add-Member -NotePropertyName result_file -NotePropertyValue $growthResultFile -Force
        $growthMonitor | Add-Member -NotePropertyName task_id -NotePropertyValue $growthMonitorInput.task_id -Force
        $growthMonitor | Add-Member -NotePropertyName lease_token -NotePropertyValue $growthMonitorInput.lease_token -Force
        $growthMonitorJson = $growthMonitor | ConvertTo-Json -Depth 10
        Set-Content -LiteralPath $growthResultFile -Value $growthMonitorJson -Encoding UTF8
        $growthMonitorJson
    } else {
        python @growthArguments
        if ($LASTEXITCODE -ne 0) { throw 'Executive operation failed.' }
    }
} finally {
    $env:DATABASE_URL = $growthPriorDatabase
    $growthVariables = $null
    foreach ($growthKey in $growthPriorEmailVariables.Keys) {
        [Environment]::SetEnvironmentVariable($growthKey, $growthPriorEmailVariables[$growthKey], 'Process')
    }
    $growthBackendVariables = $null
    Pop-Location
}
