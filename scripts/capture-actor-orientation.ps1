[CmdletBinding()]
param(
    [switch]$Json,
    [string]$Label,
    [switch]$RefreshOwnerComponents,
    [switch]$RefreshReaderBridge,
    [switch]$NoAhkFallback,
    [string]$ProcessName = 'rift_x64',
    [string]$BehaviorBackedLeadFile = (Join-Path $PSScriptRoot 'actor-facing-behavior-backed-lead.json'),
    [switch]$IgnoreBehaviorBackedLead,
    [string]$OwnerComponentsFile = (Join-Path $PSScriptRoot 'captures\player-owner-components.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\player-actor-orientation.json'),
    [string]$PreviousFile = (Join-Path $PSScriptRoot 'captures\player-actor-orientation.previous.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$ownerComponentScript = Join-Path $PSScriptRoot 'capture-player-owner-components.ps1'
$refreshReaderBridgeScript = Join-Path $PSScriptRoot 'refresh-readerbridge-export.ps1'
$coordTolerance = 0.75

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

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 30
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

function Get-OptionalPropertyValue {
    param(
        $Object,
        [Parameter(Mandatory = $true)][string]$Name
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

function Format-Vector {
    param($Vector)

    if ($null -eq $Vector -or $null -eq $Vector.X -or $null -eq $Vector.Y -or $null -eq $Vector.Z) {
        return 'n/a'
    }

    return '{0}, {1}, {2}' -f
        (Format-Nullable -Value $Vector.X -Format '0.00000'),
        (Format-Nullable -Value $Vector.Y -Format '0.00000'),
        (Format-Nullable -Value $Vector.Z -Format '0.00000')
}

function Get-VectorDeltaMagnitude {
    param(
        $CurrentVector,
        $PreviousVector
    )

    if ($null -eq $CurrentVector -or $null -eq $PreviousVector) {
        return $null
    }

    if ($null -eq $CurrentVector.X -or $null -eq $CurrentVector.Y -or $null -eq $CurrentVector.Z) {
        return $null
    }

    if ($null -eq $PreviousVector.X -or $null -eq $PreviousVector.Y -or $null -eq $PreviousVector.Z) {
        return $null
    }

    $dx = [double]$CurrentVector.X - [double]$PreviousVector.X
    $dy = [double]$CurrentVector.Y - [double]$PreviousVector.Y
    $dz = [double]$CurrentVector.Z - [double]$PreviousVector.Z

    return [Math]::Sqrt(($dx * $dx) + ($dy * $dy) + ($dz * $dz))
}

function Get-CoordDeltaMagnitude {
    param(
        $CurrentCoord,
        $PreviousCoord
    )

    if ($null -eq $CurrentCoord -or $null -eq $PreviousCoord) {
        return $null
    }

    if ($null -eq $CurrentCoord.X -or $null -eq $CurrentCoord.Y -or $null -eq $CurrentCoord.Z) {
        return $null
    }

    if ($null -eq $PreviousCoord.X -or $null -eq $PreviousCoord.Y -or $null -eq $PreviousCoord.Z) {
        return $null
    }

    $dx = [double]$CurrentCoord.X - [double]$PreviousCoord.X
    $dy = [double]$CurrentCoord.Y - [double]$PreviousCoord.Y
    $dz = [double]$CurrentCoord.Z - [double]$PreviousCoord.Z

    return [Math]::Sqrt(($dx * $dx) + ($dy * $dy) + ($dz * $dz))
}

function Get-PreviousCaptureDelta {
    param(
        $CurrentCapture,
        $PreviousCapture,
        [string]$PreviousPath
    )

    if ($null -eq $PreviousCapture) {
        return $null
    }

    $currentPreferred = $CurrentCapture.ReaderOrientation.PreferredEstimate
    $previousPreferred = $PreviousCapture.ReaderOrientation.PreferredEstimate

    $yawDeltaDegrees = $null
    if ($currentPreferred -and $previousPreferred -and $null -ne $currentPreferred.YawRadians -and $null -ne $previousPreferred.YawRadians) {
        $yawDeltaDegrees = Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ([double]$currentPreferred.YawRadians - [double]$previousPreferred.YawRadians))
    }

    $pitchDeltaDegrees = $null
    if ($currentPreferred -and $previousPreferred -and $null -ne $currentPreferred.PitchRadians -and $null -ne $previousPreferred.PitchRadians) {
        $pitchDeltaDegrees = Convert-RadiansToDegrees -Radians (Normalize-AngleRadians -Radians ([double]$currentPreferred.PitchRadians - [double]$previousPreferred.PitchRadians))
    }

    return [pscustomobject]@{
        PreviousFile = $PreviousPath
        PreviousGeneratedAtUtc = $PreviousCapture.GeneratedAtUtc
        PreferredYawDeltaDegrees = $yawDeltaDegrees
        PreferredPitchDeltaDegrees = $pitchDeltaDegrees
        VectorDeltaMagnitude = Get-VectorDeltaMagnitude -CurrentVector $currentPreferred.Vector -PreviousVector $previousPreferred.Vector
        CoordDeltaMagnitude = Get-CoordDeltaMagnitude -CurrentCoord $CurrentCapture.ReaderOrientation.PlayerCoord -PreviousCoord $PreviousCapture.ReaderOrientation.PlayerCoord
    }
}

function Write-ActorOrientationText {
    param($Document)

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("Actor orientation capture")
    $lines.Add("Output file:                 $($Document.OutputFile)")
    $lines.Add("Generated (UTC):             $($Document.GeneratedAtUtc)")
    $lines.Add("Label:                       $(if ([string]::IsNullOrWhiteSpace([string]$Document.Label)) { 'n/a' } else { [string]$Document.Label })")
    $lines.Add("Artifact file:               $($Document.ReaderOrientation.ArtifactFile)")
    $lines.Add("Artifact generated (UTC):    $($Document.ReaderOrientation.ArtifactGeneratedAtUtc)")
    $lines.Add("Snapshot file:               $(if ($Document.ReaderOrientation.SnapshotFile) { $Document.ReaderOrientation.SnapshotFile } else { 'n/a' })")
    $lines.Add("Player:                      $(if ($Document.ReaderOrientation.PlayerName) { $Document.ReaderOrientation.PlayerName } else { 'n/a' })")
    $lines.Add("Player coords:               $(Format-Vector $Document.ReaderOrientation.PlayerCoord)")
    $lines.Add("Selected source:             $($Document.ReaderOrientation.SelectedSourceAddress)")
    if ($Document.ReaderOrientation.ResolutionMode) {
        $lines.Add("Resolution mode:             $($Document.ReaderOrientation.ResolutionMode)")
    }
    if ($Document.ReaderOrientation.BasisForwardOffset) {
        $lines.Add("Basis forward offset:        $($Document.ReaderOrientation.BasisForwardOffset)")
    }
    $lines.Add("Selected entry:              index $($Document.ReaderOrientation.SelectedEntryIndex) | $($Document.ReaderOrientation.SelectedEntryAddress)")
    $lines.Add("Preferred vector:            $(Format-Vector $Document.ReaderOrientation.PreferredEstimate.Vector)")
    $lines.Add("Actor yaw/pitch (rad):       $(Format-Nullable $Document.ReaderOrientation.PreferredEstimate.YawRadians '0.000000') / $(Format-Nullable $Document.ReaderOrientation.PreferredEstimate.PitchRadians '0.000000')")
    $lines.Add("Actor yaw/pitch (deg):       $(Format-Nullable $Document.ReaderOrientation.PreferredEstimate.YawDegrees '0.000') / $(Format-Nullable $Document.ReaderOrientation.PreferredEstimate.PitchDegrees '0.000')")

    if ($Document.ReaderOrientation.PreferredBasis) {
        $basis = $Document.ReaderOrientation.PreferredBasis
        $lines.Add("Preferred basis:             $($basis.Name) | det $(Format-Nullable $basis.Determinant '0.000000') | orthonormal $($basis.IsOrthonormal)")
        $lines.Add("Basis forward/up/right:      $(Format-Vector $basis.Forward) | $(Format-Vector $basis.Up) | $(Format-Vector $basis.Right)")
    }

    if ($Document.ReaderOrientation.DuplicateBasisAgreement) {
        $agreement = $Document.ReaderOrientation.DuplicateBasisAgreement
        $lines.Add("Basis duplicate delta:       forward $(Format-Nullable $agreement.ForwardDeltaMagnitude '0.000000') | up $(Format-Nullable $agreement.UpDeltaMagnitude '0.000000') | right $(Format-Nullable $agreement.RightDeltaMagnitude '0.000000') | max $(Format-Nullable $agreement.MaxRowDeltaMagnitude '0.000000')")
    }

    if ($Document.ChangeFromPrevious) {
        $lines.Add("Prev capture:                $($Document.ChangeFromPrevious.PreviousFile)")
        $lines.Add("Prev yaw/pitch delta (deg):  $(Format-Nullable $Document.ChangeFromPrevious.PreferredYawDeltaDegrees '0.000') / $(Format-Nullable $Document.ChangeFromPrevious.PreferredPitchDeltaDegrees '0.000')")
        $lines.Add("Prev vector delta:           $(Format-Nullable $Document.ChangeFromPrevious.VectorDeltaMagnitude '0.000000')")
        $lines.Add("Prev coord delta:            $(Format-Nullable $Document.ChangeFromPrevious.CoordDeltaMagnitude '0.000000')")
    }

    if ($Document.ReaderOrientation.Notes -and $Document.ReaderOrientation.Notes.Count -gt 0) {
        $lines.Add("Orientation notes:           $([string]::Join('; ', $Document.ReaderOrientation.Notes))")
    }

    if ($Document.Notes -and $Document.Notes.Count -gt 0) {
        $lines.Add("Capture notes:               $([string]::Join('; ', $Document.Notes))")
    }

    return [string]::Join([Environment]::NewLine, $lines)
}

function Parse-HexUInt64 {
    param([Parameter(Mandatory = $true)][string]$Value)

    $normalized = $Value.Trim()
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [UInt64]::Parse($normalized, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Convert-HexToByteArray {
    param([Parameter(Mandatory = $true)][string]$Hex)

    $normalized = ($Hex -replace '\s+', '').Trim()
    $bytes = New-Object byte[] ($normalized.Length / 2)
    for ($index = 0; $index -lt $bytes.Length; $index++) {
        $bytes[$index] = [Convert]::ToByte($normalized.Substring($index * 2, 2), 16)
    }

    return $bytes
}

function Read-SingleAt {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][int]$Offset
    )

    if (($Offset + 4) -gt $Bytes.Length) {
        throw "Offset 0x{0:X} exceeds byte buffer length {1}." -f $Offset, $Bytes.Length
    }

    return [BitConverter]::ToSingle($Bytes, $Offset)
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

function Read-TripletAt {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][int]$Offset
    )

    return [pscustomobject]@{
        X = Convert-ToFiniteDouble -Value (Read-SingleAt -Bytes $Bytes -Offset $Offset)
        Y = Convert-ToFiniteDouble -Value (Read-SingleAt -Bytes $Bytes -Offset ($Offset + 4))
        Z = Convert-ToFiniteDouble -Value (Read-SingleAt -Bytes $Bytes -Offset ($Offset + 8))
    }
}

function New-VectorEstimate {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Vector
    )

    if ($null -eq $Vector -or $null -eq $Vector.X -or $null -eq $Vector.Y -or $null -eq $Vector.Z) {
        return [pscustomobject]@{
            Name = $Name
            Vector = $Vector
            YawRadians = $null
            YawDegrees = $null
            PitchRadians = $null
            PitchDegrees = $null
            Magnitude = $null
        }
    }

    $x = [double]$Vector.X
    $y = [double]$Vector.Y
    $z = [double]$Vector.Z
    $magnitude = [Math]::Sqrt(($x * $x) + ($y * $y) + ($z * $z))

    if ($magnitude -le [double]::Epsilon) {
        return [pscustomobject]@{
            Name = $Name
            Vector = $Vector
            YawRadians = $null
            YawDegrees = $null
            PitchRadians = $null
            PitchDegrees = $null
            Magnitude = $magnitude
        }
    }

    $yawRadians = [Math]::Atan2($z, $x)
    $pitchRadians = [Math]::Atan2($y, [Math]::Sqrt(($x * $x) + ($z * $z)))

    return [pscustomobject]@{
        Name = $Name
        Vector = $Vector
        YawRadians = $yawRadians
        YawDegrees = Convert-RadiansToDegrees -Radians $yawRadians
        PitchRadians = $pitchRadians
        PitchDegrees = Convert-RadiansToDegrees -Radians $pitchRadians
        Magnitude = $magnitude
    }
}

function Get-DotProduct {
    param(
        $Left,
        $Right
    )

    if ($null -eq $Left -or $null -eq $Right) {
        return $null
    }

    if ($null -eq $Left.X -or $null -eq $Left.Y -or $null -eq $Left.Z) {
        return $null
    }

    if ($null -eq $Right.X -or $null -eq $Right.Y -or $null -eq $Right.Z) {
        return $null
    }

    return (([double]$Left.X * [double]$Right.X) +
        ([double]$Left.Y * [double]$Right.Y) +
        ([double]$Left.Z * [double]$Right.Z))
}

function Get-CrossProduct {
    param(
        $Left,
        $Right
    )

    if ($null -eq $Left -or $null -eq $Right) {
        return $null
    }

    if ($null -eq $Left.X -or $null -eq $Left.Y -or $null -eq $Left.Z) {
        return $null
    }

    if ($null -eq $Right.X -or $null -eq $Right.Y -or $null -eq $Right.Z) {
        return $null
    }

    return [pscustomobject]@{
        X = (([double]$Left.Y * [double]$Right.Z) - ([double]$Left.Z * [double]$Right.Y))
        Y = (([double]$Left.Z * [double]$Right.X) - ([double]$Left.X * [double]$Right.Z))
        Z = (([double]$Left.X * [double]$Right.Y) - ([double]$Left.Y * [double]$Right.X))
    }
}

function New-BasisMatrixEstimate {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Forward,
        [Parameter(Mandatory = $true)]$Up,
        [Parameter(Mandatory = $true)]$Right
    )

    $forwardEstimate = New-VectorEstimate -Name ('{0}.Forward' -f $Name) -Vector $Forward
    $upEstimate = New-VectorEstimate -Name ('{0}.Up' -f $Name) -Vector $Up
    $rightEstimate = New-VectorEstimate -Name ('{0}.Right' -f $Name) -Vector $Right

    $forwardDotUp = Get-DotProduct -Left $Forward -Right $Up
    $forwardDotRight = Get-DotProduct -Left $Forward -Right $Right
    $upDotRight = Get-DotProduct -Left $Up -Right $Right
    $cross = Get-CrossProduct -Left $Forward -Right $Up
    $determinant = if ($null -ne $cross) { Get-DotProduct -Left $cross -Right $Right } else { $null }

    $isOrthonormal = $false
    if ($forwardEstimate.Magnitude -and $upEstimate.Magnitude -and $rightEstimate.Magnitude -and
        $null -ne $forwardDotUp -and $null -ne $forwardDotRight -and $null -ne $upDotRight -and $null -ne $determinant) {
        $isOrthonormal =
            ([Math]::Abs([double]$forwardEstimate.Magnitude - 1.0) -le 0.02) -and
            ([Math]::Abs([double]$upEstimate.Magnitude - 1.0) -le 0.02) -and
            ([Math]::Abs([double]$rightEstimate.Magnitude - 1.0) -le 0.02) -and
            ([Math]::Abs([double]$forwardDotUp) -le 0.02) -and
            ([Math]::Abs([double]$forwardDotRight) -le 0.02) -and
            ([Math]::Abs([double]$upDotRight) -le 0.02) -and
            ([Math]::Abs([Math]::Abs([double]$determinant) - 1.0) -le 0.02)
    }

    return [pscustomobject]@{
        Name = $Name
        Forward = $Forward
        Up = $Up
        Right = $Right
        ForwardEstimate = $forwardEstimate
        UpEstimate = $upEstimate
        RightEstimate = $rightEstimate
        ForwardDotUp = $forwardDotUp
        ForwardDotRight = $forwardDotRight
        UpDotRight = $upDotRight
        Determinant = $determinant
        IsOrthonormal = $isOrthonormal
    }
}

function Get-BasisDuplicateAgreement {
    param(
        $PrimaryBasis,
        $DuplicateBasis
    )

    if ($null -eq $PrimaryBasis -or $null -eq $DuplicateBasis) {
        return $null
    }

    $forwardDelta = Get-VectorDeltaMagnitude -CurrentVector $PrimaryBasis.Forward -PreviousVector $DuplicateBasis.Forward
    $upDelta = Get-VectorDeltaMagnitude -CurrentVector $PrimaryBasis.Up -PreviousVector $DuplicateBasis.Up
    $rightDelta = Get-VectorDeltaMagnitude -CurrentVector $PrimaryBasis.Right -PreviousVector $DuplicateBasis.Right

    $maxRowDelta = $null
    $candidateValues = @($forwardDelta, $upDelta, $rightDelta) | Where-Object { $null -ne $_ }
    if ($candidateValues.Count -gt 0) {
        $maxRowDelta = ($candidateValues | Measure-Object -Maximum).Maximum
    }

    return [pscustomobject]@{
        ForwardDeltaMagnitude = $forwardDelta
        UpDeltaMagnitude = $upDelta
        RightDeltaMagnitude = $rightDelta
        MaxRowDeltaMagnitude = $maxRowDelta
    }
}

function Convert-HexOffsetToInt32 {
    param([Parameter(Mandatory = $true)][string]$Value)

    return [int](Parse-HexUInt64 -Value $Value)
}

function Get-BasisMatrixEstimateAtOffset {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][int]$ForwardOffset
    )

    $basisName = ('Basis@0x{0:X}' -f $ForwardOffset)
    return New-BasisMatrixEstimate `
        -Name $basisName `
        -Forward (Read-TripletAt -Bytes $Bytes -Offset $ForwardOffset) `
        -Up (Read-TripletAt -Bytes $Bytes -Offset ($ForwardOffset + 0x0C)) `
        -Right (Read-TripletAt -Bytes $Bytes -Offset ($ForwardOffset + 0x18))
}

function Test-MeaningfulBasisCandidate {
    param($Basis)

    if ($null -eq $Basis -or -not $Basis.IsOrthonormal) {
        return $false
    }

    if ($null -eq $Basis.ForwardEstimate -or $null -eq $Basis.ForwardEstimate.Magnitude) {
        return $false
    }

    $magnitude = [double]$Basis.ForwardEstimate.Magnitude
    return ($magnitude -ge 0.85) -and ($magnitude -le 1.15)
}

function Try-ParseDateTimeOffsetValue {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    if ($Value -is [DateTimeOffset]) {
        return $Value.ToUniversalTime()
    }

    if ($Value -is [DateTime]) {
        return ([DateTimeOffset]$Value).ToUniversalTime()
    }

    $stringValue = [string]$Value
    if ([string]::IsNullOrWhiteSpace($stringValue)) {
        return $null
    }

    $parsed = [DateTimeOffset]::MinValue
    if ([DateTimeOffset]::TryParse($stringValue, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::AssumeUniversal, [ref]$parsed)) {
        return $parsed.ToUniversalTime()
    }

    return $null
}

function Get-TargetProcessMetadata {
    param([Parameter(Mandatory = $true)][string]$Name)

    $process = Get-Process -Name $Name -ErrorAction Stop |
        Where-Object { $_.MainWindowHandle -ne 0 } |
        Sort-Object StartTime |
        Select-Object -First 1

    if ($null -eq $process) {
        throw "No process named '$Name' with a main window was found."
    }

    return [pscustomobject]@{
        ProcessId = $process.Id
        ProcessName = $process.ProcessName
        StartTimeUtc = $process.StartTime.ToUniversalTime()
        MainWindowTitle = $process.MainWindowTitle
    }
}

function Test-BehaviorBackedLeadApplicability {
    param(
        $Lead,
        $ProcessMetadata
    )

    if ($null -eq $Lead -or $null -eq $ProcessMetadata) {
        return [pscustomobject]@{
            IsValid = $true
            Reason = $null
        }
    }

    if (-not [string]::IsNullOrWhiteSpace([string]$Lead.ProcessName) -and
        -not [string]::Equals([string]$Lead.ProcessName, [string]$ProcessMetadata.ProcessName, [System.StringComparison]::OrdinalIgnoreCase)) {
        return [pscustomobject]@{
            IsValid = $false
            Reason = ("Behavior-backed lead targets process '{0}', but the live process is '{1}'." -f $Lead.ProcessName, $ProcessMetadata.ProcessName)
        }
    }

    $leadTimestamp = Try-ParseDateTimeOffsetValue -Value $Lead.ValidatedAtUtc
    if ($null -eq $leadTimestamp) {
        $leadTimestamp = Try-ParseDateTimeOffsetValue -Value $Lead.GeneratedAtUtc
    }

    if ($null -ne $leadTimestamp -and $leadTimestamp.UtcDateTime -lt $ProcessMetadata.StartTimeUtc.AddSeconds(-1)) {
        return [pscustomobject]@{
            IsValid = $false
            Reason = ("Behavior-backed lead '{0}' is stale for live PID {1}: lead timestamp {2} predates process start {3}." -f `
                $resolvedBehaviorBackedLeadFile, `
                $ProcessMetadata.ProcessId, `
                $leadTimestamp.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture), `
                $ProcessMetadata.StartTimeUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture))
        }
    }

    return [pscustomobject]@{
        IsValid = $true
        Reason = $null
    }
}

function Load-BehaviorBackedLead {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    $json = Get-Content -LiteralPath $Path -Raw
    if ([string]::IsNullOrWhiteSpace($json)) {
        throw "Behavior-backed lead file '$Path' is empty."
    }

    $document = $json | Microsoft.PowerShell.Utility\ConvertFrom-Json -Depth 20
    $sourceAddress = [string](Get-OptionalPropertyValue -Object $document -Name 'SourceAddress')
    $basisForwardOffset = [string](Get-OptionalPropertyValue -Object $document -Name 'BasisForwardOffset')

    if ([string]::IsNullOrWhiteSpace($sourceAddress)) {
        throw "Behavior-backed lead file '$Path' does not expose SourceAddress."
    }

    if ([string]::IsNullOrWhiteSpace($basisForwardOffset)) {
        throw "Behavior-backed lead file '$Path' does not expose BasisForwardOffset."
    }

    return [pscustomobject]@{
        SourceAddress = $sourceAddress
        BasisForwardOffset = $basisForwardOffset
        BasisDuplicateForwardOffset = [string](Get-OptionalPropertyValue -Object $document -Name 'BasisDuplicateForwardOffset')
        ProcessName = [string](Get-OptionalPropertyValue -Object $document -Name 'ProcessName')
        GeneratedAtUtc = Get-OptionalPropertyValue -Object $document -Name 'GeneratedAtUtc'
        ValidatedAtUtc = Get-OptionalPropertyValue -Object $document -Name 'ValidatedAtUtc'
        Status = [string](Get-OptionalPropertyValue -Object $document -Name 'Status')
        OperationalStatus = [string](Get-OptionalPropertyValue -Object $document -Name 'OperationalStatus')
        PreferredLead = [bool](Get-OptionalPropertyValue -Object $document -Name 'PreferredLead')
        SolvedActorFacing = [bool](Get-OptionalPropertyValue -Object $document -Name 'SolvedActorFacing')
        CanonicalActorYaw = [bool](Get-OptionalPropertyValue -Object $document -Name 'CanonicalActorYaw')
        Notes = @((Get-OptionalPropertyValue -Object $document -Name 'Notes'))
    }
}

function Get-ReaderBridgePlayerMetadata {
    $snapshot = Invoke-ReaderJson -Arguments @('--readerbridge-snapshot', '--json')
    $current = Get-OptionalPropertyValue -Object $snapshot -Name 'Current'
    $player = Get-OptionalPropertyValue -Object $current -Name 'Player'

    return [pscustomobject]@{
        SnapshotFile = [string](Get-OptionalPropertyValue -Object $snapshot -Name 'SourceFile')
        SnapshotLoadedAtUtc = [string](Get-OptionalPropertyValue -Object $snapshot -Name 'LoadedAtUtc')
        PlayerName = [string](Get-OptionalPropertyValue -Object $player -Name 'Name')
        PlayerLevel = Get-OptionalPropertyValue -Object $player -Name 'Level'
        PlayerGuild = [string](Get-OptionalPropertyValue -Object $player -Name 'Guild')
        PlayerLocation = [string](Get-OptionalPropertyValue -Object $player -Name 'Location')
        PlayerCoord = Get-OptionalPropertyValue -Object $player -Name 'Coord'
    }
}

function Get-LiveSourceSample {
    param(
        [Parameter(Mandatory = $true)][string]$SelectedSourceAddress,
        [Parameter(Mandatory = $true)][string]$ProcessName,
        [string]$BasisForwardOffset,
        [string]$DuplicateBasisForwardOffset
    )

    $address = Parse-HexUInt64 -Value $SelectedSourceAddress
    $memoryRead = Invoke-ReaderJson -Arguments @(
        '--process-name', $ProcessName,
        '--address', ('0x{0:X}' -f $address),
        '--length', '256',
        '--json')

    $bytes = Convert-HexToByteArray -Hex ([string]$memoryRead.BytesHex)
    $coord48 = Read-TripletAt -Bytes $bytes -Offset 0x48
    $orientation60 = Read-TripletAt -Bytes $bytes -Offset 0x60
    $coord88 = Read-TripletAt -Bytes $bytes -Offset 0x88
    $orientation94 = Read-TripletAt -Bytes $bytes -Offset 0x94
    $basis60 = New-BasisMatrixEstimate -Name 'Basis60' -Forward $orientation60 -Up (Read-TripletAt -Bytes $bytes -Offset 0x6C) -Right (Read-TripletAt -Bytes $bytes -Offset 0x78)
    $basis94 = New-BasisMatrixEstimate -Name 'Basis94' -Forward $orientation94 -Up (Read-TripletAt -Bytes $bytes -Offset 0xA0) -Right (Read-TripletAt -Bytes $bytes -Offset 0xAC)
    $resolvedForwardOffset = $null
    $resolvedDuplicateForwardOffset = $null
    $resolvedBasisCandidate = $null
    $resolvedBasisDuplicateCandidate = $null
    $resolvedBasisDuplicateAgreement = $null
    $resolvedBasis = $null
    $resolvedEstimate = $null
    $basisPrimaryForwardOffset = $null

    if (-not [string]::IsNullOrWhiteSpace($BasisForwardOffset)) {
        $resolvedForwardOffset = ('0x{0:X}' -f (Convert-HexOffsetToInt32 -Value $BasisForwardOffset))
        $resolvedBasisCandidate = Get-BasisMatrixEstimateAtOffset -Bytes $bytes -ForwardOffset (Convert-HexOffsetToInt32 -Value $BasisForwardOffset)
    }

    if (-not [string]::IsNullOrWhiteSpace($DuplicateBasisForwardOffset)) {
        $resolvedDuplicateForwardOffset = ('0x{0:X}' -f (Convert-HexOffsetToInt32 -Value $DuplicateBasisForwardOffset))
        $resolvedBasisDuplicateCandidate = Get-BasisMatrixEstimateAtOffset -Bytes $bytes -ForwardOffset (Convert-HexOffsetToInt32 -Value $DuplicateBasisForwardOffset)
    }

    if ($null -ne $resolvedBasisCandidate -and $null -ne $resolvedBasisDuplicateCandidate) {
        $resolvedBasisDuplicateAgreement = Get-BasisDuplicateAgreement -PrimaryBasis $resolvedBasisCandidate -DuplicateBasis $resolvedBasisDuplicateCandidate
    }

    if (Test-MeaningfulBasisCandidate -Basis $resolvedBasisCandidate) {
        $resolvedBasis = $resolvedBasisCandidate
        $resolvedEstimate = $resolvedBasisCandidate.ForwardEstimate
        $basisPrimaryForwardOffset = $resolvedForwardOffset
    }
    elseif (Test-MeaningfulBasisCandidate -Basis $basis60) {
        $resolvedBasis = $basis60
        $resolvedEstimate = $basis60.ForwardEstimate
        $basisPrimaryForwardOffset = '0x60'
    }
    elseif (Test-MeaningfulBasisCandidate -Basis $basis94) {
        $resolvedBasis = $basis94
        $resolvedEstimate = $basis94.ForwardEstimate
        $basisPrimaryForwardOffset = '0x94'
    }

    return [pscustomobject]@{
        AddressHex = ('0x{0:X}' -f $address)
        Coord48 = $coord48
        Orientation60 = $orientation60
        Basis60 = $basis60
        Coord88 = $coord88
        Orientation94 = $orientation94
        Basis94 = $basis94
        BasisDuplicateAgreement = Get-BasisDuplicateAgreement -PrimaryBasis $basis60 -DuplicateBasis $basis94
        ResolvedForwardOffset = $resolvedForwardOffset
        ResolvedDuplicateForwardOffset = $resolvedDuplicateForwardOffset
        ResolvedOrientation = if ($null -ne $resolvedBasis) { $resolvedBasis.Forward } else { $null }
        ResolvedBasisCandidate = $resolvedBasisCandidate
        ResolvedBasisDuplicateCandidate = $resolvedBasisDuplicateCandidate
        ResolvedBasisDuplicateAgreement = $resolvedBasisDuplicateAgreement
        BasisPrimaryForwardOffset = $basisPrimaryForwardOffset
        ResolvedBasis = $resolvedBasis
        ResolvedEstimate = $resolvedEstimate
    }
}

function Test-CoordMatch {
    param(
        $ExpectedCoord,
        $ActualCoord,
        [double]$Tolerance = 0.75
    )

    if ($null -eq $ExpectedCoord -or $null -eq $ActualCoord) {
        return $false
    }

    if ($null -eq $ExpectedCoord.X -or $null -eq $ExpectedCoord.Y -or $null -eq $ExpectedCoord.Z) {
        return $false
    }

    if ($null -eq $ActualCoord.X -or $null -eq $ActualCoord.Y -or $null -eq $ActualCoord.Z) {
        return $false
    }

    return (
        ([Math]::Abs([double]$ExpectedCoord.X - [double]$ActualCoord.X) -le $Tolerance) -and
        ([Math]::Abs([double]$ExpectedCoord.Y - [double]$ActualCoord.Y) -le $Tolerance) -and
        ([Math]::Abs([double]$ExpectedCoord.Z - [double]$ActualCoord.Z) -le $Tolerance))
}

function Resolve-LiveOrientation {
    param(
        [bool]$AllowOwnerRefresh,
        $BehaviorBackedLead
    )

    if ($null -ne $BehaviorBackedLead) {
        $snapshotMetadata = $null
        $resolutionNotes = New-Object System.Collections.Generic.List[string]
        try {
            $snapshotMetadata = Get-ReaderBridgePlayerMetadata
        }
        catch {
            $resolutionNotes.Add("ReaderBridge snapshot metadata load failed: $($_.Exception.Message)")
        }

        $liveSample = Get-LiveSourceSample `
            -SelectedSourceAddress $BehaviorBackedLead.SourceAddress `
            -ProcessName $ProcessName `
            -BasisForwardOffset $BehaviorBackedLead.BasisForwardOffset `
            -DuplicateBasisForwardOffset $BehaviorBackedLead.BasisDuplicateForwardOffset

        if (-not (Test-MeaningfulBasisCandidate -Basis $liveSample.ResolvedBasis)) {
            throw ("Behavior-backed lead '{0}' did not resolve a meaningful live basis at {1} ({2})." -f `
                $resolvedBehaviorBackedLeadFile, `
                $BehaviorBackedLead.SourceAddress, `
                $BehaviorBackedLead.BasisForwardOffset)
        }

        $resolutionNotes.Add("Resolved live source via behavior-backed lead file '$resolvedBehaviorBackedLeadFile': $($BehaviorBackedLead.SourceAddress) (basis $($BehaviorBackedLead.BasisForwardOffset)).")
        if (-not [string]::IsNullOrWhiteSpace($BehaviorBackedLead.Status)) {
            $resolutionNotes.Add("Behavior-backed lead status: $($BehaviorBackedLead.Status).")
        }
        foreach ($note in @($BehaviorBackedLead.Notes | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })) {
            $resolutionNotes.Add([string]$note)
        }

        $playerCoord = if ($null -ne $snapshotMetadata) { $snapshotMetadata.PlayerCoord } else { $null }
        $coord48Matches = Test-CoordMatch -ExpectedCoord $playerCoord -ActualCoord $liveSample.Coord48 -Tolerance $coordTolerance
        $coord88Matches = Test-CoordMatch -ExpectedCoord $playerCoord -ActualCoord $liveSample.Coord88 -Tolerance $coordTolerance
        $artifactTimestamp = (Get-Item -LiteralPath $resolvedBehaviorBackedLeadFile).LastWriteTimeUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)

        $metadata = [pscustomobject]@{
            ArtifactFile = $resolvedBehaviorBackedLeadFile
            ArtifactLoadedAtUtc = $artifactTimestamp
            ArtifactGeneratedAtUtc = $BehaviorBackedLead.GeneratedAtUtc
            SnapshotFile = if ($null -ne $snapshotMetadata) { $snapshotMetadata.SnapshotFile } else { $null }
            SnapshotLoadedAtUtc = if ($null -ne $snapshotMetadata) { $snapshotMetadata.SnapshotLoadedAtUtc } else { $null }
            PlayerName = if ($null -ne $snapshotMetadata) { $snapshotMetadata.PlayerName } else { $null }
            PlayerLevel = if ($null -ne $snapshotMetadata) { $snapshotMetadata.PlayerLevel } else { $null }
            PlayerGuild = if ($null -ne $snapshotMetadata) { $snapshotMetadata.PlayerGuild } else { $null }
            PlayerLocation = if ($null -ne $snapshotMetadata) { $snapshotMetadata.PlayerLocation } else { $null }
            PlayerCoord = $playerCoord
            SelectedSourceAddress = $BehaviorBackedLead.SourceAddress
            SelectedEntryAddress = $null
            SelectedEntryIndex = $null
            SelectedEntryMatchesSelectedSource = $null
            SelectedEntryRoleHints = @()
            RefreshedOwnerComponents = $false
            ResolutionMode = 'behavior-backed-lead'
            ResolutionNotes = $resolutionNotes.ToArray()
            BasisForwardOffset = $BehaviorBackedLead.BasisForwardOffset
            Status = $BehaviorBackedLead.Status
            OperationalStatus = $BehaviorBackedLead.OperationalStatus
            PreferredLead = $BehaviorBackedLead.PreferredLead
            SolvedActorFacing = $BehaviorBackedLead.SolvedActorFacing
            CanonicalActorYaw = $BehaviorBackedLead.CanonicalActorYaw
        }

        return [pscustomobject]@{
            Metadata = $metadata
            LiveSample = $liveSample
            Coord48Matches = $coord48Matches
            Coord88Matches = $coord88Matches
        }
    }

    $metadata = Invoke-ReaderJson -Arguments @(
        '--read-player-orientation',
        '--owner-components-file', $resolvedOwnerComponentsFile,
        '--json')

    if ([string]::IsNullOrWhiteSpace([string]$metadata.SelectedSourceAddress)) {
        throw 'The player-orientation reader did not resolve a selected source address.'
    }

    $liveSample = Get-LiveSourceSample -SelectedSourceAddress ([string]$metadata.SelectedSourceAddress) -ProcessName $ProcessName
    $playerCoord = $metadata.PlayerCoord
    $coord48Matches = Test-CoordMatch -ExpectedCoord $playerCoord -ActualCoord $liveSample.Coord48 -Tolerance $coordTolerance
    $coord88Matches = Test-CoordMatch -ExpectedCoord $playerCoord -ActualCoord $liveSample.Coord88 -Tolerance $coordTolerance

    $metadata | Add-Member -NotePropertyName RefreshedOwnerComponents -NotePropertyValue ([bool]$AllowOwnerRefresh) -Force

    return [pscustomobject]@{
        Metadata = $metadata
        LiveSample = $liveSample
        Coord48Matches = $coord48Matches
        Coord88Matches = $coord88Matches
    }
}

$resolvedOwnerComponentsFile = [System.IO.Path]::GetFullPath($OwnerComponentsFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$resolvedPreviousFile = [System.IO.Path]::GetFullPath($PreviousFile)
$resolvedBehaviorBackedLeadFile = [System.IO.Path]::GetFullPath($BehaviorBackedLeadFile)
$behaviorBackedLead = $null
$targetProcessMetadata = Get-TargetProcessMetadata -Name $ProcessName

if (-not $IgnoreBehaviorBackedLead -and (Test-Path -LiteralPath $resolvedBehaviorBackedLeadFile)) {
    $behaviorBackedLead = Load-BehaviorBackedLead -Path $resolvedBehaviorBackedLeadFile
    $behaviorBackedLeadApplicability = Test-BehaviorBackedLeadApplicability -Lead $behaviorBackedLead -ProcessMetadata $targetProcessMetadata
    if (-not $behaviorBackedLeadApplicability.IsValid) {
        throw ("{0} Rebuild the live facing lead with find-player-orientation-candidate.ps1 / test-actor-yaw-candidates.ps1, or rerun with -IgnoreBehaviorBackedLead to bypass the cached lead." -f $behaviorBackedLeadApplicability.Reason)
    }
}

if ($RefreshReaderBridge) {
    $refreshArguments = @{ 'NoReader' = $true }
    if ($NoAhkFallback) {
        $refreshArguments['NoAhkFallback'] = $true
    }

    if ($Json) {
        & $refreshReaderBridgeScript @refreshArguments *> $null
    }
    else {
        & $refreshReaderBridgeScript @refreshArguments | Out-Null
    }
}

if ($null -eq $behaviorBackedLead -and ($RefreshOwnerComponents -or -not (Test-Path -LiteralPath $resolvedOwnerComponentsFile))) {
    & $ownerComponentScript -RefreshSelectorTrace -OutputFile $resolvedOwnerComponentsFile -Json | Out-Null
}

$liveResolution = Resolve-LiveOrientation -AllowOwnerRefresh $RefreshOwnerComponents -BehaviorBackedLead $behaviorBackedLead
$orientationMetadata = $liveResolution.Metadata
$liveSourceSample = $liveResolution.LiveSample
$estimates = New-Object System.Collections.Generic.List[object]
if ($null -ne $liveSourceSample.ResolvedEstimate) {
    $estimates.Add($liveSourceSample.ResolvedEstimate) | Out-Null
}
else {
    $estimates.Add((New-VectorEstimate -Name 'Orientation60' -Vector $liveSourceSample.Orientation60)) | Out-Null
    $estimates.Add((New-VectorEstimate -Name 'Orientation94' -Vector $liveSourceSample.Orientation94)) | Out-Null
}

$preferredEstimate = if ($null -ne $liveSourceSample.ResolvedEstimate) {
    $liveSourceSample.ResolvedEstimate
}
else {
    $estimates | Where-Object { $_.Name -eq 'Orientation60' } | Select-Object -First 1
}
if ($null -eq $preferredEstimate) {
    $preferredEstimate = @($estimates) | Select-Object -First 1
}

$orientationNotes = New-Object System.Collections.Generic.List[string]
if ($orientationMetadata.PSObject.Properties.Name -contains 'Notes') {
    foreach ($note in @($orientationMetadata.Notes)) {
        if (-not [string]::IsNullOrWhiteSpace([string]$note)) {
            $orientationNotes.Add([string]$note)
        }
    }
}
elseif ($orientationMetadata.PSObject.Properties.Name -contains 'ResolutionNotes') {
    foreach ($note in @($orientationMetadata.ResolutionNotes)) {
        if (-not [string]::IsNullOrWhiteSpace([string]$note)) {
            $orientationNotes.Add([string]$note)
        }
    }
}
$orientationNotes.Add('Preferred estimate in this capture was recomputed from a fresh live memory read of the selected source object.')
if ($null -ne $liveSourceSample.ResolvedBasis -and -not [string]::IsNullOrWhiteSpace([string]$liveSourceSample.BasisPrimaryForwardOffset)) {
    $orientationNotes.Add("Yaw/pitch truth is currently derived from $($liveSourceSample.ResolvedBasis.Name).Forward at $($liveSourceSample.BasisPrimaryForwardOffset).")
}
else {
    $orientationNotes.Add('Coord48/Coord88 and Orientation60/Orientation94 were read directly from source offsets +0x48/+0x88 and +0x60/+0x94.')
    $orientationNotes.Add('The source object also exposes duplicated 3x3 basis blocks at +0x60/+0x6C/+0x78 and +0x94/+0xA0/+0xAC; yaw/pitch are derived from the forward row.')
}
if ($null -ne $behaviorBackedLead) {
    $orientationNotes.Add('Legacy refresh/recovery was suppressed because a behavior-backed lead file is present; the helper now fails closed instead of falling back to owner-component recovery.')
}
if ($liveResolution.Coord48Matches -or $liveResolution.Coord88Matches) {
    $orientationNotes.Add('Live source coords matched the current ReaderBridge player coords during capture.')
}
else {
    $orientationNotes.Add('Live source coords did not match the current ReaderBridge player coords during capture.')
}
if ($orientationMetadata.RefreshedOwnerComponents -eq $true) {
    $orientationNotes.Add('The helper refreshed the owner-component artifact before resolving the selected source for this capture.')
}
elseif ($orientationMetadata.PSObject.Properties.Name -contains 'OwnerRefreshError' -and -not [string]::IsNullOrWhiteSpace([string]$orientationMetadata.OwnerRefreshError)) {
    $orientationNotes.Add("Owner-component refresh failed; using the last known selected source. $($orientationMetadata.OwnerRefreshError)")
}

$preferredBasis = if ($null -ne $liveSourceSample.ResolvedBasis) { $liveSourceSample.ResolvedBasis } else { $liveSourceSample.Basis60 }
$duplicateBasisAgreement = if ($null -ne $liveSourceSample.ResolvedBasis) { $liveSourceSample.ResolvedBasisDuplicateAgreement } else { $liveSourceSample.BasisDuplicateAgreement }
$basisForwardOffset = if ($null -ne $liveSourceSample.BasisPrimaryForwardOffset) { $liveSourceSample.BasisPrimaryForwardOffset } elseif ($orientationMetadata.PSObject.Properties.Name -contains 'BasisForwardOffset') { $orientationMetadata.BasisForwardOffset } else { $null }
$preferredBasisName = if ($null -ne $liveSourceSample.ResolvedBasis) { $liveSourceSample.ResolvedBasis.Name } else { $null }
$resolutionMode = if ($orientationMetadata.PSObject.Properties.Name -contains 'ResolutionMode') { $orientationMetadata.ResolutionMode } else { $null }
$resolutionNotes = if ($orientationMetadata.PSObject.Properties.Name -contains 'ResolutionNotes') { $orientationMetadata.ResolutionNotes } else { $null }
$status = if ($orientationMetadata.PSObject.Properties.Name -contains 'Status') { $orientationMetadata.Status } else { $null }
$operationalStatus = if ($orientationMetadata.PSObject.Properties.Name -contains 'OperationalStatus') { $orientationMetadata.OperationalStatus } else { $null }
$preferredLeadFlag = if ($orientationMetadata.PSObject.Properties.Name -contains 'PreferredLead') { $orientationMetadata.PreferredLead } else { $null }
$solvedActorFacingFlag = if ($orientationMetadata.PSObject.Properties.Name -contains 'SolvedActorFacing') { $orientationMetadata.SolvedActorFacing } else { $null }
$canonicalActorYawFlag = if ($orientationMetadata.PSObject.Properties.Name -contains 'CanonicalActorYaw') { $orientationMetadata.CanonicalActorYaw } else { $null }
$selectedEntryRoleHints = @($orientationMetadata.SelectedEntryRoleHints)
$resolutionNotesArray = @($resolutionNotes)
$estimatesArray = $estimates.ToArray()
$orientationNotesArray = $orientationNotes.ToArray()

$orientationProperties = [ordered]@{
    Mode = 'player-orientation-live'
    ArtifactFile = $orientationMetadata.ArtifactFile
    ArtifactLoadedAtUtc = $orientationMetadata.ArtifactLoadedAtUtc
    ArtifactGeneratedAtUtc = $orientationMetadata.ArtifactGeneratedAtUtc
    SnapshotFile = $orientationMetadata.SnapshotFile
    SnapshotLoadedAtUtc = $orientationMetadata.SnapshotLoadedAtUtc
    PlayerName = $orientationMetadata.PlayerName
    PlayerLevel = $orientationMetadata.PlayerLevel
    PlayerGuild = $orientationMetadata.PlayerGuild
    PlayerLocation = $orientationMetadata.PlayerLocation
    PlayerCoord = $orientationMetadata.PlayerCoord
    SelectedSourceAddress = $orientationMetadata.SelectedSourceAddress
    SelectedEntryAddress = $orientationMetadata.SelectedEntryAddress
    SelectedEntryIndex = $orientationMetadata.SelectedEntryIndex
    SelectedEntryMatchesSelectedSource = $orientationMetadata.SelectedEntryMatchesSelectedSource
    SelectedEntryRoleHints = $selectedEntryRoleHints
    LiveSourceCoord48MatchesPlayerCoord = $liveResolution.Coord48Matches
    LiveSourceCoord88MatchesPlayerCoord = $liveResolution.Coord88Matches
    RefreshedOwnerComponents = $orientationMetadata.RefreshedOwnerComponents
    ResolutionMode = $resolutionMode
    ResolutionNotes = $resolutionNotesArray
    BasisForwardOffset = $basisForwardOffset
    PreferredBasisName = $preferredBasisName
    Status = $status
    OperationalStatus = $operationalStatus
    PreferredLead = $preferredLeadFlag
    SolvedActorFacing = $solvedActorFacingFlag
    CanonicalActorYaw = $canonicalActorYawFlag
    LiveSourceSample = $liveSourceSample
    PreferredBasis = $preferredBasis
    DuplicateBasisAgreement = $duplicateBasisAgreement
    PreferredEstimate = $preferredEstimate
    Estimates = $estimatesArray
    Notes = $orientationNotesArray
}
$orientation = New-Object psobject -Property $orientationProperties

$notes = New-Object System.Collections.Generic.List[string]
$notes.Add('This helper is actor-oriented: it reads the selected owner/source component and derives yaw/pitch from the live source basis matrix.')
$notes.Add('Use -RefreshOwnerComponents when you want to recapture the owner/source component live before computing yaw/pitch.')
$notes.Add('When a behavior-backed lead file is present, the helper prefers that live source and validates the basis before trusting the capture.')
$notes.Add('Use -RefreshReaderBridge when you want the coord-match checks to compare against a freshly exported player snapshot.')
$notes.Add('For cleaner live tests, keep movement minimal and compare labeled captures before/after controlled facing changes.')

$document = [pscustomobject]@{
    Mode = 'player-actor-orientation-capture'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    Label = $Label
    OutputFile = $resolvedOutputFile
    PreviousFile = $resolvedPreviousFile
    ReaderOrientation = $orientation
    Notes = $notes
}

$previousCapture = $null
if (Test-Path -LiteralPath $resolvedOutputFile) {
    $previousJson = Get-Content -LiteralPath $resolvedOutputFile -Raw
    if (-not [string]::IsNullOrWhiteSpace($previousJson)) {
        $previousCapture = $previousJson | ConvertFrom-Json -Depth 30
    }

    $previousDirectory = Split-Path -Path $resolvedPreviousFile -Parent
    if (-not [string]::IsNullOrWhiteSpace($previousDirectory)) {
        New-Item -ItemType Directory -Path $previousDirectory -Force | Out-Null
    }

    Copy-Item -LiteralPath $resolvedOutputFile -Destination $resolvedPreviousFile -Force
}

$document | Add-Member -NotePropertyName ChangeFromPrevious -NotePropertyValue (Get-PreviousCaptureDelta -CurrentCapture $document -PreviousCapture $previousCapture -PreviousPath $resolvedPreviousFile)

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $document | ConvertTo-Json -Depth 30
[System.IO.File]::WriteAllText($resolvedOutputFile, $jsonText)

if ($Json) {
    Write-Output $jsonText
    return
}

Write-Output (Write-ActorOrientationText -Document $document)
