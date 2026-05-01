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

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [object]$Value
    )

    Set-Content -LiteralPath $Path -Value ($Value | ConvertTo-Json -Depth 64) -Encoding UTF8
}

function Write-WorldStateFixtures {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ManifestPath,

        [Parameter(Mandatory = $true)]
        [string]$SchemaPath,

        [Parameter(Mandatory = $true)]
        [string]$WorldStatePath,

        [Parameter(Mandatory = $true)]
        [DateTimeOffset]$ObservedAtUtc
    )

    Write-JsonFile -Path $ManifestPath -Value ([ordered]@{
            name = 'ChromaLink HTTP Bridge'
            baseUrl = 'http://127.0.0.1:7337'
            localOnly = $true
            snapshotContract = [ordered]@{
                name = 'chromalink-live-telemetry'
                schemaVersion = 2
            }
            endpoints = @(
                [ordered]@{ path = '/api/v1/riftreader/world-state'; purpose = 'Reduced read-only world-state view.' },
                [ordered]@{ path = '/api/v1/riftreader/world-state/schema'; purpose = 'JSON schema.' }
            )
        })

    Write-JsonFile -Path $SchemaPath -Value ([ordered]@{
            title = 'ChromaLink RiftReader World State'
            '$defs' = [ordered]@{
                position = [ordered]@{
                    required = @('x', 'y', 'z')
                }
                navigation = [ordered]@{
                    properties = [ordered]@{
                        headingAvailable = [ordered]@{ const = $false }
                        facingAvailable = [ordered]@{ const = $false }
                        routeAvailable = [ordered]@{ const = $false }
                        controlAvailable = [ordered]@{ const = $false }
                    }
                }
                success = [ordered]@{
                    properties = [ordered]@{
                        contract = [ordered]@{
                            allOf = @(
                                [ordered]@{ '$ref' = '#/$defs/contract' },
                                [ordered]@{
                                    properties = [ordered]@{
                                        name = [ordered]@{ const = 'chromalink-riftreader-world-state' }
                                        schemaVersion = [ordered]@{ const = 1 }
                                    }
                                }
                            )
                        }
                    }
                }
            }
        })

    Write-JsonFile -Path $WorldStatePath -Value ([ordered]@{
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
            snapshotPath = 'C:\fake\chromalink-live-telemetry.json'
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
                    x = 11.0
                    y = 22.0
                    z = 33.0
                    observedAtUtc = $ObservedAtUtc.ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
                    ageMs = 100.0
                    fresh = $true
                    stale = $false
                }
            }
            target = $null
            followUnits = @()
        })
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$captureScript = Join-Path $repoRoot 'scripts\capture-chromalink-live-coords.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-chromalink-capture-' + [Guid]::NewGuid().ToString('N'))
$snapshot = Join-Path $tempRoot 'chromalink-live-telemetry.json'
$freshBundle = Join-Path $tempRoot 'fresh-bundle'
$worldStateBundle = Join-Path $tempRoot 'world-state-bundle'
$bridgeFailedBundle = Join-Path $tempRoot 'bridge-failed-bundle'
$staleBundle = Join-Path $tempRoot 'stale-bundle'
$manifest = Join-Path $tempRoot 'manifest.json'
$schema = Join-Path $tempRoot 'schema.json'
$worldState = Join-Path $tempRoot 'world-state.json'

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
    Assert-True -Condition (-not (Test-Path -LiteralPath (Join-Path $freshBundle 'chromalink-world-state-contract.json'))) -Message 'Raw snapshot capture should not write a world-state contract preflight.'

    Write-WorldStateFixtures -ManifestPath $manifest -SchemaPath $schema -WorldStatePath $worldState -ObservedAtUtc $now
    $worldStateOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $captureScript `
        -WorldStatePath $worldState `
        -ContractManifestPath $manifest `
        -ContractSchemaPath $schema `
        -BundleDirectory $worldStateBundle `
        -MaxFreshAgeMilliseconds 10000 `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected ChromaLink world-state capture to pass: {0}" -f ($worldStateOutput -join [Environment]::NewLine))
    $worldStateResult = ($worldStateOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 64
    Assert-Equal -Actual ([string]$worldStateResult.status) -Expected 'pass' -Message 'World-state capture status mismatch.'
    Assert-Equal -Actual ([string]$worldStateResult.inputMode) -Expected 'world-state-file' -Message 'World-state capture input mode mismatch.'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $worldStateBundle 'chromalink-world-state-contract.json')) -Message 'World-state contract preflight file missing.'
    Assert-Equal -Actual ([string]$worldStateResult.contract.status) -Expected 'pass' -Message 'World-state contract status mismatch.'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $worldStateBundle 'live-coords.ndjson')) -Message 'World-state live-coords.ndjson missing.'
    Assert-True -Condition (-not (Test-Path -LiteralPath (Join-Path $worldStateBundle 'chromalink-http-bridge-readiness.json'))) -Message 'World-state file capture should not write HTTP bridge readiness.'

    $bridgeFailedOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $captureScript `
        -WorldStateUrl 'http://127.0.0.1:1/api/v1/riftreader/world-state' `
        -BundleDirectory $bridgeFailedBundle `
        -BridgeWaitSeconds 0 `
        -BridgeRequestTimeoutSeconds 1 `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected unreachable ChromaLink bridge capture to fail.'
    $bridgeFailedResult = ($bridgeFailedOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 64
    Assert-Equal -Actual ([string]$bridgeFailedResult.status) -Expected 'bridge-failed' -Message 'Bridge-failed capture status mismatch.'
    Assert-True -Condition (Test-Path -LiteralPath (Join-Path $bridgeFailedBundle 'chromalink-http-bridge-readiness.json')) -Message 'Bridge readiness artifact missing for bridge failure.'
    Assert-True -Condition (-not (Test-Path -LiteralPath (Join-Path $bridgeFailedBundle 'chromalink-freshness-preflight.json'))) -Message 'Bridge-failed capture should stop before freshness preflight.'
    Assert-True -Condition (-not (Test-Path -LiteralPath (Join-Path $bridgeFailedBundle 'live-coords.ndjson'))) -Message 'Bridge-failed capture should not write live-coords.ndjson.'

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
