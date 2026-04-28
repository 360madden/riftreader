[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$NoReader,
    [switch]$NoAhkFallback,
    [switch]$SkipBackgroundFocus,
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$postCommandScript = Join-Path $PSScriptRoot 'post-rift-command.ps1'
$postCommandAhkScript = Join-Path $PSScriptRoot 'post-rift-command-ahk.ps1'

Write-Host "[RiftRefresh] Forcing a Rift UI reload via the native no-focus PostMessage helper..." -ForegroundColor Cyan
try {
    $postArguments = @{
        Command = '/reloadui'
        TargetProcessName = $ProcessName
    }
    if ($ProcessId -gt 0) {
        $postArguments['TargetProcessId'] = $ProcessId
    }
    if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
        $postArguments['TargetWindowHandle'] = $TargetWindowHandle
    }
    if ($SkipBackgroundFocus) {
        $postArguments['SkipBackgroundFocus'] = $true
        $postArguments['RequireTargetForeground'] = $true
    }

    & $postCommandScript @postArguments
}
catch {
    if ($NoAhkFallback) {
        throw
    }

    if ($ProcessId -gt 0 -or -not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
        throw "Native exact-target reload failed and AutoHotkey fallback is disabled for PID/HWND-scoped refreshes to prevent cross-window input. $($_.Exception.Message)"
    }

    Write-Warning ("Native no-focus reload failed: {0}" -f $_.Exception.Message)
    Write-Host "[RiftRefresh] Falling back to the known-good AutoHotkey helper..." -ForegroundColor Yellow
    & $postCommandAhkScript -Command '/reloadui'
}

if ($NoReader) {
    exit 0
}

$arguments = @('--readerbridge-snapshot')
if ($Json) {
    $arguments += '--json'
}

Write-Host ""
Write-Host "[RiftRefresh] Loading the fresh ReaderBridge snapshot..." -ForegroundColor Cyan
Write-Host "[RiftRefresh] dotnet run --project $readerProject -- $($arguments -join ' ')" -ForegroundColor DarkGray

& dotnet run --project $readerProject -- @arguments
exit $LASTEXITCODE
