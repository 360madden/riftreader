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
$validatorScript = Join-Path $repoRoot 'scripts\validate-current-actor-truth.ps1'
$currentTruthFile = Join-Path $repoRoot 'docs\recovery\current-actor-truth.json'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-current-actor-truth-validator-' + [System.Guid]::NewGuid().ToString('N'))
$tempTruthFile = Join-Path $tempRoot 'current-actor-truth.invalid.json'
$liveTargetSnapshotFile = Join-Path $tempRoot 'live-target.snapshot.json'
$staleLiveTargetSnapshotFile = Join-Path $tempRoot 'live-target.stale.snapshot.json'

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $passOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $validatorScript -TruthFile $currentTruthFile -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected current truth validation to pass: {0}" -f ($passOutput -join [Environment]::NewLine))
    $passResult = ($passOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
    Assert-Equal -Actual ([string]$passResult.status) -Expected 'pass' -Message 'Current truth validation status mismatch.'

    $document = Get-Content -LiteralPath $currentTruthFile -Raw | ConvertFrom-Json -Depth 80
    $targetProcessStartTimeUtc = if ($document.target.processStartTimeUtc -is [DateTime]) {
        $document.target.processStartTimeUtc.ToUniversalTime().ToString('o', [System.Globalization.CultureInfo]::InvariantCulture)
    }
    else {
        [string]$document.target.processStartTimeUtc
    }

    $liveTargetSnapshot = [ordered]@{
        processName = [string]$document.target.processName
        processId = [int]$document.target.processId
        processStartTimeUtc = $targetProcessStartTimeUtc
        targetWindowHandle = [string]$document.target.targetWindowHandle
        mainWindowTitle = 'RIFT'
    }
    Set-Content -LiteralPath $liveTargetSnapshotFile -Value ($liveTargetSnapshot | ConvertTo-Json -Depth 10) -Encoding UTF8

    $livePassOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $validatorScript -TruthFile $currentTruthFile -LiveTargetSnapshotFile $liveTargetSnapshotFile -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected live target snapshot validation to pass: {0}" -f ($livePassOutput -join [Environment]::NewLine))
    $livePassResult = ($livePassOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
    Assert-Equal -Actual ([string]$livePassResult.status) -Expected 'pass' -Message 'Live target snapshot validation status mismatch.'
    Assert-Equal -Actual ([string]$livePassResult.liveTargetCheck.status) -Expected 'pass' -Message 'Live target check status mismatch.'

    $staleLiveTargetSnapshot = [ordered]@{
        processName = [string]$document.target.processName
        processId = [int]$document.target.processId
        processStartTimeUtc = '2000-01-01T00:00:00.0000000Z'
        targetWindowHandle = '0xDEAD'
        mainWindowTitle = 'RIFT'
    }
    Set-Content -LiteralPath $staleLiveTargetSnapshotFile -Value ($staleLiveTargetSnapshot | ConvertTo-Json -Depth 10) -Encoding UTF8

    $liveFailureOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $validatorScript -TruthFile $currentTruthFile -LiveTargetSnapshotFile $staleLiveTargetSnapshotFile -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected stale live target snapshot validation to fail.'
    $liveFailureResult = ($liveFailureOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
    Assert-Equal -Actual ([string]$liveFailureResult.status) -Expected 'fail' -Message 'Stale live target validation status mismatch.'
    Assert-Equal -Actual ([string]$liveFailureResult.liveTargetCheck.status) -Expected 'fail' -Message 'Stale live target check status mismatch.'
    Assert-True -Condition (@($liveFailureResult.failures | Where-Object { $_ -like '*processStartTimeUtc mismatch*' }).Count -gt 0) -Message 'Stale live target validation did not report the process start-time mismatch.'
    Assert-True -Condition (@($liveFailureResult.failures | Where-Object { $_ -like '*targetWindowHandle mismatch*' }).Count -gt 0) -Message 'Stale live target validation did not report the HWND mismatch.'

    $document.coordinate.requiredWatchsetRegion.address = '0xDEADBEEF'
    Set-Content -LiteralPath $tempTruthFile -Value ($document | ConvertTo-Json -Depth 80) -Encoding UTF8

    $failureOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $validatorScript -TruthFile $tempTruthFile -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected corrupted truth packet validation to fail.'
    $failureResult = ($failureOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
    Assert-Equal -Actual ([string]$failureResult.status) -Expected 'fail' -Message 'Corrupted truth validation status mismatch.'
    Assert-True -Condition (@($failureResult.failures | Where-Object { $_ -like '*requiredWatchsetRegion.address*' }).Count -gt 0) -Message 'Corrupted truth validation did not report the watchset address mismatch.'
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host 'current actor truth validator regression check passed.' -ForegroundColor Green
