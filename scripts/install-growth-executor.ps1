# Process supervision for the acquisition adapter, not an hourly business-work wake.
$ErrorActionPreference = 'Stop'
$growthRepo = Split-Path -Parent $PSScriptRoot
$growthPython = (Get-Command python.exe).Source
$growthWindowless = Join-Path (Split-Path -Parent $growthPython) 'pythonw.exe'
if (Test-Path -LiteralPath $growthWindowless) { $growthPython = $growthWindowless }
$growthBins = Get-ChildItem -LiteralPath "$env:LOCALAPPDATA/OpenAI/Codex/bin" -Directory | Sort-Object LastWriteTime -Descending
$growthCodex = $growthBins | ForEach-Object { Join-Path $_.FullName 'codex.exe' } | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $growthCodex) { throw 'Installed desktop Codex executable unavailable.' }
$growthAction = New-ScheduledTaskAction -Execute $growthPython -Argument ('-m app.growth.browser_executor --production --repo "' + $growthRepo + '" --codex "' + $growthCodex + '"') -WorkingDirectory (Join-Path $growthRepo 'backend')
$growthTrigger = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$growthSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$growthPrincipal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'Skubase acquisition executor' -Action $growthAction -Trigger $growthTrigger -Settings $growthSettings -Principal $growthPrincipal -Description 'Continuously pull leased acquisition stages from the Skubase production queue; resume immediately after progress and recover after failure.' -Force | Out-Null
Start-ScheduledTask -TaskName 'Skubase acquisition executor'
Get-ScheduledTask -TaskName 'Skubase acquisition executor' | Select-Object TaskName, State
