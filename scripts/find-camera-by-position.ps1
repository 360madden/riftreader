[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$readerProject = Join-Path $scriptDir '..' 'reader' 'RiftReader.Reader' 'RiftReader.Reader.csproj'

Write-Host "=== Find Camera by Position Coordinates ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Strategy: Camera position should be near player position (offset by ~10-20 units)" -ForegroundColor Yellow
Write-Host "We'll scan for triplets matching expected camera location" -ForegroundColor Yellow
Write-Host ""

# Get player position via reader
Write-Host "Getting player position..." -ForegroundColor Yellow

$readerOutput = & dotnet run --project $readerProject --configuration Release -- `
    --process-name rift_x64 `
    --read-player-current `
    --json 2>&1

# Extract JSON
$jsonStart = $false
$jsonLines = @()
foreach ($line in $readerOutput) {
    if ($line -match '^\{') { $jsonStart = $true }
    if ($jsonStart) { $jsonLines += $line }
}

if ($jsonLines.Count -eq 0) {
    Write-Host "ERROR: Could not get player position" -ForegroundColor Red
    return
}

try {
    $playerData = ($jsonLines -join "`n") | ConvertFrom-Json -Depth 30
    $playerX = $playerData.CoordinateAnchor.X
    $playerY = $playerData.CoordinateAnchor.Y
    $playerZ = $playerData.CoordinateAnchor.Z

    Write-Host "Player position: ($playerX, $playerY, $playerZ)" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Could not parse player position: $_" -ForegroundColor Red
    return
}

# Camera is typically offset from player by:
# - Backwards: -10 to -20 units (in facing direction)
# - Up: +5 to +15 units (elevation)
# - Side: minimal offset unless in 3rd person

Write-Host ""
Write-Host "Expected camera offset patterns:" -ForegroundColor Cyan
Write-Host "  - Behind player (X/Z): -10 to -20 units" -ForegroundColor Gray
Write-Host "  - Above player (Y): +5 to +15 units" -ForegroundColor Gray
Write-Host ""

# Try scanning for likely camera X coordinate
# Typical offset: player X ± 20

$scanX = $playerX - 15  # Assume 15 units back
Write-Host "Scanning for camera X coordinate ≈ $scanX..." -ForegroundColor Yellow

$scanXOutput = & dotnet run --project $readerProject --configuration Release -- `
    --process-name rift_x64 `
    --scan-float $scanX `
    --scan-tolerance 5.0 `
    --scan-context 64 `
    --max-hits 30 `
    --json 2>&1

$jsonLines = @()
$jsonStart = $false
foreach ($line in $scanXOutput) {
    if ($line -match '^\{') { $jsonStart = $true }
    if ($jsonStart) { $jsonLines += $line }
}

if ($jsonLines.Count -gt 0) {
    try {
        $xResults = ($jsonLines -join "`n") | ConvertFrom-Json -Depth 30
        $xHits = $xResults.Hits

        Write-Host "Found $($xHits.Count) addresses with X ≈ $scanX" -ForegroundColor Green
        Write-Host ""
        Write-Host "Candidates (camera X coordinate):" -ForegroundColor Cyan

        $xHits | Select-Object -First 10 | ForEach-Object {
            Write-Host "  $($_.AddressHex): $($_.ObservedValue.ToString('F2'))  (region: $($_.RegionBaseHex))" -ForegroundColor White
        }
    } catch {
        Write-Host "Error parsing X scan: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "No results from X scan" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Check if any X candidates look reasonable (should be close to player X)" -ForegroundColor Gray
Write-Host "2. For each candidate, check if Y+4 bytes and Z+8 bytes look like camera coords" -ForegroundColor Gray
Write-Host "3. Validate: Camera position should move when camera moves but STAY SAME when player moves" -ForegroundColor Gray
Write-Host ""
Write-Host "To manually validate:" -ForegroundColor Yellow
Write-Host "  - Open Cheat Engine" -ForegroundColor Gray
Write-Host "  - Add address to address list" -ForegroundColor Gray
Write-Host "  - Watch values while camera rotates (should NOT change)" -ForegroundColor Gray
Write-Host "  - Watch values while camera moves/pans (SHOULD change)" -ForegroundColor Gray
