[CmdletBinding()]
param(
    [switch]$Json,
    [string]$ProcessName = 'rift_x64',
    [int]$MaxHits = 24,
    [int]$MaxCandidates = 12,
    [double]$CoordTolerance = 0.25,
    [double]$StrongDuplicateAgreementThreshold = 0.0001,
    [double]$DuplicateAgreementThreshold = 0.01
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'

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

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 40
}

function Parse-HexUInt64 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $normalized = $Value.Trim()
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [UInt64]::Parse($normalized, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Convert-HexToByteArray {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Hex
    )

    $normalized = ($Hex -replace '\s+', '').Trim()
    $bytes = New-Object byte[] ($normalized.Length / 2)
    for ($index = 0; $index -lt $bytes.Length; $index++) {
        $bytes[$index] = [Convert]::ToByte($normalized.Substring($index * 2, 2), 16)
    }

    return $bytes
}

function Read-Bytes {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Address,

        [Parameter(Mandatory = $true)]
        [int]$Length
    )

    $memoryRead = Invoke-ReaderJson -Arguments @(
        '--process-name', $ProcessName,
        '--address', ('0x{0:X}' -f $Address),
        '--length', $Length.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json')

    return (Convert-HexToByteArray -Hex ([string]$memoryRead.BytesHex))
}

function Read-SingleAt {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [int]$Offset
    )

    if (($Offset + 4) -gt $Bytes.Length) {
        return $null
    }

    $doubleValue = [double][BitConverter]::ToSingle($Bytes, $Offset)
    if ([double]::IsNaN($doubleValue) -or [double]::IsInfinity($doubleValue)) {
        return $null
    }

    if ([Math]::Abs($doubleValue) -gt 1000000.0) {
        return $null
    }

    return $doubleValue
}

function Read-TripletAt {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [int]$Offset
    )

    return [pscustomobject]@{
        X = Read-SingleAt -Bytes $Bytes -Offset $Offset
        Y = Read-SingleAt -Bytes $Bytes -Offset ($Offset + 4)
        Z = Read-SingleAt -Bytes $Bytes -Offset ($Offset + 8)
    }
}

function Test-TripletValid {
    param($Triplet)

    return $null -ne $Triplet -and
        $null -ne $Triplet.X -and
        $null -ne $Triplet.Y -and
        $null -ne $Triplet.Z
}

function Test-CoordMatch {
    param(
        $ExpectedCoord,
        $ActualCoord,
        [double]$Tolerance = 0.25
    )

    if (-not (Test-TripletValid -Triplet $ExpectedCoord) -or -not (Test-TripletValid -Triplet $ActualCoord)) {
        return $false
    }

    return (
        ([Math]::Abs([double]$ExpectedCoord.X - [double]$ActualCoord.X) -le $Tolerance) -and
        ([Math]::Abs([double]$ExpectedCoord.Y - [double]$ActualCoord.Y) -le $Tolerance) -and
        ([Math]::Abs([double]$ExpectedCoord.Z - [double]$ActualCoord.Z) -le $Tolerance))
}

function Get-DotProduct {
    param($Left, $Right)
    return ([double]$Left.X * [double]$Right.X) + ([double]$Left.Y * [double]$Right.Y) + ([double]$Left.Z * [double]$Right.Z)
}

function Get-CrossProduct {
    param($Left, $Right)
    return [pscustomobject]@{
        X = ([double]$Left.Y * [double]$Right.Z) - ([double]$Left.Z * [double]$Right.Y)
        Y = ([double]$Left.Z * [double]$Right.X) - ([double]$Left.X * [double]$Right.Z)
        Z = ([double]$Left.X * [double]$Right.Y) - ([double]$Left.Y * [double]$Right.X)
    }
}

function Get-VectorMagnitude {
    param($Vector)

    if (-not (Test-TripletValid -Triplet $Vector)) {
        return $null
    }

    return [Math]::Sqrt((Get-DotProduct -Left $Vector -Right $Vector))
}

function Get-VectorDeltaMagnitude {
    param($Left, $Right)

    if (-not (Test-TripletValid -Triplet $Left) -or -not (Test-TripletValid -Triplet $Right)) {
        return $null
    }

    $dx = [double]$Left.X - [double]$Right.X
    $dy = [double]$Left.Y - [double]$Right.Y
    $dz = [double]$Left.Z - [double]$Right.Z
    return [Math]::Sqrt(($dx * $dx) + ($dy * $dy) + ($dz * $dz))
}

function New-BasisMatrixEstimate {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Forward,
        [Parameter(Mandatory = $true)]$Up,
        [Parameter(Mandatory = $true)]$Right
    )

    $forwardMagnitude = Get-VectorMagnitude -Vector $Forward
    $upMagnitude = Get-VectorMagnitude -Vector $Up
    $rightMagnitude = Get-VectorMagnitude -Vector $Right
    $forwardDotUp = if ($null -ne $forwardMagnitude -and $null -ne $upMagnitude) { Get-DotProduct -Left $Forward -Right $Up } else { $null }
    $forwardDotRight = if ($null -ne $forwardMagnitude -and $null -ne $rightMagnitude) { Get-DotProduct -Left $Forward -Right $Right } else { $null }
    $upDotRight = if ($null -ne $upMagnitude -and $null -ne $rightMagnitude) { Get-DotProduct -Left $Up -Right $Right } else { $null }
    $cross = if ($null -ne $forwardMagnitude -and $null -ne $upMagnitude) { Get-CrossProduct -Left $Forward -Right $Up } else { $null }
    $determinant = if ($null -ne $cross -and $null -ne $rightMagnitude) { Get-DotProduct -Left $cross -Right $Right } else { $null }

    $isOrthonormal = $false
    if ($null -ne $forwardDotUp -and $null -ne $forwardDotRight -and $null -ne $upDotRight -and $null -ne $determinant) {
        $isOrthonormal =
            ([Math]::Abs([double]$forwardDotUp) -le 0.02) -and
            ([Math]::Abs([double]$forwardDotRight) -le 0.02) -and
            ([Math]::Abs([double]$upDotRight) -le 0.02) -and
            ($null -ne $forwardMagnitude -and [Math]::Abs([double]$forwardMagnitude - 1.0) -le 0.02) -and
            ($null -ne $upMagnitude -and [Math]::Abs([double]$upMagnitude - 1.0) -le 0.02) -and
            ($null -ne $rightMagnitude -and [Math]::Abs([double]$rightMagnitude - 1.0) -le 0.02) -and
            ([Math]::Abs([Math]::Abs([double]$determinant) - 1.0) -le 0.05)
    }

    return [pscustomobject]@{
        Name = $Name
        Forward = $Forward
        Up = $Up
        Right = $Right
        ForwardMagnitude = $forwardMagnitude
        UpMagnitude = $upMagnitude
        RightMagnitude = $rightMagnitude
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

    $forwardDelta = Get-VectorDeltaMagnitude -Left $PrimaryBasis.Forward -Right $DuplicateBasis.Forward
    $upDelta = Get-VectorDeltaMagnitude -Left $PrimaryBasis.Up -Right $DuplicateBasis.Up
    $rightDelta = Get-VectorDeltaMagnitude -Left $PrimaryBasis.Right -Right $DuplicateBasis.Right

    $candidateValues = @(@($forwardDelta, $upDelta, $rightDelta) | Where-Object { $null -ne $_ })
    $maxRowDelta = if (@($candidateValues).Count -gt 0) { ($candidateValues | Measure-Object -Maximum).Maximum } else { $null }

    return [pscustomobject]@{
        ForwardDeltaMagnitude = $forwardDelta
        UpDeltaMagnitude = $upDelta
        RightDeltaMagnitude = $rightDelta
        MaxRowDeltaMagnitude = $maxRowDelta
        Strong = ($null -ne $maxRowDelta -and [double]$maxRowDelta -le $StrongDuplicateAgreementThreshold)
        Usable = ($null -ne $maxRowDelta -and [double]$maxRowDelta -le $DuplicateAgreementThreshold)
    }
}

function New-VectorEstimate {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Vector
    )

    if (-not (Test-TripletValid -Triplet $Vector)) {
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
        YawDegrees = $yawRadians * 180.0 / [Math]::PI
        PitchRadians = $pitchRadians
        PitchDegrees = $pitchRadians * 180.0 / [Math]::PI
        Magnitude = $magnitude
    }
}

function Get-DeterminantBonus {
    param($Determinant)

    if ($null -eq $Determinant) {
        return 0
    }

    $delta = [Math]::Abs([Math]::Abs([double]$Determinant) - 1.0)
    if ($delta -gt 5.0) {
        return 0
    }

    return [Math]::Max(0, 20 - [int]($delta * 100))
}

function Get-CandidateScore {
    param(
        [bool]$Coord48Matches,
        [bool]$Coord88Matches,
        $Basis60,
        $Basis94,
        $DuplicateAgreement
    )

    $score = 0
    if ($Coord48Matches) { $score += 100 }
    if ($Coord88Matches) { $score += 100 }
    if ($Basis60.IsOrthonormal) { $score += 80 }
    if ($Basis94.IsOrthonormal) { $score += 80 }

    if ($null -ne $DuplicateAgreement -and $null -ne $DuplicateAgreement.MaxRowDeltaMagnitude) {
        if ($DuplicateAgreement.Strong) {
            $score += 80
        }
        elseif ($DuplicateAgreement.Usable) {
            $score += 60
        }
        elseif ([double]$DuplicateAgreement.MaxRowDeltaMagnitude -le 0.05) {
            $score += 40
        }
    }

    $score += Get-DeterminantBonus -Determinant $Basis60.Determinant
    $score += Get-DeterminantBonus -Determinant $Basis94.Determinant
    return $score
}

function Test-HeapPointer {
    param(
        [UInt64]$Value
    )

    return ($Value -ge 0x000002BC00000000) -and ($Value -lt 0x000002BD00000000)
}

function Test-MeaningfulBasisCandidate {
    param($Basis)

    if ($null -eq $Basis -or -not $Basis.IsOrthonormal) {
        return $false
    }

    $forward = $Basis.Forward
    if (-not (Test-TripletValid -Triplet $forward)) {
        return $false
    }

    $components = @(
        [Math]::Abs([double]$forward.X),
        [Math]::Abs([double]$forward.Y),
        [Math]::Abs([double]$forward.Z))

    $nonTrivialComponents = @($components | Where-Object { $_ -ge 0.05 }).Count
    $maxComponent = ($components | Measure-Object -Maximum).Maximum

    return ($nonTrivialComponents -ge 2) -and ([double]$maxComponent -lt 0.999)
}

function Get-PointerHopCandidateScore {
    param(
        $Basis,
        $Estimate,
        [int]$ParentScore
    )

    $score = [Math]::Max(0, $ParentScore)
    if ($Basis.IsOrthonormal) {
        $score += 80
    }

    $score += Get-DeterminantBonus -Determinant $Basis.Determinant

    if ($null -ne $Estimate -and $null -ne $Estimate.Magnitude) {
        if ([double]$Estimate.Magnitude -ge 0.85 -and [double]$Estimate.Magnitude -le 1.15) {
            $score += 40
        }
    }

    return $score
}

function Get-PointerHopOrientationCandidates {
    param(
        [Parameter(Mandatory = $true)]
        $SignatureScan,

        [Parameter(Mandatory = $true)]
        [int]$MaxCandidates
    )

    $candidatesByAddress = @{}

    foreach ($hit in @($SignatureScan.Hits)) {
        if ($null -eq $hit) {
            continue
        }

        $rootAddressHex = [string]$hit.AddressHex
        if ([string]::IsNullOrWhiteSpace($rootAddressHex)) {
            continue
        }

        try {
            $rootBytes = Read-Bytes -Address (Parse-HexUInt64 -Value $rootAddressHex) -Length 256
        }
        catch {
            continue
        }

        $childPointers = New-Object System.Collections.Generic.HashSet[string]
        for ($offset = 0; ($offset + 8) -le [Math]::Min($rootBytes.Length, 256); $offset += 8) {
            $pointerValue = [BitConverter]::ToUInt64($rootBytes, $offset)
            if (-not (Test-HeapPointer -Value $pointerValue)) {
                continue
            }

            $null = $childPointers.Add(('0x{0:X}' -f $pointerValue))
        }

        foreach ($childAddressHex in @($childPointers)) {
            try {
                $childBytes = Read-Bytes -Address (Parse-HexUInt64 -Value $childAddressHex) -Length 512
            }
            catch {
                continue
            }

            $bestForChild = $null

            foreach ($basisOffset in @(0..0x160 | Where-Object { ($_ % 4) -eq 0 })) {
                $basis = New-BasisMatrixEstimate -Name ('Basis{0}' -f ('0x{0:X}' -f $basisOffset)) `
                    -Forward (Read-TripletAt -Bytes $childBytes -Offset $basisOffset) `
                    -Up (Read-TripletAt -Bytes $childBytes -Offset ($basisOffset + 0x0C)) `
                    -Right (Read-TripletAt -Bytes $childBytes -Offset ($basisOffset + 0x18))

                if (-not (Test-MeaningfulBasisCandidate -Basis $basis)) {
                    continue
                }

                $estimate = New-VectorEstimate -Name ('Basis{0}' -f ('0x{0:X}' -f $basisOffset)) -Vector $basis.Forward
                $candidate = [pscustomobject]@{
                    AddressHex = $childAddressHex
                    ParentAddressHex = $rootAddressHex
                    ParentFamilyId = [string]$hit.FamilyId
                    ParentScore = [int]$hit.Score
                    DiscoveryMode = 'pointer-hop-from-player-signature-family'
                    BasisPrimaryForwardOffset = ('0x{0:X}' -f $basisOffset)
                    Score = Get-PointerHopCandidateScore -Basis $basis -Estimate $estimate -ParentScore ([int]$hit.Score)
                    Basis = $basis
                    PreferredEstimate = $estimate
                }

                if ($null -eq $bestForChild -or [int]$candidate.Score -gt [int]$bestForChild.Score) {
                    $bestForChild = $candidate
                }
            }

            if ($null -ne $bestForChild) {
                if (-not $candidatesByAddress.ContainsKey($bestForChild.AddressHex) -or [int]$bestForChild.Score -gt [int]$candidatesByAddress[$bestForChild.AddressHex].Score) {
                    $candidatesByAddress[$bestForChild.AddressHex] = $bestForChild
                }
            }
        }
    }

    return @($candidatesByAddress.Values | Sort-Object `
        @{ Expression = { [int]$_.Score }; Descending = $true }, `
        @{ Expression = { if ($null -ne $_.PreferredEstimate.YawDegrees) { [Math]::Abs([double]$_.PreferredEstimate.YawDegrees) } else { 999999 } }; Descending = $false } | Select-Object -First $MaxCandidates)
}

$playerCurrent = Invoke-ReaderJson -Arguments @(
    '--process-name', $ProcessName,
    '--read-player-current',
    '--json')

$playerCoord = [pscustomobject]@{
    X = [double]$playerCurrent.Memory.CoordX
    Y = [double]$playerCurrent.Memory.CoordY
    Z = [double]$playerCurrent.Memory.CoordZ
}

$coordScan = Invoke-ReaderJson -Arguments @(
    '--process-name', $ProcessName,
    '--scan-readerbridge-player-coords',
    '--scan-context', '64',
    '--max-hits', $MaxHits.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--json')

$candidatesByBase = @{}
foreach ($hit in @($coordScan.Hits)) {
    $hitAddress = [UInt64]$hit.Address
    foreach ($offset in @(0x48, 0x88)) {
        if ($hitAddress -lt [UInt64]$offset) {
            continue
        }

        $baseAddress = $hitAddress - [UInt64]$offset
        $baseKey = ('0x{0:X}' -f $baseAddress)
        try {
            $bytes = Read-Bytes -Address $baseAddress -Length 192
        }
        catch {
            continue
        }

        $coord48 = Read-TripletAt -Bytes $bytes -Offset 0x48
        $coord88 = Read-TripletAt -Bytes $bytes -Offset 0x88
        $basis60 = New-BasisMatrixEstimate -Name 'Basis60' `
            -Forward (Read-TripletAt -Bytes $bytes -Offset 0x60) `
            -Up (Read-TripletAt -Bytes $bytes -Offset 0x6C) `
            -Right (Read-TripletAt -Bytes $bytes -Offset 0x78)
        $basis94 = New-BasisMatrixEstimate -Name 'Basis94' `
            -Forward (Read-TripletAt -Bytes $bytes -Offset 0x94) `
            -Up (Read-TripletAt -Bytes $bytes -Offset 0xA0) `
            -Right (Read-TripletAt -Bytes $bytes -Offset 0xAC)
        $duplicateAgreement = Get-BasisDuplicateAgreement -PrimaryBasis $basis60 -DuplicateBasis $basis94
        $coord48Matches = Test-CoordMatch -ExpectedCoord $playerCoord -ActualCoord $coord48 -Tolerance $CoordTolerance
        $coord88Matches = Test-CoordMatch -ExpectedCoord $playerCoord -ActualCoord $coord88 -Tolerance $CoordTolerance
        $score = Get-CandidateScore `
            -Coord48Matches $coord48Matches `
            -Coord88Matches $coord88Matches `
            -Basis60 $basis60 `
            -Basis94 $basis94 `
            -DuplicateAgreement $duplicateAgreement

        if ($score -le 0) {
            continue
        }

        $candidate = [pscustomobject]@{
            AddressHex = $baseKey
            HitAddressHex = ('0x{0:X}' -f $hitAddress)
            AssumedCoordOffset = ('0x{0:X}' -f $offset)
            Score = $score
            Coord48MatchesPlayer = $coord48Matches
            Coord88MatchesPlayer = $coord88Matches
            Coord48 = $coord48
            Coord88 = $coord88
            Basis60 = $basis60
            Basis94 = $basis94
            BasisDuplicateAgreement = $duplicateAgreement
            PreferredEstimate = New-VectorEstimate -Name 'Orientation60' -Vector $basis60.Forward
            DuplicateEstimate = New-VectorEstimate -Name 'Orientation94' -Vector $basis94.Forward
        }

        if (-not $candidatesByBase.ContainsKey($baseKey) -or [int]$candidate.Score -gt [int]$candidatesByBase[$baseKey].Score) {
            $candidatesByBase[$baseKey] = $candidate
        }
    }
}

$rankedCandidates = @($candidatesByBase.Values | Sort-Object `
    @{ Expression = { [int]$_.Score }; Descending = $true }, `
    @{ Expression = { if ($null -ne $_.BasisDuplicateAgreement.MaxRowDeltaMagnitude) { [double]$_.BasisDuplicateAgreement.MaxRowDeltaMagnitude } else { 1e9 } }; Descending = $false })

$signatureScan = Invoke-ReaderJson -Arguments @(
    '--process-name', $ProcessName,
    '--scan-readerbridge-player-signature',
    '--scan-context', '96',
    '--max-hits', [Math]::Max($MaxHits, 12).ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--json')

$pointerHopCandidates = @(Get-PointerHopOrientationCandidates -SignatureScan $signatureScan -MaxCandidates $MaxCandidates)

$document = [pscustomobject]@{
    Mode = 'player-orientation-candidate-search'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    ProcessName = $ProcessName
    PlayerCurrent = $playerCurrent
    CandidateCount = @($rankedCandidates).Count
    BestCandidate = $rankedCandidates | Select-Object -First 1
    Candidates = @($rankedCandidates | Select-Object -First $MaxCandidates)
    PointerHopCandidateCount = @($pointerHopCandidates).Count
    BestPointerHopCandidate = $pointerHopCandidates | Select-Object -First 1
    PointerHopCandidates = $pointerHopCandidates
    Notes = @(
        'This is a read-only search over live coord hits and nearby basis-shaped candidate objects.',
        'Candidates are scored by duplicated coord matches, orthonormal basis quality, and duplicate-basis agreement.',
        'When local coord-window candidates fail, the helper also follows first-hop heap pointers from grouped player-signature families and surfaces meaningful orthonormal child-basis candidates.',
        'No CE debugger, breakpoints, or game-window input are used by this search.')
}

if ($Json) {
    $document | ConvertTo-Json -Depth 30
    return
}

Write-Host "Actor orientation candidate search"
Write-Host ("Player coord:               {0:N3}, {1:N3}, {2:N3}" -f [double]$playerCoord.X, [double]$playerCoord.Y, [double]$playerCoord.Z)
Write-Host ("Candidate count:            {0}" -f $document.CandidateCount)
if ($null -ne $document.BestCandidate) {
    Write-Host ("Best candidate:             {0} (score {1})" -f $document.BestCandidate.AddressHex, $document.BestCandidate.Score)
    Write-Host ("Coord matches:              +0x48={0} +0x88={1}" -f $document.BestCandidate.Coord48MatchesPlayer, $document.BestCandidate.Coord88MatchesPlayer)
    Write-Host ("Duplicate basis delta:      {0}" -f $document.BestCandidate.BasisDuplicateAgreement.MaxRowDeltaMagnitude)
    Write-Host ("Yaw/Pitch (deg):            {0:N3} / {1:N3}" -f [double]$document.BestCandidate.PreferredEstimate.YawDegrees, [double]$document.BestCandidate.PreferredEstimate.PitchDegrees)
}
Write-Host ("Pointer-hop candidates:     {0}" -f $document.PointerHopCandidateCount)
if ($null -ne $document.BestPointerHopCandidate) {
    Write-Host ("Best pointer-hop:           {0} via {1} @ {2} (score {3})" -f `
        $document.BestPointerHopCandidate.AddressHex, `
        $document.BestPointerHopCandidate.ParentAddressHex, `
        $document.BestPointerHopCandidate.BasisPrimaryForwardOffset, `
        $document.BestPointerHopCandidate.Score)
    Write-Host ("Pointer-hop yaw/pitch:      {0:N3} / {1:N3}" -f `
        [double]$document.BestPointerHopCandidate.PreferredEstimate.YawDegrees, `
        [double]$document.BestPointerHopCandidate.PreferredEstimate.PitchDegrees)
}
