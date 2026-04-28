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

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("RiftReader-telemetry-wrapper-compat-" + [System.Guid]::NewGuid().ToString('N'))
$shimDirectory = Join-Path $tempRoot 'shim'
$capturesDirectory = Join-Path $tempRoot 'captures'
$dotnetArgumentsFile = Join-Path $tempRoot 'dotnet-arguments.txt'
$outputFile = Join-Path $capturesDirectory 'telemetry.latest.json'
$eventLogFile = Join-Path $capturesDirectory 'telemetry.events.ndjson'
$diagnosticsLogFile = Join-Path $capturesDirectory 'telemetry.discovery.ndjson'
$proofCoordAnchorFile = Join-Path $capturesDirectory 'telemetry-proof-coord-anchor.json'

New-Item -ItemType Directory -Path $shimDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $capturesDirectory -Force | Out-Null

$fakePwshPath = Join-Path $shimDirectory 'pwsh.cmd'
$fakeDotnetPath = Join-Path $shimDirectory 'dotnet.cmd'

$fakePwshJson = @'
{
  "GeneratedAtUtc": "2026-04-22T22:12:27.2581693+00:00",
  "CanonicalCoordSourceKind": "coord-trace-direct-region",
  "MatchSource": "readerbridge-live",
  "CoordRegionAddress": "0x12345678",
  "Match": {
    "CoordMatchesWithinTolerance": true
  },
  "Notes": [
    "compat-regression"
  ]
}
'@

$fakePwshLines = @('@echo off', 'setlocal')
$fakePwshLines += ($fakePwshJson.Trim().Split("`n") | ForEach-Object { 'echo ' + $_.TrimEnd("`r") })
$fakePwshLines += 'exit /b 0'
Set-Content -LiteralPath $fakePwshPath -Value $fakePwshLines -Encoding ASCII

$escapedDotnetArgumentsFile = $dotnetArgumentsFile.Replace('%', '%%')
$fakeDotnetContent = @"
@echo off
setlocal
> "$escapedDotnetArgumentsFile" echo %*
echo RiftReader.Reader telemetry preflight
echo Process: shim (1234)
echo Memory coords: valid
echo Facing: valid
echo Effective position source: memory
echo Effective facing source: memory-facing
exit /b 0
"@
Set-Content -LiteralPath $fakeDotnetPath -Value $fakeDotnetContent -Encoding ASCII

$originalPath = $env:PATH

try {
    $env:PATH = "$shimDirectory;$originalPath"
    & powershell.exe `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File (Join-Path $repoRoot 'scripts\run-telemetry-host.ps1') `
        -ProcessName 'shim' `
        -Preflight `
        -Diagnostics `
        -OutputFile $outputFile `
        -EventLogFile $eventLogFile `
        -DiagnosticsLogFile $diagnosticsLogFile `
        -ProofCoordAnchorFile $proofCoordAnchorFile

    if ($LASTEXITCODE -ne 0) {
        throw "Wrapper exited with code $LASTEXITCODE."
    }

    Assert-True -Condition (Test-Path -LiteralPath $proofCoordAnchorFile) -Message "Expected proof coord anchor file '$proofCoordAnchorFile' to be created."
    Assert-True -Condition (Test-Path -LiteralPath $dotnetArgumentsFile) -Message "Expected fake dotnet argument capture '$dotnetArgumentsFile' to be created."

    $proofAnchor = Get-Content -LiteralPath $proofCoordAnchorFile -Raw | ConvertFrom-Json
    Assert-True -Condition ($proofAnchor.Match.CoordMatchesWithinTolerance -eq $true) -Message 'Expected wrapper to preserve the validated proof-anchor match.'

    $dotnetArguments = Get-Content -LiteralPath $dotnetArgumentsFile -Raw
    Assert-True -Condition ($dotnetArguments -match '--telemetry-preflight') -Message 'Expected wrapper to invoke dotnet with --telemetry-preflight.'
    Assert-True -Condition ($dotnetArguments -match '--telemetry-proof-anchor-file') -Message 'Expected wrapper to pass --telemetry-proof-anchor-file to dotnet.'

    Write-Host 'run-telemetry-host wrapper compatibility check passed.' -ForegroundColor Green
}
finally {
    $env:PATH = $originalPath
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
