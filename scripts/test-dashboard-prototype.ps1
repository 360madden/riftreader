[CmdletBinding()]
param(
    [string]$RepoPath = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if ([string]::IsNullOrWhiteSpace($RepoPath)) {
    $RepoPath = Join-Path $scriptRoot '..'
}

$repoRoot = (Resolve-Path -LiteralPath $RepoPath).Path
$buildSummaryScript = Join-Path $repoRoot 'scripts\build-dashboard-summary.ps1'
$buildLiveScript = Join-Path $repoRoot 'scripts\build-dashboard-live-data.ps1'
$appScript = Join-Path $repoRoot 'tools\dashboard\app.js'
$dashboardDataPath = Join-Path $repoRoot 'tools\dashboard\dashboard-data.js'
$dashboardLiveDataPath = Join-Path $repoRoot 'tools\dashboard\dashboard-live-data.js'

function Read-AssignedJson {
    param(
        [string]$Path,
        [string]$VariableName
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing generated file: $Path"
    }

    $raw = Get-Content -LiteralPath $Path -Raw
    $pattern = '^\s*' + [regex]::Escape($VariableName) + '\s*=\s*'
    $json = ($raw -replace $pattern, '') -replace ';\s*$', ''
    if ([string]::IsNullOrWhiteSpace($json)) {
        throw "Generated file did not contain a JSON payload: $Path"
    }

    return ($json | ConvertFrom-Json)
}

function Assert-HasProperty {
    param(
        [object]$Object,
        [string]$PropertyName,
        [string]$Context
    )

    if (-not $Object) {
        throw "Missing object for $Context"
    }

    if ($Object -is [System.Collections.IDictionary]) {
        if (-not $Object.Contains($PropertyName)) {
            throw "Missing property '$PropertyName' in $Context"
        }

        return
    }

    if ($Object.PSObject.Properties.Name -notcontains $PropertyName) {
        throw "Missing property '$PropertyName' in $Context"
    }
}

Write-Host '[DashboardTest] Syntax-checking app.js...' -ForegroundColor Cyan
& node --check $appScript
if (-not $?) {
    throw 'app.js syntax check failed.'
}

Write-Host '[DashboardTest] Rebuilding static dashboard data...' -ForegroundColor Cyan
& $buildSummaryScript -RepoPath $repoRoot
if (-not $?) {
    throw 'Static dashboard build failed.'
}

Write-Host '[DashboardTest] Rebuilding live dashboard data...' -ForegroundColor Cyan
& $buildLiveScript -RepoPath $repoRoot
if (-not $?) {
    throw 'Live dashboard build failed.'
}

$dashboardData = Read-AssignedJson -Path $dashboardDataPath -VariableName 'window.DASHBOARD_DATA'
$liveData = Read-AssignedJson -Path $dashboardLiveDataPath -VariableName 'window.DASHBOARD_LIVE_DATA'

Assert-HasProperty -Object $dashboardData -PropertyName 'meta' -Context 'dashboard data'
Assert-HasProperty -Object $dashboardData -PropertyName 'branches' -Context 'dashboard data'
if (-not @($dashboardData.branches).Count) {
    throw 'dashboard data did not contain any branches.'
}

Assert-HasProperty -Object $liveData -PropertyName 'meta' -Context 'live data'
Assert-HasProperty -Object $liveData -PropertyName 'repo' -Context 'live data'
Assert-HasProperty -Object $liveData -PropertyName 'snapshot' -Context 'live data'
Assert-HasProperty -Object $liveData -PropertyName 'player' -Context 'live data'
Assert-HasProperty -Object $liveData -PropertyName 'target' -Context 'live data'
Assert-HasProperty -Object $liveData.meta -PropertyName 'sources' -Context 'live data meta'

$sourceKeys = 'repo', 'snapshot', 'player', 'target'
foreach ($key in $sourceKeys) {
    Assert-HasProperty -Object $liveData.meta.sources -PropertyName $key -Context 'live data sources'
}

$branchCount = @($dashboardData.branches).Count
$liveStatus = $liveData.meta.status
$currentBranch = $liveData.repo.currentBranch

Write-Host "[DashboardTest] OK: branches=$branchCount liveStatus=$liveStatus currentBranch=$currentBranch" -ForegroundColor Green
