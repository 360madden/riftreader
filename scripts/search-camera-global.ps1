[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshOwnerGraph,
    [switch]$RefreshHubGraph,
    [switch]$RefreshSelectorTrace,
    [switch]$RefreshOwnerComponents,
    [string]$OwnerGraphFile = (Join-Path $PSScriptRoot 'captures\player-owner-graph.json'),
    [string]$HubGraphFile = (Join-Path $PSScriptRoot 'captures\player-stat-hub-graph.json'),
    [string]$OwnerComponentsFile = (Join-Path $PSScriptRoot 'captures\player-owner-components.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ownerGraphScript = Join-Path $PSScriptRoot 'capture-player-owner-graph.ps1'
$hubGraphScript = Join-Path $PSScriptRoot 'capture-player-stat-hub-graph.ps1'
$ownerComponentsScript = Join-Path $PSScriptRoot 'capture-player-owner-components.ps1'

function Convert-CommandOutputToJson {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$OutputLines,
        [string]$CommandName = 'command'
    )

    $text = ($OutputLines |
        ForEach-Object { $_.ToString() } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join [Environment]::NewLine

    $startIndex = $text.IndexOf('{')
    if ($startIndex -lt 0) {
        throw "$CommandName did not return JSON. Raw output: $text"
    }

    return ($text.Substring($startIndex) | ConvertFrom-Json -Depth 80)
}

function Get-EntryByIndex {
    param(
        [Parameter(Mandatory = $true)]$OwnerComponents,
        [Parameter(Mandatory = $true)][int]$Index
    )

    return $OwnerComponents.Entries | Where-Object { [int]$_.Index -eq $Index } | Select-Object -First 1
}

if ($RefreshOwnerComponents -or -not (Test-Path -LiteralPath $OwnerComponentsFile)) {
    $ownerComponentsOutput = & $ownerComponentsScript -Json -RefreshSelectorTrace 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "capture-player-owner-components failed: $($ownerComponentsOutput -join [Environment]::NewLine)"
    }
    $ownerComponents = Convert-CommandOutputToJson -OutputLines $ownerComponentsOutput -CommandName 'capture-player-owner-components'
}
else {
    $ownerComponents = Get-Content -LiteralPath $OwnerComponentsFile -Raw | ConvertFrom-Json -Depth 80
}

if ($RefreshOwnerGraph -or -not (Test-Path -LiteralPath $OwnerGraphFile)) {
    $ownerArgs = @('-Json')
    if ($RefreshSelectorTrace) {
        $ownerArgs += '-RefreshSelectorTrace'
    }
    $ownerGraphOutput = & $ownerGraphScript @ownerArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "capture-player-owner-graph failed: $($ownerGraphOutput -join [Environment]::NewLine)"
    }
    $ownerGraph = Convert-CommandOutputToJson -OutputLines $ownerGraphOutput -CommandName 'capture-player-owner-graph'
}
else {
    $ownerGraph = Get-Content -LiteralPath $OwnerGraphFile -Raw | ConvertFrom-Json -Depth 80
}

if ($RefreshHubGraph -or -not (Test-Path -LiteralPath $HubGraphFile)) {
    $hubArgs = @('-Json')
    if ($RefreshOwnerComponents) {
        $hubArgs += '-RefreshOwnerComponents'
    }
    $hubGraphOutput = & $hubGraphScript @hubArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "capture-player-stat-hub-graph failed: $($hubGraphOutput -join [Environment]::NewLine)"
    }
    $hubGraph = Convert-CommandOutputToJson -OutputLines $hubGraphOutput -CommandName 'capture-player-stat-hub-graph'
}
else {
    $hubGraph = Get-Content -LiteralPath $HubGraphFile -Raw | ConvertFrom-Json -Depth 80
}

$orbitFamilyIndices = @(0, 12, 13, 14, 15)
$orbitFamilyEntries = $orbitFamilyIndices |
    ForEach-Object { Get-EntryByIndex -OwnerComponents $ownerComponents -Index $_ } |
    Where-Object { $null -ne $_ } |
    ForEach-Object {
        [ordered]@{
            Index = [int]$_.Index
            Address = [string]$_.Address
        }
    }

$entry5 = Get-EntryByIndex -OwnerComponents $ownerComponents -Index 5

$wrapperCandidates = @(
    $ownerGraph.Children |
        Where-Object { $_.Role -in @('source-wrapper', 'owner-backref-wrapper', 'owner-state-wrapper') } |
        ForEach-Object {
            [ordered]@{
                OwnerOffsetHex = [string]$_.OwnerOffsetHex
                Address = [string]$_.Address
                Role = [string]$_.Role
                BackrefAt100 = [string]$_.BackrefAt100
                BackrefAt68 = [string]$_.BackrefAt68
                SourceAt8 = [string]$_.SourceAt8
            }
        }
)

$rankedSharedHubs = @(
    $hubGraph.RankedSharedHubs |
        Where-Object {
            $componentIndexes = @($_.ComponentRefs | ForEach-Object { [int]$_.ComponentIndex })
            @($componentIndexes | Where-Object { $_ -in $orbitFamilyIndices }).Count -ge 2
        } |
        Select-Object -First 8 |
        ForEach-Object {
            [ordered]@{
                Address = [string]$_.Address
                Score = [int]$_.Score
                OrbitFamilyRefs = @(
                    $_.ComponentRefs |
                        Where-Object { [int]$_.ComponentIndex -in $orbitFamilyIndices } |
                        ForEach-Object {
                            [ordered]@{
                                ComponentIndex = [int]$_.ComponentIndex
                                ComponentAddress = [string]$_.ComponentAddress
                                OffsetHex = [string]$_.OffsetHex
                            }
                        }
                )
                Reasons = @($_.Reasons)
            }
        }
)

$entry15 = Get-EntryByIndex -OwnerComponents $ownerComponents -Index 15

$report = [ordered]@{
    Mode = 'camera-global-search'
    GeneratedAtUtc = [DateTime]::UtcNow.ToString('o')
    OwnerGraphFile = $OwnerGraphFile
    HubGraphFile = $HubGraphFile
    OwnerComponentsFile = $OwnerComponentsFile
    KnownLiveSources = [ordered]@{
        SelectedSourceAddress = [string]$ownerComponents.Owner.SelectedSourceAddress
        YawBasisOffsets = @('0x60', '0x68', '0x78', '0x94', '0x9C', '0xAC')
        Entry15Address = if ($null -ne $entry15) { [string]$entry15.Address } else { $null }
        Entry15OrbitOffsets = @('0xA8', '0xAC', '0xB0', '0xB4', '0xB8', '0xBC')
        Entry5Address = if ($null -ne $entry5) { [string]$entry5.Address } else { $null }
        Entry5YawMirrorOffsets = if ($null -ne $entry5) { @('0x1A0', '0x1A8', '0x1B8', '0x1D4', '0x1DC', '0x1EC') } else { @() }
    }
    OrbitFamilyEntries = $orbitFamilyEntries
    WrapperCandidates = $wrapperCandidates
    RankedSharedHubs = $rankedSharedHubs
    NextCommands = @(
        'C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-components.ps1 -Json -RefreshSelectorTrace',
        'C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-graph.ps1 -Json -RefreshSelectorTrace',
        'C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1 -Json -RefreshOwnerComponents',
        'C:\RIFT MODDING\RiftReader\scripts\inspect-capture-consistency.ps1 -Json',
        'C:\RIFT MODDING\RiftReader\scripts\capture-player-source-accessor-family.ps1 -Json -RefreshSourceChain'
    )
    Notes = @(
        'This script replaces the older blind global float-pattern search with a controller-search summary built from current live graphs.',
        'Use the wrapper/backref/state roles to climb out of the selected-source/orbit sibling family.',
        'Use ranked shared hubs to prioritize parent/controller tracing above entries 12/13/14/15 and their mirrors.',
        'test-basis-live-chain.ps1 remains a brittle live checker with hardcoded session values; do not use it as the primary unattended driver.'
    )
}

$jsonText = $report | ConvertTo-Json -Depth 30
if ($Json) {
    Write-Output $jsonText
}
else {
    Write-Host 'Current camera controller search summary' -ForegroundColor Cyan
    Write-Host "  Selected source: $($report.KnownLiveSources.SelectedSourceAddress)"
    Write-Host "  Entry 15:        $($report.KnownLiveSources.Entry15Address)"
    if ($report.KnownLiveSources.Entry5Address) {
        Write-Host "  Entry 5 mirror:  $($report.KnownLiveSources.Entry5Address)"
    }
    Write-Host ''
    Write-Host 'Wrapper candidates:' -ForegroundColor Yellow
    foreach ($candidate in $wrapperCandidates) {
        Write-Host ("  {0} -> {1} [{2}]" -f $candidate.OwnerOffsetHex, $candidate.Address, $candidate.Role)
    }
    Write-Host ''
    Write-Host 'Top shared hubs touching the orbit family:' -ForegroundColor Yellow
    foreach ($hub in $rankedSharedHubs) {
        $componentSummary = ($hub.OrbitFamilyRefs | ForEach-Object { "$($_.ComponentIndex)@$($_.OffsetHex)" }) -join ', '
        Write-Host ("  {0} score={1} refs={2}" -f $hub.Address, $hub.Score, $componentSummary)
    }
}
