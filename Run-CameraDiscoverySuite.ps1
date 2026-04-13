# ====================================================================================
# Script: Run-CameraDiscoverySuite.ps1
# Version: 1.0.0
# Purpose: Run the existing Alt-S and Alt-Z camera discovery harness scripts from the
#          repo root, then consolidate their JSON outputs into a single bundle file.
# CharacterCount: 5366
# ====================================================================================

[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$HoldMilliseconds = 300,
    [int]$WaitMilliseconds = 500,
    [int]$ReadLength = 1024,
    [switch]$SkipBackgroundFocus,
    [switch]$RefreshOwnerComponents,
    [switch]$SkipAltS,
    [switch]$SkipAltZ,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptRoot = Join-Path $repoRoot 'scripts'
$captureRoot = Join-Path $scriptRoot 'captures'
$altSScript = Join-Path $scriptRoot 'test-camera-alts-stimulus.ps1'
$altZScript = Join-Path $scriptRoot 'test-camera-altz-stimulus.ps1'

function Assert-PathExists {
    param(
        [Parameter(Mandatory)]
        [string]$Path,
        [Parameter(Mandatory)]
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label not found: $Path"
    }
}

function Invoke-CameraHarness {
    param(
        [Parameter(Mandatory)]
        [string]$ScriptPath,
        [Parameter(Mandatory)]
        [string]$Label
    )

    Write-Host ''
    Write-Host "=== Running $Label ===" -ForegroundColor Cyan

    $invokeArgs = @{
        ProcessName = $ProcessName
        HoldMilliseconds = $HoldMilliseconds
        WaitMilliseconds = $WaitMilliseconds
        Json = $true
    }

    if ($PSBoundParameters.ContainsKey('ReadLength')) {
        $invokeArgs['ReadLength'] = $ReadLength
    }

    if ($SkipBackgroundFocus) {
        $invokeArgs['SkipBackgroundFocus'] = $true
    }

    if ($RefreshOwnerComponents) {
        $invokeArgs['RefreshOwnerComponents'] = $true
    }

    $output = & $ScriptPath @invokeArgs 2>&1
    $textLines = @($output | ForEach-Object { $_.ToString() })
    $jsonBlob = $textLines -join "`n"
    $startIdx = $jsonBlob.IndexOf('{')
    if ($startIdx -lt 0) {
        throw "No JSON found in $Label output. Raw output:`n$($textLines -join "`n")"
    }

    $jsonBlob = $jsonBlob.Substring($startIdx)
    $result = $jsonBlob | ConvertFrom-Json -Depth 50

    return [ordered]@{
        Label = $Label
        ScriptPath = $ScriptPath
        Result = $result
    }
}

Assert-PathExists -Path $scriptRoot -Label 'scripts folder'
Assert-PathExists -Path $altSScript -Label 'Alt-S stimulus script'
Assert-PathExists -Path $altZScript -Label 'Alt-Z stimulus script'

if (-not (Test-Path -LiteralPath $captureRoot)) {
    New-Item -ItemType Directory -Path $captureRoot -Force | Out-Null
}

$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$bundle = [ordered]@{
    Mode = 'camera-discovery-suite'
    Version = '1.0.0'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    RepoRoot = $repoRoot
    ProcessName = $ProcessName
    HoldMilliseconds = $HoldMilliseconds
    WaitMilliseconds = $WaitMilliseconds
    ReadLength = $ReadLength
    RefreshOwnerComponents = [bool]$RefreshOwnerComponents
    SkipBackgroundFocus = [bool]$SkipBackgroundFocus
    RunId = $runId
    Results = [ordered]@{}
}

if (-not $SkipAltS) {
    $altS = Invoke-CameraHarness -ScriptPath $altSScript -Label 'Alt-S look-behind test'
    $bundle.Results['AltS'] = $altS.Result
}
else {
    Write-Host 'Skipping Alt-S test by request.' -ForegroundColor DarkYellow
}

if (-not $SkipAltZ) {
    $altZ = Invoke-CameraHarness -ScriptPath $altZScript -Label 'Alt-Z zoom test'
    $bundle.Results['AltZ'] = $altZ.Result
}
else {
    Write-Host 'Skipping Alt-Z test by request.' -ForegroundColor DarkYellow
}

$summary = [ordered]@{
    AltS = if ($bundle.Results.Contains('AltS')) {
        [ordered]@{
            TotalFloatChanges = $bundle.Results.AltS.TotalFloatChanges
            FlipCandidateCount = $bundle.Results.AltS.FlipCandidateCount
            ChangedUnitVectorCount = $bundle.Results.AltS.ChangedUnitVectorCount
        }
    } else { $null }
    AltZ = if ($bundle.Results.Contains('AltZ')) {
        [ordered]@{
            TotalFloatChanges = $bundle.Results.AltZ.TotalFloatChanges
            DistanceCandidateCount = $bundle.Results.AltZ.DistanceCandidateCount
        }
    } else { $null }
}
$bundle['Summary'] = $summary

$outputFile = Join-Path $captureRoot ("camera-discovery-suite-{0}.json" -f $runId)
$bundle | ConvertTo-Json -Depth 60 | Set-Content -LiteralPath $outputFile -Encoding UTF8

Write-Host ''
Write-Host '=== Camera Discovery Suite Complete ===' -ForegroundColor Green
Write-Host "Bundle saved to: $outputFile" -ForegroundColor Green
if ($summary.AltS) {
    Write-Host ("Alt-S: changes={0}, flipCandidates={1}, changedUnitVectors={2}" -f `
        $summary.AltS.TotalFloatChanges,
        $summary.AltS.FlipCandidateCount,
        $summary.AltS.ChangedUnitVectorCount) -ForegroundColor White
}
if ($summary.AltZ) {
    Write-Host ("Alt-Z: changes={0}, distanceCandidates={1}" -f `
        $summary.AltZ.TotalFloatChanges,
        $summary.AltZ.DistanceCandidateCount) -ForegroundColor White
}

if ($Json) {
    $bundle | ConvertTo-Json -Depth 60
}

# End of script
