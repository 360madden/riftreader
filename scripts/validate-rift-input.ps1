# PREFERRED VALIDATION HARNESS: Repeatable live smoke test for RIFT input delivery.
# Verifies WASD / SPACE through SendInput and compares Alt+Z delivery through SendInput vs PostMessage.
[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$MovementHoldMilliseconds = 1000,
    [int]$AltHoldMilliseconds = 500,
    [int]$PreActionDelayMilliseconds = 400,
    [int]$WaitTimeoutMilliseconds = 1800,
    [int]$PollIntervalMilliseconds = 80,
    [double]$ChangeThresholdPercent = 0.8,
    [double]$PassMarginPercent = 0.5,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$windowToolsScript = Join-Path $repoRoot 'tools\rift-game-mcp\helpers\window-tools.ps1'
$sendKeyScript = Join-Path $PSScriptRoot 'send-rift-key.ps1'
$postKeyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'

if (-not (Test-Path -LiteralPath $windowToolsScript)) {
    throw "window-tools helper not found: $windowToolsScript"
}
if (-not (Test-Path -LiteralPath $sendKeyScript)) {
    throw "send-rift-key script not found: $sendKeyScript"
}
if (-not (Test-Path -LiteralPath $postKeyScript)) {
    throw "post-rift-key script not found: $postKeyScript"
}

$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$runDirectory = Join-Path $repoRoot ("artifacts\input-validation\run-$runId")
New-Item -ItemType Directory -Force -Path $runDirectory | Out-Null

function Invoke-FocusAndClearUi {
    $focusRaw = & $windowToolsScript -Operation focus -ProcessName $ProcessName
    $null = $focusRaw | ConvertFrom-Json -ErrorAction Stop

    & $sendKeyScript -ProcessName $ProcessName -Key ESC -HoldMilliseconds 80 -NoRefocus | Out-Null
    Start-Sleep -Milliseconds $PreActionDelayMilliseconds
}

function Invoke-InputValidationCase {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [scriptblock]$Action
    )

    Invoke-FocusAndClearUi

    $caseDirectory = Join-Path $runDirectory $Name
    New-Item -ItemType Directory -Force -Path $caseDirectory | Out-Null

    $beforePath = Join-Path $caseDirectory 'before.png'
    $afterPath = Join-Path $caseDirectory 'after.png'

    $beforeRaw = & $windowToolsScript -Operation capture -ProcessName $ProcessName -OutputPath $beforePath
    $beforeCapture = $beforeRaw | ConvertFrom-Json -ErrorAction Stop

    $job = Start-Job -ArgumentList @(
        $windowToolsScript,
        $ProcessName,
        $beforeCapture.screenshotPath,
        $afterPath,
        $WaitTimeoutMilliseconds,
        $PollIntervalMilliseconds,
        $ChangeThresholdPercent
    ) -ScriptBlock {
        param($helperPath, $targetProcessName, $baselineFile, $resultFile, $timeoutMs, $pollMs, $thresholdPercent)
        & $helperPath `
            -Operation wait-for-change `
            -ProcessName $targetProcessName `
            -BaselinePath $baselineFile `
            -OutputPath $resultFile `
            -TimeoutMilliseconds $timeoutMs `
            -PollIntervalMilliseconds $pollMs `
            -ChangeThresholdPercent $thresholdPercent
    }

    Start-Sleep -Milliseconds 220
    if ($Action) {
        & $Action
    }

    $waitRaw = Receive-Job -Wait -AutoRemoveJob $job | Out-String
    $waitResult = $waitRaw | ConvertFrom-Json -ErrorAction Stop

    return [pscustomobject]@{
        Name = $Name
        Changed = [bool]$waitResult.changed
        ChangePercent = [double]$waitResult.changePercent
        ElapsedMilliseconds = [int]$waitResult.elapsedMilliseconds
        BeforeScreenshot = $beforeCapture.screenshotPath
        AfterScreenshot = $waitResult.screenshotPath
    }
}

$results = [System.Collections.Generic.List[object]]::new()

$results.Add((Invoke-InputValidationCase -Name 'control-noinput' -Action $null))
$results.Add((Invoke-InputValidationCase -Name 'send-w' -Action {
    & $sendKeyScript -ProcessName $ProcessName -Key W -HoldMilliseconds $MovementHoldMilliseconds -NoRefocus | Out-Null
}))
$results.Add((Invoke-InputValidationCase -Name 'send-a' -Action {
    & $sendKeyScript -ProcessName $ProcessName -Key A -HoldMilliseconds $MovementHoldMilliseconds -NoRefocus | Out-Null
}))
$results.Add((Invoke-InputValidationCase -Name 'send-s' -Action {
    & $sendKeyScript -ProcessName $ProcessName -Key S -HoldMilliseconds $MovementHoldMilliseconds -NoRefocus | Out-Null
}))
$results.Add((Invoke-InputValidationCase -Name 'send-d' -Action {
    & $sendKeyScript -ProcessName $ProcessName -Key D -HoldMilliseconds $MovementHoldMilliseconds -NoRefocus | Out-Null
}))
$results.Add((Invoke-InputValidationCase -Name 'send-space' -Action {
    & $sendKeyScript -ProcessName $ProcessName -Key SPACE -HoldMilliseconds $MovementHoldMilliseconds -NoRefocus | Out-Null
}))
$results.Add((Invoke-InputValidationCase -Name 'send-alt-z' -Action {
    & $sendKeyScript -ProcessName $ProcessName -Key Z -Alt -HoldMilliseconds $AltHoldMilliseconds -NoRefocus | Out-Null
}))
$results.Add((Invoke-InputValidationCase -Name 'post-alt-z' -Action {
    & $postKeyScript -TargetProcessName $ProcessName -Key Z -Alt -HoldMilliseconds $AltHoldMilliseconds | Out-Null
}))

$ambientChangePercent = ($results | Where-Object Name -eq 'control-noinput' | Select-Object -First 1).ChangePercent
$passThresholdPercent = [Math]::Max($ChangeThresholdPercent, ($ambientChangePercent + $PassMarginPercent))

$annotatedResults = foreach ($result in $results) {
    [pscustomobject]@{
        Name = $result.Name
        Pass = ($result.Name -ne 'control-noinput' -and $result.ChangePercent -ge $passThresholdPercent)
        ChangeDetected = $result.Changed
        ChangePercent = $result.ChangePercent
        ElapsedMilliseconds = $result.ElapsedMilliseconds
        BeforeScreenshot = $result.BeforeScreenshot
        AfterScreenshot = $result.AfterScreenshot
    }
}

$summary = [pscustomobject]@{
    RunId = $runId
    RunDirectory = $runDirectory
    ProcessName = $ProcessName
    AmbientChangePercent = $ambientChangePercent
    PassThresholdPercent = $passThresholdPercent
    MovementHoldMilliseconds = $MovementHoldMilliseconds
    AltHoldMilliseconds = $AltHoldMilliseconds
    Results = $annotatedResults
}

$summaryPath = Join-Path $runDirectory 'summary.json'
$summary | ConvertTo-Json -Depth 6 | Set-Content -Path $summaryPath -Encoding UTF8

if ($Json) {
    $summary | ConvertTo-Json -Depth 6
    exit 0
}

Write-Host "[InputValidation] Run directory : $runDirectory" -ForegroundColor Cyan
Write-Host "[InputValidation] Summary file  : $summaryPath" -ForegroundColor Cyan
Write-Host ("[InputValidation] Ambient noise : {0:N4}%" -f $ambientChangePercent) -ForegroundColor DarkGray
Write-Host ("[InputValidation] Pass threshold: {0:N4}%" -f $passThresholdPercent) -ForegroundColor DarkGray
Write-Host ""
$annotatedResults | Format-Table Name, Pass, ChangePercent, ElapsedMilliseconds -AutoSize
exit 0
