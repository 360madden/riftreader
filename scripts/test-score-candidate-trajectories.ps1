[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

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

function Assert-Equal {
    param(
        $Actual,
        $Expected,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if ($Actual -ne $Expected) {
        throw ("{0} Expected '{1}', got '{2}'." -f $Message, $Expected, $Actual)
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$scoreScript = Join-Path $repoRoot 'scripts\score-candidate-trajectories.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-candidate-trajectory-' + [Guid]::NewGuid().ToString('N'))
$truthCsv = Join-Path $tempRoot 'truth.csv'
$memoryCsv = Join-Path $tempRoot 'memory-timeseries.csv'
$outputFile = Join-Path $tempRoot 'candidate-trajectory-scores.json'
$explicitSamplesOutputFile = Join-Path $tempRoot 'candidate-trajectory-scores-explicit-samples.json'
$memoryDirectory = Join-Path $tempRoot 'memory'
$directoryOutputFile = Join-Path $tempRoot 'candidate-trajectory-scores-from-directory.json'
$flattenedCsv = Join-Path $tempRoot 'flattened-memory-timeseries.csv'

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    @'
sample,x,y,z,source
1,100.0,50.0,200.0,synthetic-truth
2,101.0,50.0,200.2,synthetic-truth
3,102.0,50.0,200.4,synthetic-truth
4,102.0,50.0,200.4,synthetic-truth
5,102.0,50.0,200.4,synthetic-truth
'@ | Set-Content -LiteralPath $truthCsv -Encoding UTF8

    @'
sampleIndex,candidateId,addressHex,source,x,y,z
1,good,0xGOOD,synthetic,100.0,50.0,200.0
2,good,0xGOOD,synthetic,101.0,50.0,200.2
3,good,0xGOOD,synthetic,102.0,50.0,200.4
4,good,0xGOOD,synthetic,102.0,50.0,200.4
5,good,0xGOOD,synthetic,102.0,50.0,200.4
1,static,0xSTATIC,synthetic,100.0,50.0,200.0
2,static,0xSTATIC,synthetic,100.0,50.0,200.0
3,static,0xSTATIC,synthetic,100.0,50.0,200.0
4,static,0xSTATIC,synthetic,100.0,50.0,200.0
5,static,0xSTATIC,synthetic,100.0,50.0,200.0
1,wrong-origin,0xWRONG,synthetic,500.0,10.0,900.0
2,wrong-origin,0xWRONG,synthetic,501.0,10.0,900.2
3,wrong-origin,0xWRONG,synthetic,502.0,10.0,900.4
4,wrong-origin,0xWRONG,synthetic,502.0,10.0,900.4
5,wrong-origin,0xWRONG,synthetic,502.0,10.0,900.4
1,drift-tail,0xDRIFT,synthetic,100.0,50.0,200.0
2,drift-tail,0xDRIFT,synthetic,101.0,50.0,200.2
3,drift-tail,0xDRIFT,synthetic,102.0,50.0,200.4
4,drift-tail,0xDRIFT,synthetic,102.5,50.0,200.9
5,drift-tail,0xDRIFT,synthetic,103.0,50.0,201.4
'@ | Set-Content -LiteralPath $memoryCsv -Encoding UTF8

    $scoreOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $scoreScript `
        -TruthCsv $truthCsv `
        -MemoryTimeseriesCsv $memoryCsv `
        -OutputFile $outputFile `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected trajectory scoring to pass: {0}" -f ($scoreOutput -join [Environment]::NewLine))

    $result = ($scoreOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 64
    Assert-Equal -Actual ([string]$result.status) -Expected 'complete' -Message 'Scorer status mismatch.'
    Assert-Equal -Actual ([string]$result.bestCandidate.candidateId) -Expected 'good' -Message 'Expected exact trajectory candidate to rank first.'
    Assert-Equal -Actual ([string]$result.bestCandidate.classification) -Expected 'trajectory-match' -Message 'Best candidate classification mismatch.'
    Assert-True -Condition ([bool]$result.promotionReady) -Message 'Expected synthetic exact candidate to be promotion-ready.'

    $staticCandidate = @($result.candidates | Where-Object { $_.candidateId -eq 'static' })[0]
    Assert-Equal -Actual ([string]$staticCandidate.classification) -Expected 'static-cache' -Message 'Static candidate classification mismatch.'

    $wrongOriginCandidate = @($result.candidates | Where-Object { $_.candidateId -eq 'wrong-origin' })[0]
    Assert-Equal -Actual ([string]$wrongOriginCandidate.classification) -Expected 'movement-shape-only-wrong-origin' -Message 'Wrong-origin candidate classification mismatch.'

    $driftCandidate = @($result.candidates | Where-Object { $_.candidateId -eq 'drift-tail' })[0]
    Assert-Equal -Actual ([string]$driftCandidate.classification) -Expected 'stationary-tail-drift' -Message 'Stationary drift candidate classification mismatch.'

    $explicitSamplesOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $scoreScript `
        -TruthCsv $truthCsv `
        -MemoryTimeseriesCsv $memoryCsv `
        -OutputFile $explicitSamplesOutputFile `
        -MovementSamples 1,2,3 `
        -StationarySamples 4,5 `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected explicit sample scoring to pass: {0}" -f ($explicitSamplesOutput -join [Environment]::NewLine))
    $explicitSamplesResult = ($explicitSamplesOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 64
    Assert-Equal -Actual (([string[]]@($explicitSamplesResult.movementSamples)) -join ',') -Expected '1,2,3' -Message 'Explicit movement samples were not parsed as separate indices.'
    Assert-Equal -Actual (([string[]]@($explicitSamplesResult.stationarySamples)) -join ',') -Expected '4,5' -Message 'Explicit stationary samples were not parsed as separate indices.'

    New-Item -ItemType Directory -Path $memoryDirectory -Force | Out-Null
    $memorySample1 = [ordered]@{
        schema = 'test'
        sampleIndex = 1
        reads = @(
            [ordered]@{
                addressHex = '0xGOOD'
                source = 'directory'
                ok = $true
                values = [ordered]@{ x = 100.0; y = 50.0; z = 200.0 }
            }
        )
    }
    $memorySample2 = [ordered]@{
        schema = 'test'
        sampleIndex = 2
        reads = @(
            [ordered]@{
                addressHex = '0xGOOD'
                source = 'directory'
                ok = $true
                values = [ordered]@{ x = 101.0; y = 50.0; z = 200.2 }
            }
        )
    }
    $memorySample3 = [ordered]@{
        schema = 'test'
        sampleIndex = 3
        reads = @(
            [ordered]@{
                addressHex = '0xGOOD'
                source = 'directory'
                ok = $true
                values = [ordered]@{ x = 102.0; y = 50.0; z = 200.4 }
            }
        )
    }
    Set-Content -LiteralPath (Join-Path $memoryDirectory 'sample-0001-memory.json') -Value ($memorySample1 | ConvertTo-Json -Depth 16) -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $memoryDirectory 'sample-0002-memory.json') -Value ($memorySample2 | ConvertTo-Json -Depth 16) -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $memoryDirectory 'sample-0003-memory.json') -Value ($memorySample3 | ConvertTo-Json -Depth 16) -Encoding UTF8

    $directoryScoreOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $scoreScript `
        -TruthCsv $truthCsv `
        -MemoryDirectory $memoryDirectory `
        -FlattenedMemoryTimeseriesCsv $flattenedCsv `
        -OutputFile $directoryOutputFile `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected directory trajectory scoring to pass: {0}" -f ($directoryScoreOutput -join [Environment]::NewLine))
    Assert-True -Condition (Test-Path -LiteralPath $flattenedCsv) -Message 'Expected flattened memory-timeseries CSV to be written.'
    $directoryResult = ($directoryScoreOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 64
    Assert-Equal -Actual ([string]$directoryResult.bestCandidate.candidateId) -Expected '0xGOOD' -Message 'Directory scorer candidate mismatch.'
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host 'candidate trajectory scorer regression check passed.' -ForegroundColor Green
