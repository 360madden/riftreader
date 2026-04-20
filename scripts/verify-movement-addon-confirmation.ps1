[CmdletBinding()]
param(
    [string]$Key = 'W',
    [int]$HoldMilliseconds = 1000,
    [int]$WaitMilliseconds = 1000,
    [switch]$Json,
    [switch]$NoAhkFallback,
    [switch]$SkipBackgroundFocus,
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\movement-addon-confirmation.json'),
    [string]$HistoryFile = (Join-Path $PSScriptRoot 'captures\movement-addon-confirmation-history.ndjson')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'logging-common.ps1')

$stimulusScript = Join-Path $PSScriptRoot 'test-actor-orientation-stimulus.ps1'
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$resolvedHistoryFile = [System.IO.Path]::GetFullPath($HistoryFile)
$runId = New-LogRunId -Source 'movement-addon-confirmation'

$stimulusArgs = @{
    Key = $Key
    HoldMilliseconds = $HoldMilliseconds
    WaitMilliseconds = $WaitMilliseconds
    Json = $true
}

if ($NoAhkFallback) {
    $stimulusArgs['NoAhkFallback'] = $true
}

if ($SkipBackgroundFocus) {
    $stimulusArgs['SkipBackgroundFocus'] = $true
}

$stimulusJson = & $stimulusScript @stimulusArgs
if ($LASTEXITCODE -ne 0) {
    throw "Movement addon confirmation stimulus failed for key '$Key'."
}

$stimulus = $stimulusJson | ConvertFrom-Json -Depth 60
$comparison = $stimulus.Comparison
$summary = [pscustomobject]@{
    AddonCoordDeltaMagnitude = $comparison.AddonCoordDeltaMagnitude
    AddonCoordMovementConfirmed = [bool]$comparison.AddonCoordMovementConfirmed
    PreferredLiveCoordDeltaMagnitude = $comparison.PreferredLiveCoordDeltaMagnitude
    LiveCoord48DeltaMagnitude = $comparison.LiveCoord48DeltaMagnitude
    LiveCoord88DeltaMagnitude = $comparison.LiveCoord88DeltaMagnitude
    LiveCoordMovementConfirmed = [bool]$comparison.LiveCoordMovementConfirmed
    AnyCoordMovementConfirmed = [bool]$comparison.AnyCoordMovementConfirmed
    TelemetryAlignmentStatus = [string]$comparison.TelemetryAlignmentStatus
    TelemetryBlocker = [bool]$comparison.TelemetryBlocker
}

$document = [pscustomobject]@{
    Mode = 'movement-addon-confirmation'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    RunId = $runId
    OutputFile = $resolvedOutputFile
    HistoryFile = $resolvedHistoryFile
    Key = $Key
    HoldMilliseconds = $HoldMilliseconds
    WaitMilliseconds = $WaitMilliseconds
    Summary = $summary
    Result = $stimulus
}

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$historyDirectory = Split-Path -Path $resolvedHistoryFile -Parent
if (-not [string]::IsNullOrWhiteSpace($historyDirectory)) {
    New-Item -ItemType Directory -Path $historyDirectory -Force | Out-Null
}

$jsonText = $document | ConvertTo-Json -Depth 60
[System.IO.File]::WriteAllText($resolvedOutputFile, $jsonText)

$historyLevel = if ($summary.TelemetryBlocker) { 'warn' } elseif ($summary.AnyCoordMovementConfirmed) { 'info' } else { 'warn' }
$historyEntry = New-StructuredLogEntry `
    -Level $historyLevel `
    -Source 'movement-addon-confirmation' `
    -RunId $runId `
    -Message ("Movement addon confirmation completed for key '{0}'." -f $Key) `
    -Data ([ordered]@{
        key = $Key
        holdMilliseconds = $HoldMilliseconds
        waitMilliseconds = $WaitMilliseconds
        summary = $summary
        outputFile = $resolvedOutputFile
    })

Write-StructuredLogLine -Path $resolvedHistoryFile -Entry $historyEntry

if ($Json) {
    Write-Output $jsonText
    exit 0
}

Write-Output $jsonText
