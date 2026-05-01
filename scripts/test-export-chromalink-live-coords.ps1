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
$exportScript = Join-Path $repoRoot 'scripts\export-chromalink-live-coords.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-chromalink-live-coords-' + [Guid]::NewGuid().ToString('N'))
$snapshotFile = Join-Path $tempRoot 'chromalink-live-telemetry.json'
$worldStateFile = Join-Path $tempRoot 'chromalink-riftreader-world-state.json'
$outputFile = Join-Path $tempRoot 'live-coords.ndjson'
$worldStateOutputFile = Join-Path $tempRoot 'world-state-live-coords.ndjson'
$missingPositionSnapshotFile = Join-Path $tempRoot 'missing-player-position.json'

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $nowUtc = [DateTimeOffset]::UtcNow
    $observedAtUtc = $nowUtc.AddMilliseconds(-100)
    $snapshot = [ordered]@{
        artifactKind = 'live-telemetry'
        contract = [ordered]@{
            name = 'chromalink-live-telemetry'
            schemaVersion = 2
        }
        generatedAtUtc = $nowUtc.ToString('O')
        aggregate = [ordered]@{
            acceptedFrames = 42
            ready = $true
            healthy = $true
            stale = $false
            playerPosition = [ordered]@{
                observedAtUtc = $observedAtUtc.ToString('O')
                ageMs = 100.0
                fresh = $true
                stale = $false
                frameType = 'PlayerPosition'
                schemaId = 1
                sequence = 17
                reservedFlags = 2
                x = 7454.6
                y = 875.25
                z = 3052.75
            }
        }
    }
    Set-Content -LiteralPath $snapshotFile -Value ($snapshot | ConvertTo-Json -Depth 32) -Encoding UTF8

    $exportOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $exportScript `
        -SnapshotPath $snapshotFile `
        -OutputFile $outputFile `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected ChromaLink live coord export to pass: {0}" -f ($exportOutput -join [Environment]::NewLine))
    $exportResult = ($exportOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$exportResult.status) -Expected 'pass' -Message 'Export status mismatch.'
    Assert-Equal -Actual ([int]$exportResult.samplesWritten) -Expected 1 -Message 'Sample count mismatch.'

    $lines = @(Get-Content -LiteralPath $outputFile)
    Assert-Equal -Actual $lines.Count -Expected 1 -Message 'NDJSON line count mismatch.'
    $sample = $lines[0] | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$sample.source) -Expected 'chromalink-live-telemetry' -Message 'Sample source mismatch.'
    Assert-Equal -Actual ([int]$sample.sequence) -Expected 17 -Message 'Sample sequence mismatch.'
    Assert-Equal -Actual ([double]$sample.x) -Expected 7454.6 -Message 'Sample X mismatch.'
    Assert-Equal -Actual ([double]$sample.y) -Expected 875.25 -Message 'Sample Y mismatch.'
    Assert-Equal -Actual ([double]$sample.z) -Expected 3052.75 -Message 'Sample Z mismatch.'
    Assert-Equal -Actual ([bool]$sample.withinFreshWindow) -Expected $true -Message 'Sample freshness mismatch.'

    $worldState = [ordered]@{
        ok = $true
        artifactKind = 'riftreader-world-state'
        contract = [ordered]@{
            name = 'chromalink-riftreader-world-state'
            schemaVersion = 1
        }
        sourceContract = [ordered]@{
            name = 'chromalink-live-telemetry'
            schemaVersion = 2
        }
        ready = $true
        healthy = $true
        fresh = $true
        stale = $false
        snapshotAgeSeconds = 0.1
        snapshotPath = $snapshotFile
        navigation = [ordered]@{
            playerPositionAvailable = $true
            targetPositionAvailable = $false
            followUnitPositionsAvailable = $false
            headingAvailable = $false
            facingAvailable = $false
            routeAvailable = $false
            controlAvailable = $false
            limitations = @()
        }
        player = [ordered]@{
            position = [ordered]@{
                x = 7455.6
                y = 876.25
                z = 3053.75
                observedAtUtc = $observedAtUtc.ToString('O')
                ageMs = 100.0
                fresh = $true
                stale = $false
            }
        }
        target = $null
        followUnits = @()
    }
    Set-Content -LiteralPath $worldStateFile -Value ($worldState | ConvertTo-Json -Depth 32) -Encoding UTF8

    $worldStateExportOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $exportScript `
        -WorldStatePath $worldStateFile `
        -OutputFile $worldStateOutputFile `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected ChromaLink RiftReader world-state coord export to pass: {0}" -f ($worldStateExportOutput -join [Environment]::NewLine))
    $worldStateExportResult = ($worldStateExportOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$worldStateExportResult.status) -Expected 'pass' -Message 'World-state export status mismatch.'
    Assert-Equal -Actual ([string]$worldStateExportResult.inputMode) -Expected 'world-state-file' -Message 'World-state export input mode mismatch.'
    $worldStateSample = (@(Get-Content -LiteralPath $worldStateOutputFile))[0] | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$worldStateSample.sourceView) -Expected 'chromalink-riftreader-world-state' -Message 'World-state source view mismatch.'
    Assert-Equal -Actual ([double]$worldStateSample.x) -Expected 7455.6 -Message 'World-state sample X mismatch.'

    $staleSnapshot = $snapshot
    $staleSnapshot.generatedAtUtc = $nowUtc.AddHours(-1).ToString('O')
    $staleSnapshot.aggregate.playerPosition.observedAtUtc = $nowUtc.AddHours(-1).AddMilliseconds(-100).ToString('O')
    $staleSnapshotFile = Join-Path $tempRoot 'stale-chromalink-live-telemetry.json'
    $staleOutputFile = Join-Path $tempRoot 'stale-live-coords.ndjson'
    Set-Content -LiteralPath $staleSnapshotFile -Value ($staleSnapshot | ConvertTo-Json -Depth 32) -Encoding UTF8

    $staleOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $exportScript `
        -SnapshotPath $staleSnapshotFile `
        -OutputFile $staleOutputFile `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected stale ChromaLink snapshot export to fail closed without AllowStale.'
    $staleResult = ($staleOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$staleResult.status) -Expected 'stale' -Message 'Stale export status mismatch.'
    Assert-Equal -Actual ([int]$staleResult.samplesWritten) -Expected 1 -Message 'Stale export sample count mismatch.'
    Assert-Equal -Actual ([int]$staleResult.freshSamplesWritten) -Expected 0 -Message 'Stale export fresh sample count mismatch.'

    $missingPositionSnapshot = [ordered]@{
        contract = [ordered]@{
            name = 'chromalink-live-telemetry'
            schemaVersion = 2
        }
        aggregate = [ordered]@{
            acceptedFrames = 1
            ready = $false
            healthy = $false
        }
    }
    Set-Content -LiteralPath $missingPositionSnapshotFile -Value ($missingPositionSnapshot | ConvertTo-Json -Depth 32) -Encoding UTF8

    $missingOutputFile = Join-Path $tempRoot 'missing-live-coords.ndjson'
    $missingOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $exportScript `
        -SnapshotPath $missingPositionSnapshotFile `
        -OutputFile $missingOutputFile `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected missing playerPosition export to fail.'
    Assert-True -Condition (-not (Test-Path -LiteralPath $missingOutputFile)) -Message 'Missing playerPosition case should not write an NDJSON file.'
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host 'ChromaLink live coord export regression check passed.' -ForegroundColor Green
