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
$sourceScript = Join-Path $repoRoot 'scripts\export-proof-polling-watchset.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-proof-watchset-target-' + [System.Guid]::NewGuid().ToString('N'))
$tempScript = Join-Path $tempRoot 'export-proof-polling-watchset.ps1'
$fakeResolveScript = Join-Path $tempRoot 'resolve-proof-coord-anchor.ps1'
$logFile = Join-Path $tempRoot 'resolve-call.json'
$outputFile = Join-Path $tempRoot 'proof-polling-watchset.json'

$fakeResolveContent = @'
[CmdletBinding()]
param(
    [string]$ProcessName,
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$call = [ordered]@{
    ProcessName = $ProcessName
    ProcessId = $ProcessId
    TargetWindowHandle = $TargetWindowHandle
    Json = $Json.IsPresent
}
Set-Content -LiteralPath $env:RIFT_READER_FAKE_RESOLVE_LOG -Value ($call | ConvertTo-Json -Compress) -Encoding UTF8

$anchor = [ordered]@{
    Mode = 'proof-coord-anchor'
    GeneratedAtUtc = '2026-04-29T00:00:00.0000000Z'
    ProcessName = $ProcessName
    ProcessId = $ProcessId
    CanonicalCoordSourceKind = 'coord-trace-direct-region'
    TraceMatchesProcess = $true
    CoordRegionAddress = '0x10000000'
    ObjectBaseAddress = '0x10000000'
    CoordXRelativeOffset = 0
    CoordYRelativeOffset = 4
    CoordZRelativeOffset = 8
    LevelRelativeOffset = $null
    HealthRelativeOffset = $null
    SourceObjectAddress = '0x20000000'
    SourceCoordRelativeOffset = 72
}

$anchor | ConvertTo-Json -Depth 16
$global:LASTEXITCODE = 0
'@

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    Copy-Item -LiteralPath $sourceScript -Destination $tempScript -Force
    Set-Content -LiteralPath $fakeResolveScript -Value $fakeResolveContent -Encoding UTF8
    $env:RIFT_READER_FAKE_RESOLVE_LOG = $logFile

    $resultJson = & pwsh `
        -NoLogo `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File $tempScript `
        -Json `
        -ProcessName 'rift_x64' `
        -ProcessId 41220 `
        -TargetWindowHandle '0xBD0D94' `
        -OutputFile $outputFile

    if ($LASTEXITCODE -ne 0) {
        throw "export-proof-polling-watchset.ps1 exited with code $LASTEXITCODE."
    }

    Assert-True -Condition (Test-Path -LiteralPath $logFile) -Message 'Expected fake proof-anchor resolver to be invoked.'
    Assert-True -Condition (Test-Path -LiteralPath $outputFile) -Message 'Expected proof watchset output to be written.'

    $resolveCall = Get-Content -LiteralPath $logFile -Raw | ConvertFrom-Json
    Assert-Equal -Actual ([string]$resolveCall.ProcessName) -Expected 'rift_x64' -Message 'Resolver should receive ProcessName.'
    Assert-Equal -Actual ([int]$resolveCall.ProcessId) -Expected 41220 -Message 'Resolver should receive ProcessId.'
    Assert-Equal -Actual ([string]$resolveCall.TargetWindowHandle) -Expected '0xBD0D94' -Message 'Resolver should receive TargetWindowHandle.'
    Assert-True -Condition ([bool]$resolveCall.Json) -Message 'Resolver should receive -Json.'

    $result = ($resultJson -join [Environment]::NewLine) | ConvertFrom-Json -Depth 20
    Assert-Equal -Actual ([string]$result.ProcessName) -Expected 'rift_x64' -Message 'Result should record ProcessName.'
    Assert-Equal -Actual ([int]$result.ProcessId) -Expected 41220 -Message 'Result should record ProcessId.'
    Assert-Equal -Actual ([string]$result.TargetWindowHandle) -Expected '0xBD0D94' -Message 'Result should record TargetWindowHandle.'
    Assert-Equal -Actual ([string]$result.CoordRegionAddress) -Expected '0x10000000' -Message 'Result should report anchor coord region.'

    $watchset = Get-Content -LiteralPath $outputFile -Raw | ConvertFrom-Json -Depth 30
    Assert-Equal -Actual ([string]$watchset.ProcessName) -Expected 'rift_x64' -Message 'Watchset should record ProcessName.'
    Assert-Equal -Actual ([int]$watchset.ProcessId) -Expected 41220 -Message 'Watchset should record ProcessId.'
    Assert-Equal -Actual ([string]$watchset.TargetWindowHandle) -Expected '0xBD0D94' -Message 'Watchset should record TargetWindowHandle.'
    Assert-Equal -Actual ([string]$watchset.Anchor.CanonicalCoordSourceKind) -Expected 'coord-trace-direct-region' -Message 'Watchset should preserve canonical anchor source kind.'

    $coordRegion = @($watchset.Regions | Where-Object { $_.Name -eq 'coord-trace-coords' }) | Select-Object -First 1
    Assert-True -Condition ($null -ne $coordRegion) -Message 'Watchset should include required coord-trace-coords region.'
    Assert-Equal -Actual ([string]$coordRegion.Address) -Expected '0x10000000' -Message 'coord-trace-coords region should use validated coord region.'
    Assert-Equal -Actual ([int]$coordRegion.Length) -Expected 12 -Message 'coord-trace-coords region should cover the 12-byte triplet.'
    Assert-True -Condition ([bool]$coordRegion.Required) -Message 'coord-trace-coords region should be required.'

    Write-Host 'export-proof-polling-watchset exact-target propagation regression check passed.' -ForegroundColor Green
}
finally {
    Remove-Item Env:RIFT_READER_FAKE_RESOLVE_LOG -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
