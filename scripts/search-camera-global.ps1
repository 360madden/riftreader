[CmdletBinding()]
param(
    [string]$Label = 'camera-global-search',
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Write-Host "=== Global Camera Search ===" -ForegroundColor Cyan
Write-Host "Searching for camera-like memory patterns across entire Rift process" -ForegroundColor Green
Write-Host ""

# Strategy: Camera is typically 10-20 units behind/above player position
# Player coordinates: 7421.4, 863.59, 2942.34
# Expected camera location: (7421.4 ± 20, 863.59 + 5 ± 10, 2942.34 ± 20)
# Strategy: Scan for float triplets that match this pattern

Write-Host "Known player position: (7421.4, 863.59, 2942.34)" -ForegroundColor Yellow
Write-Host "Expected camera offset range: (±20 X, +5-15 Y, ±20 Z)" -ForegroundColor Yellow
Write-Host ""

Write-Host "Scanning for potential camera positions matching offset pattern..." -ForegroundColor Yellow

# Use reader's generic scanning capabilities
$readerPath = Join-Path (Get-Location) "reader/RiftReader.Reader/bin/Release/net10.0-windows/RiftReader.dll"

if (-not (Test-Path $readerPath)) {
    # Try dotnet run instead
    Write-Host "Using dotnet run for scanning..." -ForegroundColor Gray

    # Search for X coordinate (player X ± tolerance)
    $playerX = 7421.4
    $tolerance = 1.0

    Write-Host "Searching for X coordinate near $playerX ..." -ForegroundColor Gray
    & dotnet run --project reader/RiftReader.Reader/RiftReader.Reader.csproj --configuration Release -- `
        --process-name rift_x64 `
        --scan-float $playerX `
        --scan-tolerance $tolerance `
        --scan-context 32 `
        --max-hits 16 `
        2>&1 | Select-String "0x[0-9A-F]" | head -10
}
else {
    Write-Host "Direct assembly scan not yet implemented" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Alternative strategy: Look for 3D vector magnitude patterns" -ForegroundColor Yellow
Write-Host "3D vectors with magnitude ~1.0 (normalized) could be camera direction" -ForegroundColor Gray
Write-Host "Run: scripts\simple-camera-memory-test.ps1 -Stimulus pitch" -ForegroundColor Gray
Write-Host "Monitor memory changes in response to pitch input specifically"  -ForegroundColor Gray

Write-Host ""
Write-Host "Other approaches:" -ForegroundColor Cyan
Write-Host "1. Use Cheat Engine multi-level pointers from player position" -ForegroundColor Gray
Write-Host "2. Hook Rift input system (Win32 GetCursorPos, mouse_event)" -ForegroundColor Gray
Write-Host "3. Search for camera distance scalar (float 5-30 units)" -ForegroundColor Gray
Write-Host "4. Trace from render target or viewport camera" -ForegroundColor Gray
