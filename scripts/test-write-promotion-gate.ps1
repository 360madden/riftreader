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
$gateScript = Join-Path $repoRoot 'scripts\write-promotion-gate.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-promotion-gate-' + [Guid]::NewGuid().ToString('N'))
$passingScoresFile = Join-Path $tempRoot 'passing-candidate-trajectory-scores.json'
$passingGateFile = Join-Path $tempRoot 'passing-promotion-gate.json'
$failingScoresFile = Join-Path $tempRoot 'failing-candidate-trajectory-scores.json'
$failingGateFile = Join-Path $tempRoot 'failing-promotion-gate.json'
$truthSurfaceFile = Join-Path $tempRoot 'truth-surface.json'
$badTruthSurfaceFile = Join-Path $tempRoot 'bad-truth-surface.json'
$badTruthSurfaceGateFile = Join-Path $tempRoot 'bad-truth-surface-promotion-gate.json'
$savedVariablesFreshnessFile = Join-Path $tempRoot 'savedvariables-freshness.json'

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $passingCandidate = [ordered]@{
        rank = 1
        candidateId = '0xGOOD'
        addressHex = '0xGOOD'
        classification = 'trajectory-match'
        score = 99.5
        comparedSampleCount = 5
        missingSampleCount = 0
        absoluteRmse = 0.05
        deltaRmse = 0.03
        stationaryDriftMax = 0.0
        reasons = @('synthetic pass')
    }
    $passingScores = [ordered]@{
        schemaVersion = 1
        mode = 'candidate-trajectory-scores'
        status = 'complete'
        promotionReady = $true
        bestCandidate = $passingCandidate
        candidates = @($passingCandidate)
    }
    Set-Content -LiteralPath $passingScoresFile -Value ($passingScores | ConvertTo-Json -Depth 32) -Encoding UTF8

    $truthSurface = [ordered]@{
        schemaVersion = 1
        mode = 'truth-surface'
        authoritativeTruthSurface = 'overlay-screenshot-manual-extract'
        savedVariablesUsableAsLiveTruth = $false
    }
    Set-Content -LiteralPath $truthSurfaceFile -Value ($truthSurface | ConvertTo-Json -Depth 16) -Encoding UTF8

    $freshness = [ordered]@{
        schemaVersion = 1
        mode = 'savedvariables-freshness'
        freshnessClassification = 'stale-post-save-snapshot'
        usableAsLiveTruth = $false
    }
    Set-Content -LiteralPath $savedVariablesFreshnessFile -Value ($freshness | ConvertTo-Json -Depth 16) -Encoding UTF8

    $passingOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $gateScript `
        -CandidateScoresFile $passingScoresFile `
        -TruthSurfaceFile $truthSurfaceFile `
        -SavedVariablesFreshnessFile $savedVariablesFreshnessFile `
        -OutputFile $passingGateFile `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected passing promotion gate to succeed: {0}" -f ($passingOutput -join [Environment]::NewLine))
    $passingResult = ($passingOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 64
    Assert-Equal -Actual ([string]$passingResult.status) -Expected 'pass' -Message 'Passing gate status mismatch.'
    Assert-Equal -Actual ([bool]$passingResult.promotionAllowed) -Expected $true -Message 'Passing gate promotionAllowed mismatch.'
    Assert-True -Condition (Test-Path -LiteralPath $passingGateFile) -Message 'Passing gate file was not written.'

    Set-Content -LiteralPath $badTruthSurfaceFile -Value ([ordered]@{
            schemaVersion = 1
            mode = 'truth-surface'
            authoritativeTruthSurface = 'candidate-memory'
            savedVariablesUsableAsLiveTruth = $false
        } | ConvertTo-Json -Depth 16) -Encoding UTF8

    $badTruthSurfaceOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $gateScript `
        -CandidateScoresFile $passingScoresFile `
        -TruthSurfaceFile $badTruthSurfaceFile `
        -SavedVariablesFreshnessFile $savedVariablesFreshnessFile `
        -OutputFile $badTruthSurfaceGateFile `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected disallowed truth-surface promotion gate to fail.'
    $badTruthSurfaceResult = ($badTruthSurfaceOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 64
    Assert-Equal -Actual ([string]$badTruthSurfaceResult.status) -Expected 'fail' -Message 'Bad truth-surface gate status mismatch.'
    Assert-True -Condition (@($badTruthSurfaceResult.failures | Where-Object { $_ -like '*Authoritative truth surface must be one of*' }).Count -gt 0) -Message 'Expected allowed truth-surface failure.'

    $failingCandidate = [ordered]@{
        rank = 1
        candidateId = '0xSTATIC'
        addressHex = '0xSTATIC'
        classification = 'static-cache'
        score = 20.0
        comparedSampleCount = 5
        missingSampleCount = 0
        absoluteRmse = 150.0
        deltaRmse = 0.5
        stationaryDriftMax = 0.0
        reasons = @('Truth moved, but candidate never changed.')
    }
    $failingScores = [ordered]@{
        schemaVersion = 1
        mode = 'candidate-trajectory-scores'
        status = 'complete'
        promotionReady = $false
        bestCandidate = $failingCandidate
        candidates = @($failingCandidate)
    }
    Set-Content -LiteralPath $failingScoresFile -Value ($failingScores | ConvertTo-Json -Depth 32) -Encoding UTF8

    $failingOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $gateScript `
        -CandidateScoresFile $failingScoresFile `
        -TruthSurfaceFile $truthSurfaceFile `
        -SavedVariablesFreshnessFile $savedVariablesFreshnessFile `
        -OutputFile $failingGateFile `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected static-cache promotion gate to fail.'
    $failingResult = ($failingOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 64
    Assert-Equal -Actual ([string]$failingResult.status) -Expected 'fail' -Message 'Failing gate status mismatch.'
    Assert-Equal -Actual ([bool]$failingResult.promotionAllowed) -Expected $false -Message 'Failing gate promotionAllowed mismatch.'
    Assert-True -Condition (@($failingResult.failures | Where-Object { $_ -like '*promotionReady=true*' }).Count -gt 0) -Message 'Expected promotionReady failure.'
    Assert-True -Condition (@($failingResult.failures | Where-Object { $_ -like '*classification must be trajectory-match*' }).Count -gt 0) -Message 'Expected classification failure.'
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host 'promotion gate regression check passed.' -ForegroundColor Green
