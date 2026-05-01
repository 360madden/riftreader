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
$runnerScript = Join-Path $repoRoot 'scripts\run-candidate-trajectory-gate.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-candidate-trajectory-gate-' + [Guid]::NewGuid().ToString('N'))
$truthCsv = Join-Path $tempRoot 'truth.csv'
$passMemoryCsv = Join-Path $tempRoot 'memory-pass.csv'
$failMemoryCsv = Join-Path $tempRoot 'memory-fail.csv'
$passBundle = Join-Path $tempRoot 'pass-bundle'
$failBundle = Join-Path $tempRoot 'fail-bundle'
$truthSurfaceFile = Join-Path $tempRoot 'truth-surface.json'
$savedVariablesFreshnessFile = Join-Path $tempRoot 'savedvariables-freshness.json'

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
'@ | Set-Content -LiteralPath $passMemoryCsv -Encoding UTF8

    @'
sampleIndex,candidateId,addressHex,source,x,y,z
1,static,0xSTATIC,synthetic,100.0,50.0,200.0
2,static,0xSTATIC,synthetic,100.0,50.0,200.0
3,static,0xSTATIC,synthetic,100.0,50.0,200.0
4,static,0xSTATIC,synthetic,100.0,50.0,200.0
5,static,0xSTATIC,synthetic,100.0,50.0,200.0
'@ | Set-Content -LiteralPath $failMemoryCsv -Encoding UTF8

    Set-Content -LiteralPath $truthSurfaceFile -Value (@{
            authoritativeTruthSurface = 'overlay-screenshot-manual-extract'
        } | ConvertTo-Json -Depth 8) -Encoding UTF8

    Set-Content -LiteralPath $savedVariablesFreshnessFile -Value (@{
            freshnessClassification = 'stale-post-save-snapshot'
            usableAsLiveTruth = $false
        } | ConvertTo-Json -Depth 8) -Encoding UTF8

    $passOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $runnerScript `
        -TruthCsv $truthCsv `
        -MemoryTimeseriesCsv $passMemoryCsv `
        -BundleDirectory $passBundle `
        -TruthSurfaceFile $truthSurfaceFile `
        -SavedVariablesFreshnessFile $savedVariablesFreshnessFile `
        -MovementSamples 1,2,3 `
        -StationarySamples 4,5 `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected candidate trajectory gate runner pass: {0}" -f ($passOutput -join [Environment]::NewLine))
    $passResult = ($passOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
    Assert-Equal -Actual ([string]$passResult.status) -Expected 'pass' -Message 'Pass runner status mismatch.'
    Assert-Equal -Actual ([bool]$passResult.promotionAllowed) -Expected $true -Message 'Pass runner promotion flag mismatch.'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $passBundle 'candidate-trajectory-scores.json')) -Message 'Pass scores file missing.'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $passBundle 'promotion-gate.json')) -Message 'Pass promotion gate file missing.'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $passBundle 'promotion-gate-summary.json')) -Message 'Pass promotion summary JSON missing.'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $passBundle 'promotion-gate-summary.md')) -Message 'Pass promotion summary markdown missing.'
    Assert-Equal -Actual ([int]$passResult.summaryExitCode) -Expected 0 -Message 'Pass promotion summary exit code mismatch.'
    Assert-Equal -Actual ([bool]$passResult.promotionSummary.promotionAllowed) -Expected $true -Message 'Pass promotion summary flag mismatch.'
    $passScores = Get-Content -LiteralPath (Join-Path $passBundle 'candidate-trajectory-scores.json') -Raw | ConvertFrom-Json -Depth 80
    Assert-Equal -Actual (([string[]]@($passScores.movementSamples)) -join ',') -Expected '1,2,3' -Message 'Pass movement samples were not forwarded.'
    Assert-Equal -Actual (([string[]]@($passScores.stationarySamples)) -join ',') -Expected '4,5' -Message 'Pass stationary samples were not forwarded.'

    $failOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $runnerScript `
        -TruthCsv $truthCsv `
        -MemoryTimeseriesCsv $failMemoryCsv `
        -BundleDirectory $failBundle `
        -TruthSurfaceFile $truthSurfaceFile `
        -SavedVariablesFreshnessFile $savedVariablesFreshnessFile `
        -MovementSamples 1,2,3 `
        -StationarySamples 4,5 `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected static candidate gate runner to fail.'
    $failResult = ($failOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
    Assert-Equal -Actual ([string]$failResult.status) -Expected 'promotion-blocked' -Message 'Fail runner status mismatch.'
    Assert-Equal -Actual ([bool]$failResult.promotionAllowed) -Expected $false -Message 'Fail runner promotion flag mismatch.'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $failBundle 'promotion-gate-summary.json')) -Message 'Fail promotion summary JSON missing.'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $failBundle 'promotion-gate-summary.md')) -Message 'Fail promotion summary markdown missing.'
    Assert-Equal -Actual ([int]$failResult.summaryExitCode) -Expected 0 -Message 'Fail promotion summary exit code mismatch.'
    Assert-Equal -Actual ([bool]$failResult.promotionSummary.promotionAllowed) -Expected $false -Message 'Fail promotion summary flag mismatch.'
    Assert-True -Condition (@($failResult.gateFailures | Where-Object { $_ -like '*classification must be trajectory-match*' }).Count -gt 0) -Message 'Expected fail runner classification failure.'
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host 'candidate trajectory gate runner regression check passed.' -ForegroundColor Green
