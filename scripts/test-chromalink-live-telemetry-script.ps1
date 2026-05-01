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

function Write-WorldState {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [DateTimeOffset]$ObservedAtUtc,

        [double]$SnapshotAgeSeconds = 0.1,

        [bool]$Fresh = $true,

        [bool]$Stale = $false
    )

    $document = [ordered]@{
        ok = $Fresh
        artifactKind = 'riftreader-world-state'
        contract = [ordered]@{
            name = 'chromalink-riftreader-world-state'
            schemaVersion = 1
        }
        sourceContract = [ordered]@{
            name = 'chromalink-live-telemetry'
            schemaVersion = 2
        }
        ready = $Fresh
        healthy = $Fresh
        fresh = $Fresh
        stale = $Stale
        snapshotAgeSeconds = $SnapshotAgeSeconds
        snapshotPath = 'C:\fake\chromalink-live-telemetry.json'
        navigation = [ordered]@{
            playerPositionAvailable = $Fresh
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
                x = 4.0
                y = 5.0
                z = 6.0
                observedAtUtc = $ObservedAtUtc.ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
                ageMs = [Math]::Round($SnapshotAgeSeconds * 1000.0, 3)
                fresh = $Fresh
                stale = $Stale
            }
        }
        target = $null
        followUnits = @()
    }

    Set-Content -LiteralPath $Path -Value ($document | ConvertTo-Json -Depth 32) -Encoding UTF8
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script = Join-Path $repoRoot 'scripts\test-chromalink-live-telemetry.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-chromalink-freshness-' + [Guid]::NewGuid().ToString('N'))
$snapshot = Join-Path $tempRoot 'chromalink-live-telemetry.json'
$worldState = Join-Path $tempRoot 'chromalink-riftreader-world-state.json'

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $now = [DateTimeOffset]::UtcNow
    Write-Snapshot -Path $snapshot -GeneratedAtUtc $now -ObservedAtUtc $now -Fresh $true -Stale $false
    $freshOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $script -SnapshotPath $snapshot -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected fresh ChromaLink snapshot to pass: {0}" -f ($freshOutput -join [Environment]::NewLine))
    $freshResult = ($freshOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$freshResult.status) -Expected 'pass' -Message 'Fresh status mismatch.'
    Assert-Equal -Actual ([bool]$freshResult.fresh) -Expected $true -Message 'Fresh flag mismatch.'

    Write-WorldState -Path $worldState -ObservedAtUtc $now -SnapshotAgeSeconds 0.1 -Fresh $true -Stale $false
    $worldStateOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $script -WorldStatePath $worldState -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected fresh ChromaLink RiftReader world-state to pass: {0}" -f ($worldStateOutput -join [Environment]::NewLine))
    $worldStateResult = ($worldStateOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$worldStateResult.status) -Expected 'pass' -Message 'World-state status mismatch.'
    Assert-Equal -Actual ([string]$worldStateResult.inputMode) -Expected 'world-state-file' -Message 'World-state input mode mismatch.'
    Assert-Equal -Actual ([double]$worldStateResult.x) -Expected 4.0 -Message 'World-state X mismatch.'

    $worldStateDocument = Get-Content -LiteralPath $worldState -Raw | ConvertFrom-Json -Depth 64
    $nonSuccessPort = Get-FreeTcpPort
    $nonSuccessServer = $null
    try {
        $nonSuccessServer = Start-TestJsonServer -Port $nonSuccessPort -MaxRequests 3 -Routes @{
            '/api/v1/riftreader/world-state' = [ordered]@{
                statusCode = 500
                body = $worldStateDocument
            }
        }

        $nonSuccessOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $script `
            -WorldStateUrl "http://127.0.0.1:$nonSuccessPort/api/v1/riftreader/world-state" `
            -MaxFreshAgeMilliseconds 10000 `
            -Json 2>&1
        Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected HTTP 500 ChromaLink world-state freshness check to fail.'
        $nonSuccessResult = ($nonSuccessOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
        Assert-Equal -Actual ([string]$nonSuccessResult.status) -Expected 'stale' -Message 'HTTP 500 world-state status mismatch.'
        Assert-Equal -Actual ([int]$nonSuccessResult.httpStatusCode) -Expected 500 -Message 'HTTP 500 status code was not recorded.'
        Assert-True -Condition (@($nonSuccessResult.failures | Where-Object { $_ -like '*HTTP status*' }).Count -gt 0) -Message 'Expected HTTP status failure.'
    }
    finally {
        Stop-TestJsonServer -Job $nonSuccessServer
    }

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
