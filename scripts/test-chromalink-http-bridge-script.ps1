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

function Get-FreeTcpPort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    try {
        $listener.Start()
        return [int]$listener.LocalEndpoint.Port
    }
    finally {
        $listener.Stop()
    }
}

function Start-TestJsonServer {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port,

        [Parameter(Mandatory = $true)]
        [hashtable]$Routes,

        [int]$MaxRequests = 16
    )

    $serverScript = Join-Path $PSScriptRoot 'test-json-http-server.ps1'
    if (-not (Test-Path -LiteralPath $serverScript)) {
        throw "Test JSON HTTP server script not found: $serverScript"
    }

    $routesPath = Join-Path ([System.IO.Path]::GetTempPath()) ('riftreader-test-json-routes-{0}.json' -f ([Guid]::NewGuid().ToString('N')))
    Set-Content -LiteralPath $routesPath -Value ($Routes | ConvertTo-Json -Depth 100) -Encoding UTF8

    $process = Start-Process -FilePath 'pwsh' -ArgumentList @(
        '-NoLogo',
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        ('"{0}"' -f $serverScript),
        '-Port',
        $Port.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-RoutesPath',
        ('"{0}"' -f $routesPath),
        '-MaxRequests',
        $MaxRequests.ToString([System.Globalization.CultureInfo]::InvariantCulture)
    ) -PassThru -WindowStyle Hidden

    for ($attempt = 0; $attempt -lt 50; $attempt++) {
        try {
            Invoke-WebRequest -Method Get -Uri "http://127.0.0.1:$Port/__probe" -UseBasicParsing -SkipHttpErrorCheck -TimeoutSec 1 | Out-Null
            return [pscustomobject]@{
                Process = $process
                RoutesPath = $routesPath
            }
        }
        catch {
            if ($process.HasExited) {
                throw "Test JSON server exited before accepting connections on port $Port."
            }

            Start-Sleep -Milliseconds 100
        }
    }

    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
    if (Test-Path -LiteralPath $routesPath) {
        Remove-Item -LiteralPath $routesPath -Force
    }
    throw "Test JSON server did not start on port $Port."
}
function Stop-TestJsonServer {
    param([object]$Job)

    if ($null -ne $Job) {
        if ($Job.PSObject.Properties['Process'] -and $null -ne $Job.Process -and -not $Job.Process.HasExited) {
            Stop-Process -Id $Job.Process.Id -Force
        }
        if ($Job.PSObject.Properties['RoutesPath'] -and -not [string]::IsNullOrWhiteSpace([string]$Job.RoutesPath) -and (Test-Path -LiteralPath $Job.RoutesPath)) {
            Remove-Item -LiteralPath $Job.RoutesPath -Force
        }
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script = Join-Path $repoRoot 'scripts\test-chromalink-http-bridge.ps1'

$output = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $script `
    -BaseUrl 'http://127.0.0.1:1' `
    -WaitSeconds 0 `
    -RequestTimeoutSeconds 1 `
    -SkipContractCheck `
    -Json 2>&1

Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected unavailable bridge readiness check to fail.'
$result = ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
Assert-Equal -Actual ([string]$result.status) -Expected 'unavailable' -Message 'Unavailable status mismatch.'
Assert-Equal -Actual ([bool]$result.apiReachable) -Expected $false -Message 'apiReachable mismatch.'
Assert-True -Condition (@($result.failures).Count -gt 0) -Message 'Expected at least one failure.'

$unhealthyPort = Get-FreeTcpPort
$unhealthyServer = $null
try {
    $manifest = [ordered]@{
        name = 'ChromaLink HTTP Bridge'
        baseUrl = "http://127.0.0.1:$unhealthyPort"
        localOnly = $true
        endpoints = @(
            [ordered]@{ path = '/api/v1/riftreader/world-state'; purpose = 'Reduced read-only world-state view.' },
            [ordered]@{ path = '/api/v1/riftreader/world-state/schema'; purpose = 'JSON schema.' }
        )
    }
    $schema = [ordered]@{
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
    $unhealthy = [ordered]@{
        ok = $false
        healthy = $false
        ready = $false
        fresh = $false
        stale = $true
    }
    $unhealthyServer = Start-TestJsonServer -Port $unhealthyPort -MaxRequests 12 -Routes @{
        '/api/v1' = [ordered]@{ statusCode = 200; body = $manifest }
        '/api/v1/riftreader/world-state/schema' = [ordered]@{ statusCode = 200; body = $schema }
        '/health' = [ordered]@{ statusCode = 503; body = $unhealthy }
        '/ready' = [ordered]@{ statusCode = 503; body = $unhealthy }
    }

    $unhealthyOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $script `
        -BaseUrl "http://127.0.0.1:$unhealthyPort" `
        -WaitSeconds 0 `
        -RequestTimeoutSeconds 1 `
        -Json 2>&1

    Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected unhealthy bridge readiness check to fail.'
    $unhealthyResult = ($unhealthyOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 64
    Assert-Equal -Actual ([string]$unhealthyResult.status) -Expected 'fail' -Message 'Unhealthy bridge status mismatch.'
    Assert-Equal -Actual ([bool]$unhealthyResult.apiReachable) -Expected $true -Message 'Unhealthy bridge API reachability mismatch.'
    Assert-Equal -Actual ([int]$unhealthyResult.healthStatusCode) -Expected 503 -Message 'Unhealthy bridge health status mismatch.'
    Assert-Equal -Actual ([int]$unhealthyResult.readyStatusCode) -Expected 503 -Message 'Unhealthy bridge ready status mismatch.'
    Assert-True -Condition (@($unhealthyResult.failures | Where-Object { $_ -like '*Health endpoint*' }).Count -gt 0) -Message 'Expected health endpoint failure.'
    Assert-True -Condition (@($unhealthyResult.failures | Where-Object { $_ -like '*Ready endpoint*' }).Count -gt 0) -Message 'Expected ready endpoint failure.'
}
finally {
    Stop-TestJsonServer -Job $unhealthyServer
}

Write-Host 'ChromaLink HTTP bridge readiness regression check passed.' -ForegroundColor Green
