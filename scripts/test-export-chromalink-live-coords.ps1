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
    $stdoutLog = Join-Path ([System.IO.Path]::GetTempPath()) ('riftreader-test-json-server-out-{0}.log' -f ([Guid]::NewGuid().ToString('N')))
    $stderrLog = Join-Path ([System.IO.Path]::GetTempPath()) ('riftreader-test-json-server-err-{0}.log' -f ([Guid]::NewGuid().ToString('N')))

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
    ) -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog

    for ($attempt = 0; $attempt -lt 50; $attempt++) {
        try {
            Invoke-WebRequest -Method Get -Uri "http://127.0.0.1:$Port/__probe" -UseBasicParsing -SkipHttpErrorCheck -TimeoutSec 1 | Out-Null
            return [pscustomobject]@{
                Process = $process
                RoutesPath = $routesPath
                StdoutLog = $stdoutLog
                StderrLog = $stderrLog
            }
        }
        catch {
            if ($process.HasExited) {
                $serverOutput = if (Test-Path -LiteralPath $stdoutLog) { Get-Content -LiteralPath $stdoutLog -Raw } else { '' }
                $serverError = if (Test-Path -LiteralPath $stderrLog) { Get-Content -LiteralPath $stderrLog -Raw } else { '' }
                throw "Test JSON server exited before accepting connections on port $Port. stdout=$serverOutput stderr=$serverError"
            }

            Start-Sleep -Milliseconds 100
        }
    }

    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
    foreach ($pathToRemove in @($routesPath, $stdoutLog, $stderrLog)) {
        if (-not [string]::IsNullOrWhiteSpace($pathToRemove) -and (Test-Path -LiteralPath $pathToRemove)) {
            Remove-Item -LiteralPath $pathToRemove -Force
        }
    }
    throw "Test JSON server did not start on port $Port."
}
function Stop-TestJsonServer {
    param([object]$Job)

    if ($null -ne $Job) {
        if ($Job.PSObject.Properties['Process'] -and $null -ne $Job.Process -and -not $Job.Process.HasExited) {
            Stop-Process -Id $Job.Process.Id -Force
        }
        foreach ($pathProperty in @('RoutesPath', 'StdoutLog', 'StderrLog')) {
            if ($Job.PSObject.Properties[$pathProperty]) {
                $pathToRemove = [string]$Job.$pathProperty
                if (-not [string]::IsNullOrWhiteSpace($pathToRemove) -and (Test-Path -LiteralPath $pathToRemove)) {
                    Remove-Item -LiteralPath $pathToRemove -Force
                }
            }
        }
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
        -MaxFreshAgeMilliseconds 10000 `
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
        -MaxFreshAgeMilliseconds 10000 `
        -Json 2>&1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message ("Expected ChromaLink RiftReader world-state coord export to pass: {0}" -f ($worldStateExportOutput -join [Environment]::NewLine))
    $worldStateExportResult = ($worldStateExportOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$worldStateExportResult.status) -Expected 'pass' -Message 'World-state export status mismatch.'
    Assert-Equal -Actual ([string]$worldStateExportResult.inputMode) -Expected 'world-state-file' -Message 'World-state export input mode mismatch.'
    $worldStateSample = (@(Get-Content -LiteralPath $worldStateOutputFile))[0] | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual ([string]$worldStateSample.sourceView) -Expected 'chromalink-riftreader-world-state' -Message 'World-state source view mismatch.'
    Assert-Equal -Actual ([double]$worldStateSample.x) -Expected 7455.6 -Message 'World-state sample X mismatch.'

    $nonSuccessPort = Get-FreeTcpPort
    $nonSuccessServer = $null
    $nonSuccessOutputFile = Join-Path $tempRoot 'http-500-live-coords.ndjson'
    try {
        $nonSuccessServer = Start-TestJsonServer -Port $nonSuccessPort -MaxRequests 3 -Routes @{
            '/api/v1/riftreader/world-state' = [ordered]@{
                statusCode = 500
                body = $worldState
            }
        }

        $nonSuccessOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $exportScript `
            -WorldStateUrl "http://127.0.0.1:$nonSuccessPort/api/v1/riftreader/world-state" `
            -OutputFile $nonSuccessOutputFile `
            -MaxFreshAgeMilliseconds 10000 `
            -Json 2>&1
        Assert-True -Condition ($LASTEXITCODE -ne 0) -Message 'Expected HTTP 500 ChromaLink world-state export to fail.'
        Assert-True -Condition (($nonSuccessOutput -join [Environment]::NewLine) -like '*non-success HTTP status*') -Message 'Expected HTTP status export error.'
        Assert-True -Condition (-not (Test-Path -LiteralPath $nonSuccessOutputFile)) -Message 'HTTP 500 export should not write NDJSON.'
    }
    finally {
        Stop-TestJsonServer -Job $nonSuccessServer
    }

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
