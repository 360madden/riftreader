function Get-RiftReaderRepoRoot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptRoot
    )

    return (Resolve-Path (Join-Path $ScriptRoot '..')).Path
}

function Get-RiftReaderProjectPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    return Join-Path $RepoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
}

function Invoke-RiftReaderJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ReaderProject,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & dotnet run --project $ReaderProject -- @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Reader command failed (`$LASTEXITCODE=$exitCode): $($output -join [Environment]::NewLine)"
    }

    $text = $output -join [Environment]::NewLine
    if ([string]::IsNullOrWhiteSpace($text)) {
        throw 'Reader command returned no JSON payload.'
    }

    return $text | ConvertFrom-Json -Depth 80
}

function Get-ActorFacingThresholds {
    return [pscustomobject]@{
        DeterminantMinimum                        = 0.98
        DeterminantMaximum                        = 1.02
        RowMagnitudeMinimum                       = 0.98
        RowMagnitudeMaximum                       = 1.02
        CrossRowDotProductMaximumAbsolute         = 0.02
        DuplicateBasisMaximumRowDelta             = 0.02
        IdleYawJitterDegrees                      = 3.0
        IdlePlanarCoordDrift                      = 0.15
        TurnYawDeltaDegrees                       = 15.0
        TurnPlanarCoordDrift                      = 0.25
        ForwardMovementDistance                   = 0.75
        ForwardAngularErrorDegrees                = 12.0
        RepeatedForwardMedianAngularErrorDegrees  = 8.0
        RepeatedForwardSingleAngularErrorDegrees  = 15.0
    }
}

function Get-OptionalPropertyValue {
    param(
        $InputObject,

        [Parameter(Mandatory = $true)]
        [string]$PropertyName
    )

    if ($null -eq $InputObject) {
        return $null
    }

    $property = $InputObject.PSObject.Properties[$PropertyName]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Convert-ToFiniteDouble {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    $doubleValue = [double]$Value
    if ([double]::IsNaN($doubleValue) -or [double]::IsInfinity($doubleValue)) {
        return $null
    }

    return $doubleValue
}

function Get-VectorMagnitude {
    param($Vector)

    if ($null -eq $Vector) {
        return $null
    }

    $x = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $Vector -PropertyName 'X')
    $y = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $Vector -PropertyName 'Y')
    $z = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $Vector -PropertyName 'Z')

    if ($null -eq $x -or $null -eq $y -or $null -eq $z) {
        return $null
    }

    return [Math]::Sqrt(($x * $x) + ($y * $y) + ($z * $z))
}

function Get-VectorDotProduct {
    param(
        $Left,
        $Right
    )

    if ($null -eq $Left -or $null -eq $Right) {
        return $null
    }

    $leftX = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $Left -PropertyName 'X')
    $leftY = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $Left -PropertyName 'Y')
    $leftZ = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $Left -PropertyName 'Z')
    $rightX = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $Right -PropertyName 'X')
    $rightY = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $Right -PropertyName 'Y')
    $rightZ = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $Right -PropertyName 'Z')

    if ($null -eq $leftX -or $null -eq $leftY -or $null -eq $leftZ -or
        $null -eq $rightX -or $null -eq $rightY -or $null -eq $rightZ) {
        return $null
    }

    return ($leftX * $rightX) + ($leftY * $rightY) + ($leftZ * $rightZ)
}

function Normalize-AngleRadians {
    param([double]$Radians)

    $normalized = $Radians
    while ($normalized -gt [Math]::PI) {
        $normalized -= (2.0 * [Math]::PI)
    }

    while ($normalized -lt -[Math]::PI) {
        $normalized += (2.0 * [Math]::PI)
    }

    return $normalized
}

function Normalize-AngleDegrees {
    param([double]$Degrees)

    $normalized = $Degrees
    while ($normalized -gt 180.0) {
        $normalized -= 360.0
    }

    while ($normalized -lt -180.0) {
        $normalized += 360.0
    }

    return $normalized
}

function Convert-RadiansToDegrees {
    param([double]$Radians)
    return $Radians * 180.0 / [Math]::PI
}

function Convert-DegreesToRadians {
    param([double]$Degrees)
    return $Degrees * [Math]::PI / 180.0
}

function Get-PlanarMagnitude {
    param(
        [double]$ValueX,
        [double]$ValueZ
    )

    return [Math]::Sqrt(($ValueX * $ValueX) + ($ValueZ * $ValueZ))
}

function Try-NormalizePlanar {
    param(
        $ValueX,
        $ValueZ
    )

    $x = Convert-ToFiniteDouble $ValueX
    $z = Convert-ToFiniteDouble $ValueZ
    if ($null -eq $x -or $null -eq $z) {
        return $null
    }

    $magnitude = Get-PlanarMagnitude -ValueX $x -ValueZ $z
    if ($magnitude -le [double]::Epsilon) {
        return $null
    }

    return [pscustomobject]@{
        X = $x / $magnitude
        Z = $z / $magnitude
    }
}

function Get-PlanarDistance {
    param(
        $LeftCoord,
        $RightCoord
    )

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

    return Get-PlanarMagnitude -ValueX ($rightX - $leftX) -ValueZ ($rightZ - $leftZ)
}

function Get-Median {
    param([double[]]$Values)

    $filtered = @($Values | Where-Object { $null -ne $_ } | Sort-Object)
    if ($filtered.Count -eq 0) {
        return $null
    }

    $middle = [int][Math]::Floor($filtered.Count / 2)
    if (($filtered.Count % 2) -eq 1) {
        return $filtered[$middle]
    }

    return ($filtered[$middle - 1] + $filtered[$middle]) / 2.0
}

function Get-MaximumValue {
    param([double[]]$Values)

    $filtered = @($Values | Where-Object { $null -ne $_ })
    if ($filtered.Count -eq 0) {
        return $null
    }

    return ($filtered | Measure-Object -Maximum).Maximum
}

function Get-SignedAngularErrorDegrees {
    param(
        [double]$PredictedHeadingRadians,
        [double]$ObservedHeadingRadians
    )

    return Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ($ObservedHeadingRadians - $PredictedHeadingRadians))
}

function Normalize-HexOffset {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }

    $trimmed = $Value.Trim()
    if ($trimmed.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        return '0x' + $trimmed.Substring(2).ToUpperInvariant()
    }

    return $trimmed.ToUpperInvariant()
}
function Resolve-ActorFacingBasisForwardOffset {
    param($ReaderOrientation)

    $directCandidates = @(
        (Get-OptionalPropertyValue -InputObject $ReaderOrientation -PropertyName 'PinnedBasisForwardOffset')
    )

    $liveSourceSample = Get-OptionalPropertyValue -InputObject $ReaderOrientation -PropertyName 'LiveSourceSample'
    $directCandidates += @(
        (Get-OptionalPropertyValue -InputObject $liveSourceSample -PropertyName 'BasisPrimaryForwardOffset')
    )

    foreach ($candidate in $directCandidates) {
        if (-not [string]::IsNullOrWhiteSpace([string]$candidate)) {
            return Normalize-HexOffset -Value ([string]$candidate)
        }
    }

    $preferredBasis = Get-OptionalPropertyValue -InputObject $ReaderOrientation -PropertyName 'PreferredBasis'
    $basisName = [string](Get-OptionalPropertyValue -InputObject $preferredBasis -PropertyName 'Name')
    if ($basisName -match '@(0x[0-9A-Fa-f]+)') {
        return Normalize-HexOffset -Value $Matches[1]
    }

    $preferredEstimate = Get-OptionalPropertyValue -InputObject $ReaderOrientation -PropertyName 'PreferredEstimate'
    $estimateName = [string](Get-OptionalPropertyValue -InputObject $preferredEstimate -PropertyName 'Name')
    if ($estimateName -match '60') {
        return '0x60'
    }

    if ($estimateName -match '94') {
        return '0x94'
    }

    return $null
}

function Get-ActorFacingBasisMetrics {
    param(
        $Basis,
        $DuplicateBasisAgreement
    )

    $forwardEstimate = Get-OptionalPropertyValue -InputObject $Basis -PropertyName 'ForwardEstimate'
    $upEstimate = Get-OptionalPropertyValue -InputObject $Basis -PropertyName 'UpEstimate'
    $rightEstimate = Get-OptionalPropertyValue -InputObject $Basis -PropertyName 'RightEstimate'
    $forwardVector = Get-OptionalPropertyValue -InputObject $Basis -PropertyName 'Forward'
    $upVector = Get-OptionalPropertyValue -InputObject $Basis -PropertyName 'Up'
    $rightVector = Get-OptionalPropertyValue -InputObject $Basis -PropertyName 'Right'

    $forwardMagnitude = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $forwardEstimate -PropertyName 'Magnitude')
    if ($null -eq $forwardMagnitude) {
        $forwardMagnitude = Get-VectorMagnitude -Vector $forwardVector
    }

    $upMagnitude = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $upEstimate -PropertyName 'Magnitude')
    if ($null -eq $upMagnitude) {
        $upMagnitude = Get-VectorMagnitude -Vector $upVector
    }

    $rightMagnitude = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $rightEstimate -PropertyName 'Magnitude')
    if ($null -eq $rightMagnitude) {
        $rightMagnitude = Get-VectorMagnitude -Vector $rightVector
    }

    $forwardDotUp = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $Basis -PropertyName 'ForwardDotUp')
    if ($null -eq $forwardDotUp) {
        $forwardDotUp = Get-VectorDotProduct -Left $forwardVector -Right $upVector
    }

    $forwardDotRight = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $Basis -PropertyName 'ForwardDotRight')
    if ($null -eq $forwardDotRight) {
        $forwardDotRight = Get-VectorDotProduct -Left $forwardVector -Right $rightVector
    }

    $upDotRight = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $Basis -PropertyName 'UpDotRight')
    if ($null -eq $upDotRight) {
        $upDotRight = Get-VectorDotProduct -Left $upVector -Right $rightVector
    }

    return [pscustomobject]@{
        Determinant                   = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $Basis -PropertyName 'Determinant')
        ForwardMagnitude              = $forwardMagnitude
        UpMagnitude                   = $upMagnitude
        RightMagnitude                = $rightMagnitude
        ForwardDotUp                  = $forwardDotUp
        ForwardDotRight               = $forwardDotRight
        UpDotRight                    = $upDotRight
        DuplicateBasisMaximumRowDelta = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $DuplicateBasisAgreement -PropertyName 'MaxRowDeltaMagnitude')
    }
}

function Test-ActorFacingIntegrity {
    param(
        [Parameter(Mandatory = $true)]
        $Metrics,

        $Thresholds = (Get-ActorFacingThresholds)
    )

    $notes = New-Object System.Collections.Generic.List[string]

    $determinantPass =
        $null -ne $Metrics.Determinant -and
        $Metrics.Determinant -ge $Thresholds.DeterminantMinimum -and
        $Metrics.Determinant -le $Thresholds.DeterminantMaximum
    if (-not $determinantPass) {
        $notes.Add('determinant-out-of-range')
    }

    $rowMagnitudesPass =
        $null -ne $Metrics.ForwardMagnitude -and $Metrics.ForwardMagnitude -ge $Thresholds.RowMagnitudeMinimum -and $Metrics.ForwardMagnitude -le $Thresholds.RowMagnitudeMaximum -and
        $null -ne $Metrics.UpMagnitude -and $Metrics.UpMagnitude -ge $Thresholds.RowMagnitudeMinimum -and $Metrics.UpMagnitude -le $Thresholds.RowMagnitudeMaximum -and
        $null -ne $Metrics.RightMagnitude -and $Metrics.RightMagnitude -ge $Thresholds.RowMagnitudeMinimum -and $Metrics.RightMagnitude -le $Thresholds.RowMagnitudeMaximum
    if (-not $rowMagnitudesPass) {
        $notes.Add('row-magnitude-out-of-range')
    }

    $crossRowDotProductsPass =
        $null -ne $Metrics.ForwardDotUp -and [Math]::Abs($Metrics.ForwardDotUp) -le $Thresholds.CrossRowDotProductMaximumAbsolute -and
        $null -ne $Metrics.ForwardDotRight -and [Math]::Abs($Metrics.ForwardDotRight) -le $Thresholds.CrossRowDotProductMaximumAbsolute -and
        $null -ne $Metrics.UpDotRight -and [Math]::Abs($Metrics.UpDotRight) -le $Thresholds.CrossRowDotProductMaximumAbsolute
    if (-not $crossRowDotProductsPass) {
        $notes.Add('cross-row-dot-out-of-range')
    }

    $duplicateBasisPass =
        $null -eq $Metrics.DuplicateBasisMaximumRowDelta -or
        $Metrics.DuplicateBasisMaximumRowDelta -le $Thresholds.DuplicateBasisMaximumRowDelta
    if (-not $duplicateBasisPass) {
        $notes.Add('duplicate-basis-delta-too-large')
    }

    $pass = $determinantPass -and $rowMagnitudesPass -and $crossRowDotProductsPass -and $duplicateBasisPass
    if ($pass) {
        $notes.Add('integrity-pass')
    }

    return [pscustomobject]@{
        DeterminantPass         = $determinantPass
        RowMagnitudesPass       = $rowMagnitudesPass
        CrossRowDotProductsPass = $crossRowDotProductsPass
        DuplicateBasisPass      = $duplicateBasisPass
        Pass                    = $pass
        Notes                   = $notes
    }
}

function Classify-ActorFacingFailureShape {
    param(
        $SignedAngularErrorDegrees,
        [double]$MovementDistance,
        [bool]$IntegrityPass,
        [bool]$TurnResponsive,
        $Thresholds = (Get-ActorFacingThresholds)
    )

    if (-not $IntegrityPass) {
        return 'integrity-instability'
    }

    if ($null -eq $SignedAngularErrorDegrees -or $MovementDistance -lt $Thresholds.ForwardMovementDistance) {
        return 'insufficient-movement'
    }

    $absoluteError = [Math]::Abs((Normalize-AngleDegrees -Degrees ([double]$SignedAngularErrorDegrees)))

    if ([Math]::Abs($absoluteError - 180.0) -le 25.0) {
        return 'sign-inverted'
    }

    if ([Math]::Abs($absoluteError - 90.0) -le 20.0) {
        return 'wrong-axis'
    }

    if ($TurnResponsive -and $absoluteError -gt $Thresholds.ForwardAngularErrorDegrees) {
        return 'locomotion-mismatch'
    }

    return 'none'
}

function Resolve-ActorFacingStatus {
    param(
        $ReaderOrientation,
        $IntegrityResult
    )

    $joinedNotes = @()
    $joinedNotes += @((Get-OptionalPropertyValue -InputObject $ReaderOrientation -PropertyName 'Notes'))
    $joinedText = ($joinedNotes | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) }) -join ' '
    $joinedText = $joinedText.ToLowerInvariant()

    if ($joinedText.Contains('stale') -or $joinedText.Contains('historical')) {
        return 'stale'
    }

    if ($IntegrityResult.Pass) {
        return 'candidate'
    }

    return 'rejected'
}

function Resolve-ActorFacingOperationalStatus {
    param(
        $ReaderOrientation,
        $IntegrityResult
    )

    $resolutionMode = [string](Get-OptionalPropertyValue -InputObject $ReaderOrientation -PropertyName 'ResolutionMode')
    if ($resolutionMode -eq 'behavior-backed-lead') {
        return 'behavior-backed-lead'
    }

    return Resolve-ActorFacingStatus -ReaderOrientation $ReaderOrientation -IntegrityResult $IntegrityResult
}

function ConvertTo-ActorFacingSample {
    param(
        [Parameter(Mandatory = $true)]
        $CaptureDocument
    )

    $readerOrientation = Get-OptionalPropertyValue -InputObject $CaptureDocument -PropertyName 'ReaderOrientation'
    if ($null -eq $readerOrientation) {
        throw 'The actor-orientation capture document did not contain ReaderOrientation.'
    }

    $preferredEstimate = Get-OptionalPropertyValue -InputObject $readerOrientation -PropertyName 'PreferredEstimate'
    $preferredBasis = Get-OptionalPropertyValue -InputObject $readerOrientation -PropertyName 'PreferredBasis'
    $duplicateBasisAgreement = Get-OptionalPropertyValue -InputObject $readerOrientation -PropertyName 'DuplicateBasisAgreement'
    $forwardVector = Get-OptionalPropertyValue -InputObject $preferredEstimate -PropertyName 'Vector'
    $planarForward = $null

    if ($null -ne $forwardVector) {
        $planarForward = Try-NormalizePlanar `
            -ValueX (Get-OptionalPropertyValue -InputObject $forwardVector -PropertyName 'X') `
            -ValueZ (Get-OptionalPropertyValue -InputObject $forwardVector -PropertyName 'Z')
    }

    $metrics = Get-ActorFacingBasisMetrics -Basis $preferredBasis -DuplicateBasisAgreement $duplicateBasisAgreement
    $integrity = Test-ActorFacingIntegrity -Metrics $metrics
    $sourceName = 'selected-source-basis-forward-row'
    $resolutionMode = [string](Get-OptionalPropertyValue -InputObject $readerOrientation -PropertyName 'ResolutionMode')
    if ([string]::IsNullOrWhiteSpace($resolutionMode)) {
        $resolutionMode = $sourceName
    }
    $isBehaviorBackedLead = $resolutionMode -eq 'behavior-backed-lead'

    $notes = New-Object System.Collections.Generic.List[string]
    $notes.Add('Navigation-facing derivation uses the planar X/Z projection of the actor forward row.')
    if ($isBehaviorBackedLead) {
        $notes.Add('This capture is currently pinned to the repo-preferred behavior-backed lead.')
    }
    foreach ($note in @((Get-OptionalPropertyValue -InputObject $readerOrientation -PropertyName 'Notes'))) {
        if (-not [string]::IsNullOrWhiteSpace([string]$note)) {
            $notes.Add([string]$note)
        }
    }

    return [pscustomobject]@{
        SourceName                     = $sourceName
        SourceAddress                  = Get-OptionalPropertyValue -InputObject $readerOrientation -PropertyName 'SelectedSourceAddress'
        SelectedEntryAddress           = Get-OptionalPropertyValue -InputObject $readerOrientation -PropertyName 'SelectedEntryAddress'
        SelectedEntryIndex             = Get-OptionalPropertyValue -InputObject $readerOrientation -PropertyName 'SelectedEntryIndex'
        ForwardVector                  = $forwardVector
        PlanarForward                  = if ($null -ne $planarForward) { [pscustomobject]@{ X = $planarForward.X; Z = $planarForward.Z } } else { $null }
        YawRadians                     = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $preferredEstimate -PropertyName 'YawRadians')
        YawDegrees                     = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $preferredEstimate -PropertyName 'YawDegrees')
        PitchRadians                   = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $preferredEstimate -PropertyName 'PitchRadians')
        PitchDegrees                   = Convert-ToFiniteDouble (Get-OptionalPropertyValue -InputObject $preferredEstimate -PropertyName 'PitchDegrees')
        Determinant                    = $metrics.Determinant
        RowMagnitudes                  = [pscustomobject]@{
            Forward = $metrics.ForwardMagnitude
            Up      = $metrics.UpMagnitude
            Right   = $metrics.RightMagnitude
        }
        RowDotProducts                 = [pscustomobject]@{
            ForwardUp    = $metrics.ForwardDotUp
            ForwardRight = $metrics.ForwardDotRight
            UpRight      = $metrics.UpDotRight
        }
        DuplicateBasisDelta            = $metrics.DuplicateBasisMaximumRowDelta
        ResolutionMode                 = $resolutionMode
        ResolutionNotes                = Get-OptionalPropertyValue -InputObject $readerOrientation -PropertyName 'ResolutionNotes'
        BasisForwardOffset             = Resolve-ActorFacingBasisForwardOffset -ReaderOrientation $readerOrientation
        PreferredBasisName             = Get-OptionalPropertyValue -InputObject $preferredBasis -PropertyName 'Name'
        ArtifactFile                   = Get-OptionalPropertyValue -InputObject $readerOrientation -PropertyName 'ArtifactFile'
        ArtifactGeneratedAtUtc         = Get-OptionalPropertyValue -InputObject $readerOrientation -PropertyName 'ArtifactGeneratedAtUtc'
        SnapshotFile                   = Get-OptionalPropertyValue -InputObject $readerOrientation -PropertyName 'SnapshotFile'
        OrientationCandidateLedgerFile = Get-OptionalPropertyValue -InputObject $readerOrientation -PropertyName 'OrientationCandidateLedgerFile'
        PlayerCoord                    = Get-OptionalPropertyValue -InputObject $readerOrientation -PropertyName 'PlayerCoord'
        Status                         = Resolve-ActorFacingStatus -ReaderOrientation $readerOrientation -IntegrityResult $integrity
        OperationalStatus              = Resolve-ActorFacingOperationalStatus -ReaderOrientation $readerOrientation -IntegrityResult $integrity
        PreferredLead                  = $isBehaviorBackedLead
        Integrity                      = $integrity
        Notes                          = $notes
    }
}

function Get-ValidationHistoryEntries {
    param(
        [Parameter(Mandatory = $true)]
        [string]$HistoryFile
    )

    if (-not (Test-Path -LiteralPath $HistoryFile)) {
        return @()
    }

    $entries = New-Object System.Collections.Generic.List[object]
    foreach ($line in [System.IO.File]::ReadLines($HistoryFile)) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $entries.Add(($line | ConvertFrom-Json -Depth 80))
    }

    return $entries
}

function Test-SourceTurnResponsive {
    param(
        $HistoryEntries,
        [string]$SourceAddress,
        [string]$BasisForwardOffset
    )

    $matchingEntries = @($HistoryEntries | Where-Object {
            (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'StimulusType') -in @('turn-left', 'turn-right') -and
            (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'SourceAddress') -eq $SourceAddress -and
            (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'BasisForwardOffset') -eq $BasisForwardOffset -and
            (Get-OptionalPropertyValue -InputObject $_ -PropertyName 'Verdict') -eq 'pass'
        })

    return $matchingEntries.Count -gt 0
}



