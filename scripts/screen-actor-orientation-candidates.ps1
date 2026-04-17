[CmdletBinding()]
param(
    [switch]$Json,
    [string]$ProcessName = 'rift_x64',
    [int]$MaxHits = 8,
    [ValidateSet('A', 'D', 'Left', 'Right')]
    [string]$PreflightKey = 'D',
    [switch]$DualKeyPreflight,
    [ValidateSet('A', 'D', 'Left', 'Right')]
    [string]$SecondaryPreflightKey,
    [double]$MinimumYawResponseDegrees = 1.0,
    [double]$MaxCoordDrift = 0.25,
    [double]$MaxInterPreflightIdleDriftDegrees = 5.0,
    [int]$PostStimulusSampleCount = 0,
    [int]$TimelineIntervalMilliseconds = 250,
    [int]$FullRecoveryLimit = 2,
    [switch]$SkipFullRecovery,
    [switch]$RetestLedgerRejected,
    [switch]$RefreshReaderBridge,
    [switch]$NoAhkFallback,
    [switch]$SkipUiClearCheck,
    [switch]$RequireTargetFocus,
    [switch]$SkipLiveInputWarning,
    [switch]$StopOnFirstRecoveredYaw,
    [string]$LedgerFile,
    [string]$HistoryFile,
    [switch]$SkipHistoryWrite,
    [string]$RecoveryOutputDirectory,
    [string]$OutputFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$stimulusScript = Join-Path $PSScriptRoot 'test-actor-orientation-stimulus.ps1'
$recoveryScript = Join-Path $PSScriptRoot 'recover-actor-orientation.ps1'

if ([string]::IsNullOrWhiteSpace($LedgerFile)) {
    $LedgerFile = Join-Path $PSScriptRoot 'captures\actor-orientation-candidate-ledger.ndjson'
}

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = Join-Path $PSScriptRoot 'captures\actor-orientation-candidate-screen.json'
}

if ([string]::IsNullOrWhiteSpace($HistoryFile)) {
    $HistoryFile = Join-Path $PSScriptRoot 'captures\actor-orientation-candidate-screen-history.ndjson'
}

if ([string]::IsNullOrWhiteSpace($RecoveryOutputDirectory)) {
    $RecoveryOutputDirectory = Join-Path $PSScriptRoot 'captures\screening'
}

function Get-OppositeTurnKey {
    param([Parameter(Mandatory = $true)][string]$Key)

    switch ($Key.ToUpperInvariant()) {
        'RIGHT' { return 'Left' }
        'LEFT' { return 'Right' }
        'D' { return 'A' }
        'A' { return 'D' }
        default { throw "Unsupported turn key '$Key'." }
    }
}

function Get-RecoveryTurnKeyPair {
    param(
        [Parameter(Mandatory = $true)][string]$PrimaryKey,
        [Parameter(Mandatory = $true)][string]$SecondaryKey
    )

    $leftTurnKeys = @('A', 'LEFT')
    $rightTurnKeys = @('D', 'RIGHT')
    $primaryNormalized = $PrimaryKey.ToUpperInvariant()
    $secondaryNormalized = $SecondaryKey.ToUpperInvariant()

    if ($leftTurnKeys -contains $primaryNormalized -and $rightTurnKeys -contains $secondaryNormalized) {
        return [pscustomobject]@{
            LeftTurnKey = $PrimaryKey
            RightTurnKey = $SecondaryKey
        }
    }

    if ($rightTurnKeys -contains $primaryNormalized -and $leftTurnKeys -contains $secondaryNormalized) {
        return [pscustomobject]@{
            LeftTurnKey = $SecondaryKey
            RightTurnKey = $PrimaryKey
        }
    }

    throw "Preflight keys '$PrimaryKey' and '$SecondaryKey' must be opposite-direction turn inputs."
}

if ([string]::IsNullOrWhiteSpace($SecondaryPreflightKey)) {
    $SecondaryPreflightKey = Get-OppositeTurnKey -Key $PreflightKey
}

if (-not $PSBoundParameters.ContainsKey('RequireTargetFocus')) {
    $RequireTargetFocus = $true
}

$resolvedLedgerFile = [System.IO.Path]::GetFullPath($LedgerFile)
$resolvedHistoryFile = [System.IO.Path]::GetFullPath($HistoryFile)
$resolvedRecoveryOutputDirectory = [System.IO.Path]::GetFullPath($RecoveryOutputDirectory)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$recoveryTurnKeyPair = Get-RecoveryTurnKeyPair -PrimaryKey $PreflightKey -SecondaryKey $SecondaryPreflightKey

function ConvertFrom-JsonCompat {
    param(
        [Parameter(Mandatory = $true)]
        [string]$JsonText,
        [int]$Depth = 20
    )

    if ($PSVersionTable.PSVersion.Major -ge 6) {
        return $JsonText | ConvertFrom-Json -Depth $Depth
    }

    return $JsonText | ConvertFrom-Json
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

    return ConvertFrom-JsonCompat -JsonText ($output -join [Environment]::NewLine) -Depth 80
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

function Normalize-HexString {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }

    $trimmed = $Value.Trim()
    if ($trimmed.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $trimmed = $trimmed.Substring(2)
    }

    [UInt64]$parsedValue = 0
    if ([UInt64]::TryParse($trimmed, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$parsedValue)) {
        return ('0x{0:X}' -f $parsedValue)
    }

    if ([UInt64]::TryParse($trimmed, [System.Globalization.NumberStyles]::Integer, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$parsedValue)) {
        return ('0x{0:X}' -f $parsedValue)
    }

    return $Value
}

function New-LedgerKey {
    param(
        [string]$SourceAddress,
        [string]$BasisForwardOffset
    )

    $normalizedSource = Normalize-HexString -Value $SourceAddress
    if ([string]::IsNullOrWhiteSpace($normalizedSource)) {
        return $null
    }

    $normalizedBasis = Normalize-HexString -Value $BasisForwardOffset
    if ([string]::IsNullOrWhiteSpace($normalizedBasis)) {
        $normalizedBasis = '0x0'
    }

    return '{0}|{1}' -f $normalizedSource, $normalizedBasis
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

function Get-LedgerEvidenceIndex {
    $evidenceByKey = @{}

    if (-not (Test-Path -LiteralPath $resolvedLedgerFile)) {
        return $evidenceByKey
    }

    foreach ($line in (Get-Content -LiteralPath $resolvedLedgerFile)) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $entry = ConvertFrom-JsonCompat -JsonText $line -Depth 30
        $key = New-LedgerKey -SourceAddress ([string](Get-OptionalPropertyValue -Object $entry -Name 'SourceAddress')) -BasisForwardOffset ([string](Get-OptionalPropertyValue -Object $entry -Name 'BasisForwardOffset'))
        if ([string]::IsNullOrWhiteSpace($key)) {
            continue
        }

        if (-not $evidenceByKey.ContainsKey($key)) {
            $evidenceByKey[$key] = [ordered]@{
                SourceAddress = [string](Get-OptionalPropertyValue -Object $entry -Name 'SourceAddress')
                BasisForwardOffset = [string](Get-OptionalPropertyValue -Object $entry -Name 'BasisForwardOffset')
                StableNonresponsiveCount = 0
                ResponsiveCount = 0
                LatestCandidateResponsive = $false
                LatestCandidateRejectedReason = $null
                LatestGeneratedAtUtc = $null
            }
        }

        $bucket = $evidenceByKey[$key]
        if ([bool](Get-OptionalPropertyValue -Object $entry -Name 'CandidateResponsive')) {
            $bucket.ResponsiveCount++
        }

        $rejectedReason = [string](Get-OptionalPropertyValue -Object $entry -Name 'CandidateRejectedReason')
        if ($rejectedReason -eq 'stable_but_nonresponsive') {
            $bucket.StableNonresponsiveCount++
        }

        $generatedAtUtc = [string](Get-OptionalPropertyValue -Object $entry -Name 'GeneratedAtUtc')
        if ([string]::IsNullOrWhiteSpace([string]$bucket.LatestGeneratedAtUtc) -or $generatedAtUtc -ge [string]$bucket.LatestGeneratedAtUtc) {
            $bucket.LatestGeneratedAtUtc = $generatedAtUtc
            $bucket.LatestCandidateResponsive = [bool](Get-OptionalPropertyValue -Object $entry -Name 'CandidateResponsive')
            $bucket.LatestCandidateRejectedReason = $rejectedReason
        }
    }

    return $evidenceByKey
}

function Test-LedgerRejected {
    param($Evidence)

    return $null -ne $Evidence -and
        ((-not [bool]$Evidence.LatestCandidateResponsive -and [string]$Evidence.LatestCandidateRejectedReason -eq 'stable_but_nonresponsive') -or
         [string]$Evidence.LatestCandidateRejectedReason -eq 'idle_drift' -or
         [string]$Evidence.LatestCandidateRejectedReason -eq 'inter_preflight_idle_drift')
}

function Write-LedgerEntry {
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

    $ledgerDirectory = Split-Path -Path $resolvedLedgerFile -Parent
    if (-not [string]::IsNullOrWhiteSpace($ledgerDirectory)) {
        New-Item -ItemType Directory -Path $ledgerDirectory -Force | Out-Null
    }

    Add-Content -LiteralPath $resolvedLedgerFile -Value ($entry | ConvertTo-Json -Compress -Depth 20)
}

function Write-ScreenHistoryEntry {
    param(
        [Parameter(Mandatory = $true)]
        $Document
    )

    if ($SkipHistoryWrite) {
        return
    }

    if ([string]::IsNullOrWhiteSpace($resolvedHistoryFile)) {
        return
    }

    $historyDirectory = Split-Path -Path $resolvedHistoryFile -Parent
    if (-not [string]::IsNullOrWhiteSpace($historyDirectory)) {
        New-Item -ItemType Directory -Path $historyDirectory -Force | Out-Null
    }

    $historyEntry = [pscustomobject]@{
        GeneratedAtUtc = $Document.GeneratedAtUtc
        ProcessName = $Document.ProcessName
        PreflightKey = $Document.PreflightKey
        DualKeyPreflight = [bool]$Document.DualKeyPreflight
        SecondaryPreflightKey = $Document.SecondaryPreflightKey
        MinimumYawResponseDegrees = $Document.MinimumYawResponseDegrees
        MaxCoordDrift = $Document.MaxCoordDrift
        MaxInterPreflightIdleDriftDegrees = $Document.MaxInterPreflightIdleDriftDegrees
        FullRecoveryLimit = $Document.FullRecoveryLimit
        LedgerFile = $Document.LedgerFile
        RecoveryOutputDirectory = $Document.RecoveryOutputDirectory
        OutputFile = $Document.OutputFile
        SkipUiClearCheck = [bool]$Document.SkipUiClearCheck
        RequireTargetFocus = [bool]$Document.RequireTargetFocus
        SkipLiveInputWarning = [bool]$Document.SkipLiveInputWarning
        StopOnFirstRecoveredYaw = [bool]$Document.StopOnFirstRecoveredYaw
        StoppedAfterRecoveredYaw = [bool]$Document.StoppedAfterRecoveredYaw
        CandidateSearchSummary = [pscustomobject]@{
            CandidateCount = Get-OptionalPropertyValue -Object $Document.CandidateSearch -Name 'CandidateCount'
            PointerHopCandidateCount = Get-OptionalPropertyValue -Object $Document.CandidateSearch -Name 'PointerHopCandidateCount'
            Diagnostics = Get-OptionalPropertyValue -Object $Document.CandidateSearch -Name 'Diagnostics'
            BestPointerHopCandidate = if ($null -ne (Get-OptionalPropertyValue -Object $Document.CandidateSearch -Name 'BestPointerHopCandidate')) {
                $best = Get-OptionalPropertyValue -Object $Document.CandidateSearch -Name 'BestPointerHopCandidate'
                [pscustomobject]@{
                    Address = [string](Get-OptionalPropertyValue -Object $best -Name 'Address')
                    BasisForwardOffset = [string](Get-OptionalPropertyValue -Object $best -Name 'BasisPrimaryForwardOffset')
                    DiscoveryMode = [string](Get-OptionalPropertyValue -Object $best -Name 'DiscoveryMode')
                    ParentAddress = [string](Get-OptionalPropertyValue -Object $best -Name 'ParentAddress')
                    RootAddress = [string](Get-OptionalPropertyValue -Object $best -Name 'RootAddress')
                    RootSource = [string](Get-OptionalPropertyValue -Object $best -Name 'RootSource')
                    HopDepth = Get-OptionalPropertyValue -Object $best -Name 'HopDepth'
                    PointerOffset = [string](Get-OptionalPropertyValue -Object $best -Name 'PointerOffset')
                    Score = Get-OptionalPropertyValue -Object $best -Name 'Score'
                    RawScore = Get-OptionalPropertyValue -Object $best -Name 'RawScore'
                    LedgerPenalty = Get-OptionalPropertyValue -Object $best -Name 'LedgerPenalty'
                    LedgerRejectionReason = [string](Get-OptionalPropertyValue -Object $best -Name 'LedgerRejectionReason')
                }
            } else {
                $null
            }
        }
        Results = @($Document.Results | ForEach-Object {
                $result = $_
                $stimulus = Get-OptionalPropertyValue -Object $result -Name 'Stimulus'
                $secondaryStimulus = Get-OptionalPropertyValue -Object $result -Name 'SecondaryStimulus'
                $recovery = Get-OptionalPropertyValue -Object $result -Name 'Recovery'
                $existingLedgerEvidence = Get-OptionalPropertyValue -Object $result -Name 'ExistingLedgerEvidence'

                [pscustomobject]@{
                    Rank = Get-OptionalPropertyValue -Object $result -Name 'Rank'
                    CandidateType = [string](Get-OptionalPropertyValue -Object $result -Name 'CandidateType')
                    SourceAddress = [string](Get-OptionalPropertyValue -Object $result -Name 'SourceAddress')
                    BasisForwardOffset = [string](Get-OptionalPropertyValue -Object $result -Name 'BasisForwardOffset')
                    DiscoveryMode = [string](Get-OptionalPropertyValue -Object $result -Name 'DiscoveryMode')
                    ParentAddress = [string](Get-OptionalPropertyValue -Object $result -Name 'ParentAddress')
                    RootAddress = [string](Get-OptionalPropertyValue -Object $result -Name 'RootAddress')
                    RootSource = [string](Get-OptionalPropertyValue -Object $result -Name 'RootSource')
                    HopDepth = Get-OptionalPropertyValue -Object $result -Name 'HopDepth'
                    SearchScore = Get-OptionalPropertyValue -Object $result -Name 'SearchScore'
                    SearchRawScore = Get-OptionalPropertyValue -Object $result -Name 'SearchRawScore'
                    SearchLedgerPenalty = Get-OptionalPropertyValue -Object $result -Name 'SearchLedgerPenalty'
                    SearchLedgerRejectionReason = [string](Get-OptionalPropertyValue -Object $result -Name 'SearchLedgerRejectionReason')
                    SkippedBecauseLedger = [bool](Get-OptionalPropertyValue -Object $result -Name 'SkippedBecauseLedger')
                    ExistingLedgerLatestRejectedReason = if ($null -ne $existingLedgerEvidence) { [string](Get-OptionalPropertyValue -Object $existingLedgerEvidence -Name 'LatestCandidateRejectedReason') } else { $null }
                    PrimaryPreflightKey = if ($null -ne $stimulus) { [string](Get-OptionalPropertyValue -Object $stimulus -Name 'Key') } else { $null }
                    PrimaryYawDeltaDegrees = if ($null -ne $stimulus) { Get-OptionalPropertyValue -Object $stimulus -Name 'YawDeltaDegrees' } else { $null }
                    PrimaryPitchDeltaDegrees = if ($null -ne $stimulus) { Get-OptionalPropertyValue -Object $stimulus -Name 'PitchDeltaDegrees' } else { $null }
                    PrimaryCoordDeltaMagnitude = if ($null -ne $stimulus) { Get-OptionalPropertyValue -Object $stimulus -Name 'CoordDeltaMagnitude' } else { $null }
                    PrimaryResponsive = if ($null -ne $stimulus) { [bool](Get-OptionalPropertyValue -Object $stimulus -Name 'CandidateResponsive') } else { $false }
                    PrimaryRejectedReason = if ($null -ne $stimulus) { [string](Get-OptionalPropertyValue -Object $stimulus -Name 'CandidateRejectedReason') } else { $null }
                    SecondaryPreflightKey = if ($null -ne $secondaryStimulus) { [string](Get-OptionalPropertyValue -Object $secondaryStimulus -Name 'Key') } else { $null }
                    SecondaryYawDeltaDegrees = if ($null -ne $secondaryStimulus) { Get-OptionalPropertyValue -Object $secondaryStimulus -Name 'YawDeltaDegrees' } else { $null }
                    SecondaryPitchDeltaDegrees = if ($null -ne $secondaryStimulus) { Get-OptionalPropertyValue -Object $secondaryStimulus -Name 'PitchDeltaDegrees' } else { $null }
                    SecondaryCoordDeltaMagnitude = if ($null -ne $secondaryStimulus) { Get-OptionalPropertyValue -Object $secondaryStimulus -Name 'CoordDeltaMagnitude' } else { $null }
                    SecondaryResponsive = if ($null -ne $secondaryStimulus) { [bool](Get-OptionalPropertyValue -Object $secondaryStimulus -Name 'CandidateResponsive') } else { $false }
                    SecondaryRejectedReason = if ($null -ne $secondaryStimulus) { [string](Get-OptionalPropertyValue -Object $secondaryStimulus -Name 'CandidateRejectedReason') } else { $null }
                    PreflightPassed = [bool](Get-OptionalPropertyValue -Object $result -Name 'PreflightPassed')
                    PreflightRejectedReason = [string](Get-OptionalPropertyValue -Object $result -Name 'PreflightRejectedReason')
                    InterPreflightSourceStable = Get-OptionalPropertyValue -Object $result -Name 'InterPreflightSourceStable'
                    InterPreflightYawDriftDegrees = Get-OptionalPropertyValue -Object $result -Name 'InterPreflightYawDriftDegrees'
                    RecoveryRan = $null -ne $recovery
                    RecoveryCandidateResponsive = if ($null -ne $recovery) { [bool](Get-OptionalPropertyValue -Object $recovery -Name 'CandidateResponsive') } else { $false }
                    RecoveryCandidateRejectedReason = if ($null -ne $recovery) { [string](Get-OptionalPropertyValue -Object $recovery -Name 'CandidateRejectedReason') } else { $null }
                    YawRecovered = if ($null -ne $recovery) { [bool](Get-OptionalPropertyValue -Object $recovery -Name 'YawRecovered') } else { $false }
                    PitchRecovered = if ($null -ne $recovery) { [bool](Get-OptionalPropertyValue -Object $recovery -Name 'PitchRecovered') } else { $false }
                    IdleConsistencyPass = if ($null -ne $recovery) { Get-OptionalPropertyValue -Object $recovery -Name 'IdleConsistencyPass' } else { $null }
                    RecoveryOutputFile = if ($null -ne $recovery) { [string](Get-OptionalPropertyValue -Object $recovery -Name 'OutputFile') } else { $null }
                }
            })
        Notes = @($Document.Notes)
    }

    Add-Content -LiteralPath $resolvedHistoryFile -Value ($historyEntry | ConvertTo-Json -Compress -Depth 50)
}

function Invoke-StimulusCandidate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceAddress,

        [Parameter(Mandatory = $true)]
        [string]$BasisForwardOffset,

        [Parameter(Mandatory = $true)]
        [string]$Key
    )

    $arguments = @{
        Key = $Key
        Json = $true
        PinnedSourceAddress = $SourceAddress
        PinnedBasisForwardOffset = $BasisForwardOffset
        OrientationCandidateLedgerFile = $resolvedLedgerFile
        MinimumYawResponseDegrees = $MinimumYawResponseDegrees
        MaxCoordDrift = $MaxCoordDrift
    }

    if ($RefreshReaderBridge) {
        $arguments['RefreshReaderBridge'] = $true
    }

    if ($NoAhkFallback) {
        $arguments['NoAhkFallback'] = $true
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
        throw "Single-stimulus screening failed for $SourceAddress @ $BasisForwardOffset. Original error: $($_.Exception.Message)"
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Single-stimulus screening failed for $SourceAddress @ $BasisForwardOffset (`$LASTEXITCODE=$LASTEXITCODE)."
    }

    return ConvertFrom-JsonCompat -JsonText ([string]$jsonText) -Depth 80
}

function New-StimulusSummary {
    param(
        [Parameter(Mandatory = $true)]
        $StimulusResult,

        [Parameter(Mandatory = $true)]
        [string]$Key
    )

    $comparison = Get-OptionalPropertyValue -Object $StimulusResult -Name 'Comparison'
    $evaluation = Get-OptionalPropertyValue -Object $StimulusResult -Name 'CandidateEvaluation'
    return [pscustomobject]@{
        Key = $Key
        SourceStable = [bool](Get-OptionalPropertyValue -Object $comparison -Name 'SourceStable')
        YawDeltaDegrees = Get-OptionalPropertyValue -Object $comparison -Name 'YawDeltaDegrees'
        PitchDeltaDegrees = Get-OptionalPropertyValue -Object $comparison -Name 'PitchDeltaDegrees'
        CoordDeltaMagnitude = Get-OptionalPropertyValue -Object $comparison -Name 'CoordDeltaMagnitude'
        CandidateResponsive = [bool](Get-OptionalPropertyValue -Object $evaluation -Name 'Responsive')
        CandidateRejectedReason = [string](Get-OptionalPropertyValue -Object $evaluation -Name 'CandidateRejectedReason')
        BeforeSourceAddress = [string](Get-OptionalPropertyValue -Object $comparison -Name 'BeforeSourceAddress')
        AfterSourceAddress = [string](Get-OptionalPropertyValue -Object $comparison -Name 'AfterSourceAddress')
        Notes = @((Get-OptionalPropertyValue -Object $comparison -Name 'Notes'))
    }
}

function Invoke-RecoveryCandidate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceAddress,

        [Parameter(Mandatory = $true)]
        [string]$BasisForwardOffset,

        [Parameter(Mandatory = $true)]
        [string]$OutputPath
    )

    $arguments = @{
        Json = $true
        PinnedSourceAddress = $SourceAddress
        PinnedBasisForwardOffset = $BasisForwardOffset
        LeftTurnKey = $recoveryTurnKeyPair.LeftTurnKey
        RightTurnKey = $recoveryTurnKeyPair.RightTurnKey
        OrientationCandidateLedgerFile = $resolvedLedgerFile
        OutputFile = $OutputPath
    }

    if ($RefreshReaderBridge) {
        $arguments['RefreshReaderBridge'] = $true
    }

    if ($NoAhkFallback) {
        $arguments['NoAhkFallback'] = $true
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

    try {
        $jsonText = & $recoveryScript @arguments
    }
    catch {
        throw "Full recovery failed for $SourceAddress @ $BasisForwardOffset. Original error: $($_.Exception.Message)"
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Full recovery failed for $SourceAddress @ $BasisForwardOffset (`$LASTEXITCODE=$LASTEXITCODE)."
    }

    return ConvertFrom-JsonCompat -JsonText ([string]$jsonText) -Depth 80
}

function Get-CandidateToken {
    param(
        [string]$SourceAddress,
        [string]$BasisForwardOffset
    )

    $normalizedSource = (Normalize-HexString -Value $SourceAddress) -replace '^0x', ''
    $normalizedBasis = (Normalize-HexString -Value $BasisForwardOffset) -replace '^0x', ''
    return ('{0}-basis-{1}' -f $normalizedSource.ToLowerInvariant(), $normalizedBasis.ToLowerInvariant())
}

function Get-SearchCandidates {
    param($CandidateSearch)

    $candidates = New-Object System.Collections.Generic.List[object]
    $rank = 0

    foreach ($candidate in @($CandidateSearch.PointerHopCandidates)) {
        if ($null -eq $candidate) {
            continue
        }

        $rank++
        $candidates.Add([pscustomobject]@{
            Rank = $rank
            CandidateType = 'pointer-hop'
            SourceAddress = [string]$candidate.Address
            BasisForwardOffset = [string]$candidate.BasisPrimaryForwardOffset
            SearchScore = [int]$candidate.Score
            SearchRawScore = Get-OptionalPropertyValue -Object $candidate -Name 'RawScore'
            SearchLedgerPenalty = Get-OptionalPropertyValue -Object $candidate -Name 'LedgerPenalty'
            SearchLedgerRejectionReason = [string](Get-OptionalPropertyValue -Object $candidate -Name 'LedgerRejectionReason')
            DiscoveryMode = [string](Get-OptionalPropertyValue -Object $candidate -Name 'DiscoveryMode')
            ParentAddress = [string](Get-OptionalPropertyValue -Object $candidate -Name 'ParentAddress')
            RootAddress = [string](Get-OptionalPropertyValue -Object $candidate -Name 'RootAddress')
            RootSource = [string](Get-OptionalPropertyValue -Object $candidate -Name 'RootSource')
            HopDepth = Get-OptionalPropertyValue -Object $candidate -Name 'HopDepth'
        })
    }

    if ($candidates.Count -gt 0) {
        return $candidates.ToArray()
    }

    foreach ($candidate in @($CandidateSearch.Candidates)) {
        if ($null -eq $candidate) {
            continue
        }

        $rank++
        $candidates.Add([pscustomobject]@{
            Rank = $rank
            CandidateType = 'local-window'
            SourceAddress = [string]$candidate.Address
            BasisForwardOffset = [string]$candidate.BasisPrimaryForwardOffset
            SearchScore = [int]$candidate.Score
            SearchRawScore = $null
            SearchLedgerPenalty = 0
            SearchLedgerRejectionReason = $null
            DiscoveryMode = [string](Get-OptionalPropertyValue -Object $candidate -Name 'DiscoveryMode')
            ParentAddress = $null
            RootAddress = [string](Get-OptionalPropertyValue -Object $candidate -Name 'ProbeRootAddress')
            RootSource = [string](Get-OptionalPropertyValue -Object $candidate -Name 'ProbeSource')
            HopDepth = 0
        })
    }

    return $candidates.ToArray()
}

$candidateSearch = Invoke-ReaderJson -Arguments @(
    '--process-name', $ProcessName,
    '--find-player-orientation-candidate',
    '--orientation-candidate-ledger-file', $resolvedLedgerFile,
    '--max-hits', $MaxHits.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--json')

$ledgerEvidence = Get-LedgerEvidenceIndex
$screenResults = New-Object System.Collections.Generic.List[object]
$recoveryRunCount = 0
$stoppedAfterRecoveredYaw = $false
$winningRecoveryResult = $null

foreach ($candidate in @(Get-SearchCandidates -CandidateSearch $candidateSearch)) {
    $candidateKey = New-LedgerKey -SourceAddress $candidate.SourceAddress -BasisForwardOffset $candidate.BasisForwardOffset
    $existingEvidence = if (-not [string]::IsNullOrWhiteSpace($candidateKey) -and $ledgerEvidence.ContainsKey($candidateKey)) { $ledgerEvidence[$candidateKey] } else { $null }
    $skipFromLedger = (-not $RetestLedgerRejected) -and (Test-LedgerRejected -Evidence $existingEvidence)

    $candidateRecord = [ordered]@{
        Rank = $candidate.Rank
        CandidateType = $candidate.CandidateType
        SourceAddress = $candidate.SourceAddress
        BasisForwardOffset = $candidate.BasisForwardOffset
        SearchScore = $candidate.SearchScore
        SearchRawScore = $candidate.SearchRawScore
        SearchLedgerPenalty = $candidate.SearchLedgerPenalty
        SearchLedgerRejectionReason = $candidate.SearchLedgerRejectionReason
        DiscoveryMode = $candidate.DiscoveryMode
        ParentAddress = $candidate.ParentAddress
        RootAddress = $candidate.RootAddress
        RootSource = $candidate.RootSource
        HopDepth = $candidate.HopDepth
        SkippedBecauseLedger = $skipFromLedger
        ExistingLedgerEvidence = $existingEvidence
        Stimulus = $null
        SecondaryStimulus = $null
        PreflightPassed = $false
        PreflightRejectedReason = $null
        InterPreflightSourceStable = $null
        InterPreflightYawDriftDegrees = $null
        Recovery = $null
    }

    if ($skipFromLedger) {
        $candidateRecord['Notes'] = @("Skipped due to prior stable-but-nonresponsive ledger evidence for $($candidate.SourceAddress) @ $($candidate.BasisForwardOffset).")
        $screenResults.Add([pscustomobject]$candidateRecord)
        continue
    }

    $stimulusResult = Invoke-StimulusCandidate -SourceAddress $candidate.SourceAddress -BasisForwardOffset $candidate.BasisForwardOffset -Key $PreflightKey
    $stimulusSummary = New-StimulusSummary -StimulusResult $stimulusResult -Key $PreflightKey
    $stimulusComparison = Get-OptionalPropertyValue -Object $stimulusResult -Name 'Comparison'
    $stimulusResponsive = [bool]$stimulusSummary.CandidateResponsive
    $stimulusRejectedReason = [string]$stimulusSummary.CandidateRejectedReason

    Write-LedgerEntry `
        -BaselineCapture $stimulusResult.Before `
        -CandidateResponsive $stimulusResponsive `
        -EvaluationMode 'single-stimulus-screen' `
        -StimulusKey $PreflightKey `
        -SourceStable ([bool](Get-OptionalPropertyValue -Object $stimulusComparison -Name 'SourceStable')) `
        -CoordDriftMagnitude (Get-OptionalPropertyValue -Object $stimulusComparison -Name 'CoordDeltaMagnitude') `
        -YawDeltaDegrees (Get-OptionalPropertyValue -Object $stimulusComparison -Name 'YawDeltaDegrees') `
        -PitchDeltaDegrees (Get-OptionalPropertyValue -Object $stimulusComparison -Name 'PitchDeltaDegrees') `
        -CandidateRejectedReason $stimulusRejectedReason `
        -Notes @($stimulusSummary.Notes)

    $candidateRecord['Stimulus'] = $stimulusSummary
    $preflightPassed = $stimulusResponsive
    $preflightRejectedReason = $stimulusRejectedReason

    if ($stimulusResponsive -and $DualKeyPreflight) {
        $secondaryStimulusResult = Invoke-StimulusCandidate -SourceAddress $candidate.SourceAddress -BasisForwardOffset $candidate.BasisForwardOffset -Key $SecondaryPreflightKey
        $secondaryStimulusSummary = New-StimulusSummary -StimulusResult $secondaryStimulusResult -Key $SecondaryPreflightKey
        $secondaryComparison = Get-OptionalPropertyValue -Object $secondaryStimulusResult -Name 'Comparison'
        $secondaryResponsive = [bool]$secondaryStimulusSummary.CandidateResponsive
        $secondaryRejectedReason = [string]$secondaryStimulusSummary.CandidateRejectedReason

        Write-LedgerEntry `
            -BaselineCapture $secondaryStimulusResult.Before `
            -CandidateResponsive $secondaryResponsive `
            -EvaluationMode 'dual-preflight-secondary' `
            -StimulusKey $SecondaryPreflightKey `
            -SourceStable ([bool](Get-OptionalPropertyValue -Object $secondaryComparison -Name 'SourceStable')) `
            -CoordDriftMagnitude (Get-OptionalPropertyValue -Object $secondaryComparison -Name 'CoordDeltaMagnitude') `
            -YawDeltaDegrees (Get-OptionalPropertyValue -Object $secondaryComparison -Name 'YawDeltaDegrees') `
            -PitchDeltaDegrees (Get-OptionalPropertyValue -Object $secondaryComparison -Name 'PitchDeltaDegrees') `
            -CandidateRejectedReason $secondaryRejectedReason `
            -Notes @($secondaryStimulusSummary.Notes)

        $primaryYawDelta = Get-OptionalPropertyValue -Object $stimulusSummary -Name 'YawDeltaDegrees'
        $secondaryYawDelta = Get-OptionalPropertyValue -Object $secondaryStimulusSummary -Name 'YawDeltaDegrees'
        $interPreflightSourceStable =
            (-not [string]::IsNullOrWhiteSpace([string]$stimulusSummary.AfterSourceAddress)) -and
            [string]::Equals([string]$stimulusSummary.AfterSourceAddress, [string]$secondaryStimulusSummary.BeforeSourceAddress, [System.StringComparison]::OrdinalIgnoreCase)
        $interPreflightYawDrift = Get-EstimateYawDeltaDegrees -BeforeEstimate (Get-CaptureEstimate -CaptureDocument $stimulusResult.After) -AfterEstimate (Get-CaptureEstimate -CaptureDocument $secondaryStimulusResult.Before)
        $oppositeSigns =
            $null -ne $primaryYawDelta -and
            $null -ne $secondaryYawDelta -and
            (Get-OppositeSigns -Left ([double]$primaryYawDelta) -Right ([double]$secondaryYawDelta))

        if (-not $secondaryResponsive) {
            $preflightPassed = $false
            $preflightRejectedReason = if (-not [string]::IsNullOrWhiteSpace($secondaryRejectedReason)) { "secondary_$secondaryRejectedReason" } else { 'secondary_preflight_failed' }
        }
        elseif (-not $interPreflightSourceStable) {
            $preflightPassed = $false
            $preflightRejectedReason = 'inter_preflight_source_drift'
        }
        elseif ($null -eq $interPreflightYawDrift) {
            $preflightPassed = $false
            $preflightRejectedReason = 'inter_preflight_no_yaw_measurement'
        }
        elseif ([Math]::Abs([double]$interPreflightYawDrift) -gt $MaxInterPreflightIdleDriftDegrees) {
            $preflightPassed = $false
            $preflightRejectedReason = 'inter_preflight_idle_drift'
        }
        elseif (-not $oppositeSigns) {
            $preflightPassed = $false
            $preflightRejectedReason = 'preflight_direction_mismatch'
        }
        else {
            $preflightPassed = $true
            $preflightRejectedReason = $null
        }

        $primaryCoordMagnitude = if ($null -ne $stimulusSummary.CoordDeltaMagnitude) { [double]$stimulusSummary.CoordDeltaMagnitude } else { 0.0 }
        $secondaryCoordMagnitude = if ($null -ne $secondaryStimulusSummary.CoordDeltaMagnitude) { [double]$secondaryStimulusSummary.CoordDeltaMagnitude } else { 0.0 }
        $preflightCoordMax = [Math]::Max($primaryCoordMagnitude, $secondaryCoordMagnitude)

        $candidateRecord['SecondaryStimulus'] = $secondaryStimulusSummary
        $candidateRecord['InterPreflightSourceStable'] = $interPreflightSourceStable
        $candidateRecord['InterPreflightYawDriftDegrees'] = $interPreflightYawDrift

        $preflightNotes = New-Object System.Collections.Generic.List[string]
        $preflightNotes.Add("Primary preflight yaw delta: $(Format-Nullable $primaryYawDelta '0.000') deg")
        $preflightNotes.Add("Secondary preflight yaw delta: $(Format-Nullable $secondaryYawDelta '0.000') deg")
        $preflightNotes.Add("Inter-preflight yaw drift without input: $(Format-Nullable $interPreflightYawDrift '0.000') deg")
        $preflightNotes.Add("Inter-preflight source stable: $interPreflightSourceStable")
        if (-not $preflightPassed) {
            $preflightNotes.Add("Dual-key preflight rejected candidate: $preflightRejectedReason")
        }
        else {
            $preflightNotes.Add('Dual-key preflight passed.')
        }

        Write-LedgerEntry `
            -BaselineCapture $stimulusResult.Before `
            -CandidateResponsive $preflightPassed `
            -EvaluationMode 'dual-preflight-summary' `
            -StimulusKey "$PreflightKey+$SecondaryPreflightKey" `
            -SourceStable $interPreflightSourceStable `
            -CoordDriftMagnitude $preflightCoordMax `
            -YawDeltaDegrees $interPreflightYawDrift `
            -PitchDeltaDegrees $null `
            -CandidateRejectedReason $preflightRejectedReason `
            -Notes @($preflightNotes.ToArray())
    }

    $candidateRecord['PreflightPassed'] = $preflightPassed
    $candidateRecord['PreflightRejectedReason'] = $preflightRejectedReason

    if ($preflightPassed -and -not $SkipFullRecovery -and $recoveryRunCount -lt $FullRecoveryLimit) {
        $candidateToken = Get-CandidateToken -SourceAddress $candidate.SourceAddress -BasisForwardOffset $candidate.BasisForwardOffset
        $recoveryOutputPath = Join-Path $resolvedRecoveryOutputDirectory ("recovery-{0}.json" -f $candidateToken)
        $recoveryResult = Invoke-RecoveryCandidate -SourceAddress $candidate.SourceAddress -BasisForwardOffset $candidate.BasisForwardOffset -OutputPath $recoveryOutputPath
        $recoveryRunCount++
        $candidateRecord['Recovery'] = [pscustomobject]@{
            OutputFile = $recoveryOutputPath
            BasisRecovered = [bool](Get-OptionalPropertyValue -Object $recoveryResult.Recovery -Name 'BasisRecovered')
            CandidateResponsive = [bool](Get-OptionalPropertyValue -Object $recoveryResult.Recovery -Name 'CandidateResponsive')
            CandidateRejectedReason = [string](Get-OptionalPropertyValue -Object $recoveryResult.Recovery -Name 'CandidateRejectedReason')
            YawRecovered = [bool](Get-OptionalPropertyValue -Object $recoveryResult.Recovery -Name 'YawRecovered')
            PitchRecovered = [bool](Get-OptionalPropertyValue -Object $recoveryResult.Recovery -Name 'PitchRecovered')
            IdleConsistencyPass = [bool](Get-OptionalPropertyValue -Object $recoveryResult.Recovery -Name 'IdleConsistencyPass')
            BaselineIdleYawDeltaDegrees = Get-OptionalPropertyValue -Object $recoveryResult.Recovery -Name 'BaselineIdleYawDeltaDegrees'
            InterStimulusYawDeltaDegrees = Get-OptionalPropertyValue -Object $recoveryResult.Recovery -Name 'InterStimulusYawDeltaDegrees'
            Notes = @((Get-OptionalPropertyValue -Object $recoveryResult -Name 'Notes'))
        }

        if ($StopOnFirstRecoveredYaw -and [bool](Get-OptionalPropertyValue -Object $recoveryResult.Recovery -Name 'YawRecovered')) {
            $winningRecoveryResult = $candidateRecord['Recovery']
            $stoppedAfterRecoveredYaw = $true
            $candidateRecord['Notes'] = @(
                'Screen stopped after this candidate because full recovery produced a validated yaw winner.'
            )
            $screenResults.Add([pscustomobject]$candidateRecord)
            break
        }
    }

    $screenResults.Add([pscustomobject]$candidateRecord)
}

$responsiveCandidates = @($screenResults | Where-Object {
        [bool](Get-OptionalPropertyValue -Object $_ -Name 'PreflightPassed')
    })
$skippedCandidates = @($screenResults | Where-Object { [bool](Get-OptionalPropertyValue -Object $_ -Name 'SkippedBecauseLedger') })
$deadCandidates = @($screenResults | Where-Object {
        [string](Get-OptionalPropertyValue -Object $_ -Name 'PreflightRejectedReason') -eq 'stable_but_nonresponsive' -or
        [string](Get-OptionalPropertyValue -Object $_ -Name 'PreflightRejectedReason') -eq 'secondary_stable_but_nonresponsive'
    })

$document = [pscustomobject]@{
    Mode = 'actor-orientation-candidate-screen'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    OutputFile = $resolvedOutputFile
    LedgerFile = $resolvedLedgerFile
    HistoryFile = $resolvedHistoryFile
    RecoveryOutputDirectory = $resolvedRecoveryOutputDirectory
    ProcessName = $ProcessName
    PreflightKey = $PreflightKey
    DualKeyPreflight = [bool]$DualKeyPreflight
    SecondaryPreflightKey = $SecondaryPreflightKey
    MinimumYawResponseDegrees = $MinimumYawResponseDegrees
    MaxCoordDrift = $MaxCoordDrift
    MaxInterPreflightIdleDriftDegrees = $MaxInterPreflightIdleDriftDegrees
    FullRecoveryLimit = $FullRecoveryLimit
    SkipUiClearCheck = [bool]$SkipUiClearCheck
    RequireTargetFocus = [bool]$RequireTargetFocus
    SkipLiveInputWarning = [bool]$SkipLiveInputWarning
    StopOnFirstRecoveredYaw = [bool]$StopOnFirstRecoveredYaw
    StoppedAfterRecoveredYaw = $stoppedAfterRecoveredYaw
    WinningRecovery = $winningRecoveryResult
    CandidateSearch = $candidateSearch
    ScreenedCandidateCount = $screenResults.Count
    SkippedCandidateCount = @($skippedCandidates).Count
    ResponsiveCandidateCount = @($responsiveCandidates).Count
    DeadCandidateCount = @($deadCandidates).Count
    RecoveryRunCount = $recoveryRunCount
    Results = $screenResults.ToArray()
    Notes = @(
        $(if ($DualKeyPreflight) { 'Candidates are screened with paired trusted opposite-direction turn stimuli before any full recovery run.' } else { 'Candidates are screened with a single trusted turn stimulus before any full recovery run.' }),
        'Known stable-but-nonresponsive candidates are skipped by default using the dead-candidate ledger.',
        $(if ($DualKeyPreflight) { 'Full recovery is only attempted for candidates that react to both preflight directions, keep opposite-sign deltas, and stay stable between the two preflights.' } else { 'Full recovery is only attempted for candidates that remain stable and show a nontrivial preflight yaw delta.' }),
        $(if ($StopOnFirstRecoveredYaw) { 'Screen exits immediately after the first full recovery that proves yaw.' } else { 'Screen continues through the candidate set even after a successful recovery.' })
    )
}

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $document | ConvertTo-Json -Depth 80
[System.IO.File]::WriteAllText($resolvedOutputFile, $jsonText)
Write-ScreenHistoryEntry -Document $document

if ($Json) {
    Write-Output $jsonText
    return
}

Write-Host 'Actor orientation candidate screen'
Write-Host ("Process:                     {0}" -f $ProcessName)
Write-Host ("Ledger file:                 {0}" -f $resolvedLedgerFile)
Write-Host ("History file:                {0}" -f $resolvedHistoryFile)
Write-Host ("Recovery output dir:         {0}" -f $resolvedRecoveryOutputDirectory)
Write-Host ("Require target focus:        {0}" -f $document.RequireTargetFocus)
Write-Host ("Skip UI clear-check:         {0}" -f $document.SkipUiClearCheck)
Write-Host ("Skip live warning:           {0}" -f $document.SkipLiveInputWarning)
Write-Host ("Stop on yaw winner:          {0}" -f $document.StopOnFirstRecoveredYaw)
Write-Host ("Preflight key:               {0}" -f $PreflightKey)
if ($DualKeyPreflight) {
    Write-Host ("Secondary preflight key:     {0}" -f $SecondaryPreflightKey)
    Write-Host ("Max inter-preflight drift:   {0}" -f (Format-Nullable $MaxInterPreflightIdleDriftDegrees '0.000'))
}
Write-Host ("Screened candidates:         {0}" -f $document.ScreenedCandidateCount)
Write-Host ("Skipped by ledger:           {0}" -f $document.SkippedCandidateCount)
Write-Host ("Responsive candidates:       {0}" -f $document.ResponsiveCandidateCount)
Write-Host ("Dead candidates:             {0}" -f $document.DeadCandidateCount)
Write-Host ("Recovery runs:               {0}" -f $document.RecoveryRunCount)
Write-Host ("Stopped after yaw winner:    {0}" -f $document.StoppedAfterRecoveredYaw)

foreach ($result in @($document.Results)) {
    $stimulus = Get-OptionalPropertyValue -Object $result -Name 'Stimulus'
    $secondaryStimulus = Get-OptionalPropertyValue -Object $result -Name 'SecondaryStimulus'
    $recovery = Get-OptionalPropertyValue -Object $result -Name 'Recovery'
    Write-Host ''
    Write-Host ("[{0}] {1} @ {2}" -f $result.Rank, $result.SourceAddress, $result.BasisForwardOffset)
    Write-Host ("  type/score:                {0} / {1}" -f $result.CandidateType, $result.SearchScore)
    if ([bool]$result.SkippedBecauseLedger) {
        Write-Host ("  skipped:                   yes ({0})" -f $result.ExistingLedgerEvidence.LatestCandidateRejectedReason)
        continue
    }

    Write-Host ("  preflight yaw / coord:     {0} / {1}" -f (Format-Nullable (Get-OptionalPropertyValue -Object $stimulus -Name 'YawDeltaDegrees') '0.000'), (Format-Nullable (Get-OptionalPropertyValue -Object $stimulus -Name 'CoordDeltaMagnitude') '0.000000'))
    Write-Host ("  responsive / rejected:     {0} / {1}" -f (Get-OptionalPropertyValue -Object $stimulus -Name 'CandidateResponsive'), $(if (-not [string]::IsNullOrWhiteSpace([string](Get-OptionalPropertyValue -Object $stimulus -Name 'CandidateRejectedReason'))) { [string](Get-OptionalPropertyValue -Object $stimulus -Name 'CandidateRejectedReason') } else { 'n/a' }))
    if ($secondaryStimulus) {
        Write-Host ("  2nd preflight yaw/coord:   {0} / {1}" -f (Format-Nullable (Get-OptionalPropertyValue -Object $secondaryStimulus -Name 'YawDeltaDegrees') '0.000'), (Format-Nullable (Get-OptionalPropertyValue -Object $secondaryStimulus -Name 'CoordDeltaMagnitude') '0.000000'))
        Write-Host ("  preflight gate/rejected:   {0} / {1}" -f (Get-OptionalPropertyValue -Object $result -Name 'PreflightPassed'), $(if (-not [string]::IsNullOrWhiteSpace([string](Get-OptionalPropertyValue -Object $result -Name 'PreflightRejectedReason'))) { [string](Get-OptionalPropertyValue -Object $result -Name 'PreflightRejectedReason') } else { 'n/a' }))
        Write-Host ("  inter-preflight drift:     {0}" -f (Format-Nullable (Get-OptionalPropertyValue -Object $result -Name 'InterPreflightYawDriftDegrees') '0.000'))
    }
    if ($recovery) {
        Write-Host ("  recovery yaw / rejected:   {0} / {1}" -f (Get-OptionalPropertyValue -Object $recovery -Name 'YawRecovered'), $(if (-not [string]::IsNullOrWhiteSpace([string](Get-OptionalPropertyValue -Object $recovery -Name 'CandidateRejectedReason'))) { [string](Get-OptionalPropertyValue -Object $recovery -Name 'CandidateRejectedReason') } else { 'n/a' }))
    }
}

Write-Host ''
Write-Host ("Output file:                 {0}" -f $resolvedOutputFile)
