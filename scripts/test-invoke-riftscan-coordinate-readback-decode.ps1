[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-Equal {
    param(
        [Parameter(Mandatory = $true)]
        $Actual,
        [Parameter(Mandatory = $true)]
        $Expected,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Assert-True {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$Condition,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function New-BytesHexWithVec3 {
    param(
        [Parameter(Mandatory = $true)]
        [single]$X,

        [Parameter(Mandatory = $true)]
        [single]$Y,

        [Parameter(Mandatory = $true)]
        [single]$Z,

        [Parameter(Mandatory = $true)]
        [int]$Offset,

        [int]$Length = 64
    )

    $bytes = New-Object byte[] $Length
    [Array]::Copy([BitConverter]::GetBytes($X), 0, $bytes, $Offset, 4)
    [Array]::Copy([BitConverter]::GetBytes($Y), 0, $bytes, ($Offset + 4), 4)
    [Array]::Copy([BitConverter]::GetBytes($Z), 0, $bytes, ($Offset + 8), 4)
    return (($bytes | ForEach-Object { $_.ToString('X2', [System.Globalization.CultureInfo]::InvariantCulture) }) -join '')
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$wrapper = Join-Path $repoRoot 'scripts\invoke-riftscan-coordinate-readback.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-riftscan-readback-decode-' + [System.Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $watchsetFile = Join-Path $tempRoot 'watchset.json'
    $samplesFile = Join-Path $tempRoot 'samples.ndjson'
    $referenceFile = Join-Path $tempRoot 'reference.json'
    $summaryFile = Join-Path $tempRoot 'summary.json'

    $watchset = [ordered]@{
        SchemaVersion = 1
        Mode = 'riftscan-coordinate-candidate-watchset'
        CandidateCount = 2
        NoCheatEngine = $true
        MovementAllowed = $false
        CanonicalCoordSource = 'none-candidate-watchset-only'
        Candidates = @(
            [ordered]@{
                CandidateId = 'vec3-000001'
                AbsoluteAddressHex = '0x1010'
                RegionAddressHex = '0x1000'
                RegionLength = 64
                ValuePreview = @(1.25, 2.5, 3.75)
                ValueSequenceSummary = 'samples=2;delta=0;preview=1.25|2.5|3.75'
            },
            [ordered]@{
                CandidateId = 'vec3-000002'
                AbsoluteAddressHex = '0x2014'
                RegionAddressHex = '0x2000'
                RegionLength = 64
                ValuePreview = @(-1.0, 0.5, 4.25)
                ValueSequenceSummary = 'samples=2;delta=0;preview=-1|0.5|4.25'
            }
        )
    }
    $watchset | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $watchsetFile -Encoding UTF8

    $sampleLines = @(
        ([ordered]@{
            SampleIndex = 0
            RecordedAtUtc = '2026-05-06T00:00:00.0000000+00:00'
            Regions = @(
                [ordered]@{
                    Name = 'riftscan-vec3-vec3-000001'
                    ReadSucceeded = $true
                    BytesHex = New-BytesHexWithVec3 -X 1.25 -Y 2.5 -Z 3.75 -Offset 16
                },
                [ordered]@{
                    Name = 'riftscan-vec3-vec3-000002'
                    ReadSucceeded = $true
                    BytesHex = New-BytesHexWithVec3 -X -1.0 -Y 0.5 -Z 4.25 -Offset 20
                }
            )
        } | ConvertTo-Json -Depth 20 -Compress),
        ([ordered]@{
            SampleIndex = 1
            RecordedAtUtc = '2026-05-06T00:00:00.1000000+00:00'
            Regions = @(
                [ordered]@{
                    Name = 'riftscan-vec3-vec3-000001'
                    ReadSucceeded = $true
                    BytesHex = New-BytesHexWithVec3 -X 1.25 -Y 2.5 -Z 3.75 -Offset 16
                },
                [ordered]@{
                    Name = 'riftscan-vec3-vec3-000002'
                    ReadSucceeded = $true
                    BytesHex = New-BytesHexWithVec3 -X -1.0 -Y 0.5 -Z 4.25 -Offset 20
                }
            )
        } | ConvertTo-Json -Depth 20 -Compress)
    )
    Set-Content -LiteralPath $samplesFile -Value $sampleLines -Encoding UTF8

    $reference = [ordered]@{
        source = 'fixture-reference-file'
        captured_at_utc = [DateTimeOffset]::UtcNow.ToString('O')
        tolerance = 0.001
        coordinate = [ordered]@{
            x = 1.25
            y = 2.5
            z = 3.75
        }
    }
    $reference | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $referenceFile -Encoding UTF8

    & $wrapper `
        -DecodeOnlyWatchsetFile $watchsetFile `
        -DecodeOnlySamplesFile $samplesFile `
        -DecodeOnlyOutputFile $summaryFile `
        -ReferenceFile $referenceFile `
        -ReferenceMaxAgeSeconds 3600 `
        -TopReferenceMatches 1 `
        -Json | Out-Null

    $summary = Get-Content -LiteralPath $summaryFile -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal -Actual $summary.Mode -Expected 'riftscan-riftreader-readback-decode' -Message 'Unexpected decode-only mode.'
    Assert-True -Condition ([bool]$summary.NoCheatEngine) -Message 'Decode-only summary must mark NoCheatEngine=true.'
    Assert-True -Condition (-not [bool]$summary.MovementSent) -Message 'Decode-only summary must not report movement.'
    Assert-True -Condition (-not [bool]$summary.MovementAllowed) -Message 'Decode-only summary must not allow movement.'
    Assert-Equal -Actual $summary.CandidateCount -Expected 2 -Message 'Candidate count should match fixture watchset.'
    Assert-Equal -Actual $summary.DecodedCandidateCount -Expected 2 -Message 'Both fixture candidates should decode.'
    Assert-Equal -Actual $summary.StableDecodedCandidateCount -Expected 2 -Message 'Both fixture candidates should be stable.'
    Assert-Equal -Actual $summary.SourcePreviewMatchCount -Expected 2 -Message 'Both fixture candidates should match source preview.'
    Assert-Equal -Actual $summary.ReferenceMatchCount -Expected 1 -Message 'Only one fixture candidate should match the supplied reference coordinate.'
    Assert-Equal -Actual $summary.ReferenceCoordinate.Source -Expected 'fixture-reference-file' -Message 'Reference source should be read from the reference file.'
    Assert-Equal -Actual $summary.ReferenceCoordinate.Tolerance -Expected 0.001 -Message 'Reference tolerance should be read from the reference file.'
    Assert-Equal -Actual $summary.ReferenceCoordinate.ReferenceFile -Expected ([System.IO.Path]::GetFullPath($referenceFile)) -Message 'Reference file path should be preserved.'
    Assert-Equal -Actual $summary.BestReferenceMatchLimit -Expected 1 -Message 'Best reference match limit should be preserved.'
    Assert-Equal -Actual $summary.BestReferenceMatchCount -Expected 1 -Message 'Best reference match list should honor the requested top count.'
    Assert-Equal -Actual $summary.BestReferenceMatches[0].CandidateId -Expected 'vec3-000001' -Message 'Best reference match should be the exact fixture candidate.'
    Assert-Equal -Actual $summary.BestReferenceMatches[0].Rank -Expected 1 -Message 'Best reference match rank should be one.'
    Assert-True -Condition ([bool]$summary.BestReferenceMatches[0].ReferenceMatchesReadback) -Message 'Best reference match should be within tolerance.'
    Assert-Equal -Actual $summary.BestReferenceMatches[0].FirstDecodedSample.X -Expected 1.25 -Message 'Best reference match should preserve first decoded sample.'

    $first = @($summary.CandidateReadbacks | Where-Object { $_.CandidateId -eq 'vec3-000001' })[0]
    Assert-Equal -Actual $first.DecodedSampleCount -Expected 2 -Message 'First fixture candidate should have two decoded samples.'
    Assert-Equal -Actual $first.CandidateOffsetInRegion -Expected 16 -Message 'First fixture candidate offset should be address minus region address.'
    Assert-Equal -Actual $first.DecodedSamples[0].X -Expected 1.25 -Message 'First fixture X decode mismatch.'
    Assert-Equal -Actual $first.DecodedSamples[0].Y -Expected 2.5 -Message 'First fixture Y decode mismatch.'
    Assert-Equal -Actual $first.DecodedSamples[0].Z -Expected 3.75 -Message 'First fixture Z decode mismatch.'
    Assert-True -Condition ([double]$first.MaxAbsDeltaAcrossReadbackSamples -eq 0.0) -Message 'First fixture should be stable across samples.'
    Assert-True -Condition ([bool]$first.SourcePreviewMatchesReadback) -Message 'First fixture should match source preview.'
    Assert-True -Condition ([bool]$first.ReferenceMatchesReadback) -Message 'First fixture should match the supplied reference coordinate.'
    Assert-True -Condition ([double]$first.ReferenceMaxAbsDelta -eq 0.0) -Message 'First fixture reference max abs delta should be zero.'

    $second = @($summary.CandidateReadbacks | Where-Object { $_.CandidateId -eq 'vec3-000002' })[0]
    Assert-True -Condition (-not [bool]$second.ReferenceMatchesReadback) -Message 'Second fixture should not match the supplied reference coordinate.'

    Write-Host 'RiftScan readback decode regression passed.' -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
