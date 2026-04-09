[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$SkipRefresh,
    [switch]$RefreshAnchor,
    [switch]$RefreshTraceAnchor,
    [switch]$RequireSmartCapture,
    [switch]$NoAhkFallback,
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

function Write-ReaderCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host "[ReadPlayerCurrent] dotnet run --project $readerProject -- $($Arguments -join ' ')" -ForegroundColor DarkGray
}

function Try-RefreshTraceAnchor {
    $anchorProbeArguments = @(
        '--process-name', 'rift_x64',
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
        & $traceScript -Json -MaxCandidates 1 | Out-Null
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
    & $postKeyScript -Key $RecoveryKey -HoldMilliseconds $RecoveryHoldMilliseconds

    $refreshArguments = @{
        NoReader = $true
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
        & $smartCaptureScript -ScanContextBytes $ScanContextBytes -MaxScanHits $MaxHits | Out-Null
    }
    catch {
        if ($RequireSmartCapture) {
            throw
        }

        Write-Warning ("CE-backed smart capture failed; continuing with normal family selection. {0}" -f $_.Exception.Message)
    }
}

$readerArguments = @(
    '--process-name', 'rift_x64',
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
