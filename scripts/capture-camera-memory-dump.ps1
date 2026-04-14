[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshOwnerComponents,
    [switch]$IncludeOrbitSiblings,
    [string]$ProcessName = 'rift_x64',
    [string]$OwnerComponentsFile = (Join-Path $PSScriptRoot 'captures\player-owner-components.json'),
    [string]$OutputFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
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

function Invoke-ReaderMemoryBlock {
    param(
        [Parameter(Mandatory = $true)][string]$Address,
        [Parameter(Mandatory = $true)][int]$Length
    )

    $output = & dotnet run --project $readerProject --configuration Release -- `
        --process-name $ProcessName --address $Address --length $Length --json 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Reader memory read failed for ${Address}: $($output -join [Environment]::NewLine)"
    }

    return Convert-CommandOutputToJson -OutputLines $output -CommandName "memory read $Address"
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

$selectedSource = [string]$ownerComponents.Owner.SelectedSourceAddress
$entry5 = Get-EntryByIndex -OwnerComponents $ownerComponents -Index 5
$entry15 = Get-EntryByIndex -OwnerComponents $ownerComponents -Index 15

if ($null -eq $entry15) {
    throw 'Entry 15 is not present in the current owner-components capture.'
}

$selectedSourceDump = Invoke-ReaderMemoryBlock -Address $selectedSource -Length 0xC0
$entry15Dump = Invoke-ReaderMemoryBlock -Address ([string]$entry15.Address) -Length 0x100
$entry5Dump = if ($null -ne $entry5) { Invoke-ReaderMemoryBlock -Address ([string]$entry5.Address) -Length 0x220 } else { $null }

$orbitSiblingDumps = @()
if ($IncludeOrbitSiblings) {
    foreach ($index in @(0, 12, 13, 14, 15)) {
        $entry = Get-EntryByIndex -OwnerComponents $ownerComponents -Index $index
        if ($null -eq $entry) {
            continue
        }

        $orbitSiblingDumps += [ordered]@{
            Index = $index
            Address = [string]$entry.Address
            Memory = Invoke-ReaderMemoryBlock -Address ([string]$entry.Address) -Length 0x100
        }
    }
}

$document = [ordered]@{
    Mode = 'camera-memory-dump'
    GeneratedAtUtc = [DateTime]::UtcNow.ToString('o')
    ProcessName = $ProcessName
    OwnerComponentsFile = $OwnerComponentsFile
    CurrentLiveCamera = $liveCamera
    Dumps = [ordered]@{
        SelectedSource = [ordered]@{
            Address = $selectedSource
            Length = 0xC0
            Memory = $selectedSourceDump
        }
        Entry15 = [ordered]@{
            Address = [string]$entry15.Address
            Length = 0x100
            Memory = $entry15Dump
        }
        Entry5YawMirror = if ($null -ne $entry5) {
            [ordered]@{
                Address = [string]$entry5.Address
                Length = 0x220
                Memory = $entry5Dump
            }
        } else { $null }
        OrbitSiblingEntries = $orbitSiblingDumps
    }
    Notes = @(
        'This dump now targets verified live anchors instead of the dead selected-source +0xB8..+0x150 window.',
        'SelectedSource covers the live yaw basis rows at +0x60/+0x68/+0x78 and +0x94/+0x9C/+0xAC.',
        'Entry15 covers the verified orbit-coordinate family at +0xA8..+0xBC used for derived pitch and distance.'
    )
}

$jsonText = $document | ConvertTo-Json -Depth 40
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
    Write-Host 'Current camera memory dump targets' -ForegroundColor Cyan
    Write-Host "  Selected source: $selectedSource"
    Write-Host "  Entry 15:        $($entry15.Address)"
    if ($null -ne $entry5) {
        Write-Host "  Entry 5 mirror:  $($entry5.Address)"
    }
    if ($OutputFile) {
        Write-Host "Saved dump: $OutputFile" -ForegroundColor Green
    }
}
