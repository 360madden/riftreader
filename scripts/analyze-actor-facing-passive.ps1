[CmdletBinding()]
param(
    [switch]$Json,
    [string]$OwnerComponentsFile,
    [string]$HistoricalActorOrientationFile,
    [string]$OrientationProbeFile,
    [string]$BoundaryCaptureFile,
    [string]$CaptureFallbackRoot = 'C:\RIFT MODDING\RiftReader\scripts\captures',
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\actor-facing-passive-analysis.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'actor-facing-common.ps1')

$repoRoot = Get-RiftReaderRepoRoot -ScriptRoot $PSScriptRoot
$readerProject = Get-RiftReaderProjectPath -RepoRoot $repoRoot
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

function Resolve-CaptureInputPath {
    param(
        [string]$ExplicitPath,
        [Parameter(Mandatory = $true)]
        [string]$DefaultFileName
    )

    $candidates = New-Object System.Collections.Generic.List[string]

    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
        $candidates.Add([System.IO.Path]::GetFullPath($ExplicitPath))
    }

    $candidates.Add((Join-Path (Join-Path $PSScriptRoot 'captures') $DefaultFileName))

    if (-not [string]::IsNullOrWhiteSpace($CaptureFallbackRoot)) {
        $candidates.Add((Join-Path $CaptureFallbackRoot $DefaultFileName))
    }

    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }

        if (Test-Path -LiteralPath $candidate) {
            return [System.IO.Path]::GetFullPath($candidate)
        }
    }

    return $null
}

function Load-JsonDocument {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    return (Get-Content -LiteralPath $Path -Raw) | ConvertFrom-Json -Depth 80
}

function Invoke-ReaderBridgeSnapshot {
    return Invoke-RiftReaderJson -ReaderProject $readerProject -Arguments @('--readerbridge-snapshot', '--json')
}

function Invoke-PlayerOrientationRead {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ResolvedOwnerComponentsFile
    )

    return Invoke-RiftReaderJson -ReaderProject $readerProject -Arguments @(
        '--read-player-orientation',
        '--owner-components-file', $ResolvedOwnerComponentsFile,
        '--json')
}

function Invoke-OwnerComponentRank {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ResolvedOwnerComponentsFile
    )

    return Invoke-RiftReaderJson -ReaderProject $readerProject -Arguments @(
        '--rank-owner-components',
        '--owner-components-file', $ResolvedOwnerComponentsFile,
        '--json')
}

function Format-Nullable {
    param(
        $Value,
        [string]$Format = '0.000'
    )

    if ($null -eq $Value) {
        return 'n/a'
    }

    return ([double]$Value).ToString($Format, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Format-Vector {
    param($Vector)

    if ($null -eq $Vector) {
        return 'n/a'
    }

    $x = Get-OptionalPropertyValue -InputObject $Vector -PropertyName 'X'
    $y = Get-OptionalPropertyValue -InputObject $Vector -PropertyName 'Y'
    $z = Get-OptionalPropertyValue -InputObject $Vector -PropertyName 'Z'
    if ($null -eq $x -or $null -eq $y -or $null -eq $z) {
        return 'n/a'
    }

    return '{0}, {1}, {2}' -f
        (Format-Nullable -Value $x -Format '0.00000'),
        (Format-Nullable -Value $y -Format '0.00000'),
        (Format-Nullable -Value $z -Format '0.00000')
}

function Write-PassiveAnalysisText {
    param($Document)

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('Actor-facing passive analysis')
    $lines.Add("Output file:                 $($Document.OutputFile)")
    $lines.Add("Generated (UTC):             $($Document.GeneratedAtUtc)")
    $lines.Add("Phase verdict:               $($Document.PhaseVerdict)")
    $lines.Add("Snapshot source mode:        $(if ($Document.CurrentSnapshot.SourceMode) { $Document.CurrentSnapshot.SourceMode } else { 'n/a' })")
    $lines.Add("Snapshot export count:       $(if ($null -ne $Document.CurrentSnapshot.ExportCount) { $Document.CurrentSnapshot.ExportCount } else { 'n/a' })")
    $lines.Add("Player/location:             $(if ($Document.CurrentSnapshot.PlayerName) { $Document.CurrentSnapshot.PlayerName } else { 'n/a' }) @ $(if ($Document.CurrentSnapshot.LocationName) { $Document.CurrentSnapshot.LocationName } else { 'n/a' })")
    $lines.Add("Current coords:              $(Format-Vector $Document.CurrentSnapshot.PlayerCoord)")
    $lines.Add("Selected source:             $(if ($Document.CurrentOrientation.SelectedSourceAddress) { $Document.CurrentOrientation.SelectedSourceAddress } else { 'n/a' })")
    $lines.Add("Preferred yaw/pitch (deg):   $(Format-Nullable $Document.CurrentOrientation.PreferredYawDegrees '0.000') / $(Format-Nullable $Document.CurrentOrientation.PreferredPitchDegrees '0.000')")
    $lines.Add("Duplicate basis delta:       $(Format-Nullable $Document.CurrentOrientation.DuplicateBasisDeltaMagnitude '0.000000')")
    $lines.Add("Selected-source owner rank:  $(if ($null -ne $Document.OwnerComponentContext.SelectedSourceRank) { $Document.OwnerComponentContext.SelectedSourceRank } else { 'n/a' })")
    $lines.Add("Top owner rank candidate:    $(if ($Document.OwnerComponentContext.TopRankCandidateAddress) { $Document.OwnerComponentContext.TopRankCandidateAddress } else { 'n/a' })")
    $lines.Add("Addon facing signal:         $(if ($Document.AddonFacingSupport.HasAnySignal -eq $true) { 'present' } else { 'not present' })")
    $lines.Add("Addon expansion verdict:     $($Document.AddonExpansionRecommendation)")

    if ($Document.HistoricalComparison) {
        $lines.Add("Historical source match:     $($Document.HistoricalComparison.SelectedSourceMatchesHistorical)")
        $lines.Add("Historical planar drift:     $(Format-Nullable $Document.HistoricalComparison.PlayerCoordPlanarDrift '0.000')")
    }

    if ($Document.BoundaryCapture) {
        $lines.Add("Boundary capture used:       $($Document.BoundaryCapture.SourceFile)")
        $lines.Add("Boundary export count:       $(if ($null -ne $Document.BoundaryCapture.ExportCount) { $Document.BoundaryCapture.ExportCount } else { 'n/a' })")
    }

    if ($Document.Notes -and $Document.Notes.Count -gt 0) {
        $lines.Add("Notes:                       $([string]::Join('; ', $Document.Notes))")
    }

    return [string]::Join([Environment]::NewLine, $lines)
}

$resolvedOwnerComponentsFile = Resolve-CaptureInputPath -ExplicitPath $OwnerComponentsFile -DefaultFileName 'player-owner-components.json'
if ([string]::IsNullOrWhiteSpace($resolvedOwnerComponentsFile)) {
    throw 'Unable to resolve a player-owner-components artifact for passive actor-facing analysis.'
}

$resolvedHistoricalActorOrientationFile = Resolve-CaptureInputPath -ExplicitPath $HistoricalActorOrientationFile -DefaultFileName 'player-actor-orientation.json'
$resolvedOrientationProbeFile = Resolve-CaptureInputPath -ExplicitPath $OrientationProbeFile -DefaultFileName 'readerbridge-orientation-probe.json'
$resolvedBoundaryCaptureFile = Resolve-CaptureInputPath -ExplicitPath $BoundaryCaptureFile -DefaultFileName 'readerbridge-boundary.json'

$snapshot = Invoke-ReaderBridgeSnapshot
$orientation = Invoke-PlayerOrientationRead -ResolvedOwnerComponentsFile $resolvedOwnerComponentsFile
$ownerRank = Invoke-OwnerComponentRank -ResolvedOwnerComponentsFile $resolvedOwnerComponentsFile

$historicalOrientation = $null
if (-not [string]::IsNullOrWhiteSpace($resolvedHistoricalActorOrientationFile)) {
    $historicalOrientation = Load-JsonDocument -Path $resolvedHistoricalActorOrientationFile
}

$orientationProbe = $null
if (-not [string]::IsNullOrWhiteSpace($resolvedOrientationProbeFile)) {
    $orientationProbe = Load-JsonDocument -Path $resolvedOrientationProbeFile
}

$boundaryCapture = $null
if (-not [string]::IsNullOrWhiteSpace($resolvedBoundaryCaptureFile)) {
    $boundaryCapture = Load-JsonDocument -Path $resolvedBoundaryCaptureFile
}

$currentPlayer = Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $snapshot -PropertyName 'Current') -PropertyName 'Player'
$playerCoord = Get-OptionalPropertyValue -InputObject $currentPlayer -PropertyName 'Coord'
$selectedSourceRankEntry = @($ownerRank.Candidates | Where-Object {
        (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'AddressHex') -eq $orientation.SelectedSourceAddress
    } | Select-Object -First 1)
$topRankEntry = @($ownerRank.Candidates | Select-Object -First 1)
$historicalReaderOrientation = if ($null -ne $historicalOrientation) { Get-OptionalPropertyValue -InputObject $historicalOrientation -PropertyName 'ReaderOrientation' } else { $null }
$historicalPlayerCoord = if ($null -ne $historicalReaderOrientation) { Get-OptionalPropertyValue -InputObject $historicalReaderOrientation -PropertyName 'PlayerCoord' } else { $null }
$historicalSelectedSource = if ($null -ne $historicalReaderOrientation) { Get-OptionalPropertyValue -InputObject $historicalReaderOrientation -PropertyName 'SelectedSourceAddress' } else { $null }
$playerCoordPlanarDrift = Get-PlanarDistance -LeftCoord $historicalPlayerCoord -RightCoord $playerCoord
$addonHasAnySignal = $false

if ($null -ne $orientationProbe) {
    $addonHasAnySignal =
        ([bool](Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $orientationProbe -PropertyName 'Player') -PropertyName 'HasAnySignal')) -or
        ([bool](Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $orientationProbe -PropertyName 'Target') -PropertyName 'HasAnySignal'))
}

$notes = New-Object System.Collections.Generic.List[string]
$notes.Add('Passive analysis avoids movement and treats addon telemetry as coordinate/freshness truth only.')

if ($null -eq $selectedSourceRankEntry) {
    $notes.Add('The selected source was not present in the current owner-component ranking output.')
}
else {
    $notes.Add('The selected source still appears in the owner-component artifact and remains tagged as a transform/source-shaped entry.')
}

if ($addonHasAnySignal) {
    $notes.Add('The addon-side orientation probe reported at least one facing signal; verify it before expanding the export contract.')
}
else {
    $notes.Add('The addon-side orientation probe still reports no direct facing signal, so addon expansion is not required for this no-movement phase.')
}

if ($null -ne $playerCoordPlanarDrift) {
    $notes.Add('Historical actor-orientation artifacts should be treated as evidence only when compared against the current player coord drift.')
}

$document = [pscustomobject]@{
    Mode = 'actor-facing-passive-analysis'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    OutputFile = $resolvedOutputFile
    Inputs = [pscustomobject]@{
        OwnerComponentsFile = $resolvedOwnerComponentsFile
        HistoricalActorOrientationFile = $resolvedHistoricalActorOrientationFile
        OrientationProbeFile = $resolvedOrientationProbeFile
        BoundaryCaptureFile = $resolvedBoundaryCaptureFile
    }
    CurrentSnapshot = [pscustomobject]@{
        SnapshotFile = Get-OptionalPropertyValue -InputObject $snapshot -PropertyName 'SourceFile'
        LoadedAtUtc = Get-OptionalPropertyValue -InputObject $snapshot -PropertyName 'LoadedAtUtc'
        ExportCount = Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $snapshot -PropertyName 'Current') -PropertyName 'ExportCount'
        ExportReason = Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $snapshot -PropertyName 'Current') -PropertyName 'ExportReason'
        GeneratedAtRealtime = Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $snapshot -PropertyName 'Current') -PropertyName 'GeneratedAtRealtime'
        SourceMode = Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $snapshot -PropertyName 'Current') -PropertyName 'SourceMode'
        SourceAddon = Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $snapshot -PropertyName 'Current') -PropertyName 'SourceAddon'
        PlayerName = Get-OptionalPropertyValue -InputObject $currentPlayer -PropertyName 'Name'
        PlayerLevel = Get-OptionalPropertyValue -InputObject $currentPlayer -PropertyName 'Level'
        LocationName = Get-OptionalPropertyValue -InputObject $currentPlayer -PropertyName 'LocationName'
        Zone = Get-OptionalPropertyValue -InputObject $currentPlayer -PropertyName 'Zone'
        PlayerCoord = $playerCoord
    }
    CurrentOrientation = [pscustomobject]@{
        ArtifactFile = Get-OptionalPropertyValue -InputObject $orientation -PropertyName 'ArtifactFile'
        ArtifactGeneratedAtUtc = Get-OptionalPropertyValue -InputObject $orientation -PropertyName 'ArtifactGeneratedAtUtc'
        SelectedSourceAddress = Get-OptionalPropertyValue -InputObject $orientation -PropertyName 'SelectedSourceAddress'
        SelectedEntryAddress = Get-OptionalPropertyValue -InputObject $orientation -PropertyName 'SelectedEntryAddress'
        SelectedEntryIndex = Get-OptionalPropertyValue -InputObject $orientation -PropertyName 'SelectedEntryIndex'
        SelectedEntryRoleHints = Get-OptionalPropertyValue -InputObject $orientation -PropertyName 'SelectedEntryRoleHints'
        PreferredYawDegrees = Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $orientation -PropertyName 'PreferredEstimate') -PropertyName 'YawDegrees'
        PreferredPitchDegrees = Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $orientation -PropertyName 'PreferredEstimate') -PropertyName 'PitchDegrees'
        PreferredVector = Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $orientation -PropertyName 'PreferredEstimate') -PropertyName 'Vector'
        DuplicateBasisDeltaMagnitude = Get-OptionalPropertyValue -InputObject $orientation -PropertyName 'BasisDuplicateDeltaMagnitude'
        DuplicateBasisAgreementStrong = Get-OptionalPropertyValue -InputObject $orientation -PropertyName 'BasisDuplicateAgreementStrong'
        Notes = Get-OptionalPropertyValue -InputObject $orientation -PropertyName 'Notes'
    }
    OwnerComponentContext = [pscustomobject]@{
        OwnerAddress = Get-OptionalPropertyValue -InputObject $ownerRank -PropertyName 'OwnerAddress'
        ContainerAddress = Get-OptionalPropertyValue -InputObject $ownerRank -PropertyName 'ContainerAddress'
        StateRecordAddress = Get-OptionalPropertyValue -InputObject $ownerRank -PropertyName 'StateRecordAddress'
        SelectedSourceRank = if ($selectedSourceRankEntry.Count -gt 0) { Get-OptionalPropertyValue -InputObject $selectedSourceRankEntry[0] -PropertyName 'Rank' } else { $null }
        SelectedSourceKind = if ($selectedSourceRankEntry.Count -gt 0) { Get-OptionalPropertyValue -InputObject $selectedSourceRankEntry[0] -PropertyName 'Kind' } else { $null }
        SelectedSourceReasons = if ($selectedSourceRankEntry.Count -gt 0) { Get-OptionalPropertyValue -InputObject $selectedSourceRankEntry[0] -PropertyName 'Reasons' } else { @() }
        TopRankCandidateAddress = if ($topRankEntry.Count -gt 0) { Get-OptionalPropertyValue -InputObject $topRankEntry[0] -PropertyName 'AddressHex' } else { $null }
        TopRankCandidateKind = if ($topRankEntry.Count -gt 0) { Get-OptionalPropertyValue -InputObject $topRankEntry[0] -PropertyName 'Kind' } else { $null }
        TopRankCandidateScore = if ($topRankEntry.Count -gt 0) { Get-OptionalPropertyValue -InputObject $topRankEntry[0] -PropertyName 'Score' } else { $null }
        TopRankCandidateReasons = if ($topRankEntry.Count -gt 0) { Get-OptionalPropertyValue -InputObject $topRankEntry[0] -PropertyName 'Reasons' } else { @() }
    }
    HistoricalComparison = if ($null -ne $historicalReaderOrientation) {
        [pscustomobject]@{
            HistoricalFile = $resolvedHistoricalActorOrientationFile
            HistoricalGeneratedAtUtc = Get-OptionalPropertyValue -InputObject $historicalOrientation -PropertyName 'GeneratedAtUtc'
            HistoricalSelectedSourceAddress = $historicalSelectedSource
            SelectedSourceMatchesHistorical = [string]::Equals([string]$historicalSelectedSource, [string]$orientation.SelectedSourceAddress, [System.StringComparison]::OrdinalIgnoreCase)
            HistoricalPlayerCoord = $historicalPlayerCoord
            PlayerCoordPlanarDrift = $playerCoordPlanarDrift
        }
    } else { $null }
    AddonFacingSupport = if ($null -ne $orientationProbe) {
        [pscustomobject]@{
            OrientationProbeFile = $resolvedOrientationProbeFile
            ProbeGeneratedAtUtc = Get-OptionalPropertyValue -InputObject $orientationProbe -PropertyName 'GeneratedAtUtc'
            SnapshotStatus = Get-OptionalPropertyValue -InputObject $orientationProbe -PropertyName 'SnapshotStatus'
            DirectHeadingApiAvailable = Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $orientationProbe -PropertyName 'Player') -PropertyName 'DirectHeadingApiAvailable'
            DirectPitchApiAvailable = Get-OptionalPropertyValue -InputObject (Get-OptionalPropertyValue -InputObject $orientationProbe -PropertyName 'Player') -PropertyName 'DirectPitchApiAvailable'
            HasAnySignal = $addonHasAnySignal
            Notes = Get-OptionalPropertyValue -InputObject $orientationProbe -PropertyName 'Notes'
        }
    } else {
        [pscustomobject]@{
            OrientationProbeFile = $null
            HasAnySignal = $false
            Notes = @('No ReaderBridge orientation probe artifact was available.')
        }
    }
    BoundaryCapture = if ($null -ne $boundaryCapture) {
        [pscustomobject]@{
            BoundaryFile = $resolvedBoundaryCaptureFile
            SourceFile = Get-OptionalPropertyValue -InputObject $boundaryCapture -PropertyName 'SourceFile'
            ExportCount = Get-OptionalPropertyValue -InputObject $boundaryCapture -PropertyName 'ExportCount'
            GeneratedAtRealtime = Get-OptionalPropertyValue -InputObject $boundaryCapture -PropertyName 'GeneratedAtRealtime'
            PlayerCoord = Get-OptionalPropertyValue -InputObject $boundaryCapture -PropertyName 'PlayerCoord'
            Notes = Get-OptionalPropertyValue -InputObject $boundaryCapture -PropertyName 'Notes'
        }
    } else { $null }
    AddonExpansionRecommendation = if ($addonHasAnySignal) { 'optional-probe-followup-only' } else { 'not-needed-now' }
    PhaseVerdict = if ($addonHasAnySignal) { 'memory-candidate-with-addon-followup' } else { 'memory-candidate-passive-only' }
    Notes = $notes
}

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $document | ConvertTo-Json -Depth 80
[System.IO.File]::WriteAllText($resolvedOutputFile, $jsonText)

if ($Json) {
    Write-Output $jsonText
    return
}

Write-Output (Write-PassiveAnalysisText -Document $document)
