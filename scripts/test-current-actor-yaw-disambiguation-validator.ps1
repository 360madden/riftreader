[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$testFile = Join-Path $repoRoot 'scripts\test_current_actor_yaw_disambiguation.py'

$output = & python $testFile 2>&1
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    if ($output.Count -gt 0) {
        Write-Host ($output -join [Environment]::NewLine)
    }
    exit $exitCode
}

Write-Host 'current actor-yaw disambiguation validator regression check passed.' -ForegroundColor Green
