# ====================================================================================
# Script: Run-AltZRetry.ps1
# Version: 1.0.0
# Purpose: Retry the safe Alt-Z camera stimulus with longer hold/wait timings and
#          preserve attempt artifacts without crashing on partial failures.
# CharacterCount: 0
# ====================================================================================

[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$FirstHoldMilliseconds = 750,
    [int]$FirstWaitMilliseconds = 800,
    [int]$SecondHoldMilliseconds = 1200,
    [int]$SecondWaitMilliseconds = 1000,
    [int]$ReadLength = 1024,
    [string]$ArtifactRoot = 'artifacts\camera-discovery-altz',
    [switch]$RefreshOwnerComponents,
    [switch]$SkipBackgroundFocus,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptRoot = Join-Path $repoRoot 'scripts'
$altZScript = Join-Path $scriptRoot 'test-camera-altz-stimulus-safe.ps1'
$altZResultFile = Join-Path $scriptRoot 'captures' 'camera-altz-stimulus-safe.json'
$ownerComponentsFile = Join-Path $scriptRoot 'captures' 'player-owner-components.json'
$selectorTraceFile = Join-Path $scriptRoot 'captures' 'player-selector-owner-trace.json'
$artifactBase = Join-Path $repoRoot $ArtifactRoot

function New-DirectoryIfMissing {
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
        New-DirectoryIfMissing -Path $parent
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

function Invoke-AltZAttempt {
    param(
        [Parameter(Mandatory)][string]$Label,
        [Parameter(Mandatory)][int]$HoldMilliseconds,
        [Parameter(Mandatory)][int]$WaitMilliseconds,
        [Parameter(Mandatory)][string]$DestinationResultFile
    )

    $scriptArgs = @{
        ProcessName = $ProcessName
        HoldMilliseconds = $HoldMilliseconds
        WaitMilliseconds = $WaitMilliseconds
        ReadLength = $ReadLength
        Json = $true
    }

    if ($RefreshOwnerComponents) {
        $scriptArgs['RefreshOwnerComponents'] = $true
    }
    if ($SkipBackgroundFocus) {
        $scriptArgs['SkipBackgroundFocus'] = $true
    }

    $output = $null
    $exitCode = 0
    $exceptionMessage = $null

    try {
        $output = & $altZScript @scriptArgs 2>&1
        if ($null -ne $LASTEXITCODE) {
            $exitCode = $LASTEXITCODE
        }
    }
    catch {
        $exitCode = 1
        $exceptionMessage = $_.Exception.Message
    }

    $copied = Copy-IfExists -Source $altZResultFile -Destination $DestinationResultFile
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

    $outputText = if ($null -ne $output) { (($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine) } else { $null }

    return [ordered]@{
        Label = $Label
        HoldMilliseconds = $HoldMilliseconds
        WaitMilliseconds = $WaitMilliseconds
        ExitCode = $exitCode
        ExceptionMessage = $exceptionMessage
        ResultFileCreated = $copied
        ResultFile = if ($copied) { $DestinationResultFile } else { $null }
        ParseError = $parseError
        OutputTail = if ([string]::IsNullOrWhiteSpace($outputText)) { $null } elseif ($outputText.Length -gt 3000) { $outputText.Substring($outputText.Length - 3000) } else { $outputText }
        ParsedJson = $parsedJson
    }
}

if (-not (Test-Path -LiteralPath $altZScript)) {
    throw "Missing script: $altZScript"
}

if (-not $RefreshOwnerComponents) {
    if (-not (Test-Path -LiteralPath $ownerComponentsFile)) {
        throw "Cached owner components file is missing: $ownerComponentsFile"
    }
    if (-not (Test-Path -LiteralPath $selectorTraceFile)) {
        throw "Cached selector trace file is missing: $selectorTraceFile"
    }
}

New-DirectoryIfMissing -Path $artifactBase
$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$runDirectory = Join-Path $artifactBase ("run-{0}" -f $runId)
New-DirectoryIfMissing -Path $runDirectory
$bundlePath = Join-Path $runDirectory 'bundle.json'
$eventsPath = Join-Path $runDirectory 'events.jsonl'
Write-Utf8File -Path $eventsPath -Content ''

$bundle = [ordered]@{
    Mode = 'camera-discovery-altz-retry'
    Version = '1.0.0'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    RunId = $runId
    RunDirectory = $runDirectory
    ProcessName = $ProcessName
    ReadLength = $ReadLength
    RefreshOwnerComponents = [bool]$RefreshOwnerComponents
    SkipBackgroundFocus = [bool]$SkipBackgroundFocus
    Status = 'running'
    Attempts = @()
    Errors = @()
}
Save-Bundle -Bundle $bundle -Path $bundlePath
Add-Event -EventsPath $eventsPath -Phase 'suite' -Kind 'start' -Data ([ordered]@{ RunId = $runId })

$attempt1 = Invoke-AltZAttempt -Label 'attempt-1' -HoldMilliseconds $FirstHoldMilliseconds -WaitMilliseconds $FirstWaitMilliseconds -DestinationResultFile (Join-Path $runDirectory 'alt-z-attempt-1.json')
$bundle.Attempts += $attempt1
Add-Event -EventsPath $eventsPath -Phase 'attempt-1' -Kind 'finish' -Data ([ordered]@{ ExitCode = $attempt1.ExitCode; HoldMilliseconds = $FirstHoldMilliseconds; WaitMilliseconds = $FirstWaitMilliseconds })
Save-Bundle -Bundle $bundle -Path $bundlePath

$needSecondAttempt = $true
if ($attempt1.ExitCode -eq 0 -and $null -ne $attempt1.ParsedJson) {
    $changes = [int]$attempt1.ParsedJson.TotalFloatChanges
    $distance = [int]$attempt1.ParsedJson.DistanceCandidateCount
    if ($changes -gt 0 -or $distance -gt 0) {
        $needSecondAttempt = $false
    }
}

if ($needSecondAttempt) {
    Add-Event -EventsPath $eventsPath -Phase 'attempt-2' -Kind 'start' -Data ([ordered]@{ Reason = 'first attempt had no useful Alt-Z signal or failed' })
    $attempt2 = Invoke-AltZAttempt -Label 'attempt-2' -HoldMilliseconds $SecondHoldMilliseconds -WaitMilliseconds $SecondWaitMilliseconds -DestinationResultFile (Join-Path $runDirectory 'alt-z-attempt-2.json')
    $bundle.Attempts += $attempt2
    Add-Event -EventsPath $eventsPath -Phase 'attempt-2' -Kind 'finish' -Data ([ordered]@{ ExitCode = $attempt2.ExitCode; HoldMilliseconds = $SecondHoldMilliseconds; WaitMilliseconds = $SecondWaitMilliseconds })
    Save-Bundle -Bundle $bundle -Path $bundlePath
}

foreach ($attempt in $bundle.Attempts) {
    if ($attempt.ExitCode -ne 0 -or $null -ne $attempt.ExceptionMessage) {
        $bundle.Errors += [ordered]@{
            Attempt = $attempt.Label
            Message = if ($attempt.ExceptionMessage) { $attempt.ExceptionMessage } else { "Exit code $($attempt.ExitCode)" }
        }
    }
}

$bestAttempt = $null
foreach ($attempt in $bundle.Attempts) {
    if ($null -eq $attempt.ParsedJson) { continue }
    if ($null -eq $bestAttempt) {
        $bestAttempt = $attempt
        continue
    }

    $currentScore = ([int]$attempt.ParsedJson.DistanceCandidateCount * 1000) + [int]$attempt.ParsedJson.TotalFloatChanges
    $bestScore = ([int]$bestAttempt.ParsedJson.DistanceCandidateCount * 1000) + [int]$bestAttempt.ParsedJson.TotalFloatChanges
    if ($currentScore -gt $bestScore) {
        $bestAttempt = $attempt
    }
}

$bundle.Status = if ($bundle.Errors.Count -gt 0) { 'completed-with-errors' } else { 'completed' }
$bundle.Summary = [ordered]@{
    AttemptCount = $bundle.Attempts.Count
    ErrorCount = $bundle.Errors.Count
    BestAttempt = if ($null -ne $bestAttempt) { $bestAttempt.Label } else { $null }
    BestAttemptDistanceCandidateCount = if ($null -ne $bestAttempt -and $null -ne $bestAttempt.ParsedJson) { $bestAttempt.ParsedJson.DistanceCandidateCount } else { $null }
    BestAttemptTotalFloatChanges = if ($null -ne $bestAttempt -and $null -ne $bestAttempt.ParsedJson) { $bestAttempt.ParsedJson.TotalFloatChanges } else { $null }
}
Save-Bundle -Bundle $bundle -Path $bundlePath
Add-Event -EventsPath $eventsPath -Phase 'suite' -Kind 'finish' -Data ([ordered]@{ Status = $bundle.Status; AttemptCount = $bundle.Attempts.Count; ErrorCount = $bundle.Errors.Count })

Write-Host ''
Write-Host '=== Alt-Z Retry Run Complete ===' -ForegroundColor Green
Write-Host "Run directory: $runDirectory" -ForegroundColor Green
Write-Host "Bundle:        $bundlePath" -ForegroundColor Green
Write-Host "Status:        $($bundle.Status)" -ForegroundColor White

if ($Json) {
    $bundle | ConvertTo-Json -Depth 40
}

# End of script
