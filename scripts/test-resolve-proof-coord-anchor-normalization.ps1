[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-Equal {
    param(
        [Parameter(Mandatory = $true)]
        $Actual,
        [Parameter(Mandatory = $true)]
        $Expected,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("RiftReader-proof-anchor-normalization-" + [System.Guid]::NewGuid().ToString('N'))
$shimDirectory = Join-Path $tempRoot 'shim'
$proofCoordAnchorFile = Join-Path $tempRoot 'telemetry-proof-coord-anchor.json'

New-Item -ItemType Directory -Path $shimDirectory -Force | Out-Null

$fakeDotnetPath = Join-Path $shimDirectory 'dotnet.cmd'
$fakeAnchorJson = @'
{
  "Mode": "read-player-coord-anchor",
  "GeneratedAtUtc": "2026-04-30T12:00:00.0000000+00:00",
  "ProcessName": "shim",
  "ProcessId": 0,
  "SourceFile": "",
  "VerificationMethod": "coord-triplet-access",
  "TraceMatchesProcess": true,
  "TargetAddress": "",
  "CandidateAddress": "",
  "ObjectBaseAddress": "0x2000",
  "CoordXRelativeOffset": 32,
  "CoordYRelativeOffset": 36,
  "CoordZRelativeOffset": 40,
  "LevelRelativeOffset": null,
  "HealthRelativeOffset": null,
  "MemorySample": {
    "AddressHex": "0x2020",
    "CoordX": 1.0,
    "CoordY": 2.0,
    "CoordZ": 3.0
  },
  "Expected": {
    "Name": "Atank",
    "Location": "Regression",
    "CoordX": 100.0,
    "CoordY": 200.0,
    "CoordZ": 300.0
  },
  "Match": {
    "CoordMatchesWithinTolerance": false,
    "DeltaX": -99.0,
    "DeltaY": -198.0,
    "DeltaZ": -297.0
  },
  "SourceObjectAddress": "0x1000",
  "SourceCoordRelativeOffset": 72,
  "SourceObjectSample": {
    "AddressHex": "0x1000",
    "CoordX": 100.0,
    "CoordY": 200.0,
    "CoordZ": 300.0
  },
  "SourceObjectMatch": {
    "CoordMatchesWithinTolerance": true,
    "DeltaX": 0.0,
    "DeltaY": 0.0,
    "DeltaZ": 0.0
  }
}
'@

$fakeDotnetLines = @('@echo off', 'setlocal')
$fakeDotnetLines += ($fakeAnchorJson.Trim().Split("`n") | ForEach-Object { 'echo ' + $_.TrimEnd("`r") })
$fakeDotnetLines += 'exit /b 0'
Set-Content -LiteralPath $fakeDotnetPath -Value $fakeDotnetLines -Encoding ASCII

$originalPath = $env:PATH

try {
    $env:PATH = "$shimDirectory;$originalPath"
    $output = & pwsh `
        -NoLogo `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File (Join-Path $repoRoot 'scripts\resolve-proof-coord-anchor.ps1') `
        -ProcessName 'shim' `
        -RefreshAttempts 0 `
        -SkipRefresh `
        -Json `
        -ProofCoordAnchorFile $proofCoordAnchorFile

    if ($LASTEXITCODE -ne 0) {
        throw "resolve-proof-coord-anchor.ps1 exited with code $LASTEXITCODE. Output: $($output -join [Environment]::NewLine)"
    }

    $resolved = ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual $resolved.CanonicalCoordSourceKind -Expected 'coord-trace-source-object' -Message 'Expected source-object fallback selection.'
    Assert-Equal -Actual $resolved.ObjectBaseAddress -Expected '0x1000' -Message 'Expected source object base to be preserved.'
    Assert-Equal -Actual $resolved.CoordRegionAddress -Expected '0x1048' -Message 'Expected coord region to be shifted to the XYZ triplet.'
    Assert-Equal -Actual $resolved.CoordXRelativeOffset -Expected 0 -Message 'Expected X offset to be normalized relative to coord region.'
    Assert-Equal -Actual $resolved.CoordYRelativeOffset -Expected 4 -Message 'Expected Y offset to be normalized relative to coord region.'
    Assert-Equal -Actual $resolved.CoordZRelativeOffset -Expected 8 -Message 'Expected Z offset to be normalized relative to coord region.'
    Assert-Equal -Actual $resolved.MemorySample.AddressHex -Expected '0x1048' -Message 'Expected memory sample address to match normalized coord region.'

    if (-not (Test-Path -LiteralPath $proofCoordAnchorFile)) {
        throw "Expected normalized proof coord anchor file '$proofCoordAnchorFile' to be written."
    }

    $persisted = Get-Content -LiteralPath $proofCoordAnchorFile -Raw | ConvertFrom-Json -Depth 32
    Assert-Equal -Actual $persisted.CoordRegionAddress -Expected '0x1048' -Message 'Expected persisted coord region to be normalized.'
    Assert-Equal -Actual $persisted.CoordXRelativeOffset -Expected 0 -Message 'Expected persisted X offset to be normalized.'
    Assert-Equal -Actual $persisted.CoordYRelativeOffset -Expected 4 -Message 'Expected persisted Y offset to be normalized.'
    Assert-Equal -Actual $persisted.CoordZRelativeOffset -Expected 8 -Message 'Expected persisted Z offset to be normalized.'

    Write-Host 'resolve-proof-coord-anchor normalization regression passed.' -ForegroundColor Green
}
finally {
    $env:PATH = $originalPath
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
