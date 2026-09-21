# Offline CLI regression: no database access and no external send.
$ErrorActionPreference = 'Stop'
$testRepo = Split-Path -Parent $PSScriptRoot
$testId = [guid]::NewGuid().ToString('N')
$testInput = Join-Path $testRepo ('.growth-deploy/test-authorization-input-' + $testId + '.json')
$testResult = Join-Path $testRepo ('.growth-deploy/outreach-authorization-' + $testId + '.json')
$testState = @{calls=0; failure=$false}

function railway {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'status') { '{"id":"15ef1e57-3759-4e47-a921-fc4814883839"}' }
    else { '{"DATABASE_PUBLIC_URL":"sqlite:///:memory:"}' }
}
function python {
    $testState.calls++
    if ($testState.failure) { $global:LASTEXITCODE = 1; return }
    $global:LASTEXITCODE = 0
    @{reservation_id=$testId; submit_before=1234567890.125; instruction='Submit once before this deadline.'} | ConvertTo-Json -Compress
}
try {
    @{reservation_id=$testId} | ConvertTo-Json | Set-Content -LiteralPath $testInput -Encoding UTF8
    $result = (& (Join-Path $PSScriptRoot 'growth-review.ps1') -Action outreach-authorize -File $testInput) | ConvertFrom-Json
    $retained = Get-Content -LiteralPath $testResult -Raw | ConvertFrom-Json
    if ($testState.calls -ne 1 -or $retained.reservation_id -ne $testId -or
        $retained.submit_before -ne 1234567890.125 -or $result.result_file -ne $testResult) {
        throw 'One-use result or original deadline was not retained exactly.'
    }
    Remove-Item -LiteralPath $testResult
    $testState.failure = $true
    $failed = $false
    try { & (Join-Path $PSScriptRoot 'growth-review.ps1') -Action outreach-authorize -File $testInput | Out-Null }
    catch { $failed = $true }
    if (-not $failed -or (Test-Path -LiteralPath $testResult) -or $testState.calls -ne 2) {
        throw 'Failed authorization must not create a result or retry.'
    }
    'PASS: exact authorization retained once; expiry unchanged; failures create no permit.'
} finally {
    foreach ($testPath in @($testInput, $testResult)) {
        if (Test-Path -LiteralPath $testPath) { Remove-Item -LiteralPath $testPath }
    }
}

