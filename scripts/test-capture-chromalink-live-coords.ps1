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

function Write-Snapshot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [DateTimeOffset]$GeneratedAtUtc,

        [DateTimeOffset]$ObservedAtUtc,

        [bool]$Fresh = $true,

        [bool]$Stale = $false
    )

    if ($null -eq $ObservedAtUtc) {
        $ObservedAtUtc = $GeneratedAtUtc
    }

    $document = [ordered]@{
        generatedAtUtc = $GeneratedAtUtc.ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        contract = [ordered]@{
            name = 'chromalink-live-telemetry'
            schemaVersion = 1
        }
        aggregate = [ordered]@{
            ready = $true
            healthy = $Fresh
            stale = $Stale
            acceptedFrames = 1
            playerPosition = [ordered]@{
                frameType = 'PlayerPosition'
                schemaId = 1
                sequence = 1
                observedAtUtc = $ObservedAtUtc.ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
                ageMs = 0
                fresh = $Fresh
                stale = $Stale
                x = 10.0
                y = 20.0
                z = 30.0
            }
        }
    }

    Set-Content -LiteralPath $Path -Value ($document | ConvertTo-Json -Depth 16) -Encoding UTF8
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$captureScript = Join-Path $repoRoot 'scripts\capture-chromalink-live-coords.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-chromalink-capture-' + [Guid]::NewGuid().ToString('N'))
$snapshot = Join-Path $tempRoot 'chromalink-live-telemetry.json'
$freshBundle = Join-Path $tempRoot 'fresh-bundle'
$staleBundle = Join-Path $tempRoot 'stale-bundle'

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $now = [DateTimeOffset]::UtcNow
    Write-Snapshot -Path $snapshot -GeneratedAtUtc $now -ObservedAtUtc $now -Fresh $true -Stale $false

    $freshOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $captureScript `
        -SnapshotPath $snapshot `
        -BundleDirectory $freshBundle `
        -MaxFreshAgeMilliseconds 10000 `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected fresh ChromaLink capture to pass: {0}" -f ($freshOutput -join [Environment]::NewLine))
    $freshResult = ($freshOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 64
    Assert-Equal -Actual ([string]$freshResult.status) -Expected 'pass' -Message 'Fresh capture status mismatch.'
    Assert-Equal -Actual ([bool]$freshResult.exported) -Expected $true -Message 'Fresh capture exported flag mismatch.'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $freshBundle 'live-coords.ndjson')) -Message 'Fresh live-coords.ndjson missing.'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $freshBundle 'chromalink-freshness-preflight.json')) -Message 'Fresh preflight file missing.'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $freshBundle 'chromalink-live-coords-export-result.json')) -Message 'Fresh export result file missing.'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $freshBundle 'chromalink-live-coords-capture-summary.json')) -Message 'Fresh summary file missing.'

    $staleTime = [DateTimeOffset]::UtcNow.AddSeconds(-10)
    Write-Snapshot -Path $snapshot -GeneratedAtUtc $staleTime -ObservedAtUtc $staleTime -Fresh $true -Stale $false

    $staleOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $captureScript `
        -SnapshotPath $snapshot `
        -BundleDirectory $staleBundle `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected stale ChromaLink capture to fail preflight.'
    $staleResult = ($staleOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 64
    Assert-Equal -Actual ([string]$staleResult.status) -Expected 'preflight-failed' -Message 'Stale capture status mismatch.'
    Assert-Equal -Actual ([bool]$staleResult.exported) -Expected $false -Message 'Stale capture exported flag mismatch.'
    Assert-True -Condition (-not (Test-Path -LiteralPath (Join-Path $staleBundle 'live-coords.ndjson'))) -Message 'Stale capture should not write live-coords.ndjson.'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $staleBundle 'chromalink-freshness-preflight.json')) -Message 'Stale preflight file missing.'
    Assert-True -Condition (-not (Test-Path -LiteralPath (Join-Path $staleBundle 'chromalink-live-coords-export-result.json'))) -Message 'Stale capture should not write export result.'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $staleBundle 'chromalink-live-coords-capture-summary.json')) -Message 'Stale summary file missing.'
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host 'ChromaLink live coord capture regression check passed.' -ForegroundColor Green
