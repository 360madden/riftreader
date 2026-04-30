[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tests = @(
    'C:\RIFT MODDING\RiftReader\scripts\test-actor-facing-truth-proof.ps1',
    'C:\RIFT MODDING\RiftReader\scripts\test-actor-facing-truth-proof-fail.ps1',
    'C:\RIFT MODDING\RiftReader\scripts\test-player-source-chain-recovery.ps1',
    'C:\RIFT MODDING\RiftReader\scripts\test-player-source-chain-fresh-rebuild.ps1',
    'C:\RIFT MODDING\RiftReader\scripts\test-refresh-discovery-chain-exact-target.ps1'
)

$results = New-Object System.Collections.Generic.List[object]

foreach ($testFile in $tests) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $output = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $testFile 2>&1
    $exitCode = $LASTEXITCODE
    $sw.Stop()

    $results.Add([pscustomobject]@{
        TestFile = $testFile
        ExitCode = $exitCode
        DurationSeconds = [Math]::Round($sw.Elapsed.TotalSeconds, 3)
        Output = ($output -join [Environment]::NewLine).Trim()
        Status = if ($exitCode -eq 0) { 'pass' } else { 'fail' }
    }) | Out-Null
}

$failed = @($results | Where-Object { $_.ExitCode -ne 0 })
if ($failed.Count -gt 0) {
    Write-Host 'Actor-facing proof suite failed:' -ForegroundColor Red
    foreach ($result in $results) {
        Write-Host ("[{0}] {1} ({2}s)" -f $result.Status.ToUpperInvariant(), $result.TestFile, $result.DurationSeconds)
        if (-not [string]::IsNullOrWhiteSpace($result.Output)) {
            Write-Host $result.Output
        }
    }

    exit 1
}

Write-Host 'Actor-facing proof suite passed.' -ForegroundColor Green
foreach ($result in $results) {
    Write-Host ("[PASS] {0} ({1}s)" -f $result.TestFile, $result.DurationSeconds)
}
