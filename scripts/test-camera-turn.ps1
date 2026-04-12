[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$captureScript = Join-Path $scriptDir 'capture-camera-snapshot.ps1'

Write-Host "=== Camera Basis Change Test ===" -ForegroundColor Cyan
Write-Host ""

# Baseline - fresh read
Write-Host "Capturing BEFORE..." -ForegroundColor Yellow
$before = & $captureScript -Json | ConvertFrom-Json -Depth 30
$beforeCameraYaw = $before.CameraYaw.Degrees
$beforeActorYaw = $before.ActorYaw.Degrees
Write-Host "  Actor Yaw: $beforeActorYaw°, Camera Yaw: $beforeCameraYaw°" -ForegroundColor Green

# Turn right
Write-Host "Turning right (4x D key)..." -ForegroundColor Yellow
$keyScript = Join-Path $scriptDir 'post-rift-key.ps1'
for ($i = 0; $i -lt 4; $i++) {
    & $keyScript -Key D
    Start-Sleep -Milliseconds 250
}
Start-Sleep -Milliseconds 1000

# After - fresh read
Write-Host "Capturing AFTER..." -ForegroundColor Yellow
$after = & $captureScript -Json | ConvertFrom-Json -Depth 30
$afterCameraYaw = $after.CameraYaw.Degrees
$afterActorYaw = $after.ActorYaw.Degrees

Write-Host "  Actor Yaw: $afterActorYaw°, Camera Yaw: $afterCameraYaw°" -ForegroundColor Green
Write-Host ""

$actorDelta = [Math]::Round($afterActorYaw - $beforeActorYaw, 2)
$cameraDelta = [Math]::Round($afterCameraYaw - $beforeCameraYaw, 2)

Write-Host "Actor Yaw Delta:  $actorDelta°" -ForegroundColor Yellow
Write-Host "Camera Yaw Delta: $cameraDelta°" -ForegroundColor Yellow
Write-Host ""

if ([Math]::Abs($cameraDelta) -lt 1) {
    Write-Host "✗ Camera basis at +0x7D0 is STATIC - NOT camera data" -ForegroundColor Red
    Write-Host "  Camera must be in separate memory location" -ForegroundColor Yellow
} else {
    Write-Host "✓ Camera basis changed - offsets are valid" -ForegroundColor Green
}
