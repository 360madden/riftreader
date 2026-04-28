[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$SkipRefresh,
    [switch]$RefreshAnchor,
    [switch]$RefreshTraceAnchor,
    [switch]$RequireSmartCapture,
    [switch]$NoAhkFallback,
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [int]$RecoveryAttempts = 2,
    [string]$RecoveryKey = 'w',
    [int]$RecoveryHoldMilliseconds = 1000,
    [int]$ScanContextBytes = 192,
    [int]$MaxHits = 12
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$refreshScript = Join-Path $PSScriptRoot 'refresh-readerbridge-export.ps1'
$smartCaptureScript = Join-Path $PSScriptRoot 'smart-capture-player-family.ps1'
$postKeyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'
$traceScript = Join-Path $PSScriptRoot 'trace-player-coord-write.ps1'

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RiftReadPlayerCurrentTargetNative
{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@

function Invoke-ReaderCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & dotnet run --project $readerProject -- @Arguments 2>&1
    $exitCode = $LASTEXITCODE

    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = ($output -join [Environment]::NewLine)
    }
}

function ConvertTo-WindowHandle {
    param([string]$HandleText)

    if ([string]::IsNullOrWhiteSpace($HandleText)) {
        return [IntPtr]::Zero
    }

    if ($HandleText.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $raw = [UInt64]::Parse($HandleText.Substring(2), [System.Globalization.NumberStyles]::AllowHexSpecifier, [System.Globalization.CultureInfo]::InvariantCulture)
        return [IntPtr]([Int64]$raw)
    }

    return [IntPtr]([Int64]::Parse($HandleText, [System.Globalization.CultureInfo]::InvariantCulture))
}

function Get-EffectiveTargetProcessId {
    $handle = ConvertTo-WindowHandle -HandleText $TargetWindowHandle
    if ($handle -ne [IntPtr]::Zero) {
        if (-not [RiftReadPlayerCurrentTargetNative]::IsWindow($handle)) {
            throw "Target window handle '$TargetWindowHandle' is not a valid window."
        }

        $ownerProcessId = [uint32]0
        [void][RiftReadPlayerCurrentTargetNative]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
        if ($ownerProcessId -eq 0) {
            throw "Target window handle '$TargetWindowHandle' did not resolve to a process id."
        }

        if ($ProcessId -gt 0 -and [int]$ownerProcessId -ne $ProcessId) {
            throw "Target window handle '$TargetWindowHandle' belongs to PID $ownerProcessId, not PID $ProcessId."
        }

        return [int]$ownerProcessId
    }

    if ($ProcessId -gt 0) {
        return $ProcessId
    }

    return $null
}

function Get-ReaderTargetArguments {
    $effectiveProcessId = Get-EffectiveTargetProcessId
    if ($null -ne $effectiveProcessId -and $effectiveProcessId -gt 0) {
        return @('--pid', $effectiveProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    }

    return @('--process-name', $ProcessName)
}

function Get-TargetedScriptArguments {
    $effectiveProcessId = Get-EffectiveTargetProcessId
    $arguments = @{}
    if ($null -ne $effectiveProcessId -and $effectiveProcessId -gt 0) {
        $arguments['ProcessId'] = $effectiveProcessId
    }

    if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
        $arguments['TargetWindowHandle'] = $TargetWindowHandle
    }

    return $arguments
}

function Get-PostKeyTargetArguments {
    $effectiveProcessId = Get-EffectiveTargetProcessId
    $arguments = @{
        TargetProcessName = $ProcessName
    }
    if ($null -ne $effectiveProcessId -and $effectiveProcessId -gt 0) {
        $arguments['TargetProcessId'] = $effectiveProcessId
    }

    if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
        $arguments['TargetWindowHandle'] = $TargetWindowHandle
    }

    return $arguments
}

function Assert-ExactRecoveryTarget {
    $effectiveProcessId = Get-EffectiveTargetProcessId
    if ($null -eq $effectiveProcessId -or $effectiveProcessId -le 0) {
        throw "Recovery movement/input requires -ProcessId or -TargetWindowHandle. Refusing name-only '$ProcessName' targeting; rerun with an exact target or set -RecoveryAttempts 0."
    }
}

function Write-ReaderCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host "[ReadPlayerCurrent] dotnet run --project $readerProject -- $($Arguments -join ' ')" -ForegroundColor DarkGray
}

function Try-RefreshTraceAnchor {
    $anchorProbeArguments = @(Get-ReaderTargetArguments) + @(
        '--read-player-coord-anchor',
        '--json'
    )

    $anchorProbe = Invoke-ReaderCommand -Arguments $anchorProbeArguments
    if ($anchorProbe.ExitCode -ne 0) {
        Write-Host "[ReadPlayerCurrent] No usable coord-trace anchor artifact is available yet; skipping trace refresh." -ForegroundColor DarkGray
        return
    }

    $anchorState = $null
    try {
        $anchorState = $anchorProbe.Output | ConvertFrom-Json -Depth 20
    }
    catch {
        Write-Warning ("Unable to parse coord-trace anchor state; skipping trace refresh. {0}" -f $_.Exception.Message)
        return
    }

    if ($anchorState.TraceMatchesProcess -eq $true) {
        Write-Host "[ReadPlayerCurrent] Coord-trace anchor already matches the current Rift process." -ForegroundColor DarkGray
        return
    }

    Write-Host ""
    Write-Host "[ReadPlayerCurrent] Coord-trace anchor is stale; attempting a fresh coord trace for the current process..." -ForegroundColor Cyan

    try {
        $traceArguments = Get-TargetedScriptArguments
        $traceArguments['Json'] = $true
        $traceArguments['ProcessName'] = $ProcessName
        $traceArguments['MaxCandidates'] = 1
        $traceArguments['WatchMode'] = 'access'
        $traceArguments['StimulusMode'] = 'AutoHotkey'
        & $traceScript @traceArguments | Out-Null
    }
    catch {
        Write-Warning ("Coord-trace refresh failed; continuing without a fresh trace anchor. {0}" -f $_.Exception.Message)
    }
}

function Invoke-RecoveryMove {
    param(
        [Parameter(Mandatory = $true)]
        [int]$AttemptNumber
    )

    Write-Host ""
    Write-Host "[ReadPlayerCurrent] Recovery attempt $AttemptNumber/${RecoveryAttempts}: nudging the player to reacquire a full family..." -ForegroundColor Yellow
    Assert-ExactRecoveryTarget
    $postKeyArguments = Get-PostKeyTargetArguments
    $postKeyArguments['Key'] = $RecoveryKey
    $postKeyArguments['HoldMilliseconds'] = $RecoveryHoldMilliseconds
    & $postKeyScript @postKeyArguments

    $refreshArguments = @{
        NoReader = $true
        ProcessName = $ProcessName
    }
    $targetedArguments = Get-TargetedScriptArguments
    foreach ($key in $targetedArguments.Keys) {
        $refreshArguments[$key] = $targetedArguments[$key]
    }
    if ($NoAhkFallback) {
        $refreshArguments['NoAhkFallback'] = $true
    }

    & $refreshScript @refreshArguments
}

if (-not $SkipRefresh) {
    Write-Host "[ReadPlayerCurrent] Refreshing ReaderBridge export first..." -ForegroundColor Cyan
    $refreshArguments = @{
        NoReader = $true
        ProcessName = $ProcessName
    }
    $targetedArguments = Get-TargetedScriptArguments
    foreach ($key in $targetedArguments.Keys) {
        $refreshArguments[$key] = $targetedArguments[$key]
    }
    if ($NoAhkFallback) {
        $refreshArguments['NoAhkFallback'] = $true
    }

    & $refreshScript @refreshArguments
}

if ($RefreshTraceAnchor) {
    Try-RefreshTraceAnchor
}

if ($RefreshAnchor) {
    Write-Host ""
    Write-Host "[ReadPlayerCurrent] Refreshing the CE-backed player-family confirmation..." -ForegroundColor Cyan
    try {
        $smartCaptureArguments = Get-TargetedScriptArguments
        $smartCaptureArguments['ProcessName'] = $ProcessName
        $smartCaptureArguments['ScanContextBytes'] = $ScanContextBytes
        $smartCaptureArguments['MaxScanHits'] = $MaxHits
        & $smartCaptureScript @smartCaptureArguments | Out-Null
    }
    catch {
        if ($RequireSmartCapture) {
            throw
        }

        Write-Warning ("CE-backed smart capture failed; continuing with normal family selection. {0}" -f $_.Exception.Message)
    }
}

$readerArguments = @(Get-ReaderTargetArguments) + @(
    '--read-player-current',
    '--scan-context', $ScanContextBytes.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--max-hits', $MaxHits.ToString([System.Globalization.CultureInfo]::InvariantCulture)
)

if ($Json) {
    $readerArguments += '--json'
}

Write-ReaderCommand -Arguments $readerArguments
$readerResult = Invoke-ReaderCommand -Arguments $readerArguments
if ($readerResult.ExitCode -eq 0) {
    Write-Output $readerResult.Output
    exit 0
}

for ($attempt = 1; $attempt -le $RecoveryAttempts; $attempt++) {
    Invoke-RecoveryMove -AttemptNumber $attempt
    Write-ReaderCommand -Arguments $readerArguments
    $readerResult = Invoke-ReaderCommand -Arguments $readerArguments
    if ($readerResult.ExitCode -eq 0) {
        Write-Output $readerResult.Output
        exit 0
    }
}

Write-Error $readerResult.Output
exit $readerResult.ExitCode
