# PREFERRED UNATTENDED HARNESS: Run repeated live input validation passes and aggregate the results.
[CmdletBinding()]
param(
    [ValidateRange(1, 20)]
    [int]$Trials = 3,
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
$validatorScript = Join-Path $PSScriptRoot 'validate-rift-input.ps1'

if (-not (Test-Path -LiteralPath $validatorScript)) {
    throw "Validation script not found: $validatorScript"
}

$batchId = Get-Date -Format 'yyyyMMdd-HHmmss'
$batchDirectory = Join-Path $repoRoot ("artifacts\input-validation\batch-$batchId")
New-Item -ItemType Directory -Force -Path $batchDirectory | Out-Null

function Convert-ValidatorOutputToJson {
    param([string]$RawOutput)

    $lines = $RawOutput -split "`r?`n"
    $jsonStart = -1
    for ($i = 0; $i -lt $lines.Length; $i++) {
        if ($lines[$i].TrimStart().StartsWith('{')) {
            $jsonStart = $i
            break
        }
    }

    if ($jsonStart -lt 0) {
        throw "Could not find JSON payload in validator output."
    }

    $jsonText = $lines[$jsonStart..($lines.Length - 1)] -join [Environment]::NewLine
    return ($jsonText | ConvertFrom-Json -ErrorAction Stop)
}

$trialSummaries = [System.Collections.Generic.List[object]]::new()

for ($trial = 1; $trial -le $Trials; $trial++) {
    Write-Host "[UnattendedInputValidation] Starting trial $trial of $Trials..." -ForegroundColor Cyan

    $raw = & $validatorScript `
        -Json `
        -ProcessName $ProcessName `
        -MovementHoldMilliseconds $MovementHoldMilliseconds `
        -AltHoldMilliseconds $AltHoldMilliseconds `
        -PreActionDelayMilliseconds $PreActionDelayMilliseconds `
        -WaitTimeoutMilliseconds $WaitTimeoutMilliseconds `
        -PollIntervalMilliseconds $PollIntervalMilliseconds `
        -ChangeThresholdPercent $ChangeThresholdPercent `
        -PassMarginPercent $PassMarginPercent 2>&1 | Out-String

    $summary = Convert-ValidatorOutputToJson -RawOutput $raw
    $trialSummaries.Add($summary)
    Start-Sleep -Milliseconds 500
}

$aggregatedResults = foreach ($group in ($trialSummaries.Results | Group-Object Name)) {
    $items = @($group.Group)
    $changeValues = @($items | ForEach-Object { [double]$_.ChangePercent } | Sort-Object)
    $medianIndex = [int][Math]::Floor(($changeValues.Count - 1) / 2)
    $medianChange = $changeValues[$medianIndex]

    $relativeValues = [System.Collections.Generic.List[double]]::new()
    $overAmbientCount = 0
    $overPassThresholdCount = 0

    foreach ($trialSummary in $trialSummaries) {
        $trialResult = @($trialSummary.Results | Where-Object Name -eq $group.Name)[0]
        $relative = [double]$trialResult.ChangePercent - [double]$trialSummary.AmbientChangePercent
        $relativeValues.Add($relative)
        if ($trialResult.ChangePercent -gt $trialSummary.AmbientChangePercent) {
            $overAmbientCount++
        }
        if ($trialResult.ChangePercent -ge $trialSummary.PassThresholdPercent) {
            $overPassThresholdCount++
        }
    }

    $sortedRelativeValues = @($relativeValues | Sort-Object)
    $medianRelative = $sortedRelativeValues[$medianIndex]

    [pscustomobject]@{
        Name = $group.Name
        MedianChangePercent = [Math]::Round($medianChange, 4)
        MedianRelativeToAmbient = [Math]::Round($medianRelative, 4)
        OverAmbientRuns = "$overAmbientCount/$Trials"
        OverPassThresholdRuns = "$overPassThresholdCount/$Trials"
    }
}

$aggregateSummary = [pscustomobject]@{
    BatchId = $batchId
    BatchDirectory = $batchDirectory
    TrialCount = $Trials
    TrialRunDirectories = @($trialSummaries | ForEach-Object { $_.RunDirectory })
    AmbientChangePercents = @($trialSummaries | ForEach-Object { [double]$_.AmbientChangePercent })
    PassThresholdPercents = @($trialSummaries | ForEach-Object { [double]$_.PassThresholdPercent })
    AggregatedResults = $aggregatedResults
}

$summaryPath = Join-Path $batchDirectory 'aggregate-summary.json'
$aggregateSummary | ConvertTo-Json -Depth 6 | Set-Content -Path $summaryPath -Encoding UTF8

if ($Json) {
    $aggregateSummary | ConvertTo-Json -Depth 6
    exit 0
}

Write-Host "[UnattendedInputValidation] Batch directory: $batchDirectory" -ForegroundColor Cyan
Write-Host "[UnattendedInputValidation] Summary file  : $summaryPath" -ForegroundColor Cyan
Write-Host ""
$aggregatedResults | Format-Table Name, MedianChangePercent, MedianRelativeToAmbient, OverAmbientRuns, OverPassThresholdRuns -AutoSize
exit 0
