# ====================================================================================
# Script: Run-CameraDiscoveryStable.ps1
# Version: 1.0.0
# Purpose: Minimal, defensive root runner for the safe camera discovery scripts.
# CharacterCount: 0
# ====================================================================================

[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$HoldMilliseconds = 300,
    [int]$WaitMilliseconds = 500,
    [int]$ReadLength = 1024,
    [string]$ArtifactRoot = 'artifacts\camera-discovery',
    [switch]$RefreshOwnerComponents,
    [switch]$SkipBackgroundFocus,
    [switch]$SkipAltS,
    [switch]$SkipAltZ,
    [switch]$StopOnFirstError,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptRoot = Join-Path $repoRoot 'scripts'
$altSScript = Join-Path $scriptRoot 'test-camera-alts-stimulus-safe.ps1'
$altZScript = Join-Path $scriptRoot 'test-camera-altz-stimulus-safe.ps1'
$altSResultFile = Join-Path $scriptRoot 'captures' 'camera-alts-stimulus-safe.json'
$altZResultFile = Join-Path $scriptRoot 'captures' 'camera-altz-stimulus-safe.json'
$ownerComponentsFile = Join-Path $scriptRoot 'captures' 'player-owner-components.json'
$selectorTraceFile = Join-Path $scriptRoot 'captures' 'player-selector-owner-trace.json'
$artifactBase = Join-Path $repoRoot $ArtifactRoot

function Ensure-Directory {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Write-Utf8File {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][AllowEmptyString()][string]$Content
    )

    $parent = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($parent)) {
        Ensure-Directory -Path $parent
    }

    Set-Content -LiteralPath $Path -Value $Content -Encoding UTF8
}

function Add-Event {
    param(
        [Parameter(Mandatory)][string]$EventsPath,
        [Parameter(Mandatory)][string]$Phase,
        [Parameter(Mandatory)][string]$Kind,
        [object]$Data
    )

    $record = [ordered]@{
        TimestampUtc = [DateTimeOffset]::UtcNow.ToString('O')
        Phase = $Phase
        Kind = $Kind
        Data = if ($null -ne $Data) { $Data } else { [ordered]@{} }
    }

    Add-Content -LiteralPath $EventsPath -Value (($record | ConvertTo-Json -Depth 20 -Compress)) -Encoding UTF8
}

function Save-Bundle {
    param(
        [Parameter(Mandatory)][object]$Bundle,
        [Parameter(Mandatory)][string]$Path
    )

    Write-Utf8File -Path $Path -Content ($Bundle | ConvertTo-Json -Depth 40)
}

function Copy-IfExists {
    param(
        [Parameter(Mandatory)][string]$Source,
        [Parameter(Mandatory)][string]$Destination
    )

    if (Test-Path -LiteralPath $Source) {
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
        return $true
    }

    return $false
}

function Invoke-Phase {
    param(
        [Parameter(Mandatory)][string]$PhaseName,
        [Parameter(Mandatory)][string]$ScriptPath,
        [Parameter(Mandatory)][string]$SourceResultFile,
        [Parameter(Mandatory)][string]$DestinationResultFile
    )

    $args = @{
        ProcessName = $ProcessName
        HoldMilliseconds = $HoldMilliseconds
        WaitMilliseconds = $WaitMilliseconds
        ReadLength = $ReadLength
        Json = $true
    }

    if ($RefreshOwnerComponents) {
        $args['RefreshOwnerComponents'] = $true
    }

    if ($SkipBackgroundFocus) {
        $args['SkipBackgroundFocus'] = $true
    }

    $phaseOutput = $null
    $exitCode = 0
    $exceptionMessage = $null

    try {
        $phaseOutput = & $ScriptPath @args 2>&1
        if ($null -ne $LASTEXITCODE) {
            $exitCode = $LASTEXITCODE
        }
    }
    catch {
        $exitCode = 1
        $exceptionMessage = $_.Exception.Message
    }

    $copied = Copy-IfExists -Source $SourceResultFile -Destination $DestinationResultFile
    $parsedJson = $null
    $parseError = $null

    if ($copied) {
        try {
            $parsedJson = Get-Content -LiteralPath $DestinationResultFile -Raw | ConvertFrom-Json -Depth 40
        }
        catch {
            $parseError = $_.Exception.Message
        }
    }

    $outputText = if ($null -ne $phaseOutput) {
        (($phaseOutput | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine)
    } else {
        $null
    }

    return [ordered]@{
        ExitCode = $exitCode
        ExceptionMessage = $exceptionMessage
        ResultFileCreated = $copied
        ResultFile = if ($copied) { $DestinationResultFile } else { $null }
        ParseError = $parseError
        OutputTail = if ([string]::IsNullOrWhiteSpace($outputText)) { $null } elseif ($outputText.Length -gt 3000) { $outputText.Substring($outputText.Length - 3000) } else { $outputText }
        ParsedJson = $parsedJson
    }
}

if (-not (Test-Path -LiteralPath $altSScript)) { throw "Missing script: $altSScript" }
if (-not (Test-Path -LiteralPath $altZScript)) { throw "Missing script: $altZScript" }

if (-not $RefreshOwnerComponents) {
    if (-not (Test-Path -LiteralPath $ownerComponentsFile)) {
        throw "Cached owner components file is missing: $ownerComponentsFile"
    }

    if (-not (Test-Path -LiteralPath $selectorTraceFile)) {
        throw "Cached selector trace file is missing: $selectorTraceFile"
    }
}

Ensure-Directory -Path $artifactBase

$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$runDirectory = Join-Path $artifactBase ("run-{0}" -f $runId)
Ensure-Directory -Path $runDirectory

$bundlePath = Join-Path $runDirectory 'bundle.json'
$eventsPath = Join-Path $runDirectory 'events.jsonl'

Write-Utf8File -Path $eventsPath -Content ''

$bundle = [ordered]@{
    Mode = 'camera-discovery-stable'
    Version = '1.0.0'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    RunId = $runId
    RepoRoot = $repoRoot
    RunDirectory = $runDirectory
    RefreshOwnerComponents = [bool]$RefreshOwnerComponents
    SkipBackgroundFocus = [bool]$SkipBackgroundFocus
    StopOnFirstError = [bool]$StopOnFirstError
    ProcessName = $ProcessName
    HoldMilliseconds = $HoldMilliseconds
    WaitMilliseconds = $WaitMilliseconds
    ReadLength = $ReadLength
    Status = 'running'
    Results = [ordered]@{}
    Errors = @()
}

Save-Bundle -Bundle $bundle -Path $bundlePath
Add-Event -EventsPath $eventsPath -Phase 'suite' -Kind 'start' -Data ([ordered]@{ RunId = $runId })

if (-not $SkipAltS) {
    Add-Event -EventsPath $eventsPath -Phase 'AltS' -Kind 'start' -Data ([ordered]@{})
    $altSPhase = Invoke-Phase -PhaseName 'AltS' -ScriptPath $altSScript -SourceResultFile $altSResultFile -DestinationResultFile (Join-Path $runDirectory 'alt-s.json')
    $bundle.Results['AltS'] = $altSPhase
    if ($altSPhase.ExitCode -ne 0 -or $null -ne $altSPhase.ExceptionMessage) {
        $bundle.Errors += [ordered]@{ Phase = 'AltS'; Message = if ($altSPhase.ExceptionMessage) { $altSPhase.ExceptionMessage } else { "Exit code $($altSPhase.ExitCode)" } }
        Add-Event -EventsPath $eventsPath -Phase 'AltS' -Kind 'error' -Data $bundle.Errors[-1]
        if ($StopOnFirstError) {
            $bundle.Status = 'failed'
            Save-Bundle -Bundle $bundle -Path $bundlePath
            throw 'AltS phase failed.'
        }
    } else {
        Add-Event -EventsPath $eventsPath -Phase 'AltS' -Kind 'finish' -Data ([ordered]@{ ExitCode = 0 })
    }
    Save-Bundle -Bundle $bundle -Path $bundlePath
}

if (-not $SkipAltZ) {
    Add-Event -EventsPath $eventsPath -Phase 'AltZ' -Kind 'start' -Data ([ordered]@{})
    $altZPhase = Invoke-Phase -PhaseName 'AltZ' -ScriptPath $altZScript -SourceResultFile $altZResultFile -DestinationResultFile (Join-Path $runDirectory 'alt-z.json')
    $bundle.Results['AltZ'] = $altZPhase
    if ($altZPhase.ExitCode -ne 0 -or $null -ne $altZPhase.ExceptionMessage) {
        $bundle.Errors += [ordered]@{ Phase = 'AltZ'; Message = if ($altZPhase.ExceptionMessage) { $altZPhase.ExceptionMessage } else { "Exit code $($altZPhase.ExitCode)" } }
        Add-Event -EventsPath $eventsPath -Phase 'AltZ' -Kind 'error' -Data $bundle.Errors[-1]
        if ($StopOnFirstError) {
            $bundle.Status = 'failed'
            Save-Bundle -Bundle $bundle -Path $bundlePath
            throw 'AltZ phase failed.'
        }
    } else {
        Add-Event -EventsPath $eventsPath -Phase 'AltZ' -Kind 'finish' -Data ([ordered]@{ ExitCode = 0 })
    }
    Save-Bundle -Bundle $bundle -Path $bundlePath
}

$bundle.Status = if ($bundle.Errors.Count -gt 0) { 'completed-with-errors' } else { 'completed' }
$bundle.Summary = [ordered]@{
    ErrorCount = $bundle.Errors.Count
    AltSResultFile = if ($bundle.Results.Contains('AltS')) { $bundle.Results.AltS.ResultFile } else { $null }
    AltZResultFile = if ($bundle.Results.Contains('AltZ')) { $bundle.Results.AltZ.ResultFile } else { $null }
    AltSTotalFloatChanges = if ($bundle.Results.Contains('AltS') -and $null -ne $bundle.Results.AltS.ParsedJson) { $bundle.Results.AltS.ParsedJson.TotalFloatChanges } else { $null }
    AltSFlipCandidateCount = if ($bundle.Results.Contains('AltS') -and $null -ne $bundle.Results.AltS.ParsedJson) { $bundle.Results.AltS.ParsedJson.FlipCandidateCount } else { $null }
    AltZTotalFloatChanges = if ($bundle.Results.Contains('AltZ') -and $null -ne $bundle.Results.AltZ.ParsedJson) { $bundle.Results.AltZ.ParsedJson.TotalFloatChanges } else { $null }
    AltZDistanceCandidateCount = if ($bundle.Results.Contains('AltZ') -and $null -ne $bundle.Results.AltZ.ParsedJson) { $bundle.Results.AltZ.ParsedJson.DistanceCandidateCount } else { $null }
}

Save-Bundle -Bundle $bundle -Path $bundlePath
Add-Event -EventsPath $eventsPath -Phase 'suite' -Kind 'finish' -Data ([ordered]@{ Status = $bundle.Status; ErrorCount = $bundle.Errors.Count })

Write-Host ''
Write-Host '=== Camera Discovery Stable Run Complete ===' -ForegroundColor Green
Write-Host "Run directory: $runDirectory" -ForegroundColor Green
Write-Host "Bundle:        $bundlePath" -ForegroundColor Green
Write-Host "Events:        $eventsPath" -ForegroundColor Green
Write-Host "Status:        $($bundle.Status)" -ForegroundColor White

if ($Json) {
    $bundle | ConvertTo-Json -Depth 40
}

# End of script
