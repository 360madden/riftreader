[CmdletBinding()]
param(
    [switch]$Json,
    [string]$ProcessName = 'rift_x64',
    [int]$HoldMilliseconds = 700,
    [int]$WaitMilliseconds = 250,
    [int]$PostStimulusSampleCount = 0,
    [int]$TimelineIntervalMilliseconds = 250,
    [switch]$RefreshReaderBridge,
    [switch]$NoAhkFallback,
    [string]$PinnedSourceAddress,
    [string]$PinnedBasisForwardOffset,
    [ValidateSet('A', 'D', 'Left', 'Right')]
    [string]$LeftTurnKey = 'A',
    [ValidateSet('A', 'D', 'Left', 'Right')]
    [string]$RightTurnKey = 'D',
    [string]$OrientationCandidateLedgerFile,
    [switch]$SkipCandidateLedgerWrite,
    [switch]$SkipUiClearCheck,
    [switch]$RequireTargetFocus,
    [switch]$SkipLiveInputWarning,
    [string]$OutputFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$captureScript = Join-Path $PSScriptRoot 'capture-actor-orientation.ps1'
$stimulusScript = Join-Path $PSScriptRoot 'test-actor-orientation-stimulus.ps1'

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = Join-Path $PSScriptRoot 'captures\actor-orientation-recovery.json'
}

if ([string]::IsNullOrWhiteSpace($OrientationCandidateLedgerFile)) {
    $OrientationCandidateLedgerFile = Join-Path $PSScriptRoot 'captures\actor-orientation-candidate-ledger.ndjson'
}

$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$resolvedOrientationCandidateLedgerFile = [System.IO.Path]::GetFullPath($OrientationCandidateLedgerFile)

if (-not $PSBoundParameters.ContainsKey('RequireTargetFocus')) {
    $RequireTargetFocus = $true
}

if ([string]::Equals($LeftTurnKey, $RightTurnKey, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "LeftTurnKey and RightTurnKey must be different opposite-direction turn inputs."
}

function Invoke-ReaderJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & dotnet run --project $readerProject -- @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Reader command failed (`$LASTEXITCODE=$exitCode): $($output -join [Environment]::NewLine)"
    }

    $jsonText = $output -join [Environment]::NewLine
    if ((Get-Command Microsoft.PowerShell.Utility\ConvertFrom-Json).Parameters.ContainsKey('Depth')) {
        return ($jsonText | Microsoft.PowerShell.Utility\ConvertFrom-Json -Depth 80)
    }

    return ($jsonText | Microsoft.PowerShell.Utility\ConvertFrom-Json)
}

function Get-OptionalPropertyValue {
    param(
        [AllowNull()]
        $Object,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $Object) {
        return $null
    }

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Invoke-Capture {
    param([Parameter(Mandatory = $true)][string]$Label)

    $arguments = @{
        Json = $true
        Label = $Label
    }

    if ($RefreshReaderBridge) {
        $arguments['RefreshReaderBridge'] = $true
    }

    if ($NoAhkFallback) {
        $arguments['NoAhkFallback'] = $true
    }

    if (-not [string]::IsNullOrWhiteSpace($PinnedSourceAddress)) {
        $arguments['PinnedSourceAddress'] = $PinnedSourceAddress
    }

    if (-not [string]::IsNullOrWhiteSpace($PinnedBasisForwardOffset)) {
        $arguments['PinnedBasisForwardOffset'] = $PinnedBasisForwardOffset
    }

    if (-not [string]::IsNullOrWhiteSpace($resolvedOrientationCandidateLedgerFile)) {
        $arguments['OrientationCandidateLedgerFile'] = $resolvedOrientationCandidateLedgerFile
    }

    $jsonText = & $captureScript @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Actor orientation capture failed for '$Label'."
    }

    if ((Get-Command Microsoft.PowerShell.Utility\ConvertFrom-Json).Parameters.ContainsKey('Depth')) {
        return ($jsonText | Microsoft.PowerShell.Utility\ConvertFrom-Json -Depth 80)
    }

    return ($jsonText | Microsoft.PowerShell.Utility\ConvertFrom-Json)
}

function Invoke-Stimulus {
    param(
        [Parameter(Mandatory = $true)][string]$Key,
        [string]$PinnedSourceAddress,
        [string]$PinnedBasisForwardOffset
    )

    $arguments = @{
        Key = $Key
        Json = $true
        HoldMilliseconds = $HoldMilliseconds
        WaitMilliseconds = $WaitMilliseconds
    }

    if ($RefreshReaderBridge) {
        $arguments['RefreshReaderBridge'] = $true
    }

    if ($NoAhkFallback) {
        $arguments['NoAhkFallback'] = $true
    }

    if (-not [string]::IsNullOrWhiteSpace($PinnedSourceAddress)) {
        $arguments['PinnedSourceAddress'] = $PinnedSourceAddress
    }

    if (-not [string]::IsNullOrWhiteSpace($PinnedBasisForwardOffset)) {
        $arguments['PinnedBasisForwardOffset'] = $PinnedBasisForwardOffset
    }

    if (-not [string]::IsNullOrWhiteSpace($resolvedOrientationCandidateLedgerFile)) {
        $arguments['OrientationCandidateLedgerFile'] = $resolvedOrientationCandidateLedgerFile
    }

    if ($SkipUiClearCheck) {
        $arguments['SkipUiClearCheck'] = $true
    }

    if ($RequireTargetFocus) {
        $arguments['RequireTargetFocus'] = $true
    }

    if ($SkipLiveInputWarning) {
        $arguments['SkipLiveInputWarning'] = $true
    }

    if ($PostStimulusSampleCount -gt 0) {
        $arguments['PostStimulusSampleCount'] = $PostStimulusSampleCount
        $arguments['TimelineIntervalMilliseconds'] = $TimelineIntervalMilliseconds
    }

    try {
        $jsonText = & $stimulusScript @arguments
    }
    catch {
        throw "Stimulus helper failed for key '$Key'. Original error: $($_.Exception.Message)"
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Stimulus helper failed for key '$Key' (`$LASTEXITCODE=$LASTEXITCODE)."
    }

    if ((Get-Command Microsoft.PowerShell.Utility\ConvertFrom-Json).Parameters.ContainsKey('Depth')) {
        return ($jsonText | Microsoft.PowerShell.Utility\ConvertFrom-Json -Depth 80)
    }

    return ($jsonText | Microsoft.PowerShell.Utility\ConvertFrom-Json)
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

function Normalize-AngleRadians {
    param([double]$Radians)

    $normalized = $Radians
    while ($normalized -gt [Math]::PI) {
        $normalized -= 2.0 * [Math]::PI
    }

    while ($normalized -lt -[Math]::PI) {
        $normalized += 2.0 * [Math]::PI
    }

    return $normalized
}

function Convert-RadiansToDegrees {
    param([double]$Radians)
    return $Radians * 180.0 / [Math]::PI
}

function Get-OppositeSigns {
    param(
        [double]$Left,
        [double]$Right
    )

    if ([Math]::Abs($Left) -lt [double]::Epsilon -or [Math]::Abs($Right) -lt [double]::Epsilon) {
        return $false
    }

    return ($Left -gt 0 -and $Right -lt 0) -or ($Left -lt 0 -and $Right -gt 0)
}

function Get-CaptureSourceAddress {
    param($CaptureDocument)

    $readerOrientation = Get-OptionalPropertyValue -Object $CaptureDocument -Name 'ReaderOrientation'
    return [string](Get-OptionalPropertyValue -Object $readerOrientation -Name 'SelectedSourceAddress')
}

function Get-CaptureBasisForwardOffset {
    param($CaptureDocument)

    $readerOrientation = Get-OptionalPropertyValue -Object $CaptureDocument -Name 'ReaderOrientation'
    $pinnedBasisForwardOffset = [string](Get-OptionalPropertyValue -Object $readerOrientation -Name 'PinnedBasisForwardOffset')
    if (-not [string]::IsNullOrWhiteSpace($pinnedBasisForwardOffset)) {
        return $pinnedBasisForwardOffset
    }

    $liveSourceSample = Get-OptionalPropertyValue -Object $readerOrientation -Name 'LiveSourceSample'
    return [string](Get-OptionalPropertyValue -Object $liveSourceSample -Name 'BasisPrimaryForwardOffset')
}

function Get-CaptureLiveSourceSample {
    param($CaptureDocument)

    $readerOrientation = Get-OptionalPropertyValue -Object $CaptureDocument -Name 'ReaderOrientation'
    return Get-OptionalPropertyValue -Object $readerOrientation -Name 'LiveSourceSample'
}

function Get-CaptureEstimate {
    param($CaptureDocument)

    $readerOrientation = Get-OptionalPropertyValue -Object $CaptureDocument -Name 'ReaderOrientation'
    return Get-OptionalPropertyValue -Object $readerOrientation -Name 'PreferredEstimate'
}

function Get-EstimateYawDeltaDegrees {
    param(
        $BeforeEstimate,
        $AfterEstimate
    )

    if ($null -eq $BeforeEstimate -or $null -eq $AfterEstimate) {
        return $null
    }

    $beforeYaw = Get-OptionalPropertyValue -Object $BeforeEstimate -Name 'YawRadians'
    $afterYaw = Get-OptionalPropertyValue -Object $AfterEstimate -Name 'YawRadians'
    if ($null -eq $beforeYaw -or $null -eq $afterYaw) {
        return $null
    }

    return Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ([double]$afterYaw - [double]$beforeYaw))
}

function Get-OrientationProbeSnapshot {
    try {
        $snapshot = Invoke-ReaderJson -Arguments @('--readerbridge-snapshot', '--json')
        return $snapshot.Current.OrientationProbe
    }
    catch {
        return $null
    }
}

function Get-CandidateRejectedReason {
    param(
        [bool]$BasisRecovered,
        [bool]$YawRecovered,
        [bool]$IdleConsistencyPass,
        [bool]$BaselineToLeftBeforeSourceStable,
        [bool]$LeftAfterToRightBeforeSourceStable,
        [bool]$LeftSourceStable,
        [bool]$RightSourceStable,
        $LeftYaw,
        $RightYaw,
        [double]$LeftCoord,
        [double]$RightCoord
    )

    if ($YawRecovered) {
        return $null
    }

    if (-not $BasisRecovered) {
        return 'basis_unavailable'
    }

    if (-not $BaselineToLeftBeforeSourceStable -or -not $LeftAfterToRightBeforeSourceStable -or -not $LeftSourceStable -or -not $RightSourceStable) {
        return 'source_drift'
    }

    if (-not $IdleConsistencyPass) {
        return 'idle_drift'
    }

    if ($null -eq $LeftYaw -or $null -eq $RightYaw) {
        return 'no_yaw_measurement'
    }

    if ($LeftCoord -gt 0.25 -or $RightCoord -gt 0.25) {
        return 'coord_drift'
    }

    if ([Math]::Abs([double]$LeftYaw) -lt 1.0 -and [Math]::Abs([double]$RightYaw) -lt 1.0) {
        return 'stable_but_nonresponsive'
    }

    if ([Math]::Abs([double]$LeftYaw) -lt 15.0 -or [Math]::Abs([double]$RightYaw) -lt 15.0) {
        return 'insufficient_turn_response'
    }

    if (-not (Get-OppositeSigns -Left ([double]$LeftYaw) -Right ([double]$RightYaw))) {
        return 'same_direction_response'
    }

    return 'unclassified'
}

function Write-CandidateLedgerEntry {
    param(
        [Parameter(Mandatory = $true)]
        $BaselineCapture,

        [Parameter(Mandatory = $true)]
        [bool]$CandidateResponsive,

        [Parameter(Mandatory = $true)]
        [string]$EvaluationMode,

        [string]$StimulusKey,

        [bool]$SourceStable,

        $CoordDriftMagnitude,

        $YawDeltaDegrees,

        $PitchDeltaDegrees,

        [string]$CandidateRejectedReason,

        [string[]]$Notes
    )

    if ($SkipCandidateLedgerWrite) {
        return
    }

    if ([string]::IsNullOrWhiteSpace($resolvedOrientationCandidateLedgerFile)) {
        return
    }

    $sourceAddress = Get-CaptureSourceAddress -CaptureDocument $BaselineCapture
    if ([string]::IsNullOrWhiteSpace($sourceAddress)) {
        return
    }

    $basisForwardOffset = Get-CaptureBasisForwardOffset -CaptureDocument $BaselineCapture
    $readerOrientation = Get-OptionalPropertyValue -Object $BaselineCapture -Name 'ReaderOrientation'
    $liveSourceSample = Get-CaptureLiveSourceSample -CaptureDocument $BaselineCapture

    $entry = [pscustomobject]@{
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
        ProcessName = $ProcessName
        SourceAddress = $sourceAddress
        BasisForwardOffset = $basisForwardOffset
        ResolutionMode = [string](Get-OptionalPropertyValue -Object $readerOrientation -Name 'ResolutionMode')
        DiscoveryMode = [string](Get-OptionalPropertyValue -Object $liveSourceSample -Name 'DiscoveryMode')
        ParentAddress = [string](Get-OptionalPropertyValue -Object $liveSourceSample -Name 'ParentAddress')
        RootAddress = [string](Get-OptionalPropertyValue -Object $liveSourceSample -Name 'RootAddress')
        RootSource = [string](Get-OptionalPropertyValue -Object $liveSourceSample -Name 'RootSource')
        HopDepth = Get-OptionalPropertyValue -Object $liveSourceSample -Name 'HopDepth'
        EvaluationMode = $EvaluationMode
        StimulusKey = $StimulusKey
        SourceStable = $SourceStable
        CoordDriftMagnitude = $CoordDriftMagnitude
        YawDeltaDegrees = $YawDeltaDegrees
        PitchDeltaDegrees = $PitchDeltaDegrees
        CandidateResponsive = $CandidateResponsive
        CandidateRejectedReason = $CandidateRejectedReason
        Notes = @($Notes)
    }

    $ledgerDirectory = Split-Path -Path $resolvedOrientationCandidateLedgerFile -Parent
    if (-not [string]::IsNullOrWhiteSpace($ledgerDirectory)) {
        New-Item -ItemType Directory -Path $ledgerDirectory -Force | Out-Null
    }

    $entryJson = $entry | ConvertTo-Json -Compress -Depth 20
    Add-Content -LiteralPath $resolvedOrientationCandidateLedgerFile -Value $entryJson
}

$baseline = Invoke-Capture -Label 'recovery-baseline'
$baselinePinnedSourceAddress = if (-not [string]::IsNullOrWhiteSpace($PinnedSourceAddress)) { $PinnedSourceAddress } else { [string](Get-OptionalPropertyValue -Object $baseline.ReaderOrientation -Name 'SelectedSourceAddress') }
$baselineLiveSourceSample = Get-OptionalPropertyValue -Object $baseline.ReaderOrientation -Name 'LiveSourceSample'
$baselinePinnedBasisForwardOffset = if (-not [string]::IsNullOrWhiteSpace($PinnedBasisForwardOffset)) { $PinnedBasisForwardOffset } else { [string](Get-OptionalPropertyValue -Object $baselineLiveSourceSample -Name 'BasisPrimaryForwardOffset') }
$leftStimulus = Invoke-Stimulus -Key $LeftTurnKey -PinnedSourceAddress $baselinePinnedSourceAddress -PinnedBasisForwardOffset $baselinePinnedBasisForwardOffset
$rightStimulus = Invoke-Stimulus -Key $RightTurnKey -PinnedSourceAddress $baselinePinnedSourceAddress -PinnedBasisForwardOffset $baselinePinnedBasisForwardOffset
$orientationProbe = Get-OrientationProbeSnapshot

$preferredBasis = $baseline.ReaderOrientation.PreferredBasis
$duplicateAgreement = $baseline.ReaderOrientation.DuplicateBasisAgreement
$preferredEstimate = $baseline.ReaderOrientation.PreferredEstimate
$resolutionMode = [string](Get-OptionalPropertyValue -Object $baseline.ReaderOrientation -Name 'ResolutionMode')
$pointerHopResolution = -not [string]::IsNullOrWhiteSpace($resolutionMode) -and $resolutionMode -like '*pointer-hop*'

$basisRecovered =
    $null -ne $preferredBasis -and
    $preferredBasis.IsOrthonormal -eq $true -and
    ((
        $null -ne $duplicateAgreement -and
        $null -ne $duplicateAgreement.MaxRowDeltaMagnitude -and
        [double]$duplicateAgreement.MaxRowDeltaMagnitude -le 0.05
    ) -or $pointerHopResolution)

$leftYawRaw = Get-OptionalPropertyValue -Object $leftStimulus.Comparison -Name 'YawDeltaDegrees'
$rightYawRaw = Get-OptionalPropertyValue -Object $rightStimulus.Comparison -Name 'YawDeltaDegrees'
$leftPitchRaw = Get-OptionalPropertyValue -Object $leftStimulus.Comparison -Name 'PitchDeltaDegrees'
$rightPitchRaw = Get-OptionalPropertyValue -Object $rightStimulus.Comparison -Name 'PitchDeltaDegrees'
$leftYaw = if ($null -ne $leftYawRaw) { [double]$leftYawRaw } else { $null }
$rightYaw = if ($null -ne $rightYawRaw) { [double]$rightYawRaw } else { $null }
$leftPitch = if ($null -ne $leftPitchRaw) { [double]$leftPitchRaw } else { $null }
$rightPitch = if ($null -ne $rightPitchRaw) { [double]$rightPitchRaw } else { $null }
$leftCoord = if ($null -ne $leftStimulus.Comparison.CoordDeltaMagnitude) { [double]$leftStimulus.Comparison.CoordDeltaMagnitude } else { 9999.0 }
$rightCoord = if ($null -ne $rightStimulus.Comparison.CoordDeltaMagnitude) { [double]$rightStimulus.Comparison.CoordDeltaMagnitude } else { 9999.0 }
$leftSourceStable = [bool](Get-OptionalPropertyValue -Object $leftStimulus.Comparison -Name 'SourceStable')
$rightSourceStable = [bool](Get-OptionalPropertyValue -Object $rightStimulus.Comparison -Name 'SourceStable')
$baselineSourceAddress = Get-CaptureSourceAddress -CaptureDocument $baseline
$leftBeforeSourceAddress = Get-CaptureSourceAddress -CaptureDocument $leftStimulus.Before
$leftAfterSourceAddress = Get-CaptureSourceAddress -CaptureDocument $leftStimulus.After
$rightBeforeSourceAddress = Get-CaptureSourceAddress -CaptureDocument $rightStimulus.Before
$rightAfterSourceAddress = Get-CaptureSourceAddress -CaptureDocument $rightStimulus.After
$baselineToLeftBeforeSourceStable =
    (-not [string]::IsNullOrWhiteSpace($baselineSourceAddress)) -and
    [string]::Equals($baselineSourceAddress, $leftBeforeSourceAddress, [System.StringComparison]::OrdinalIgnoreCase)
$leftAfterToRightBeforeSourceStable =
    (-not [string]::IsNullOrWhiteSpace($leftAfterSourceAddress)) -and
    [string]::Equals($leftAfterSourceAddress, $rightBeforeSourceAddress, [System.StringComparison]::OrdinalIgnoreCase)
$baselineIdleYawDelta = Get-EstimateYawDeltaDegrees -BeforeEstimate (Get-CaptureEstimate -CaptureDocument $baseline) -AfterEstimate (Get-CaptureEstimate -CaptureDocument $leftStimulus.Before)
$interStimulusYawDelta = Get-EstimateYawDeltaDegrees -BeforeEstimate (Get-CaptureEstimate -CaptureDocument $leftStimulus.After) -AfterEstimate (Get-CaptureEstimate -CaptureDocument $rightStimulus.Before)
$idleConsistencyPass =
    $baselineToLeftBeforeSourceStable -and
    $leftAfterToRightBeforeSourceStable -and
    $null -ne $baselineIdleYawDelta -and
    $null -ne $interStimulusYawDelta -and
    [Math]::Abs([double]$baselineIdleYawDelta) -le 5.0 -and
    [Math]::Abs([double]$interStimulusYawDelta) -le 5.0

$candidateResponsive =
    $basisRecovered -and
    $leftSourceStable -and
    $rightSourceStable -and
    $leftCoord -le 0.25 -and
    $rightCoord -le 0.25 -and
    (($null -ne $leftYaw -and [Math]::Abs([double]$leftYaw) -ge 1.0) -or ($null -ne $rightYaw -and [Math]::Abs([double]$rightYaw) -ge 1.0))

$yawRecovered =
    $basisRecovered -and
    $idleConsistencyPass -and
    $leftSourceStable -and
    $rightSourceStable -and
    $null -ne $leftYaw -and
    $null -ne $rightYaw -and
    [Math]::Abs([double]$leftYaw) -ge 15.0 -and
    [Math]::Abs([double]$rightYaw) -ge 15.0 -and
    (Get-OppositeSigns -Left ([double]$leftYaw) -Right ([double]$rightYaw)) -and
    $leftCoord -le 0.25 -and
    $rightCoord -le 0.25

$pitchRecovered =
    $basisRecovered -and
    $null -ne $preferredEstimate -and
    $null -ne $preferredEstimate.PitchDegrees

$candidateRejectedReason = Get-CandidateRejectedReason `
    -BasisRecovered $basisRecovered `
    -YawRecovered $yawRecovered `
    -IdleConsistencyPass $idleConsistencyPass `
    -BaselineToLeftBeforeSourceStable $baselineToLeftBeforeSourceStable `
    -LeftAfterToRightBeforeSourceStable $leftAfterToRightBeforeSourceStable `
    -LeftSourceStable $leftSourceStable `
    -RightSourceStable $rightSourceStable `
    -LeftYaw $leftYaw `
    -RightYaw $rightYaw `
    -LeftCoord $leftCoord `
    -RightCoord $rightCoord

$notes = New-Object System.Collections.Generic.List[string]
if (-not [string]::IsNullOrWhiteSpace($resolutionMode)) {
    $notes.Add("Resolution mode: $resolutionMode")
}
if ($pointerHopResolution) {
    $notes.Add('Recovery used a pointer-hop candidate without duplicate-basis agreement; orthonormal basis quality was used as the basis gate instead.')
}
if (-not [string]::IsNullOrWhiteSpace($baselinePinnedSourceAddress)) {
    $notes.Add("Pinned recovery source: $baselinePinnedSourceAddress")
}
if (-not $baselineToLeftBeforeSourceStable) {
    $notes.Add("Baseline-to-left-before source drifted: baseline=$baselineSourceAddress leftBefore=$leftBeforeSourceAddress")
}
if (-not $leftAfterToRightBeforeSourceStable) {
    $notes.Add("Left-after to right-before source drifted: leftAfter=$leftAfterSourceAddress rightBefore=$rightBeforeSourceAddress")
}
if ($null -ne $baselineIdleYawDelta -and [Math]::Abs([double]$baselineIdleYawDelta) -gt 5.0) {
    $notes.Add(("Baseline-to-left-before yaw drifted without input: {0} deg" -f (Format-Nullable $baselineIdleYawDelta '0.000')))
}
if ($null -ne $interStimulusYawDelta -and [Math]::Abs([double]$interStimulusYawDelta) -gt 5.0) {
    $notes.Add(("Left-after to right-before yaw drifted without input: {0} deg" -f (Format-Nullable $interStimulusYawDelta '0.000')))
}
if (-not $leftSourceStable) {
    $notes.Add("Left stimulus source was not stable: before=$($leftStimulus.Comparison.BeforeSourceAddress) after=$($leftStimulus.Comparison.AfterSourceAddress)")
}
if (-not $rightSourceStable) {
    $notes.Add("Right stimulus source was not stable: before=$($rightStimulus.Comparison.BeforeSourceAddress) after=$($rightStimulus.Comparison.AfterSourceAddress)")
}
if ($yawRecovered) {
    $notes.Add("Yaw recovery passed the opposite-direction turn gate ($LeftTurnKey/$RightTurnKey).")
}
else {
    $notes.Add("Yaw recovery did not pass the opposite-direction turn gate yet ($LeftTurnKey/$RightTurnKey).")
    if (-not [string]::IsNullOrWhiteSpace($candidateRejectedReason)) {
        $notes.Add("Candidate rejected reason: $candidateRejectedReason")
    }
}
if ($pitchRecovered) {
    $notes.Add('Pitch is available from the recovered orientation basis.')
}
if ($candidateResponsive -and -not $yawRecovered) {
    $notes.Add("Candidate showed some stable turn response but did not satisfy the full opposite-direction turn gate ($LeftTurnKey/$RightTurnKey).")
}
if ($orientationProbe) {
    $orientationProbePlayer = Get-OptionalPropertyValue -Object $orientationProbe -Name 'Player'
    $playerDirectHeading = Get-OptionalPropertyValue -Object $orientationProbePlayer -Name 'DirectHeading'
    $playerDirectPitch = Get-OptionalPropertyValue -Object $orientationProbePlayer -Name 'DirectPitch'

    if ($null -ne $playerDirectHeading) {
        $notes.Add("Addon direct heading candidate: $playerDirectHeading")
    }
    if ($null -ne $playerDirectPitch) {
        $notes.Add("Addon direct pitch candidate: $playerDirectPitch")
    }
}

$document = [pscustomobject]@{
    Mode = 'actor-orientation-recovery'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    OutputFile = $resolvedOutputFile
    OrientationCandidateLedgerFile = $resolvedOrientationCandidateLedgerFile
    ProcessName = $ProcessName
    LeftTurnKey = $LeftTurnKey
    RightTurnKey = $RightTurnKey
    SkipUiClearCheck = [bool]$SkipUiClearCheck
    RequireTargetFocus = [bool]$RequireTargetFocus
    SkipLiveInputWarning = [bool]$SkipLiveInputWarning
    Recovery = [pscustomobject]@{
        BasisRecovered = $basisRecovered
        CandidateResponsive = $candidateResponsive
        CandidateRejectedReason = $candidateRejectedReason
        YawRecovered = $yawRecovered
        PitchRecovered = $pitchRecovered
        IdleConsistencyPass = $idleConsistencyPass
        BaselineIdleYawDeltaDegrees = $baselineIdleYawDelta
        InterStimulusYawDeltaDegrees = $interStimulusYawDelta
    }
    Baseline = $baseline
    LeftStimulus = $leftStimulus
    RightStimulus = $rightStimulus
    OrientationProbe = $orientationProbe
    Notes = $notes
}

Write-CandidateLedgerEntry `
    -BaselineCapture $baseline `
    -CandidateResponsive $candidateResponsive `
    -EvaluationMode 'full-recovery' `
    -StimulusKey "$LeftTurnKey+$RightTurnKey" `
    -SourceStable ($baselineToLeftBeforeSourceStable -and $leftAfterToRightBeforeSourceStable -and $leftSourceStable -and $rightSourceStable) `
    -CoordDriftMagnitude ([Math]::Max($leftCoord, $rightCoord)) `
    -YawDeltaDegrees $(if ($null -ne $leftYaw -and $null -ne $rightYaw) { [Math]::Max([Math]::Abs([double]$leftYaw), [Math]::Abs([double]$rightYaw)) } else { $null }) `
    -PitchDeltaDegrees $(if ($null -ne $leftPitch -and $null -ne $rightPitch) { [Math]::Max([Math]::Abs([double]$leftPitch), [Math]::Abs([double]$rightPitch)) } else { $null }) `
    -CandidateRejectedReason $candidateRejectedReason `
    -Notes @($notes.ToArray())

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $document | ConvertTo-Json -Depth 80
[System.IO.File]::WriteAllText($resolvedOutputFile, $jsonText)

if ($Json) {
    Write-Output $jsonText
    exit 0
}

Write-Host "Actor orientation recovery"
Write-Host ("Process:                     {0}" -f $ProcessName)
Write-Host ("Resolution mode:             {0}" -f $(if (-not [string]::IsNullOrWhiteSpace($resolutionMode)) { $resolutionMode } else { 'n/a' }))
Write-Host ("Require target focus:        {0}" -f $document.RequireTargetFocus)
Write-Host ("Skip UI clear-check:         {0}" -f $document.SkipUiClearCheck)
Write-Host ("Skip live warning:           {0}" -f $document.SkipLiveInputWarning)
Write-Host ("Basis recovered:             {0}" -f $document.Recovery.BasisRecovered)
Write-Host ("Candidate responsive:        {0}" -f $document.Recovery.CandidateResponsive)
Write-Host ("Yaw recovered:               {0}" -f $document.Recovery.YawRecovered)
Write-Host ("Pitch recovered:             {0}" -f $document.Recovery.PitchRecovered)
Write-Host ("Idle consistency pass:       {0}" -f $document.Recovery.IdleConsistencyPass)
Write-Host ("Rejected reason:             {0}" -f $(if (-not [string]::IsNullOrWhiteSpace($document.Recovery.CandidateRejectedReason)) { $document.Recovery.CandidateRejectedReason } else { 'n/a' }))
Write-Host ("Baseline yaw/pitch (deg):    {0} / {1}" -f (Format-Nullable $preferredEstimate.YawDegrees '0.000'), (Format-Nullable $preferredEstimate.PitchDegrees '0.000'))
Write-Host ("Idle yaw drift (deg):        {0} / {1}" -f (Format-Nullable $document.Recovery.BaselineIdleYawDeltaDegrees '0.000'), (Format-Nullable $document.Recovery.InterStimulusYawDeltaDegrees '0.000'))
Write-Host ("{0} yaw delta / coord:       {1} / {2}" -f $LeftTurnKey, (Format-Nullable $leftYaw '0.000'), (Format-Nullable $leftCoord '0.000000'))
Write-Host ("{0} yaw delta / coord:       {1} / {2}" -f $RightTurnKey, (Format-Nullable $rightYaw '0.000'), (Format-Nullable $rightCoord '0.000000'))
if ($orientationProbe) {
    $orientationProbePlayer = Get-OptionalPropertyValue -Object $orientationProbe -Name 'Player'
    $playerDirectHeading = Get-OptionalPropertyValue -Object $orientationProbePlayer -Name 'DirectHeading'
    $playerDirectPitch = Get-OptionalPropertyValue -Object $orientationProbePlayer -Name 'DirectPitch'
    Write-Host ("Addon direct heading/pitch:  {0} / {1}" -f (Format-Nullable $playerDirectHeading '0.000'), (Format-Nullable $playerDirectPitch '0.000'))
}
Write-Host ("Output file:                 {0}" -f $resolvedOutputFile)
Write-Host ("Ledger file:                 {0}" -f $resolvedOrientationCandidateLedgerFile)
