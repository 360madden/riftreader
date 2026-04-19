[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [string]$InstructionAddress = '0x7FF62BCE560E',
    [int]$DurationMilliseconds = 8000,
    [int]$MaxHits = 12,
    [int]$ArmTimeoutMilliseconds = 35000,
    [int]$KeyHoldMilliseconds = 150,
    [int]$InterStimulusDelayMilliseconds = 350,
    [string[]]$StimulusKeys = @('d', 'a', 'w', 'd', 'a', 'w'),
    [string]$PreferredAttachLabel = 'interface-2',
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { (Get-Location).Path }
$ceExecScript = Join-Path $scriptRoot 'cheatengine-exec.ps1'
$luaScript = Join-Path $scriptRoot 'cheat-engine\RiftReaderPersistentInstructionBatch.lua'
$postKeyScript = Join-Path $scriptRoot 'post-rift-key.ps1'
$captureRoot = Join-Path $scriptRoot 'captures\persistent-instruction-batch'
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$runDirectory = Join-Path $captureRoot $timestamp
$statusFile = Join-Path $runDirectory 'status.txt'
$hitsFile = Join-Path $runDirectory 'hits.ndjson'
$summaryFile = Join-Path $runDirectory 'summary.json'

New-Item -ItemType Directory -Force -Path $runDirectory | Out-Null

function ConvertTo-LuaString {
    param([string]$Value)

    return '[[' + ($Value -replace ']]', ']\]') + ']]'
}

function Read-KeyValueFile {
    param([string]$Path)

    $map = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $map
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $parts = $line -split '=', 2
        if ($parts.Count -eq 2) {
            $map[$parts[0]] = $parts[1]
        }
    }

    return $map
}

function Wait-ForStatusValue {
    param(
        [string]$Path,
        [string]$ExpectedValue,
        [int]$TimeoutMilliseconds = 15000
    )

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    while ($stopwatch.ElapsedMilliseconds -lt $TimeoutMilliseconds) {
        $status = Read-KeyValueFile -Path $Path
        if ($status.ContainsKey('status') -and $status['status'] -eq $ExpectedValue) {
            return $status
        }

        if ($status.ContainsKey('status') -and $status['status'] -eq 'error') {
            return $status
        }

        Start-Sleep -Milliseconds 100
    }

    return (Read-KeyValueFile -Path $Path)
}

$luaCode = @"
dofile($(ConvertTo-LuaString $luaScript))
return RiftReaderPersistentInstructionBatch.runAsync(
  $(ConvertTo-LuaString $ProcessName),
  $InstructionAddress,
  $(ConvertTo-LuaString $statusFile),
  $(ConvertTo-LuaString $hitsFile),
  $MaxHits,
  $DurationMilliseconds,
  $(ConvertTo-LuaString $PreferredAttachLabel)
)
"@

& powershell -ExecutionPolicy Bypass -File $ceExecScript -Code $luaCode | Out-Null

$sessionStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$initialStatus = Wait-ForStatusValue -Path $statusFile -ExpectedValue 'armed' -TimeoutMilliseconds $ArmTimeoutMilliseconds
if ($initialStatus['status'] -eq 'error') {
    throw "Persistent CE batch failed before arming: $($initialStatus['error'])"
}
if ($initialStatus['status'] -ne 'armed') {
    throw "Persistent CE batch never reached armed state within ${ArmTimeoutMilliseconds}ms. Last status: $($initialStatus['status']); stage: $($initialStatus['stage']); error: $($initialStatus['error'])"
}

$stimulusResults = @()
foreach ($key in $StimulusKeys) {
    $beforeStatus = Read-KeyValueFile -Path $statusFile
    if ($beforeStatus.ContainsKey('status') -and $beforeStatus['status'] -eq 'completed') {
        break
    }

    $stimulusOutput = (& powershell -ExecutionPolicy Bypass -File $postKeyScript -Key $key -HoldMilliseconds $KeyHoldMilliseconds -SkipBackgroundFocus 2>&1 | Out-String).Trim()
    $stimulusResults += [pscustomobject]@{
        Key = $key
        HoldMilliseconds = $KeyHoldMilliseconds
        Output = $stimulusOutput
        RecordedAtUtc = [DateTime]::UtcNow.ToString('o')
    }

    Start-Sleep -Milliseconds $InterStimulusDelayMilliseconds
}

$finalStatus = Read-KeyValueFile -Path $statusFile
while (($finalStatus['status'] -ne 'completed') -and ($finalStatus['status'] -ne 'error') -and ($sessionStopwatch.ElapsedMilliseconds -lt $DurationMilliseconds)) {
    Start-Sleep -Milliseconds 100
    $finalStatus = Read-KeyValueFile -Path $statusFile
}

if ($finalStatus['status'] -ne 'completed' -and $finalStatus['status'] -ne 'error') {
    $completeCode = @"
dofile($(ConvertTo-LuaString $luaScript))
return RiftReaderPersistentInstructionBatch.complete('timeout')
"@
    & powershell -ExecutionPolicy Bypass -File $ceExecScript -Code $completeCode | Out-Null
    $finalStatus = Read-KeyValueFile -Path $statusFile
}

$hits = @()
if (Test-Path -LiteralPath $hitsFile) {
    foreach ($line in Get-Content -LiteralPath $hitsFile) {
        if (-not [string]::IsNullOrWhiteSpace($line)) {
            $hits += $line | ConvertFrom-Json
        }
    }
}

$summary = [pscustomobject]@{
    RunDirectory = $runDirectory
    ProcessName = $ProcessName
    InstructionAddress = $InstructionAddress
    DurationMilliseconds = $DurationMilliseconds
    MaxHits = $MaxHits
    StimulusKeys = $StimulusKeys
    Status = $finalStatus
    HitCount = $hits.Count
    Hits = $hits
    StimulusResults = $stimulusResults
    StatusFile = $statusFile
    HitsFile = $hitsFile
}

$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryFile -Encoding UTF8

if ($Json) {
    $summary | ConvertTo-Json -Depth 8
}
else {
    $summary
}
