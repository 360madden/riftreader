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
$summaryScript = Join-Path $repoRoot 'scripts\summarize-promotion-gate.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-promotion-summary-' + [Guid]::NewGuid().ToString('N'))
$scoresFile = Join-Path $tempRoot 'candidate-trajectory-scores.json'
$gateFile = Join-Path $tempRoot 'promotion-gate.json'
$summaryJsonFile = Join-Path $tempRoot 'promotion-gate-summary.json'
$summaryMarkdownFile = Join-Path $tempRoot 'promotion-gate-summary.md'

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $scores = [ordered]@{
        status = 'complete'
        promotionReady = $false
        truthSampleCount = 5
        memoryRecordCount = 10
        candidateCount = 2
        bestCandidate = [ordered]@{
            candidateId = 'static'
            addressHex = '0xSTATIC'
            classification = 'static-cache'
            score = 20.0
            comparedSampleCount = 5
            missingSampleCount = 0
            absoluteRmse = 123.4
            deltaRmse = 0.1
            stationaryDriftMax = 0.0
        }
    }
    Set-Content -LiteralPath $scoresFile -Value ($scores | ConvertTo-Json -Depth 16) -Encoding UTF8

    $gate = [ordered]@{
        status = 'fail'
        promotionAllowed = $false
        candidateScoresFile = $scoresFile
        selectedCandidateId = 'static'
        selectedCandidate = $scores.bestCandidate
        failures = @(
            'Candidate scores document must have promotionReady=true.',
            'Selected candidate classification must be trajectory-match; actual=static-cache.'
        )
        warnings = @()
    }
    Set-Content -LiteralPath $gateFile -Value ($gate | ConvertTo-Json -Depth 16) -Encoding UTF8

    $output = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $summaryScript `
        -PromotionGateFile $gateFile `
        -OutputJsonFile $summaryJsonFile `
        -OutputMarkdownFile $summaryMarkdownFile `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected promotion summary to pass: {0}" -f ($output -join [Environment]::NewLine))
    $result = ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32

    Assert-Equal -Actual ([bool]$result.promotionAllowed) -Expected $false -Message 'Promotion flag mismatch.'
    Assert-Equal -Actual ([string]$result.gateStatus) -Expected 'fail' -Message 'Gate status mismatch.'
    Assert-Equal -Actual ([string]$result.scoreStatus) -Expected 'complete' -Message 'Score status mismatch.'
    Assert-Equal -Actual ([string]$result.selectedCandidateId) -Expected 'static' -Message 'Selected candidate mismatch.'
    Assert-Equal -Actual ([string]$result.classification) -Expected 'static-cache' -Message 'Classification mismatch.'
    Assert-Equal -Actual ([double]$result.score) -Expected 20.0 -Message 'Score mismatch.'
    Assert-Equal -Actual ([int]$result.truthSampleCount) -Expected 5 -Message 'Truth sample count mismatch.'
    Assert-True -Condition (Test-Path -LiteralPath $summaryJsonFile) -Message 'Summary JSON file missing.'
    Assert-True -Condition (Test-Path -LiteralPath $summaryMarkdownFile) -Message 'Summary markdown file missing.'
    $markdown = Get-Content -LiteralPath $summaryMarkdownFile -Raw
    Assert-True -Condition ($markdown -like '*Promotion gate summary*') -Message 'Markdown title missing.'
    Assert-True -Condition ($markdown -like '*static-cache*') -Message 'Markdown classification missing.'
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host 'promotion gate summary regression check passed.' -ForegroundColor Green
