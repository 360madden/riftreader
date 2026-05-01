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
$metadataScript = Join-Path $repoRoot 'scripts\write-capture-metadata.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-capture-metadata-' + [Guid]::NewGuid().ToString('N'))

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $captureStart = [DateTimeOffset]::Parse('2026-04-30T18:25:38.0000000Z')
    $captureEnd = [DateTimeOffset]::Parse('2026-04-30T18:26:07.0000000Z')
    $savedVariablesFile = Join-Path $tempRoot 'ReaderBridgeExport.lua'
    Set-Content -LiteralPath $savedVariablesFile -Value '-- fake savedvariables snapshot' -Encoding UTF8
    (Get-Item -LiteralPath $savedVariablesFile).LastWriteTimeUtc = $captureStart.AddMinutes(-10).UtcDateTime

    $safeBundle = Join-Path $tempRoot 'safe-overlay'
    $safeOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $metadataScript `
        -BundleDirectory $safeBundle `
        -Label 'safe-overlay' `
        -Purpose 'regression test' `
        -TruthSurface overlay `
        -SavedVariablesUse seed-only `
        -SavedVariablesFilePath $savedVariablesFile `
        -CaptureStartUtc $captureStart.ToString('O') `
        -CaptureEndUtc $captureEnd.ToString('O') `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected overlay truth with stale seed-only SavedVariables to pass with warning: {0}" -f ($safeOutput -join [Environment]::NewLine))

    $safeResult = ($safeOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$safeResult.status) -Expected 'warning' -Message 'Safe metadata status mismatch.'
    $safeFreshness = Get-Content -LiteralPath (Join-Path $safeBundle 'savedvariables-freshness.json') -Raw | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$safeFreshness.freshnessClassification) -Expected 'stale-post-save-snapshot' -Message 'Expected stale freshness classification.'
    Assert-Equal -Actual ([bool]$safeFreshness.usableAsLiveTruth) -Expected $false -Message 'SavedVariables must not be usable as live truth.'

    $badBundle = Join-Path $tempRoot 'bad-savedvariables-live'
    $badOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $metadataScript `
        -BundleDirectory $badBundle `
        -Label 'bad-savedvariables-live' `
        -Purpose 'regression test' `
        -TruthSurface savedvariables-live `
        -SavedVariablesUse invalid-for-live `
        -SavedVariablesFilePath $savedVariablesFile `
        -CaptureStartUtc $captureStart.ToString('O') `
        -CaptureEndUtc $captureEnd.ToString('O') `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected SavedVariables-as-live quality gate to fail.'
    $badResult = ($badOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$badResult.status) -Expected 'fail' -Message 'Bad metadata status mismatch.'
    $badQualityGate = Get-Content -LiteralPath (Join-Path $badBundle 'quality-gate.json') -Raw | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$badQualityGate.status) -Expected 'fail' -Message 'Quality gate file did not record failure.'
    Assert-True -Condition (@($badQualityGate.failures | Where-Object { $_ -like '*SavedVariables cannot be used as a live truth surface*' }).Count -gt 0) -Message 'Expected explicit SavedVariables-as-live failure.'

    $freshSavedVariablesFile = Join-Path $tempRoot 'ReaderBridgeExport-post-flush.lua'
    Set-Content -LiteralPath $freshSavedVariablesFile -Value '-- fake post-flush savedvariables snapshot' -Encoding UTF8
    (Get-Item -LiteralPath $freshSavedVariablesFile).LastWriteTimeUtc = $captureEnd.AddSeconds(5).UtcDateTime

    $postFlushBundle = Join-Path $tempRoot 'post-flush'
    $postFlushOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $metadataScript `
        -BundleDirectory $postFlushBundle `
        -Label 'post-flush' `
        -Purpose 'regression test' `
        -TruthSurface post-flush-savedvariables `
        -SavedVariablesUse post-flush-snapshot `
        -SavedVariablesFilePath $freshSavedVariablesFile `
        -CaptureStartUtc $captureStart.ToString('O') `
        -CaptureEndUtc $captureEnd.ToString('O') `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected post-flush SavedVariables snapshot to pass when file is newer than capture end: {0}" -f ($postFlushOutput -join [Environment]::NewLine))
    $postFlushResult = ($postFlushOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$postFlushResult.status) -Expected 'pass' -Message 'Post-flush metadata status mismatch.'
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host 'capture metadata regression check passed.' -ForegroundColor Green
