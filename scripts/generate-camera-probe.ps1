[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshOwnerComponents,
    [string]$OwnerComponentsFile = (Join-Path $PSScriptRoot 'captures\player-owner-components.json'),
    [string]$OutputFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ownerComponentsScript = Join-Path $PSScriptRoot 'capture-player-owner-components.ps1'
$liveReaderScript = Join-Path $PSScriptRoot 'read-live-camera-yaw-pitch.ps1'

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

    return ($text.Substring($startIndex) | ConvertFrom-Json -Depth 60)
}

function Get-EntryByIndex {
    param(
        [Parameter(Mandatory = $true)]$OwnerComponents,
        [Parameter(Mandatory = $true)][int]$Index
    )

    return $OwnerComponents.Entries | Where-Object { [int]$_.Index -eq $Index } | Select-Object -First 1
}

if ($RefreshOwnerComponents -or -not (Test-Path -LiteralPath $OwnerComponentsFile)) {
    $ownerOutput = & $ownerComponentsScript -Json -RefreshSelectorTrace 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "capture-player-owner-components failed: $($ownerOutput -join [Environment]::NewLine)"
    }
    $ownerComponents = Convert-CommandOutputToJson -OutputLines $ownerOutput -CommandName 'capture-player-owner-components'
}
else {
    $ownerComponents = Get-Content -LiteralPath $OwnerComponentsFile -Raw | ConvertFrom-Json -Depth 60
}

$liveOutput = & $liveReaderScript -Json 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "read-live-camera-yaw-pitch failed: $($liveOutput -join [Environment]::NewLine)"
}
$liveCamera = Convert-CommandOutputToJson -OutputLines $liveOutput -CommandName 'read-live-camera-yaw-pitch'

$entry5 = Get-EntryByIndex -OwnerComponents $ownerComponents -Index 5
$entry15 = Get-EntryByIndex -OwnerComponents $ownerComponents -Index 15
$orbitSiblings = @(0, 12, 13, 14, 15) |
    ForEach-Object { Get-EntryByIndex -OwnerComponents $ownerComponents -Index $_ } |
    Where-Object { $null -ne $_ } |
    ForEach-Object {
        [ordered]@{
            Index = [int]$_.Index
            Address = [string]$_.Address
        }
    }

$selectedSource = [string]$ownerComponents.Owner.SelectedSourceAddress
$selectedSourceValue = [UInt64]::Parse($selectedSource.Substring(2), [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)

$watchTargets = New-Object System.Collections.Generic.List[object]
$watchTargets.Add([ordered]@{
    Label = 'selected-source-basis60'
    BaseAddress = $selectedSource
    Address = ('0x{0:X}' -f ($selectedSourceValue + 0x60))
    Offsets = @('0x60', '0x68', '0x78')
    WhatItTracks = 'direct live yaw basis'
})
$watchTargets.Add([ordered]@{
    Label = 'selected-source-basis94'
    BaseAddress = $selectedSource
    Address = ('0x{0:X}' -f ($selectedSourceValue + 0x94))
    Offsets = @('0x94', '0x9C', '0xAC')
    WhatItTracks = 'duplicate live yaw basis'
})

if ($null -ne $entry5) {
    $entry5Value = [UInt64]::Parse(([string]$entry5.Address).Substring(2), [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
    $watchTargets.Add([ordered]@{
        Label = 'entry5-yaw-mirror'
        BaseAddress = [string]$entry5.Address
        Address = ('0x{0:X}' -f ($entry5Value + 0x1A0))
        Offsets = @('0x1A0', '0x1A8', '0x1B8', '0x1D4', '0x1DC', '0x1EC')
        WhatItTracks = 'mirrored yaw-family basis'
    })
}

if ($null -ne $entry15) {
    $entry15Value = [UInt64]::Parse(([string]$entry15.Address).Substring(2), [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
    $watchTargets.Add([ordered]@{
        Label = 'entry15-orbit-primary'
        BaseAddress = [string]$entry15.Address
        Address = ('0x{0:X}' -f ($entry15Value + 0xA8))
        Offsets = @('0xA8', '0xAC', '0xB0')
        WhatItTracks = 'primary orbit coordinates for derived pitch/distance'
    })
    $watchTargets.Add([ordered]@{
        Label = 'entry15-orbit-duplicate'
        BaseAddress = [string]$entry15.Address
        Address = ('0x{0:X}' -f ($entry15Value + 0xB4))
        Offsets = @('0xB4', '0xB8', '0xBC')
        WhatItTracks = 'duplicate orbit coordinates for consistency checks'
    })
}

$probe = [ordered]@{
    Mode = 'camera-probe'
    GeneratedAtUtc = [DateTime]::UtcNow.ToString('o')
    OwnerComponentsFile = $OwnerComponentsFile
    SelectedSourceAddress = $selectedSource
    CurrentLiveCamera = $liveCamera
    WatchTargets = $watchTargets.ToArray()
    OrbitSiblingEntries = $orbitSiblings
    RecommendedStimulusOrder = @(
        'RMB + horizontal mouse move for yaw'
        'RMB + vertical mouse move for pitch'
        'mouse wheel for zoom'
    )
    CheatEngineNotes = @(
        'Use these targets as live watch entries or break-on-write anchors.'
        'Do not scan the dead selected-source +0xB8..+0x150 window.'
        'Selected-source basis tracks live yaw; entry15 orbit tracks pitch/distance via derivation.'
        'The next high-value target is the parent/controller object above the mirrored orbit/yaw families.'
    )
}

$jsonText = $probe | ConvertTo-Json -Depth 30
if ($OutputFile) {
    $outputDirectory = Split-Path -Parent $OutputFile
    if ($outputDirectory) {
        New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    }
    Set-Content -LiteralPath $OutputFile -Value $jsonText -Encoding UTF8
}

if ($Json) {
    Write-Output $jsonText
}
else {
    Write-Host 'Current camera probe targets' -ForegroundColor Cyan
    Write-Host "Selected source: $selectedSource"
    foreach ($target in $watchTargets) {
        Write-Host ("  {0}: {1} ({2})" -f $target.Label, $target.Address, $target.WhatItTracks)
    }
    if ($OutputFile) {
        Write-Host "Saved probe document: $OutputFile" -ForegroundColor Green
    }
}
