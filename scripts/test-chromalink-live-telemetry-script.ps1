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
                x = 1.0
                y = 2.0
                z = 3.0
            }
        }
    }

    Set-Content -LiteralPath $Path -Value ($document | ConvertTo-Json -Depth 16) -Encoding UTF8
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script = Join-Path $repoRoot 'scripts\test-chromalink-live-telemetry.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-chromalink-freshness-' + [Guid]::NewGuid().ToString('N'))
$snapshot = Join-Path $tempRoot 'chromalink-live-telemetry.json'

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $now = [DateTimeOffset]::UtcNow
    Write-Snapshot -Path $snapshot -GeneratedAtUtc $now -ObservedAtUtc $now -Fresh $true -Stale $false
    $freshOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $script -SnapshotPath $snapshot -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected fresh ChromaLink snapshot to pass: {0}" -f ($freshOutput -join [Environment]::NewLine))
    $freshResult = ($freshOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$freshResult.status) -Expected 'pass' -Message 'Fresh status mismatch.'
    Assert-Equal -Actual ([bool]$freshResult.fresh) -Expected $true -Message 'Fresh flag mismatch.'

    $staleTime = [DateTimeOffset]::UtcNow.AddSeconds(-10)
    Write-Snapshot -Path $snapshot -GeneratedAtUtc $staleTime -ObservedAtUtc $staleTime -Fresh $true -Stale $false
    $staleOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $script -SnapshotPath $snapshot -MaxFreshAgeMilliseconds 2000 -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected stale ChromaLink snapshot to fail.'
    $staleResult = ($staleOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$staleResult.status) -Expected 'stale' -Message 'Stale status mismatch.'
    Assert-Equal -Actual ([bool]$staleResult.fresh) -Expected $false -Message 'Stale fresh flag mismatch.'
    Assert-True -Condition (@($staleResult.failures | Where-Object { $_ -like '*Snapshot age exceeds*' }).Count -gt 0) -Message 'Expected stale snapshot age failure.'

    Remove-Item -LiteralPath $snapshot -Force
    $missingOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $script -SnapshotPath $snapshot -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected missing ChromaLink snapshot to fail.'
    $missingResult = ($missingOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$missingResult.status) -Expected 'missing' -Message 'Missing status mismatch.'
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host 'ChromaLink live telemetry freshness regression check passed.' -ForegroundColor Green
