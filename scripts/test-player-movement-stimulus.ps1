[CmdletBinding()]
param(
    [string[]]$Keys = @('W'),
    [string[]]$PreKeys = @(),
    [switch]$Json,
    [int]$RepeatCount = 1,
    [int]$HoldMilliseconds = 1200,
    [int]$WaitMilliseconds = 250,
    [int]$PreKeyHoldMilliseconds = 150,
    [int]$PreKeyWaitMilliseconds = 150,
    [double]$MinimumPlanarDistance = 0.10,
    [switch]$UseAhkSendKey,
    [switch]$UseBackgroundPostKey,
    [switch]$SkipRefocus,
    [switch]$CompareReaderBridgeBoundary,
    [switch]$CompareActorOrientationSource,
    [string]$PlayerCurrentAnchorFile = 'captures\player-current-anchor.json',
    [string]$OutputFile = 'captures\movement-stimulus-verification.json',
    [string]$HistoryFile = 'captures\movement-stimulus-verification-history.ndjson'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { (Get-Location).Path }

function Assert-PowerShell7 {
    if ($PSVersionTable.PSVersion.Major -lt 7) {
        throw "PowerShell 7+ (pwsh) is required for $PSCommandPath. Use C:\RIFT MODDING\RiftReader_facing\scripts\test-player-movement-stimulus.cmd or run the script with pwsh.exe."
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
$boundaryCaptureScript = Join-Path $scriptRoot 'capture-readerbridge-boundary.ps1'
$orientationCaptureScript = Join-Path $scriptRoot 'capture-actor-orientation.ps1'
$keyScript = if ($UseAhkSendKey) {
    Join-Path $scriptRoot 'send-rift-key-ahk.ps1'
}
elseif ($UseBackgroundPostKey) {
    Join-Path $scriptRoot 'post-rift-key.ps1'
}
else {
    Join-Path $scriptRoot 'send-rift-key.ps1'
}
$resolvedOutputFile = Resolve-ScriptRelativePath -Path $OutputFile
$resolvedHistoryFile = Resolve-ScriptRelativePath -Path $HistoryFile
$resolvedPlayerCurrentAnchorFile = Resolve-ScriptRelativePath -Path $PlayerCurrentAnchorFile

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

function Get-ObservedHeadingRadians {
    param($BeforeCoord, $AfterCoord)

    if ($null -eq $BeforeCoord -or $null -eq $AfterCoord) {
        return $null
    }

    $beforeX = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $BeforeCoord -PropertyName 'X')
    $beforeZ = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $BeforeCoord -PropertyName 'Z')
    $afterX = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $AfterCoord -PropertyName 'X')
    $afterZ = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $AfterCoord -PropertyName 'Z')
    if ($null -eq $beforeX -or $null -eq $beforeZ -or $null -eq $afterX -or $null -eq $afterZ) {
        return $null
    }

    $deltaX = $afterX - $beforeX
    $deltaZ = $afterZ - $beforeZ
    if ((Get-PlanarMagnitude -ValueX $deltaX -ValueZ $deltaZ) -le [double]::Epsilon) {
        return $null
    }

    return [Math]::Atan2($deltaZ, $deltaX)
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

function Invoke-PlayerCurrentCoordRead {
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
        X = [BitConverter]::ToSingle($bytes, $coordXOffset - $minimumOffset)
        Y = [BitConverter]::ToSingle($bytes, $coordYOffset - $minimumOffset)
        Z = [BitConverter]::ToSingle($bytes, $coordZOffset - $minimumOffset)
    }
}

function Invoke-ReaderBridgeCoordRead {
    $jsonText = & $boundaryCaptureScript -NoTrigger -Json -Label 'movement-stimulus-compare'
    if ($LASTEXITCODE -ne 0) {
        throw 'ReaderBridge boundary compare read failed.'
    }

    $document = $jsonText | ConvertFrom-Json -Depth 80
    return [pscustomobject]@{
        Source         = 'readerbridge-boundary'
        Coord          = Get-OptionalPropertyValue -InputObject $document -PropertyName 'PlayerCoord'
        SnapshotFile   = Get-OptionalPropertyValue -InputObject $document -PropertyName 'SourceFile'
        GeneratedAtUtc = Get-OptionalPropertyValue -InputObject $document -PropertyName 'GeneratedAtUtc'
    }
}

function Invoke-ActorOrientationSourceCoordRead {
    $jsonText = & $orientationCaptureScript -Json
    if ($LASTEXITCODE -ne 0) {
        throw 'Actor-orientation source compare read failed.'
    }

    $document = $jsonText | ConvertFrom-Json -Depth 80
    $readerOrientation = Get-OptionalPropertyValue -InputObject $document -PropertyName 'ReaderOrientation'
    return [pscustomobject]@{
        Source             = 'actor-orientation-source'
        Coord              = Get-OptionalPropertyValue -InputObject $readerOrientation -PropertyName 'PlayerCoord'
        SourceAddress      = Get-OptionalPropertyValue -InputObject $readerOrientation -PropertyName 'SelectedSourceAddress'
        ResolutionMode     = Get-OptionalPropertyValue -InputObject $readerOrientation -PropertyName 'ResolutionMode'
        SnapshotFile       = Get-OptionalPropertyValue -InputObject $readerOrientation -PropertyName 'SnapshotFile'
        GeneratedAtUtc     = Get-OptionalPropertyValue -InputObject $document -PropertyName 'GeneratedAtUtc'
    }
}

function New-CoordSourceSnapshot {
    $snapshot = [ordered]@{}
    $snapshot['player-current-anchor'] = [pscustomobject]@{
        Source = 'player-current-anchor'
        Coord  = Invoke-PlayerCurrentCoordRead
    }

    if ($CompareReaderBridgeBoundary) {
        try {
            $snapshot['readerbridge-boundary'] = Invoke-ReaderBridgeCoordRead
        }
        catch {
            $snapshot['readerbridge-boundary'] = [pscustomobject]@{
                Source = 'readerbridge-boundary'
                Coord  = $null
                Error  = $_.Exception.Message
            }
        }
    }

    if ($CompareActorOrientationSource) {
        try {
            $snapshot['actor-orientation-source'] = Invoke-ActorOrientationSourceCoordRead
        }
        catch {
            $snapshot['actor-orientation-source'] = [pscustomobject]@{
                Source = 'actor-orientation-source'
                Coord  = $null
                Error  = $_.Exception.Message
            }
        }
    }

    return [pscustomobject]$snapshot
}

function Get-CoordDeltaDocument {
    param($BeforeCoord, $AfterCoord)

    $beforeX = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $BeforeCoord -PropertyName 'X')
    $beforeY = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $BeforeCoord -PropertyName 'Y')
    $beforeZ = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $BeforeCoord -PropertyName 'Z')
    $afterX = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $AfterCoord -PropertyName 'X')
    $afterY = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $AfterCoord -PropertyName 'Y')
    $afterZ = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $AfterCoord -PropertyName 'Z')

    return [pscustomobject]@{
        DeltaX   = if ($null -ne $beforeX -and $null -ne $afterX) { $afterX - $beforeX } else { $null }
        DeltaY   = if ($null -ne $beforeY -and $null -ne $afterY) { $afterY - $beforeY } else { $null }
        DeltaZ   = if ($null -ne $beforeZ -and $null -ne $afterZ) { $afterZ - $beforeZ } else { $null }
        Distance = Get-PlanarDistance -LeftCoord $BeforeCoord -RightCoord $AfterCoord
    }
}

function Invoke-StimulusKey {
    param(
        [Parameter(Mandatory = $true)][string]$Key,
        [int]$CustomHoldMilliseconds = $HoldMilliseconds
    )

    $keyArgs = @{
        Key              = $Key
        HoldMilliseconds = $CustomHoldMilliseconds
    }

    if ($UseAhkSendKey -or -not $UseBackgroundPostKey) {
        if ($SkipRefocus) {
            $keyArgs['NoRefocus'] = $true
        }
    }
    elseif ($SkipRefocus) {
        $keyArgs['SkipBackgroundFocus'] = $true
    }

    & $keyScript @keyArgs *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Movement stimulus key '$Key' failed."
    }
}

function Invoke-PreKeys {
    foreach ($preKey in $PreKeys) {
        if ([string]::IsNullOrWhiteSpace([string]$preKey)) {
            continue
        }

        Invoke-StimulusKey -Key ([string]$preKey) -CustomHoldMilliseconds $PreKeyHoldMilliseconds
        Start-Sleep -Milliseconds $PreKeyWaitMilliseconds
    }
}

function Write-VerificationText {
    param($Document)

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('Player movement stimulus verification')
    $lines.Add("Output file:                 $($Document.OutputFile)")
    $lines.Add("Generated (UTC):             $($Document.GeneratedAtUtc)")
    $lines.Add("Keys tested:                 $($Document.KeysTested -join ', ')")
    $lines.Add("Pre-keys:                    $(if ($Document.PreKeys.Count -gt 0) { $Document.PreKeys -join ', ' } else { 'none' })")
    $lines.Add("Repeat count:                $($Document.RepeatCount)")
    $lines.Add("Hold/Wait ms:                $($Document.HoldMilliseconds) / $($Document.WaitMilliseconds)")
    $lines.Add("Pre-key hold/wait ms:        $($Document.PreKeyHoldMilliseconds) / $($Document.PreKeyWaitMilliseconds)")
    $lines.Add("Minimum planar distance:     $(Format-Nullable $Document.MinimumPlanarDistance '0.000')")
    $lines.Add("Summary verdict:             $($Document.Summary.OverallVerdict)")
    $lines.Add("Primary-source working keys: $(if ($Document.Summary.PrimarySourceWorkingKeys.Count -gt 0) { $Document.Summary.PrimarySourceWorkingKeys -join ', ' } else { 'none' })")
    $lines.Add("Working keys:                $(if ($Document.Summary.WorkingKeys.Count -gt 0) { $Document.Summary.WorkingKeys -join ', ' } else { 'none' })")
    $lines.Add("Source-mismatch keys:        $(if ($Document.Summary.SourceMismatchKeys.Count -gt 0) { $Document.Summary.SourceMismatchKeys -join ', ' } else { 'none' })")
    $lines.Add("Non-moving keys:             $(if ($Document.Summary.NonMovingKeys.Count -gt 0) { $Document.Summary.NonMovingKeys -join ', ' } else { 'none' })")
    $lines.Add('Results:')

    foreach ($entry in $Document.Results) {
        $lines.Add("  - $($entry.Key) run $($entry.Iteration): $($entry.Verdict) | primary move $(Format-Nullable $entry.PlanarCoordDelta.Distance '0.000000') | any-source $($entry.AnySourceMoved) | sources $(if ($entry.MovingSources.Count -gt 0) { $entry.MovingSources -join ', ' } else { 'none' }) | heading $(Format-Nullable $entry.ObservedMovementHeadingDegrees '0.000') | failure $(if ($entry.FailureShape) { $entry.FailureShape } else { 'n/a' })")
    }

    return [string]::Join([Environment]::NewLine, $lines)
}

$results = New-Object System.Collections.Generic.List[object]
$historyEntries = Get-ValidationHistoryEntries -HistoryFile $resolvedHistoryFile

foreach ($key in $Keys) {
    if ([string]::IsNullOrWhiteSpace($key)) {
        continue
    }

    for ($iteration = 1; $iteration -le $RepeatCount; $iteration++) {
        $beforeSources = New-CoordSourceSnapshot
        $beforeCoord = (Get-OptionalPropertyValue -InputObject $beforeSources -PropertyName 'player-current-anchor').Coord
        Invoke-PreKeys
        Invoke-StimulusKey -Key $key
        Start-Sleep -Milliseconds $WaitMilliseconds
        $afterSources = New-CoordSourceSnapshot
        $afterCoord = (Get-OptionalPropertyValue -InputObject $afterSources -PropertyName 'player-current-anchor').Coord

        $planarDelta = Get-CoordDeltaDocument -BeforeCoord $beforeCoord -AfterCoord $afterCoord
        $verticalDelta = $planarDelta.DeltaY
        $observedHeadingRadians = Get-ObservedHeadingRadians -BeforeCoord $beforeCoord -AfterCoord $afterCoord
        $observedHeadingDegrees = if ($null -ne $observedHeadingRadians) { Convert-RadiansToDegrees -Radians $observedHeadingRadians } else { $null }
        $primaryMoved = ([double]$planarDelta.Distance) -ge $MinimumPlanarDistance

        $sourceDeltas = [ordered]@{}
        foreach ($property in $beforeSources.PSObject.Properties) {
            $beforeSource = $property.Value
            $afterSource = Get-OptionalPropertyValue -InputObject $afterSources -PropertyName $property.Name
            $beforeSourceCoord = Get-OptionalPropertyValue -InputObject $beforeSource -PropertyName 'Coord'
            $afterSourceCoord = Get-OptionalPropertyValue -InputObject $afterSource -PropertyName 'Coord'
            $delta = Get-CoordDeltaDocument -BeforeCoord $beforeSourceCoord -AfterCoord $afterSourceCoord
            $sourceDeltas[$property.Name] = [pscustomobject]@{
                Source = $property.Name
                Delta  = $delta
                Before = $beforeSourceCoord
                After  = $afterSourceCoord
                Error  = if ($null -ne $beforeSource -and $beforeSource.PSObject.Properties['Error']) { $beforeSource.Error } elseif ($null -ne $afterSource -and $afterSource.PSObject.Properties['Error']) { $afterSource.Error } else { $null }
            }
        }

        $movingSources = @($sourceDeltas.GetEnumerator() | Where-Object {
                $delta = $_.Value.Delta
                $null -ne $delta -and $null -ne $delta.Distance -and ([double]$delta.Distance) -ge $MinimumPlanarDistance
            } | ForEach-Object { $_.Key })
        $anySourceMoved = $movingSources.Count -gt 0
        $verdict = if ($primaryMoved) { 'pass' } elseif ($anySourceMoved) { 'source-mismatch' } else { 'fail' }
        $failureShape = if ($primaryMoved) { 'none' } elseif ($anySourceMoved) { 'primary-source-no-planar-movement' } else { 'no-planar-movement' }

        $runResult = [pscustomobject]@{
            Mode                         = 'movement-stimulus-verification-run'
            GeneratedAtUtc               = [DateTimeOffset]::UtcNow.ToString('O')
            Key                          = $key
            Iteration                    = $iteration
            BeforeCoordSources           = $beforeSources
            AfterCoordSources            = $afterSources
            BeforeCoord                  = $beforeCoord
            AfterCoord                   = $afterCoord
            PlanarCoordDelta             = $planarDelta
            SourceDeltas                 = [pscustomobject]$sourceDeltas
            MovingSources                = $movingSources
            AnySourceMoved               = $anySourceMoved
            VerticalDelta                = $verticalDelta
            ObservedMovementHeadingRadians = $observedHeadingRadians
            ObservedMovementHeadingDegrees = $observedHeadingDegrees
            MinimumPlanarDistance        = $MinimumPlanarDistance
            PreKeys                      = @($PreKeys)
            PreKeyHoldMilliseconds       = $PreKeyHoldMilliseconds
            PreKeyWaitMilliseconds       = $PreKeyWaitMilliseconds
            HoldMilliseconds             = $HoldMilliseconds
            WaitMilliseconds             = $WaitMilliseconds
            Verdict                      = $verdict
            FailureShape                 = $failureShape
            Notes                        = @(
                'This verifier checks only whether the tested gameplay key produces actual player-current-anchor movement in live memory.',
                'It is intentionally separate from solved actor-facing validation and does not reopen actor-facing discovery by itself.',
                $(if ($anySourceMoved -and -not $primaryMoved) { 'At least one secondary coordinate source moved while the primary player-current-anchor source did not; treat this as a movement-truth source mismatch until resolved.' } else { 'All compared movement sources agreed on the observed outcome for this key.' })
            )
        }

        $results.Add($runResult)
        $historyEntries = @($historyEntries) + @($runResult)

        $historyDirectory = Split-Path -Path $resolvedHistoryFile -Parent
        if (-not [string]::IsNullOrWhiteSpace($historyDirectory)) {
            New-Item -ItemType Directory -Path $historyDirectory -Force | Out-Null
        }

        Add-Content -LiteralPath $resolvedHistoryFile -Value ($runResult | ConvertTo-Json -Depth 40 -Compress)
    }
}

$workingKeys = @($results | Where-Object { $_.AnySourceMoved } | Select-Object -ExpandProperty Key -Unique)
$primaryWorkingKeys = @($results | Where-Object { $_.Verdict -eq 'pass' } | Select-Object -ExpandProperty Key -Unique)
$sourceMismatchKeys = @($results | Where-Object { $_.Verdict -eq 'source-mismatch' } | Select-Object -ExpandProperty Key -Unique)
$nonMovingKeys = @($results | Where-Object { $_.Verdict -eq 'fail' } | Select-Object -ExpandProperty Key -Unique)
$maximumPlanarDistance = if ($results.Count -gt 0) { ($results | ForEach-Object { [double]$_.PlanarCoordDelta.Distance } | Measure-Object -Maximum).Maximum } else { $null }

$document = [pscustomobject]@{
    Mode                 = 'movement-stimulus-verification'
    GeneratedAtUtc       = [DateTimeOffset]::UtcNow.ToString('O')
    OutputFile           = $resolvedOutputFile
    HistoryFile          = $resolvedHistoryFile
    AnchorFile           = $resolvedPlayerCurrentAnchorFile
    KeyBackend           = if ($UseAhkSendKey) { 'ahk-send-key' } elseif ($UseBackgroundPostKey) { 'background-post-key' } else { 'send-input' }
    KeysTested           = @($Keys | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    PreKeys              = @($PreKeys | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    RepeatCount          = $RepeatCount
    HoldMilliseconds     = $HoldMilliseconds
    WaitMilliseconds     = $WaitMilliseconds
    PreKeyHoldMilliseconds = $PreKeyHoldMilliseconds
    PreKeyWaitMilliseconds = $PreKeyWaitMilliseconds
    MinimumPlanarDistance = $MinimumPlanarDistance
    Results              = $results
    Summary              = [pscustomobject]@{
        OverallVerdict        = if ($primaryWorkingKeys.Count -gt 0) { 'pass' } elseif ($sourceMismatchKeys.Count -gt 0) { 'source-mismatch' } else { 'fail' }
        WorkingKeys           = $workingKeys
        PrimarySourceWorkingKeys = $primaryWorkingKeys
        SourceMismatchKeys    = $sourceMismatchKeys
        NonMovingKeys         = $nonMovingKeys
        PassCount             = @($results | Where-Object { $_.Verdict -eq 'pass' }).Count
        SourceMismatchCount   = @($results | Where-Object { $_.Verdict -eq 'source-mismatch' }).Count
        FailCount             = @($results | Where-Object { $_.Verdict -eq 'fail' }).Count
        MaximumPlanarDistance = $maximumPlanarDistance
    }
    Notes                = @(
        'Movement truth is sampled directly from the verified player-current anchor in live memory.',
        $(if ($CompareReaderBridgeBoundary -or $CompareActorOrientationSource) { 'Secondary coordinate sources were also sampled so source-mismatch can be distinguished from pure no-movement failures.' } else { 'Only the primary player-current-anchor source was sampled in this run.' }),
        'Use this helper to prove that a candidate gameplay key actually produces movement before retrying move-forward actor-facing validation.',
        'Actor-facing remains solved separately at 0x1B115201EB0 + 0xD4.'
    )
}

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

[System.IO.File]::WriteAllText($resolvedOutputFile, ($document | ConvertTo-Json -Depth 40))

if ($Json) {
    $document | ConvertTo-Json -Depth 40
}
else {
    Write-Output (Write-VerificationText -Document $document)
}
