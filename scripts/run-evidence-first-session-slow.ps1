# Version: 1.0.0
# TotalCharacters: 0
# Purpose: Run the evidence-first workflow more slowly, with deliberate sleeps before and after keystroke-driven phases to reduce UI contamination risk.

[CmdletBinding()]
param(
    [string]$Label = 'evidence-slow',
    [string[]]$Keys = @('Left', 'Right', 'A', 'D'),
    [int]$HoldMilliseconds = 1000,
    [int]$WaitMilliseconds = 1000,
    [int]$InterPhaseDelaySeconds = 3,
    [switch]$RefreshReaderBridge,
    [switch]$RefreshDiscoveryChain,
    [switch]$RefreshProjectorTrace,
    [switch]$NoAhkFallback
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$mainScript = Join-Path $PSScriptRoot 'run-evidence-first-session.ps1'
if (-not (Test-Path -LiteralPath $mainScript)) {
    throw "Target script not found: $mainScript"
}

Write-Host ''
Write-Host 'Slow evidence-first runner starting...'
Write-Host ("Label: {0}" -f $Label)
Write-Host ("Keys: {0}" -f ($Keys -join ', '))
Write-Host ("HoldMilliseconds: {0}" -f $HoldMilliseconds)
Write-Host ("WaitMilliseconds: {0}" -f $WaitMilliseconds)
Write-Host ("InterPhaseDelaySeconds: {0}" -f $InterPhaseDelaySeconds)
Write-Host ''

Write-Host 'Settling before start...'
Start-Sleep -Seconds $InterPhaseDelaySeconds

$arguments = @{
    Label = $Label
    Keys = $Keys
    HoldMilliseconds = $HoldMilliseconds
    WaitMilliseconds = $WaitMilliseconds
}

if ($RefreshReaderBridge) {
    $arguments['RefreshReaderBridge'] = $true
}

if ($RefreshDiscoveryChain) {
    $arguments['RefreshDiscoveryChain'] = $true
}

if ($RefreshProjectorTrace) {
    $arguments['RefreshProjectorTrace'] = $true
}

if ($NoAhkFallback) {
    $arguments['NoAhkFallback'] = $true
}

& $mainScript @arguments
$exitCode = $LASTEXITCODE

Write-Host ''
Write-Host 'Settling after run...'
Start-Sleep -Seconds $InterPhaseDelaySeconds

if ($exitCode -ne 0) {
    exit $exitCode
}

Write-Host 'Slow evidence-first runner finished.'

# End of script
