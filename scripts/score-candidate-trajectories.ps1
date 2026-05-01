[CmdletBinding()]
param(
    [string]$TruthCsv,

    [string]$LiveCoordsFile,

    [string]$MemoryTimeseriesCsv,

    [string]$MemoryDirectory,

    [string]$FlattenedMemoryTimeseriesCsv,

    [string]$OutputFile = (Join-Path (Join-Path $PSScriptRoot 'captures') ('candidate-trajectory-scores-{0}.json' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))),

    [string[]]$MovementSamples = @(),

    [string[]]$StationarySamples = @(),

    [int]$MinimumComparedSamples = 3,

    [double]$MovementEpsilon = 0.05,

    [double]$StrongDistanceTolerance = 0.75,

    [double]$StationaryDriftTolerance = 0.15,

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$schemaVersion = 1

if ([string]::IsNullOrWhiteSpace($TruthCsv) -and [string]::IsNullOrWhiteSpace($LiveCoordsFile)) {
    throw 'Specify either -TruthCsv or -LiveCoordsFile.'
}

if (-not [string]::IsNullOrWhiteSpace($TruthCsv) -and -not [string]::IsNullOrWhiteSpace($LiveCoordsFile)) {
    throw 'Specify only one truth source: -TruthCsv or -LiveCoordsFile.'
}

if ([string]::IsNullOrWhiteSpace($MemoryTimeseriesCsv) -and [string]::IsNullOrWhiteSpace($MemoryDirectory)) {
    throw 'Specify either -MemoryTimeseriesCsv or -MemoryDirectory.'
}

if ($MinimumComparedSamples -lt 2) {
    throw 'MinimumComparedSamples must be at least 2.'
}

if ($MovementEpsilon -lt 0) {
    throw 'MovementEpsilon must be zero or greater.'
}

function ConvertTo-DoubleOrNull {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    try {
        $number = [double]::Parse($text, [System.Globalization.CultureInfo]::InvariantCulture)
        if ([double]::IsNaN($number) -or [double]::IsInfinity($number)) {
            return $null
        }

        return $number
    }
    catch {
        return $null
    }
}

function ConvertTo-IntOrNull {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    try {
        return [int]::Parse($text, [System.Globalization.CultureInfo]::InvariantCulture)
    }
    catch {
        return $null
    }
}

function ConvertTo-SampleIndexArray {
    param(
        [string[]]$Values,

        [Parameter(Mandatory = $true)]
        [string]$ParameterName
    )

    $samples = [System.Collections.Generic.List[int]]::new()
    foreach ($value in @($Values)) {
        if ([string]::IsNullOrWhiteSpace($value)) {
            continue
        }

        foreach ($part in ([string]$value -split '[,\s;]+')) {
            if ([string]::IsNullOrWhiteSpace($part)) {
                continue
            }

            try {
                $samples.Add([int]::Parse($part, [System.Globalization.CultureInfo]::InvariantCulture)) | Out-Null
            }
            catch {
                throw "$ParameterName contains a non-integer sample index: $part"
            }
        }
    }

    return $samples.ToArray()
}

function Get-PropertyValue {
    param(
        [object]$InputObject,
        [Parameter(Mandatory = $true)]
        [string[]]$Names
    )

    if ($null -eq $InputObject) {
        return $null
    }

    foreach ($name in $Names) {
        if ($InputObject -is [System.Collections.IDictionary]) {
            if ($InputObject.Contains($name)) {
                return $InputObject[$name]
            }
        }
        else {
            $property = $InputObject.PSObject.Properties[$name]
            if ($null -ne $property) {
                return $property.Value
            }
        }
    }

    return $null
}

function Get-NestedValue {
    param(
        [object]$InputObject,
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $current = $InputObject
    foreach ($segment in $Path.Split('.')) {
        $current = Get-PropertyValue -InputObject $current -Names @($segment)
        if ($null -eq $current) {
            return $null
        }
    }

    return $current
}

function Get-Distance3d {
    param(
        [double]$X1,
        [double]$Y1,
        [double]$Z1,
        [double]$X2,
        [double]$Y2,
        [double]$Z2
    )

    $dx = $X2 - $X1
    $dy = $Y2 - $Y1
    $dz = $Z2 - $Z1
    return [Math]::Sqrt(($dx * $dx) + ($dy * $dy) + ($dz * $dz))
}

function Get-Mean {
    param([double[]]$Values)

    $valid = @($Values | Where-Object { -not [double]::IsNaN($_) -and -not [double]::IsInfinity($_) })
    if ($valid.Count -eq 0) {
        return $null
    }

    return ($valid | Measure-Object -Average).Average
}

function Get-RootMeanSquare {
    param([double[]]$Values)

    $valid = @($Values | Where-Object { -not [double]::IsNaN($_) -and -not [double]::IsInfinity($_) })
    if ($valid.Count -eq 0) {
        return $null
    }

    $sum = 0.0
    foreach ($value in $valid) {
        $sum += $value * $value
    }

    return [Math]::Sqrt($sum / $valid.Count)
}

function Limit-Score {
    param([double]$Value)

    return [Math]::Round([Math]::Max(0.0, [Math]::Min(100.0, $Value)), 3)
}

function Read-TruthCsv {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = [System.IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $resolved)) {
        throw "Truth CSV not found: $resolved"
    }

    $rows = Import-Csv -LiteralPath $resolved
    $index = 0
    $truth = [System.Collections.Generic.List[object]]::new()
    foreach ($row in $rows) {
        $index++
        $sampleIndex = ConvertTo-IntOrNull (Get-PropertyValue -InputObject $row -Names @('sampleIndex', 'sample', 'index'))
        if ($null -eq $sampleIndex) {
            $sampleIndex = $index
        }

        $x = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $row -Names @('x', 'X'))
        $y = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $row -Names @('y', 'Y'))
        $z = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $row -Names @('z', 'Z'))
        if ($null -eq $x -or $null -eq $y -or $null -eq $z) {
            continue
        }

        $truth.Add([pscustomobject]@{
                SampleIndex = [int]$sampleIndex
                X = [double]$x
                Y = [double]$y
                Z = [double]$z
                TimestampUtc = $null
                Source = [string](Get-PropertyValue -InputObject $row -Names @('source', 'Source'))
            }) | Out-Null
    }

    return $truth.ToArray()
}

function Read-LiveCoordsNdjson {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = [System.IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $resolved)) {
        throw "Live coords NDJSON not found: $resolved"
    }

    $truth = [System.Collections.Generic.List[object]]::new()
    $lineIndex = 0
    foreach ($line in Get-Content -LiteralPath $resolved) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $lineIndex++
        $document = $line | ConvertFrom-Json -Depth 32
        $sampleIndex = ConvertTo-IntOrNull (Get-PropertyValue -InputObject $document -Names @('sampleIndex', 'sample', 'index'))
        if ($null -eq $sampleIndex) {
            $sampleIndex = $lineIndex
        }

        $x = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $document -Names @('x', 'X'))
        $y = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $document -Names @('y', 'Y'))
        $z = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $document -Names @('z', 'Z'))
        if ($null -eq $x -or $null -eq $y -or $null -eq $z) {
            continue
        }

        $truth.Add([pscustomobject]@{
                SampleIndex = [int]$sampleIndex
                X = [double]$x
                Y = [double]$y
                Z = [double]$z
                TimestampUtc = [string](Get-PropertyValue -InputObject $document -Names @('observedAtUtc', 'exportedAtUtc', 'timestampUtc', 'capturedUtc'))
                Source = [string](Get-PropertyValue -InputObject $document -Names @('source', 'mode'))
            }) | Out-Null
    }

    return $truth.ToArray()
}

function Read-MemoryTimeseriesCsv {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = [System.IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $resolved)) {
        throw "Memory timeseries CSV not found: $resolved"
    }

    $rows = Import-Csv -LiteralPath $resolved
    $records = [System.Collections.Generic.List[object]]::new()
    foreach ($row in $rows) {
        $sampleIndex = ConvertTo-IntOrNull (Get-PropertyValue -InputObject $row -Names @('sampleIndex', 'sample', 'index'))
        $x = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $row -Names @('x', 'X'))
        $y = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $row -Names @('y', 'Y'))
        $z = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $row -Names @('z', 'Z'))
        if ($null -eq $sampleIndex -or $null -eq $x -or $null -eq $y -or $null -eq $z) {
            continue
        }

        $candidateId = [string](Get-PropertyValue -InputObject $row -Names @('candidateId', 'addressHex', 'address', 'id'))
        if ([string]::IsNullOrWhiteSpace($candidateId)) {
            $candidateId = 'candidate'
        }

        $records.Add([pscustomobject]@{
                SampleIndex = [int]$sampleIndex
                CandidateId = $candidateId
                AddressHex = [string](Get-PropertyValue -InputObject $row -Names @('addressHex', 'address'))
                Source = [string](Get-PropertyValue -InputObject $row -Names @('source', 'Source'))
                X = [double]$x
                Y = [double]$y
                Z = [double]$z
                Ok = $true
            }) | Out-Null
    }

    return $records.ToArray()
}

function Read-MemoryDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = [System.IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $resolved)) {
        throw "Memory directory not found: $resolved"
    }

    $records = [System.Collections.Generic.List[object]]::new()
    Get-ChildItem -LiteralPath $resolved -File -Filter '*.json' |
        Sort-Object Name |
        ForEach-Object {
            $document = Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json -Depth 64
            $sampleIndex = ConvertTo-IntOrNull (Get-PropertyValue -InputObject $document -Names @('sampleIndex', 'sample'))
            if ($null -eq $sampleIndex -and $_.BaseName -match 'sample-(\d+)') {
                $sampleIndex = [int]$Matches[1]
            }

            foreach ($read in @($document.reads)) {
                $okValue = Get-PropertyValue -InputObject $read -Names @('ok', 'Ok')
                if ($okValue -eq $false) {
                    continue
                }

                $values = Get-PropertyValue -InputObject $read -Names @('values', 'Values')
                $x = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $values -Names @('x', 'X'))
                $y = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $values -Names @('y', 'Y'))
                $z = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $values -Names @('z', 'Z'))
                if ($null -eq $sampleIndex -or $null -eq $x -or $null -eq $y -or $null -eq $z) {
                    continue
                }

                $addressHex = [string](Get-PropertyValue -InputObject $read -Names @('addressHex', 'address'))
                $source = [string](Get-PropertyValue -InputObject $read -Names @('source', 'Source'))
                $records.Add([pscustomobject]@{
                        SampleIndex = [int]$sampleIndex
                        CandidateId = $addressHex
                        AddressHex = $addressHex
                        Source = $source
                        X = [double]$x
                        Y = [double]$y
                        Z = [double]$z
                        Ok = $true
                    }) | Out-Null
            }
        }

    return $records.ToArray()
}

function Write-MemoryTimeseriesCsv {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Records,

        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $resolved = [System.IO.Path]::GetFullPath($Path)
    $directory = Split-Path -Path $resolved -Parent
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $Records |
        Sort-Object CandidateId, SampleIndex |
        Select-Object SampleIndex, CandidateId, AddressHex, Source, X, Y, Z, Ok |
        Export-Csv -LiteralPath $resolved -NoTypeInformation -Encoding UTF8
}

function Get-TruthSampleSets {
    param([Parameter(Mandatory = $true)][object[]]$TruthSamples)

    $movement = [System.Collections.Generic.HashSet[int]]::new()
    $stationary = [System.Collections.Generic.HashSet[int]]::new()
    $explicitMovementSamples = @(ConvertTo-SampleIndexArray -Values $MovementSamples -ParameterName 'MovementSamples')
    $explicitStationarySamples = @(ConvertTo-SampleIndexArray -Values $StationarySamples -ParameterName 'StationarySamples')

    if ($explicitMovementSamples.Count -gt 0) {
        foreach ($sample in $explicitMovementSamples) {
            [void]$movement.Add($sample)
        }
    }

    if ($explicitStationarySamples.Count -gt 0) {
        foreach ($sample in $explicitStationarySamples) {
            [void]$stationary.Add($sample)
        }
    }

    if ($movement.Count -eq 0 -or $stationary.Count -eq 0) {
        $ordered = @($TruthSamples | Sort-Object SampleIndex)
        for ($i = 1; $i -lt $ordered.Count; $i++) {
            $previous = $ordered[$i - 1]
            $current = $ordered[$i]
            $distance = Get-Distance3d -X1 $previous.X -Y1 $previous.Y -Z1 $previous.Z -X2 $current.X -Y2 $current.Y -Z2 $current.Z
            if ($distance -gt $MovementEpsilon) {
                if ($movement.Count -eq 0) {
                    [void]$movement.Add([int]$previous.SampleIndex)
                }
                [void]$movement.Add([int]$current.SampleIndex)
            }
            else {
                [void]$stationary.Add([int]$current.SampleIndex)
            }
        }
    }

    return [pscustomobject]@{
        Movement = $movement
        Stationary = $stationary
    }
}

function Score-Candidate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CandidateId,

        [Parameter(Mandatory = $true)]
        [object[]]$CandidateRows,

        [Parameter(Mandatory = $true)]
        [hashtable]$TruthBySample,

        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.HashSet[int]]$MovementSampleSet,

        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.HashSet[int]]$StationarySampleSet,

        [int]$TruthSampleCount
    )

    $aligned = [System.Collections.Generic.List[object]]::new()
    foreach ($row in @($CandidateRows | Sort-Object SampleIndex)) {
        if (-not $TruthBySample.ContainsKey([int]$row.SampleIndex)) {
            continue
        }

        $truth = $TruthBySample[[int]$row.SampleIndex]
        $absoluteError = Get-Distance3d -X1 $truth.X -Y1 $truth.Y -Z1 $truth.Z -X2 $row.X -Y2 $row.Y -Z2 $row.Z
        $aligned.Add([pscustomobject]@{
                SampleIndex = [int]$row.SampleIndex
                Truth = $truth
                Candidate = $row
                AbsoluteError = $absoluteError
                XError = [Math]::Abs($row.X - $truth.X)
                YError = [Math]::Abs($row.Y - $truth.Y)
                ZError = [Math]::Abs($row.Z - $truth.Z)
            }) | Out-Null
    }

    $compared = $aligned.Count
    if ($compared -eq 0) {
        return [ordered]@{
            candidateId = $CandidateId
            status = 'insufficient-samples'
            score = 0.0
            comparedSampleCount = 0
            missingSampleCount = $TruthSampleCount
        }
    }

    $absoluteErrors = @($aligned | ForEach-Object { [double]$_.AbsoluteError })
    $xErrors = @($aligned | ForEach-Object { [double]$_.XError })
    $yErrors = @($aligned | ForEach-Object { [double]$_.YError })
    $zErrors = @($aligned | ForEach-Object { [double]$_.ZError })

    $candidateDeltaDistances = [System.Collections.Generic.List[double]]::new()
    $truthDeltaDistances = [System.Collections.Generic.List[double]]::new()
    $deltaErrors = [System.Collections.Generic.List[double]]::new()
    $directionMatches = 0
    $directionComparable = 0

    for ($i = 1; $i -lt $aligned.Count; $i++) {
        $previous = $aligned[$i - 1]
        $current = $aligned[$i]

        $truthDx = $current.Truth.X - $previous.Truth.X
        $truthDy = $current.Truth.Y - $previous.Truth.Y
        $truthDz = $current.Truth.Z - $previous.Truth.Z
        $candidateDx = $current.Candidate.X - $previous.Candidate.X
        $candidateDy = $current.Candidate.Y - $previous.Candidate.Y
        $candidateDz = $current.Candidate.Z - $previous.Candidate.Z

        $truthDelta = [Math]::Sqrt(($truthDx * $truthDx) + ($truthDy * $truthDy) + ($truthDz * $truthDz))
        $candidateDelta = [Math]::Sqrt(($candidateDx * $candidateDx) + ($candidateDy * $candidateDy) + ($candidateDz * $candidateDz))
        $deltaError = [Math]::Sqrt(
            (($candidateDx - $truthDx) * ($candidateDx - $truthDx)) +
            (($candidateDy - $truthDy) * ($candidateDy - $truthDy)) +
            (($candidateDz - $truthDz) * ($candidateDz - $truthDz)))

        $truthDeltaDistances.Add($truthDelta) | Out-Null
        $candidateDeltaDistances.Add($candidateDelta) | Out-Null
        $deltaErrors.Add($deltaError) | Out-Null

        if ($truthDelta -gt $MovementEpsilon -and $candidateDelta -gt $MovementEpsilon) {
            $directionComparable++
            $dot = ($truthDx * $candidateDx) + ($truthDy * $candidateDy) + ($truthDz * $candidateDz)
            if ($dot -gt 0) {
                $directionMatches++
            }
        }
    }

    $stationaryAligned = @($aligned | Where-Object { $StationarySampleSet.Contains([int]$_.SampleIndex) })
    $stationaryDriftMax = 0.0
    if ($stationaryAligned.Count -gt 1) {
        $baseline = $stationaryAligned[0].Candidate
        foreach ($entry in $stationaryAligned) {
            $drift = Get-Distance3d -X1 $baseline.X -Y1 $baseline.Y -Z1 $baseline.Z -X2 $entry.Candidate.X -Y2 $entry.Candidate.Y -Z2 $entry.Candidate.Z
            if ($drift -gt $stationaryDriftMax) {
                $stationaryDriftMax = $drift
            }
        }
    }

    $candidateChangedPairCount = @($candidateDeltaDistances | Where-Object { $_ -gt $MovementEpsilon }).Count
    $truthChangedPairCount = @($truthDeltaDistances | Where-Object { $_ -gt $MovementEpsilon }).Count

    $firstAligned = $aligned[0]
    $lastAligned = $aligned[$aligned.Count - 1]
    $truthMovementDistance = Get-Distance3d -X1 $firstAligned.Truth.X -Y1 $firstAligned.Truth.Y -Z1 $firstAligned.Truth.Z -X2 $lastAligned.Truth.X -Y2 $lastAligned.Truth.Y -Z2 $lastAligned.Truth.Z
    $candidateMovementDistance = Get-Distance3d -X1 $firstAligned.Candidate.X -Y1 $firstAligned.Candidate.Y -Z1 $firstAligned.Candidate.Z -X2 $lastAligned.Candidate.X -Y2 $lastAligned.Candidate.Y -Z2 $lastAligned.Candidate.Z
    $responseRatio = if ($truthMovementDistance -gt $MovementEpsilon) { $candidateMovementDistance / $truthMovementDistance } else { $null }

    $absoluteRmse = Get-RootMeanSquare -Values $absoluteErrors
    $deltaRmse = Get-RootMeanSquare -Values $deltaErrors.ToArray()
    if ($null -eq $deltaRmse) {
        $deltaRmse = 999999.0
    }

    $directionAgreement = if ($directionComparable -gt 0) { $directionMatches / [double]$directionComparable } else { 0.0 }
    $missingSampleCount = [Math]::Max(0, $TruthSampleCount - $compared)

    $absScore = Limit-Score (100.0 - ([double]$absoluteRmse * 5.0))
    $deltaScore = Limit-Score (100.0 - ([double]$deltaRmse * 50.0))
    $stationaryScore = Limit-Score (100.0 - ($stationaryDriftMax * 50.0))
    $responseScore = if ($null -ne $responseRatio) { Limit-Score (100.0 - ([Math]::Abs($responseRatio - 1.0) * 100.0)) } else { 0.0 }
    $directionScore = Limit-Score ($directionAgreement * 100.0)
    $missingPenalty = if ($TruthSampleCount -gt 0) { 20.0 * ($missingSampleCount / [double]$TruthSampleCount) } else { 0.0 }

    $score = Limit-Score (($deltaScore * 0.35) + ($absScore * 0.25) + ($stationaryScore * 0.20) + ($responseScore * 0.15) + ($directionScore * 0.05) - $missingPenalty)

    $classification = 'candidate-only'
    $reasons = [System.Collections.Generic.List[string]]::new()
    if ($compared -lt $MinimumComparedSamples) {
        $classification = 'insufficient-samples'
        $reasons.Add("Compared samples below MinimumComparedSamples=$MinimumComparedSamples.") | Out-Null
    }
    elseif ($truthChangedPairCount -gt 0 -and $candidateChangedPairCount -eq 0) {
        $classification = 'static-cache'
        $reasons.Add('Truth moved, but candidate never changed.') | Out-Null
    }
    elseif ($stationaryAligned.Count -gt 1 -and $stationaryDriftMax -gt $StationaryDriftTolerance) {
        $classification = 'stationary-tail-drift'
        $reasons.Add('Candidate drifted during truth stationary/control samples.') | Out-Null
    }
    elseif ($absoluteRmse -le $StrongDistanceTolerance -and $deltaRmse -le $StrongDistanceTolerance -and $score -ge 80.0) {
        $classification = 'trajectory-match'
        $reasons.Add('Absolute position and trajectory deltas are within strong-match tolerances.') | Out-Null
    }
    elseif ($absoluteRmse -gt $StrongDistanceTolerance -and $deltaRmse -le $StrongDistanceTolerance) {
        $classification = 'movement-shape-only-wrong-origin'
        $reasons.Add('Candidate motion shape is close, but absolute coordinates are not.') | Out-Null
    }
    elseif ($truthChangedPairCount -gt 0 -and $candidateMovementDistance -lt $MovementEpsilon) {
        $classification = 'nonresponsive-or-stale'
        $reasons.Add('Candidate total movement is below movement epsilon while truth moved.') | Out-Null
    }
    else {
        $reasons.Add('Candidate did not satisfy strong-match, static-cache, or drift classifications.') | Out-Null
    }

    switch ($classification) {
        'insufficient-samples' {
            $score = Limit-Score ([Math]::Min($score, 5.0))
        }
        'static-cache' {
            $score = Limit-Score ([Math]::Min($score, 20.0))
        }
        'nonresponsive-or-stale' {
            $score = Limit-Score ([Math]::Min($score, 20.0))
        }
        'stationary-tail-drift' {
            $score = Limit-Score ([Math]::Min($score, 60.0))
        }
        'movement-shape-only-wrong-origin' {
            $score = Limit-Score ([Math]::Min($score, 70.0))
        }
    }

    $sampleRows = @($aligned | Select-Object -First 8 | ForEach-Object {
            [ordered]@{
                sampleIndex = $_.SampleIndex
                truth = [ordered]@{ x = $_.Truth.X; y = $_.Truth.Y; z = $_.Truth.Z }
                candidate = [ordered]@{ x = $_.Candidate.X; y = $_.Candidate.Y; z = $_.Candidate.Z }
                absoluteError = [Math]::Round([double]$_.AbsoluteError, 6)
            }
        })

    return [ordered]@{
        candidateId = $CandidateId
        addressHex = [string]($CandidateRows | Select-Object -First 1).AddressHex
        source = [string]($CandidateRows | Select-Object -First 1).Source
        classification = $classification
        score = $score
        comparedSampleCount = $compared
        missingSampleCount = $missingSampleCount
        truthChangedPairCount = $truthChangedPairCount
        candidateChangedPairCount = $candidateChangedPairCount
        stationaryComparedSampleCount = $stationaryAligned.Count
        absoluteRmse = [Math]::Round([double]$absoluteRmse, 6)
        xRmse = [Math]::Round([double](Get-RootMeanSquare -Values $xErrors), 6)
        yRmse = [Math]::Round([double](Get-RootMeanSquare -Values $yErrors), 6)
        zRmse = [Math]::Round([double](Get-RootMeanSquare -Values $zErrors), 6)
        meanAbsoluteError = [Math]::Round([double](Get-Mean -Values $absoluteErrors), 6)
        deltaRmse = [Math]::Round([double]$deltaRmse, 6)
        stationaryDriftMax = [Math]::Round($stationaryDriftMax, 6)
        truthMovementDistance = [Math]::Round($truthMovementDistance, 6)
        candidateMovementDistance = [Math]::Round($candidateMovementDistance, 6)
        responseRatio = $(if ($null -ne $responseRatio) { [Math]::Round([double]$responseRatio, 6) } else { $null })
        directionAgreement = [Math]::Round($directionAgreement, 6)
        componentScores = [ordered]@{
            absolute = $absScore
            delta = $deltaScore
            stationary = $stationaryScore
            response = $responseScore
            direction = $directionScore
            missingPenalty = [Math]::Round($missingPenalty, 6)
        }
        reasons = $reasons.ToArray()
        samplePreview = $sampleRows
    }
}

$truthSourceKind = if (-not [string]::IsNullOrWhiteSpace($TruthCsv)) { 'truth-csv' } else { 'live-coords-ndjson' }
$truthSamples = if ($truthSourceKind -eq 'truth-csv') {
    Read-TruthCsv -Path $TruthCsv
}
else {
    Read-LiveCoordsNdjson -Path $LiveCoordsFile
}

$truthSamples = @($truthSamples | Sort-Object SampleIndex)
if ($truthSamples.Count -lt 2) {
    throw 'At least two valid truth samples are required.'
}

$memoryRecords = if (-not [string]::IsNullOrWhiteSpace($MemoryTimeseriesCsv)) {
    Read-MemoryTimeseriesCsv -Path $MemoryTimeseriesCsv
}
else {
    Read-MemoryDirectory -Path $MemoryDirectory
}

$memoryRecords = @($memoryRecords)
if ($memoryRecords.Count -eq 0) {
    throw 'No valid memory candidate rows were found.'
}

if (-not [string]::IsNullOrWhiteSpace($FlattenedMemoryTimeseriesCsv)) {
    Write-MemoryTimeseriesCsv -Records $memoryRecords -Path $FlattenedMemoryTimeseriesCsv
}

$sampleSets = Get-TruthSampleSets -TruthSamples $truthSamples
$truthBySample = @{}
foreach ($truth in $truthSamples) {
    $truthBySample[[int]$truth.SampleIndex] = $truth
}

$candidateScores = [System.Collections.Generic.List[object]]::new()
$groups = $memoryRecords | Group-Object CandidateId
foreach ($group in $groups) {
    $candidateScores.Add((Score-Candidate -CandidateId $group.Name -CandidateRows @($group.Group) -TruthBySample $truthBySample -MovementSampleSet $sampleSets.Movement -StationarySampleSet $sampleSets.Stationary -TruthSampleCount $truthSamples.Count)) | Out-Null
}

$ranked = @($candidateScores.ToArray() | Sort-Object @{ Expression = { [double]$_.score }; Descending = $true }, @{ Expression = { [int]$_.missingSampleCount }; Ascending = $true }, candidateId)
$rank = 0
$rankedWithRank = @($ranked | ForEach-Object {
        $rank++
        $entry = [ordered]@{ rank = $rank }
        foreach ($property in $_.GetEnumerator()) {
            $entry[$property.Key] = $property.Value
        }
        $entry
    })

$bestCandidate = if ($rankedWithRank.Count -gt 0) { $rankedWithRank[0] } else { $null }
$promotionReady = $false
if ($null -ne $bestCandidate -and
    [string]$bestCandidate.classification -eq 'trajectory-match' -and
    [double]$bestCandidate.score -ge 80.0 -and
    [int]$bestCandidate.comparedSampleCount -ge $MinimumComparedSamples) {
    $promotionReady = $true
}

$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$result = [ordered]@{
    schemaVersion = $schemaVersion
    mode = 'candidate-trajectory-scores'
    generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    status = 'complete'
    promotionReady = $promotionReady
    truthSourceKind = $truthSourceKind
    truthSourceFile = $(if ($truthSourceKind -eq 'truth-csv') { [System.IO.Path]::GetFullPath($TruthCsv) } else { [System.IO.Path]::GetFullPath($LiveCoordsFile) })
    memorySourceFile = $(if (-not [string]::IsNullOrWhiteSpace($MemoryTimeseriesCsv)) { [System.IO.Path]::GetFullPath($MemoryTimeseriesCsv) } else { $null })
    memoryDirectory = $(if (-not [string]::IsNullOrWhiteSpace($MemoryDirectory)) { [System.IO.Path]::GetFullPath($MemoryDirectory) } else { $null })
    flattenedMemoryTimeseriesCsv = $(if (-not [string]::IsNullOrWhiteSpace($FlattenedMemoryTimeseriesCsv)) { [System.IO.Path]::GetFullPath($FlattenedMemoryTimeseriesCsv) } else { $null })
    outputFile = $resolvedOutputFile
    parameters = [ordered]@{
        minimumComparedSamples = $MinimumComparedSamples
        movementEpsilon = $MovementEpsilon
        strongDistanceTolerance = $StrongDistanceTolerance
        stationaryDriftTolerance = $StationaryDriftTolerance
    }
    truthSampleCount = $truthSamples.Count
    memoryRecordCount = $memoryRecords.Count
    candidateCount = $rankedWithRank.Count
    movementSamples = @($sampleSets.Movement | Sort-Object)
    stationarySamples = @($sampleSets.Stationary | Sort-Object)
    bestCandidate = $bestCandidate
    candidates = $rankedWithRank
    notes = @(
        'Scoring is evidence for ranking only; promotion still requires a separate promotion gate.',
        'SavedVariables-derived memory rows remain candidate/negative evidence unless paired with a live truth surface.'
    )
}

[System.IO.File]::WriteAllText($resolvedOutputFile, ($result | ConvertTo-Json -Depth 32), [System.Text.UTF8Encoding]::new($false))

if ($Json) {
    $result | ConvertTo-Json -Depth 32
}
else {
    Write-Host 'Candidate trajectory scoring complete.' -ForegroundColor Green
    Write-Host ("Output:        {0}" -f $resolvedOutputFile)
    Write-Host ("Candidates:    {0}" -f $rankedWithRank.Count)
    if ($null -ne $bestCandidate) {
        Write-Host ("Best:          #{0} {1} score={2} class={3}" -f $bestCandidate.rank, $bestCandidate.candidateId, $bestCandidate.score, $bestCandidate.classification)
    }
    Write-Host ("PromotionReady:{0}" -f $promotionReady)
}
