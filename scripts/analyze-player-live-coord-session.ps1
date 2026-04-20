[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SessionDirectory,

    [string]$OutputFile,

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Convert-HexToFloatTriplet {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BytesHex
    )

    if ([string]::IsNullOrWhiteSpace($BytesHex) -or $BytesHex.Length -lt 24) {
        return $null
    }

    $bytes = [Convert]::FromHexString($BytesHex)
    if ($bytes.Length -lt 12) {
        return $null
    }

    return [ordered]@{
        X = [BitConverter]::ToSingle($bytes, 0)
        Y = [BitConverter]::ToSingle($bytes, 4)
        Z = [BitConverter]::ToSingle($bytes, 8)
    }
}

function New-RoundedTriplet {
    param(
        [Parameter(Mandatory = $true)]
        $Triplet
    )

    return [ordered]@{
        X = [math]::Round([double]$Triplet.X, 5)
        Y = [math]::Round([double]$Triplet.Y, 5)
        Z = [math]::Round([double]$Triplet.Z, 5)
    }
}

function Get-TripletDistance {
    param(
        $Left,
        $Right
    )

    if ($null -eq $Left -or $null -eq $Right) {
        return $null
    }

    return [math]::Round(
        [math]::Sqrt(
            [math]::Pow(([double]$Left.X - [double]$Right.X), 2) +
            [math]::Pow(([double]$Left.Y - [double]$Right.Y), 2) +
            [math]::Pow(([double]$Left.Z - [double]$Right.Z), 2)),
        5)
}

function Format-TripletText {
    param(
        $Triplet
    )

    if ($null -eq $Triplet) {
        return $null
    }

    return ('{0:F5}, {1:F5}, {2:F5}' -f [double]$Triplet.X, [double]$Triplet.Y, [double]$Triplet.Z)
}

$resolvedSessionDirectory = [System.IO.Path]::GetFullPath($SessionDirectory)
if (-not (Test-Path -LiteralPath $resolvedSessionDirectory)) {
    throw "Session directory was not found: '$resolvedSessionDirectory'."
}

$manifestFile = Join-Path $resolvedSessionDirectory 'recording-manifest.json'
$samplesFile = Join-Path $resolvedSessionDirectory 'samples.ndjson'
$startArtifactFile = Join-Path $resolvedSessionDirectory 'start-live-coord-backtrace.json'
$endArtifactFile = Join-Path $resolvedSessionDirectory 'end-live-coord-backtrace.json'

foreach ($requiredFile in @($manifestFile, $samplesFile, $startArtifactFile)) {
    if (-not (Test-Path -LiteralPath $requiredFile)) {
        throw "Required session file was not found: '$requiredFile'."
    }
}

$resolvedOutputFile = if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    Join-Path $resolvedSessionDirectory 'live-coord-session-analysis.json'
}
else {
    [System.IO.Path]::GetFullPath($OutputFile)
}

$manifest = Get-Content -LiteralPath $manifestFile -Raw | ConvertFrom-Json -Depth 64
$startArtifact = Get-Content -LiteralPath $startArtifactFile -Raw | ConvertFrom-Json -Depth 64
$endArtifact = if (Test-Path -LiteralPath $endArtifactFile) {
    Get-Content -LiteralPath $endArtifactFile -Raw | ConvertFrom-Json -Depth 64
}
else {
    $null
}

$samples = @(Get-Content -LiteralPath $samplesFile | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object {
        $_ | ConvertFrom-Json -Depth 64
    })

if ($samples.Count -eq 0) {
    throw "Session samples file '$samplesFile' does not contain any samples."
}

$startTriplet = [ordered]@{
    X = [double]$startArtifact.Snapshot.Player.Coord.X
    Y = [double]$startArtifact.Snapshot.Player.Coord.Y
    Z = [double]$startArtifact.Snapshot.Player.Coord.Z
}

$endTriplet = if ($null -ne $endArtifact) {
    [ordered]@{
        X = [double]$endArtifact.Snapshot.Player.Coord.X
        Y = [double]$endArtifact.Snapshot.Player.Coord.Y
        Z = [double]$endArtifact.Snapshot.Player.Coord.Z
    }
}
else {
    $null
}

$regionSummaryMap = @{}
foreach ($summary in @($manifest.RegionSummaries)) {
    if ($null -eq $summary -or [string]::IsNullOrWhiteSpace([string]$summary.Name)) {
        continue
    }

    $regionSummaryMap[[string]$summary.Name] = $summary
}

$firstSampleRegions = @($samples[0].Regions)
$candidateNames = @(
    $firstSampleRegions |
    Where-Object { $null -ne $_ -and [int]$_.Length -eq 12 -and [string]$_.Category -eq 'player-coord-sample' } |
    ForEach-Object { [string]$_.Name }
) | Select-Object -Unique

$candidateResults = [System.Collections.Generic.List[object]]::new()
$responsiveSampleIndexes = [System.Collections.Generic.List[int]]::new()

foreach ($candidateName in $candidateNames) {
    $series = [System.Collections.Generic.List[object]]::new()

    foreach ($sample in $samples) {
        $region = @($sample.Regions | Where-Object { [string]$_.Name -eq $candidateName })[0]
        if ($null -eq $region) {
            continue
        }

        $triplet = Convert-HexToFloatTriplet -BytesHex ([string]$region.BytesHex)
        if ($null -eq $triplet) {
            continue
        }

        $series.Add([ordered]@{
                SampleIndex = [int]$sample.SampleIndex
                Address = [string]$region.Address
                BytesHex = [string]$region.BytesHex
                Triplet = $triplet
            }) | Out-Null
    }

    if ($series.Count -eq 0) {
        continue
    }

    $firstValue = $series[0]
    $lastValue = $series[$series.Count - 1]
    $distinctBytesHex = @($series | ForEach-Object { $_.BytesHex } | Select-Object -Unique)
    $changeEvents = [System.Collections.Generic.List[object]]::new()
    $maxDistanceFromStart = -1.0
    $maxDistanceSampleIndex = $null
    $maxDistanceTriplet = $null
    $minDistanceToEnd = $null
    $minDistanceEndSampleIndex = $null
    $minDistanceEndTriplet = $null
    $previousBytesHex = $null

    foreach ($entry in $series) {
        $distanceFromStart = Get-TripletDistance -Left $entry.Triplet -Right $startTriplet
        if ($null -ne $distanceFromStart -and $distanceFromStart -gt $maxDistanceFromStart) {
            $maxDistanceFromStart = $distanceFromStart
            $maxDistanceSampleIndex = $entry.SampleIndex
            $maxDistanceTriplet = $entry.Triplet
        }

        if ($null -ne $endTriplet) {
            $distanceToEnd = Get-TripletDistance -Left $entry.Triplet -Right $endTriplet
            if ($null -eq $minDistanceToEnd -or $distanceToEnd -lt $minDistanceToEnd) {
                $minDistanceToEnd = $distanceToEnd
                $minDistanceEndSampleIndex = $entry.SampleIndex
                $minDistanceEndTriplet = $entry.Triplet
            }
        }

        if ($entry.BytesHex -ne $previousBytesHex) {
            $changeEvents.Add([ordered]@{
                    SampleIndex = $entry.SampleIndex
                    Triplet = New-RoundedTriplet -Triplet $entry.Triplet
                }) | Out-Null

            if ($entry.SampleIndex -gt 0) {
                $responsiveSampleIndexes.Add($entry.SampleIndex) | Out-Null
            }

            $previousBytesHex = $entry.BytesHex
        }
    }

    $summary = $regionSummaryMap[$candidateName]
    $candidateResults.Add([ordered]@{
            Name = $candidateName
            Address = [string]$firstValue.Address
            ChangedSampleCount = if ($null -ne $summary) { [int]$summary.ChangedSampleCount } else { [Math]::Max(0, $changeEvents.Count - 1) }
            DistinctValueCount = $distinctBytesHex.Count
            FirstTriplet = New-RoundedTriplet -Triplet $firstValue.Triplet
            LastTriplet = New-RoundedTriplet -Triplet $lastValue.Triplet
            LastDistanceToStart = Get-TripletDistance -Left $lastValue.Triplet -Right $startTriplet
            LastDistanceToEnd = Get-TripletDistance -Left $lastValue.Triplet -Right $endTriplet
            MaxDistanceFromStart = if ($maxDistanceFromStart -lt 0) { $null } else { $maxDistanceFromStart }
            MaxDistanceSampleIndex = $maxDistanceSampleIndex
            MaxDistanceTriplet = if ($null -ne $maxDistanceTriplet) { New-RoundedTriplet -Triplet $maxDistanceTriplet } else { $null }
            MinDistanceToEnd = $minDistanceToEnd
            MinDistanceEndSampleIndex = $minDistanceEndSampleIndex
            MinDistanceEndTriplet = if ($null -ne $minDistanceEndTriplet) { New-RoundedTriplet -Triplet $minDistanceEndTriplet } else { $null }
            ChangeEvents = $changeEvents.ToArray()
        }) | Out-Null
}

$rankedByResponsiveness = @(
    $candidateResults |
    Sort-Object `
        @{ Expression = { [double]($_.MaxDistanceFromStart ?? -1) }; Descending = $true }, `
        @{ Expression = { [int]$_.ChangedSampleCount }; Descending = $true }, `
        @{ Expression = { [int]$_.DistinctValueCount }; Descending = $true }, `
        @{ Expression = { [string]$_.Name }; Descending = $false }
)

$rankedByEndProximity = @(
    $candidateResults |
    Sort-Object `
        @{ Expression = { if ($null -eq $_.MinDistanceToEnd) { [double]::PositiveInfinity } else { [double]$_.MinDistanceToEnd } }; Descending = $false }, `
        @{ Expression = { [double]($_.MaxDistanceFromStart ?? -1) }; Descending = $true }, `
        @{ Expression = { [string]$_.Name }; Descending = $false }
)

$responsiveWindow = if ($responsiveSampleIndexes.Count -gt 0) {
    [ordered]@{
        FirstResponsiveSampleIndex = ($responsiveSampleIndexes | Measure-Object -Minimum).Minimum
        LastResponsiveSampleIndex = ($responsiveSampleIndexes | Measure-Object -Maximum).Maximum
    }
}
else {
    $null
}

$bestEndCandidate = if ($rankedByEndProximity.Count -gt 0) { $rankedByEndProximity[0] } else { $null }
$bestResponsiveCandidate = if ($rankedByResponsiveness.Count -gt 0) { $rankedByResponsiveness[0] } else { $null }
$matchedEndCandidate = $false
if ($null -ne $bestEndCandidate -and $null -ne $bestEndCandidate.MinDistanceToEnd) {
    $matchedEndCandidate = ([double]$bestEndCandidate.MinDistanceToEnd -le 1.0)
}

$analysis = [ordered]@{
    Mode = 'player-live-coord-session-analysis'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    SessionDirectory = $resolvedSessionDirectory
    ManifestFile = $manifestFile
    SamplesFile = $samplesFile
    StartArtifactFile = $startArtifactFile
    EndArtifactFile = if ($null -ne $endArtifact) { $endArtifactFile } else { $null }
    SampleCount = $samples.Count
    IntervalMilliseconds = [int]$manifest.IntervalMilliseconds
    Start = [ordered]@{
        Location = [string]$startArtifact.Snapshot.Player.Location
        Triplet = New-RoundedTriplet -Triplet $startTriplet
        SelectedAddress = [string]$startArtifact.Selected.Hit.AddressHex
    }
    End = if ($null -ne $endArtifact) {
        [ordered]@{
            Location = [string]$endArtifact.Snapshot.Player.Location
            Triplet = New-RoundedTriplet -Triplet $endTriplet
            SelectedAddress = [string]$endArtifact.Selected.Hit.AddressHex
        }
    }
    else {
        $null
    }
    ResponsiveWindow = $responsiveWindow
    BestResponsiveCandidate = $bestResponsiveCandidate
    BestEndProximityCandidate = $bestEndCandidate
    MatchedEndCandidate = $matchedEndCandidate
    RankedByResponsiveness = $rankedByResponsiveness
    RankedByEndProximity = $rankedByEndProximity
}

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$analysisJson = $analysis | ConvertTo-Json -Depth 16
[System.IO.File]::WriteAllText($resolvedOutputFile, $analysisJson, [System.Text.UTF8Encoding]::new($false))

if ($Json) {
    $analysisJson
    exit 0
}

Write-Host "Player live coord session analysis complete." -ForegroundColor Green
Write-Host ("Session directory:         {0}" -f $resolvedSessionDirectory)
Write-Host ("Sample count:              {0}" -f $samples.Count)
Write-Host ("Interval (ms):             {0}" -f [int]$manifest.IntervalMilliseconds)
Write-Host ("Start:                     {0} @ {1}" -f [string]$startArtifact.Snapshot.Player.Location, (Format-TripletText -Triplet $startTriplet))
if ($null -ne $endArtifact) {
    Write-Host ("End:                       {0} @ {1}" -f [string]$endArtifact.Snapshot.Player.Location, (Format-TripletText -Triplet $endTriplet))
}
if ($null -ne $responsiveWindow) {
    Write-Host ("Responsive window:         samples {0}..{1}" -f $responsiveWindow.FirstResponsiveSampleIndex, $responsiveWindow.LastResponsiveSampleIndex)
}
if ($null -ne $bestResponsiveCandidate) {
    Write-Host ("Best responsive candidate: {0} ({1}) max drift {2}" -f $bestResponsiveCandidate.Name, $bestResponsiveCandidate.Address, $bestResponsiveCandidate.MaxDistanceFromStart)
}
if ($null -ne $bestEndCandidate) {
    Write-Host ("Best end candidate:        {0} ({1}) min end distance {2}" -f $bestEndCandidate.Name, $bestEndCandidate.Address, $bestEndCandidate.MinDistanceToEnd)
}
Write-Host ("Matched end candidate:     {0}" -f $(if ($matchedEndCandidate) { 'yes' } else { 'no' }))
Write-Host ("Output file:               {0}" -f $resolvedOutputFile)
