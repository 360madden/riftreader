[CmdletBinding()]
param(
    [switch]$Json,
    [string]$PlayerCurrentAnchorFile = 'captures\player-current-anchor.json',
    [string]$OutputFile = 'captures\live-player-coord-source-comparison.json'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { (Get-Location).Path }

function Assert-PowerShell7 {
    if ($PSVersionTable.PSVersion.Major -lt 7) {
        throw "PowerShell 7+ (pwsh) is required for $PSCommandPath. Use C:\RIFT MODDING\RiftReader_facing\scripts\compare-live-player-coord-sources.cmd or run the script with pwsh.exe."
    }
}

function Resolve-ScriptRelativePath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $scriptRoot $Path))
}

Assert-PowerShell7

. (Join-Path $scriptRoot 'actor-facing-common.ps1')

$repoRoot = Get-RiftReaderRepoRoot -ScriptRoot $scriptRoot
$readerProject = Get-RiftReaderProjectPath -RepoRoot $repoRoot
$resolvedPlayerCurrentAnchorFile = Resolve-ScriptRelativePath -Path $PlayerCurrentAnchorFile
$resolvedOutputFile = Resolve-ScriptRelativePath -Path $OutputFile
$boundaryCaptureScript = Join-Path $scriptRoot 'capture-readerbridge-boundary.ps1'
$orientationCaptureScript = Join-Path $scriptRoot 'capture-actor-orientation.ps1'

function Parse-UnsignedAddress {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AddressText
    )

    $normalized = $AddressText.Trim()
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [Convert]::ToUInt64($normalized, 16)
}

function Read-PlayerCurrentAnchorCoord {
    if (-not (Test-Path -LiteralPath $resolvedPlayerCurrentAnchorFile)) {
        throw "Player-current anchor file was not found: $resolvedPlayerCurrentAnchorFile"
    }

    $anchorDocument = Get-Content -LiteralPath $resolvedPlayerCurrentAnchorFile -Raw | ConvertFrom-Json -Depth 40
    $addressText = [string](Get-OptionalPropertyValue -InputObject $anchorDocument -PropertyName 'AddressHex')
    if ([string]::IsNullOrWhiteSpace($addressText)) {
        throw "Player-current anchor file did not contain AddressHex: $resolvedPlayerCurrentAnchorFile"
    }

    $processName = [string](Get-OptionalPropertyValue -InputObject $anchorDocument -PropertyName 'ProcessName')
    if ([string]::IsNullOrWhiteSpace($processName)) {
        $processName = 'rift_x64'
    }

    $coordXOffset = [int](Get-OptionalPropertyValue -InputObject $anchorDocument -PropertyName 'CoordXOffset')
    $coordYOffset = [int](Get-OptionalPropertyValue -InputObject $anchorDocument -PropertyName 'CoordYOffset')
    $coordZOffset = [int](Get-OptionalPropertyValue -InputObject $anchorDocument -PropertyName 'CoordZOffset')
    $offsets = @($coordXOffset, $coordYOffset, $coordZOffset)
    $minimumOffset = [int](($offsets | Measure-Object -Minimum).Minimum)
    $maximumOffset = [int](($offsets | Measure-Object -Maximum).Maximum)
    $baseAddress = Parse-UnsignedAddress -AddressText $addressText
    $readAddress = $baseAddress + [uint64]$minimumOffset
    $length = ($maximumOffset - $minimumOffset) + 4

    $memoryRead = Invoke-RiftReaderJson -ReaderProject $readerProject -Arguments @(
        '--process-name', $processName,
        '--address', ('0x{0:X}' -f $readAddress),
        '--length', $length.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json'
    )

    $bytesHex = [string](Get-OptionalPropertyValue -InputObject $memoryRead -PropertyName 'BytesHex')
    if ([string]::IsNullOrWhiteSpace($bytesHex)) {
        throw "Live player-current memory read returned no bytes for anchor $addressText."
    }

    $bytes = [Convert]::FromHexString($bytesHex)
    return [pscustomobject]@{
        AddressHex = $addressText
        FamilyId   = Get-OptionalPropertyValue -InputObject $anchorDocument -PropertyName 'FamilyId'
        Coord      = [pscustomobject]@{
            X = [BitConverter]::ToSingle($bytes, $coordXOffset - $minimumOffset)
            Y = [BitConverter]::ToSingle($bytes, $coordYOffset - $minimumOffset)
            Z = [BitConverter]::ToSingle($bytes, $coordZOffset - $minimumOffset)
        }
    }
}

function Get-CoordDistance {
    param($LeftCoord, $RightCoord)

    if ($null -eq $LeftCoord -or $null -eq $RightCoord) {
        return $null
    }

    $leftX = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $LeftCoord -PropertyName 'X')
    $leftZ = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $LeftCoord -PropertyName 'Z')
    $rightX = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $RightCoord -PropertyName 'X')
    $rightZ = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $RightCoord -PropertyName 'Z')

    if ($null -eq $leftX -or $null -eq $leftZ -or $null -eq $rightX -or $null -eq $rightZ) {
        return $null
    }

    return [pscustomobject]@{
        DeltaX   = $rightX - $leftX
        DeltaZ   = $rightZ - $leftZ
        Distance = Get-PlanarMagnitude -ValueX ($rightX - $leftX) -ValueZ ($rightZ - $leftZ)
    }
}

$playerCurrentAnchor = $null
$playerCurrentRead = $null
$readerBridgeBoundary = $null
$actorOrientation = $null
$errors = New-Object System.Collections.Generic.List[object]

try {
    $playerCurrentAnchor = Read-PlayerCurrentAnchorCoord
}
catch {
    $errors.Add([pscustomobject]@{ Source = 'player-current-anchor'; Error = $_.Exception.Message })
}

try {
    $playerCurrentRead = Invoke-RiftReaderJson -ReaderProject $readerProject -Arguments @(
        '--process-name', 'rift_x64',
        '--read-player-current',
        '--json'
    )
}
catch {
    $errors.Add([pscustomobject]@{ Source = 'read-player-current'; Error = $_.Exception.Message })
}

try {
    $readerBridgeBoundary = (& $boundaryCaptureScript -NoTrigger -Json -Label 'coord-source-compare') | ConvertFrom-Json -Depth 80
}
catch {
    $errors.Add([pscustomobject]@{ Source = 'readerbridge-boundary'; Error = $_.Exception.Message })
}

try {
    $actorOrientation = (& $orientationCaptureScript -Json) | ConvertFrom-Json -Depth 80
}
catch {
    $errors.Add([pscustomobject]@{ Source = 'actor-orientation'; Error = $_.Exception.Message })
}

$readerBridgeCoord = if ($readerBridgeBoundary) { Get-OptionalPropertyValue -InputObject $readerBridgeBoundary -PropertyName 'PlayerCoord' } else { $null }
$actorOrientationCoord = if ($actorOrientation) { Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $actorOrientation -PropertyName 'ReaderOrientation') -PropertyName 'PlayerCoord' } else { $null }
$playerCurrentReadCoord = if ($playerCurrentRead) {
    $cur = Get-OptionalPropertyValue -InputObject $playerCurrentRead -PropertyName 'Current'
    $player = Get-OptionalPropertyValue -InputObject $cur -PropertyName 'Player'
    Get-OptionalPropertyValue -InputObject $player -PropertyName 'Coord'
} else { $null }

$comparisons = @(
    [pscustomobject]@{
        Left     = 'readerbridge-boundary'
        Right    = 'player-current-anchor'
        Delta    = Get-CoordDistance -LeftCoord $readerBridgeCoord -RightCoord $(if ($playerCurrentAnchor) { $playerCurrentAnchor.Coord } else { $null })
    },
    [pscustomobject]@{
        Left     = 'readerbridge-boundary'
        Right    = 'actor-orientation-source'
        Delta    = Get-CoordDistance -LeftCoord $readerBridgeCoord -RightCoord $actorOrientationCoord
    },
    [pscustomobject]@{
        Left     = 'player-current-anchor'
        Right    = 'actor-orientation-source'
        Delta    = Get-CoordDistance -LeftCoord $(if ($playerCurrentAnchor) { $playerCurrentAnchor.Coord } else { $null }) -RightCoord $actorOrientationCoord
    },
    [pscustomobject]@{
        Left     = 'readerbridge-boundary'
        Right    = 'read-player-current'
        Delta    = Get-CoordDistance -LeftCoord $readerBridgeCoord -RightCoord $playerCurrentReadCoord
    }
)

$document = [pscustomobject]@{
    Mode                = 'live-player-coord-source-comparison'
    GeneratedAtUtc      = [DateTimeOffset]::UtcNow.ToString('O')
    OutputFile          = $resolvedOutputFile
    PlayerCurrentAnchor = $playerCurrentAnchor
    ReadPlayerCurrent   = $playerCurrentRead
    ReaderBridgeBoundary = $readerBridgeBoundary
    ActorOrientation    = $actorOrientation
    Comparisons         = $comparisons
    Errors              = $errors
    Notes               = @(
        'This diagnostic compares competing live player-coordinate truth sources without using Cheat Engine.',
        'Use it when move-forward validation is blocked and actor-facing is already solved.',
        'Large pairwise deltas mean movement validation should not trust those sources interchangeably.'
    )
}

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

[System.IO.File]::WriteAllText($resolvedOutputFile, ($document | ConvertTo-Json -Depth 60))

if ($Json) {
    $document | ConvertTo-Json -Depth 60
}
else {
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('Live player coord source comparison')
    $lines.Add("Output file: $resolvedOutputFile")
    foreach ($comparison in $comparisons) {
        $delta = $comparison.Delta
        $lines.Add(("{0} vs {1}: dx={2} dz={3} dist={4}" -f $comparison.Left, $comparison.Right, $(if ($delta) { [double]$delta.DeltaX } else { [double]::NaN }), $(if ($delta) { [double]$delta.DeltaZ } else { [double]::NaN }), $(if ($delta) { [double]$delta.Distance } else { [double]::NaN })))
    }
    if ($errors.Count -gt 0) {
        $lines.Add('Errors:')
        foreach ($entry in $errors) {
            $lines.Add(" - $($entry.Source): $($entry.Error)")
        }
    }
    Write-Output ([string]::Join([Environment]::NewLine, $lines))
}
