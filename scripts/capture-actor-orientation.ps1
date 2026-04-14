[CmdletBinding()]
param(
    [switch]$Json,
    [string]$Label,
    [switch]$RefreshOwnerComponents,
    [switch]$RefreshReaderBridge,
    [switch]$NoAhkFallback,
    [string]$ProcessName = 'rift_x64',
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

    return ConvertFrom-JsonCompat -JsonText ($output -join [Environment]::NewLine) -Depth 30
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

function Get-LiveSourceSample {
    param(
        [Parameter(Mandatory = $true)][string]$SelectedSourceAddress,
        [Parameter(Mandatory = $true)][string]$ProcessName
    )

    $address = Parse-HexUInt64 -Value $SelectedSourceAddress
    $memoryRead = Invoke-ReaderJson -Arguments @(
        '--process-name', $ProcessName,
        '--address', ('0x{0:X}' -f $address),
        '--length', '192',
        '--json')

    $bytes = Convert-HexToByteArray -Hex ([string]$memoryRead.BytesHex)
    $coord48 = Read-TripletAt -Bytes $bytes -Offset 0x48
    $orientation60 = Read-TripletAt -Bytes $bytes -Offset 0x60
    $coord88 = Read-TripletAt -Bytes $bytes -Offset 0x88
    $orientation94 = Read-TripletAt -Bytes $bytes -Offset 0x94
    $basis60 = New-BasisMatrixEstimate -Name 'Basis60' -Forward $orientation60 -Up (Read-TripletAt -Bytes $bytes -Offset 0x6C) -Right (Read-TripletAt -Bytes $bytes -Offset 0x78)
    $basis94 = New-BasisMatrixEstimate -Name 'Basis94' -Forward $orientation94 -Up (Read-TripletAt -Bytes $bytes -Offset 0xA0) -Right (Read-TripletAt -Bytes $bytes -Offset 0xAC)

    return [pscustomobject]@{
        AddressHex = ('0x{0:X}' -f $address)
        Coord48 = $coord48
        Orientation60 = $orientation60
        Basis60 = $basis60
        Coord88 = $coord88
        Orientation94 = $orientation94
        Basis94 = $basis94
        BasisDuplicateAgreement = Get-BasisDuplicateAgreement -PrimaryBasis $basis60 -DuplicateBasis $basis94
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
        [bool]$AllowOwnerRefresh
    )

    $metadata = Invoke-ReaderJson -Arguments @(
        '--read-player-orientation',
        '--owner-components-file', $resolvedOwnerComponentsFile,
        '--json')

    if ([string]::IsNullOrWhiteSpace([string]$metadata.SelectedSourceAddress)) {
        throw 'The player-orientation reader did not resolve a selected source address.'
    }

    $playerCoord = $metadata.PlayerCoord
    $liveSample = $null
    $coord48Matches = $false
    $coord88Matches = $false
    $resolutionMode = 'artifact-selected-source'
    $resolutionNotes = New-Object System.Collections.Generic.List[string]

    try {
        $liveSample = Get-LiveSourceSample -SelectedSourceAddress ([string]$metadata.SelectedSourceAddress) -ProcessName $ProcessName
        $coord48Matches = Test-CoordMatch -ExpectedCoord $playerCoord -ActualCoord $liveSample.Coord48 -Tolerance $coordTolerance
        $coord88Matches = Test-CoordMatch -ExpectedCoord $playerCoord -ActualCoord $liveSample.Coord88 -Tolerance $coordTolerance
    }
    catch {
        $resolutionNotes.Add("Artifact-selected source live read failed: $($_.Exception.Message)")
    }

    if ($null -eq $liveSample -or (-not $coord48Matches -and -not $coord88Matches)) {
        try {
            $candidateSearch = Invoke-ReaderJson -Arguments @(
                '--process-name', $ProcessName,
                '--find-player-orientation-candidate',
                '--max-hits', '8',
                '--json')
            if ($candidateSearch.BestCandidate -and -not [string]::IsNullOrWhiteSpace([string]$candidateSearch.BestCandidate.Address)) {
                $liveSample = [pscustomobject]@{
                    AddressHex = [string]$candidateSearch.BestCandidate.Address
                    Coord48 = $candidateSearch.BestCandidate.Coord48
                    Orientation60 = $candidateSearch.BestCandidate.Basis60.Forward
                    Basis60 = $candidateSearch.BestCandidate.Basis60
                    Coord88 = $candidateSearch.BestCandidate.Coord88
                    Orientation94 = $candidateSearch.BestCandidate.Basis94.Forward
                    Basis94 = $candidateSearch.BestCandidate.Basis94
                    BasisDuplicateAgreement = $candidateSearch.BestCandidate.BasisDuplicateAgreement
                }

                $coord48Matches = [bool]$candidateSearch.BestCandidate.Coord48MatchesPlayer
                $coord88Matches = [bool]$candidateSearch.BestCandidate.Coord88MatchesPlayer
                $resolutionMode = 'read-only-candidate-search'
                $resolutionNotes.Add("Resolved live source via read-only candidate search: $($candidateSearch.BestCandidate.Address)")
            }
            else {
                $resolutionNotes.Add('Read-only candidate search returned no viable source-object candidate.')
            }
        }
        catch {
            $resolutionNotes.Add("Read-only candidate search failed: $($_.Exception.Message)")
        }
    }

    if ($null -eq $liveSample) {
        throw 'Unable to resolve a live source object for actor orientation.'
    }

    $metadata | Add-Member -NotePropertyName RefreshedOwnerComponents -NotePropertyValue ([bool]$AllowOwnerRefresh) -Force
    $metadata | Add-Member -NotePropertyName ResolvedSourceAddress -NotePropertyValue ([string]$liveSample.AddressHex) -Force
    $metadata | Add-Member -NotePropertyName ResolutionMode -NotePropertyValue $resolutionMode -Force
    $metadata | Add-Member -NotePropertyName ResolutionNotes -NotePropertyValue ($resolutionNotes.ToArray()) -Force

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

if ($RefreshOwnerComponents -or -not (Test-Path -LiteralPath $resolvedOwnerComponentsFile)) {
    & $ownerComponentScript -RefreshSelectorTrace -OutputFile $resolvedOwnerComponentsFile -Json | Out-Null
}

$liveResolution = Resolve-LiveOrientation -AllowOwnerRefresh $RefreshOwnerComponents
$orientationMetadata = $liveResolution.Metadata
$liveSourceSample = $liveResolution.LiveSample
$estimates = @(
    (New-VectorEstimate -Name 'Orientation60' -Vector $liveSourceSample.Orientation60),
    (New-VectorEstimate -Name 'Orientation94' -Vector $liveSourceSample.Orientation94)
)

$preferredEstimate = $estimates | Where-Object { $_.Name -eq 'Orientation60' } | Select-Object -First 1
if ($null -eq $preferredEstimate) {
    $preferredEstimate = $estimates | Select-Object -First 1
}

$orientationNotes = New-Object System.Collections.Generic.List[string]
if ($orientationMetadata.Notes) {
    foreach ($note in $orientationMetadata.Notes) {
        $orientationNotes.Add([string]$note)
    }
}
$orientationNotes.Add('Preferred estimate in this capture was recomputed from a fresh live memory read of the selected source object.')
$orientationNotes.Add('Coord48/Coord88 and Orientation60/Orientation94 were read directly from source offsets +0x48/+0x88 and +0x60/+0x94.')
$orientationNotes.Add('The source object also exposes duplicated 3x3 basis blocks at +0x60/+0x6C/+0x78 and +0x94/+0xA0/+0xAC; yaw/pitch are derived from the forward row.')
if ($orientationMetadata.PSObject.Properties.Name -contains 'ResolutionMode') {
    $orientationNotes.Add("Live source resolution mode: $($orientationMetadata.ResolutionMode)")
}
if ($orientationMetadata.PSObject.Properties.Name -contains 'ResolutionNotes' -and $orientationMetadata.ResolutionNotes) {
    foreach ($resolutionNote in $orientationMetadata.ResolutionNotes) {
        $orientationNotes.Add([string]$resolutionNote)
    }
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

$orientation = [pscustomobject]@{
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
    SelectedSourceAddress = if ($orientationMetadata.PSObject.Properties.Name -contains 'ResolvedSourceAddress' -and -not [string]::IsNullOrWhiteSpace([string]$orientationMetadata.ResolvedSourceAddress)) { $orientationMetadata.ResolvedSourceAddress } else { $orientationMetadata.SelectedSourceAddress }
    SelectedEntryAddress = $orientationMetadata.SelectedEntryAddress
    SelectedEntryIndex = $orientationMetadata.SelectedEntryIndex
    SelectedEntryMatchesSelectedSource = $orientationMetadata.SelectedEntryMatchesSelectedSource
    SelectedEntryRoleHints = $orientationMetadata.SelectedEntryRoleHints
    LiveSourceCoord48MatchesPlayerCoord = $liveResolution.Coord48Matches
    LiveSourceCoord88MatchesPlayerCoord = $liveResolution.Coord88Matches
    RefreshedOwnerComponents = $orientationMetadata.RefreshedOwnerComponents
    LiveSourceSample = $liveSourceSample
    PreferredBasis = $liveSourceSample.Basis60
    DuplicateBasisAgreement = $liveSourceSample.BasisDuplicateAgreement
    PreferredEstimate = $preferredEstimate
    Estimates = $estimates
    Notes = $orientationNotes
}

$notes = New-Object System.Collections.Generic.List[string]
$notes.Add('This helper is actor-oriented: it reads the selected owner/source component and derives yaw/pitch from the live source basis matrix.')
$notes.Add('Use -RefreshOwnerComponents when you want to recapture the owner/source component live before computing yaw/pitch.')
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
        $previousCapture = ConvertFrom-JsonCompat -JsonText $previousJson -Depth 30
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
