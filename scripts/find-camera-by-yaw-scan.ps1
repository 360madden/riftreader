[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$captureScript = Join-Path $scriptDir 'capture-camera-snapshot.ps1'
$keyScript = Join-Path $scriptDir 'post-rift-key.ps1'
$readerProject = Join-Path $scriptDir '..' 'reader' 'RiftReader.Reader' 'RiftReader.Reader.csproj'

Write-Host "=== Camera Yaw Search by Value Scan ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Strategy: Capture camera yaw before/after rotation, then scan for the changed value" -ForegroundColor Yellow
Write-Host ""

# Baseline
Write-Host "BEFORE: Capturing baseline..." -ForegroundColor Yellow
$before = & $captureScript -Json | ConvertFrom-Json -Depth 30
$beforeYaw = $before.CameraYaw.Degrees
Write-Host "  Camera Yaw: $beforeYaw°" -ForegroundColor Green
Write-Host ""

# User rotates camera right
Write-Host "ROTATE CAMERA: Moving mouse RIGHT approximately 90 degrees" -ForegroundColor Yellow
Write-Host "  (You: Please rotate camera to the right while I wait...)" -ForegroundColor Cyan
Start-Sleep -Seconds 3

# After
Write-Host ""
Write-Host "AFTER: Capturing new state..." -ForegroundColor Yellow
$after = & $captureScript -Json | ConvertFrom-Json -Depth 30
$afterYaw = $after.CameraYaw.Degrees
Write-Host "  Camera Yaw: $afterYaw°" -ForegroundColor Green
Write-Host ""

$yawDelta = [Math]::Round($afterYaw - $beforeYaw, 2)
Write-Host "Yaw Delta: $yawDelta°" -ForegroundColor Yellow
Write-Host ""

# Now scan for the "after" yaw value
# The new yaw value is stored somewhere in memory; let's find it
Write-Host "Scanning memory for new yaw value ($afterYaw ± 0.1)..." -ForegroundColor Yellow

$scanOutput = & dotnet run --project $readerProject --configuration Release -- `
    --process-name rift_x64 `
    --scan-float $afterYaw `
    --scan-tolerance 0.1 `
    --scan-context 32 `
    --max-hits 50 `
    --json 2>&1

# Extract just the JSON part (filter out verbose logging)
$jsonStart = $scanOutput | Select-String '^\{' | Select-Object -First 1
if ($jsonStart) {
    $jsonLines = @()
    $captureJson = $false
    foreach ($line in $scanOutput) {
        if ($line -match '^\{') { $captureJson = $true }
        if ($captureJson) { $jsonLines += $line }
    }
    $jsonText = $jsonLines -join "`n"

    try {
        $results = $jsonText | ConvertFrom-Json -Depth 30
        $hits = $results.Hits

        Write-Host "Found $($hits.Count) candidates with yaw ≈ $afterYaw°" -ForegroundColor Green
        Write-Host ""

        if ($hits.Count -gt 0) {
            Write-Host "Top 10 candidates:" -ForegroundColor Cyan
            $hits | Select-Object -First 10 | ForEach-Object {
                Write-Host "  $($_.AddressHex): $($_.ObservedValue.ToString('F4'))°  region=$($_.RegionBaseHex)" -ForegroundColor White
            }

            Write-Host ""
            Write-Host "Next steps:" -ForegroundColor Yellow
            Write-Host "1. Manual verification in Cheat Engine" -ForegroundColor Gray
            Write-Host "2. Test addresses by reading before/after" -ForegroundColor Gray
            Write-Host "3. Look for address pattern consistency" -ForegroundColor Gray
        }
    } catch {
        Write-Host "Error parsing scan results: $_" -ForegroundColor Red
        Write-Host "Raw output:" -ForegroundColor Gray
        Write-Host ($scanOutput | ConvertTo-Json) -ForegroundColor Gray
    }
} else {
    Write-Host "No JSON found in output" -ForegroundColor Red
    Write-Host ($scanOutput | Out-String) -ForegroundColor Gray
}
