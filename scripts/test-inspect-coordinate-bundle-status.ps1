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
$script = Join-Path $repoRoot 'scripts\inspect-coordinate-bundle-status.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-coordinate-bundle-status-' + [Guid]::NewGuid().ToString('N'))
$blockedBundle = Join-Path $tempRoot 'blocked'
$awaitingBundle = Join-Path $tempRoot 'awaiting'

New-Item -ItemType Directory -Path $blockedBundle -Force | Out-Null
New-Item -ItemType Directory -Path $awaitingBundle -Force | Out-Null

try {
    Set-Content -LiteralPath (Join-Path $blockedBundle 'candidate-trajectory-scores.json') -Value (@{
            status = 'complete'
            promotionReady = $false
            truthSampleCount = 5
            memoryRecordCount = 10
            candidateCount = 1
            bestCandidate = @{
                candidateId = 'static'
                classification = 'static-cache'
                score = 20.0
            }
        } | ConvertTo-Json -Depth 16) -Encoding UTF8

    Set-Content -LiteralPath (Join-Path $blockedBundle 'promotion-gate.json') -Value (@{
            status = 'fail'
            promotionAllowed = $false
            selectedCandidateId = 'static'
            selectedCandidate = @{
                candidateId = 'static'
                classification = 'static-cache'
                score = 20.0
            }
            failures = @('Selected candidate classification must be trajectory-match; actual=static-cache.')
            warnings = @()
        } | ConvertTo-Json -Depth 16) -Encoding UTF8

    Set-Content -LiteralPath (Join-Path $blockedBundle 'promotion-gate-summary.json') -Value (@{
            gateStatus = 'fail'
            promotionAllowed = $false
            scoreStatus = 'complete'
            promotionReady = $false
            selectedCandidateId = 'static'
            classification = 'static-cache'
            score = 20.0
            truthSampleCount = 5
            memoryRecordCount = 10
            candidateCount = 1
            failures = @('Selected candidate classification must be trajectory-match; actual=static-cache.')
            warnings = @()
        } | ConvertTo-Json -Depth 16) -Encoding UTF8

    Set-Content -LiteralPath (Join-Path $blockedBundle 'truth-surface.json') -Value (@{
            authoritativeTruthSurface = 'overlay-screenshot-manual-extract'
            savedVariablesUse = 'backup-only'
            savedVariablesUsableAsLiveTruth = $false
        } | ConvertTo-Json -Depth 16) -Encoding UTF8

    Set-Content -LiteralPath (Join-Path $blockedBundle 'savedvariables-freshness.json') -Value (@{
            freshnessClassification = 'stale-post-save-snapshot'
            usableAsLiveTruth = $false
        } | ConvertTo-Json -Depth 16) -Encoding UTF8

    $blockedOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $script -BundleDirectory $blockedBundle -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected blocked bundle inspection to pass: {0}" -f ($blockedOutput -join [Environment]::NewLine))
    $blocked = ($blockedOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$blocked.status) -Expected 'promotion-blocked' -Message 'Blocked status mismatch.'
    Assert-Equal -Actual ([bool]$blocked.promotion.allowed) -Expected $false -Message 'Blocked promotion flag mismatch.'
    Assert-Equal -Actual ([string]$blocked.promotion.classification) -Expected 'static-cache' -Message 'Blocked classification mismatch.'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $blockedBundle 'coordinate-bundle-status.json')) -Message 'Blocked status JSON missing.'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $blockedBundle 'coordinate-bundle-status.md')) -Message 'Blocked status markdown missing.'

    $awaitingOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $script -BundleDirectory $awaitingBundle -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected awaiting bundle inspection to pass: {0}" -f ($awaitingOutput -join [Environment]::NewLine))
    $awaiting = ($awaitingOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$awaiting.status) -Expected 'awaiting-live-truth' -Message 'Awaiting status mismatch.'
    Assert-True -Condition (@($awaiting.blockers | Where-Object { $_ -like '*No live-coords.ndjson*' }).Count -gt 0) -Message 'Expected live truth blocker.'
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host 'coordinate bundle status regression check passed.' -ForegroundColor Green
