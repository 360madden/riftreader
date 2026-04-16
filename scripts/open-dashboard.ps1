[CmdletBinding()]
param(
    [switch]$NoOpen,
    [switch]$Live,
    [int]$PollSeconds = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$buildScript = Join-Path $PSScriptRoot 'build-dashboard-summary.ps1'
$buildLiveScript = Join-Path $PSScriptRoot 'build-dashboard-live-data.ps1'
$dashboardPath = Join-Path $repoRoot 'tools\dashboard\index.html'

if (-not (Test-Path -LiteralPath $buildScript)) {
    throw "Dashboard build script was not found: $buildScript"
}

if (-not (Test-Path -LiteralPath $buildLiveScript)) {
    throw "Dashboard live-data script was not found: $buildLiveScript"
}

if (-not (Test-Path -LiteralPath $dashboardPath)) {
    throw "Dashboard entrypoint was not found: $dashboardPath"
}

Write-Host "[Dashboard] Rebuilding dashboard snapshot..." -ForegroundColor Cyan
& $buildScript -RepoPath $repoRoot
if (-not $?) {
    exit 1
}

if ($Live) {
    Write-Host "[Dashboard] Building live dashboard payload..." -ForegroundColor Cyan
    & $buildLiveScript -RepoPath $repoRoot -PollSeconds $PollSeconds
    if (-not $?) {
        exit 1
    }
}

if ($NoOpen) {
    Write-Host "[Dashboard] Dashboard ready at $dashboardPath" -ForegroundColor Green
    if (-not $Live) {
        exit 0
    }
}
elseif ($Live) {
    Write-Host "[Dashboard] Opening dashboard in the default browser..." -ForegroundColor Cyan
    Start-Process -FilePath $dashboardPath
    Write-Host "[Dashboard] Opened $dashboardPath" -ForegroundColor Green
}
else {
    Write-Host "[Dashboard] Opening dashboard in the default browser..." -ForegroundColor Cyan
    Start-Process -FilePath $dashboardPath
    Write-Host "[Dashboard] Opened $dashboardPath" -ForegroundColor Green
    exit 0
}

Write-Host "[Dashboard] Live mode running. Press Ctrl+C to stop." -ForegroundColor Yellow
& $buildLiveScript -RepoPath $repoRoot -PollSeconds $PollSeconds -Watch
