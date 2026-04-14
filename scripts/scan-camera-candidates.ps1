[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshOwnerComponents,
    [switch]$ScanAllEntries,
    [string]$ProcessName = 'rift_x64',
    [string]$OwnerComponentsFile = (Join-Path $PSScriptRoot 'captures\player-owner-components.json'),
    [int]$SelectedSourceLength = 2048,
    [int]$EntryLength = 2048,
    [int]$MousePixels = 140
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$targetScript = Join-Path $PSScriptRoot 'find-live-camera-angle-candidates.ps1'

$arguments = @()
if ($Json) { $arguments += '-Json' }
if ($RefreshOwnerComponents) { $arguments += '-RefreshOwnerComponents' }
if ($ScanAllEntries) { $arguments += '-ScanAllEntries' }
$arguments += @(
    '-ProcessName', $ProcessName,
    '-OwnerComponentsFile', $OwnerComponentsFile,
    '-SelectedSourceLength', $SelectedSourceLength.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-EntryLength', $EntryLength.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-MousePixels', $MousePixels.ToString([System.Globalization.CultureInfo]::InvariantCulture)
)

if (-not $Json) {
    Write-Warning 'scan-camera-candidates.ps1 now forwards to find-live-camera-angle-candidates.ps1. The old selected-source +0xB8..+0x150 camera window is obsolete.'
}

& $targetScript @arguments
exit $LASTEXITCODE
