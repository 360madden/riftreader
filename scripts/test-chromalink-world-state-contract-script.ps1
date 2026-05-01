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

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [object]$Value
    )

    Set-Content -LiteralPath $Path -Value ($Value | ConvertTo-Json -Depth 64) -Encoding UTF8
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script = Join-Path $repoRoot 'scripts\test-chromalink-world-state-contract.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-chromalink-contract-' + [Guid]::NewGuid().ToString('N'))
$manifestPath = Join-Path $tempRoot 'manifest.json'
$schemaPath = Join-Path $tempRoot 'schema.json'
$worldStatePath = Join-Path $tempRoot 'world-state.json'
$badWorldStatePath = Join-Path $tempRoot 'bad-world-state.json'

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $manifest = [ordered]@{
        name = 'ChromaLink HTTP Bridge'
        baseUrl = 'http://127.0.0.1:7337'
        localOnly = $true
        snapshotContract = [ordered]@{
            name = 'chromalink-live-telemetry'
            schemaVersion = 2
        }
        endpoints = @(
            [ordered]@{ path = '/latest-snapshot'; purpose = 'Full rolling telemetry snapshot.' },
            [ordered]@{ path = '/api/v1/riftreader/world-state'; purpose = 'Reduced read-only world-state view.' },
            [ordered]@{ path = '/api/v1/riftreader/world-state/schema'; purpose = 'JSON schema.' },
            [ordered]@{ path = '/health'; purpose = 'Bridge health.' }
        )
    }

    $schema = [ordered]@{
        '$schema' = 'https://json-schema.org/draft/2020-12/schema'
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
    }

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
                x = 12.5
                y = 44.25
                z = -8.0
                observedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
                ageMs = 100.0
                fresh = $true
                stale = $false
            }
        }
        target = $null
        followUnits = @()
    }

    Write-JsonFile -Path $manifestPath -Value $manifest
    Write-JsonFile -Path $schemaPath -Value $schema
    Write-JsonFile -Path $worldStatePath -Value $worldState

    $output = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $script `
        -ManifestPath $manifestPath `
        -SchemaPath $schemaPath `
        -WorldStatePath $worldStatePath `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected ChromaLink world-state contract check to pass: {0}" -f ($output -join [Environment]::NewLine))
    $result = ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 64
    Assert-Equal -Actual ([string]$result.status) -Expected 'pass' -Message 'Pass status mismatch.'
    Assert-Equal -Actual ([string]$result.expectedContractName) -Expected 'chromalink-riftreader-world-state' -Message 'Expected contract name mismatch.'

    $badWorldState = $worldState.PSObject.Copy()
    $badWorldState.navigation = [ordered]@{
        playerPositionAvailable = $true
        targetPositionAvailable = $false
        followUnitPositionsAvailable = $false
        headingAvailable = $true
        facingAvailable = $false
        routeAvailable = $false
        controlAvailable = $false
        limitations = @()
    }
    Write-JsonFile -Path $badWorldStatePath -Value $badWorldState

    $badOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $script `
        -ManifestPath $manifestPath `
        -SchemaPath $schemaPath `
        -WorldStatePath $badWorldStatePath `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected bad world-state contract to fail.'
    $badResult = ($badOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 64
    Assert-Equal -Actual ([string]$badResult.status) -Expected 'fail' -Message 'Bad status mismatch.'
    Assert-True -Condition (@($badResult.failures | Where-Object { $_ -like '*headingAvailable*' }).Count -gt 0) -Message 'Expected headingAvailable failure.'
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host 'ChromaLink world-state contract regression check passed.' -ForegroundColor Green
