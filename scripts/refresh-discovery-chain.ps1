[CmdletBinding()]
param(
    [switch]$NoReaderBridgeRefresh
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = if (-not [string]::IsNullOrWhiteSpace($PSScriptRoot)) {
    $PSScriptRoot
}
elseif (-not [string]::IsNullOrWhiteSpace($PSCommandPath)) {
    Split-Path -Parent $PSCommandPath
}
else {
    (Get-Location).Path
}

$refreshReaderBridgeScript = Join-Path $scriptRoot 'refresh-readerbridge-export.ps1'
$sourceChainScript = Join-Path $scriptRoot 'capture-player-source-chain.ps1'
$selectorTraceScript = Join-Path $scriptRoot 'trace-player-selector-owner.ps1'
$ownerComponentsScript = Join-Path $scriptRoot 'capture-player-owner-components.ps1'
$ownerGraphScript = Join-Path $scriptRoot 'capture-player-owner-graph.ps1'
$sourceAccessorFamilyScript = Join-Path $scriptRoot 'capture-player-source-accessor-family.ps1'
$statHubGraphScript = Join-Path $scriptRoot 'capture-player-stat-hub-graph.ps1'

function Invoke-DiscoveryStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    Write-Host ("[DiscoveryChain] {0}..." -f $Name) -ForegroundColor Cyan
    & $Action

    if ($LASTEXITCODE -ne 0) {
        throw ("{0} failed with exit code {1}." -f $Name, $LASTEXITCODE)
    }
}

Write-Host 'Discovery refresh chain' -ForegroundColor Cyan
Write-Host ("Script root: {0}" -f $scriptRoot)
Write-Host ''

if (-not $NoReaderBridgeRefresh) {
    Invoke-DiscoveryStep -Name 'refresh-readerbridge-export' -Action {
        & $refreshReaderBridgeScript
    }
    Write-Host ''
}

Invoke-DiscoveryStep -Name 'capture-player-source-chain' -Action {
    & $sourceChainScript
}

Invoke-DiscoveryStep -Name 'trace-player-selector-owner' -Action {
    & $selectorTraceScript -RefreshSourceChain
}

Invoke-DiscoveryStep -Name 'capture-player-owner-components' -Action {
    & $ownerComponentsScript -RefreshSelectorTrace
}

Invoke-DiscoveryStep -Name 'capture-player-owner-graph' -Action {
    & $ownerGraphScript -RefreshSelectorTrace
}

Invoke-DiscoveryStep -Name 'capture-player-source-accessor-family' -Action {
    & $sourceAccessorFamilyScript -RefreshSourceChain
}

Invoke-DiscoveryStep -Name 'capture-player-stat-hub-graph' -Action {
    & $statHubGraphScript -RefreshOwnerComponents
}

Write-Host ''
Write-Host '[DiscoveryChain] Discovery refresh chain complete.' -ForegroundColor Green
