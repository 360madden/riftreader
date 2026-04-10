[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$captureScript = Join-Path $scriptDir 'capture-camera-snapshot.ps1'
$readerProject = Join-Path $scriptDir '..' 'reader' 'RiftReader.Reader' 'RiftReader.Reader.csproj'

Write-Host "=== Automated Camera Yaw Discovery ===" -ForegroundColor Cyan
Write-Host ""

function Get-CameraYaw {
    try {
        $snapshot = & $captureScript -Json 2>$null | ConvertFrom-Json -Depth 30
        return $snapshot.CameraYaw.Degrees
    } catch {
        return $null
    }
}

function Scan-ForYaw($yawValue, $iteration) {
    Write-Host "Scan iteration $iteration: Looking for yaw ≈ $yawValue..." -ForegroundColor Yellow

    $scanOutput = & dotnet run --project $readerProject --configuration Release -- `
        --process-name rift_x64 `
        --scan-float $yawValue `
        --scan-tolerance 0.5 `
        --scan-context 32 `
        --max-hits 100 `
        --json 2>&1

    # Extract JSON from output
    $jsonStart = $false
    $jsonLines = @()
    foreach ($line in $scanOutput) {
        if ($line -match '^\{') { $jsonStart = $true }
        if ($jsonStart) { $jsonLines += $line }
    }

    if ($jsonLines.Count -eq 0) {
        return $null
    }

    try {
        $results = ($jsonLines -join "`n") | ConvertFrom-Json -Depth 30
        return $results.Hits
    } catch {
        Write-Host "  Error parsing scan: $_" -ForegroundColor Yellow
        return $null
    }
}

# Phase 1: Baseline capture
Write-Host "PHASE 1: Baseline Capture" -ForegroundColor Cyan
Write-Host ""

$baselineYaw = Get-CameraYaw
if (-not $baselineYaw) {
    Write-Host "ERROR: Could not read baseline yaw" -ForegroundColor Red
    return
}

Write-Host "Baseline camera yaw: $baselineYaw°" -ForegroundColor Green

# Phase 2: First scan
Write-Host ""
Write-Host "PHASE 2: Initial Scan" -ForegroundColor Cyan
Write-Host ""

$candidates1 = Scan-ForYaw $baselineYaw 1
if (-not $candidates1) {
    Write-Host "ERROR: First scan failed" -ForegroundColor Red
    return
}

Write-Host "Found $($candidates1.Count) candidates from first scan" -ForegroundColor Green

# Phase 3: User rotates camera
Write-Host ""
Write-Host "PHASE 3: Camera Rotation" -ForegroundColor Cyan
Write-Host ""
Write-Host "Rotating camera (moving mouse LEFT ~120 degrees)..." -ForegroundColor Yellow
Write-Host "Please wait for system to detect camera movement..." -ForegroundColor Yellow

# Simulate mouse movement to trigger camera rotation
# In Rift, we can't inject mouse directly, but user should manually rotate
Write-Host ""
Write-Host "IMPORTANT: Manually rotate your camera to the LEFT while I wait..." -ForegroundColor Cyan
Write-Host "Wait 5 seconds..." -ForegroundColor Yellow

for ($i = 5; $i -gt 0; $i--) {
    Write-Host "  $i..." -NoNewline
    Start-Sleep -Seconds 1
}
Write-Host " Done!" -ForegroundColor Yellow

# Phase 4: Capture new yaw
Write-Host ""
Write-Host "PHASE 4: Capture After Rotation" -ForegroundColor Cyan
Write-Host ""

$newYaw = Get-CameraYaw
if (-not $newYaw) {
    Write-Host "ERROR: Could not read new yaw" -ForegroundColor Red
    return
}

$yawDelta = [Math]::Round($newYaw - $baselineYaw, 2)
Write-Host "New camera yaw: $newYaw° (delta: $yawDelta°)" -ForegroundColor Green

if ([Math]::Abs($yawDelta) -lt 1) {
    Write-Host ""
    Write-Host "WARNING: Camera yaw didn't change significantly ($yawDelta°)" -ForegroundColor Yellow
    Write-Host "This might mean:" -ForegroundColor Yellow
    Write-Host "  - Camera rotation didn't register" -ForegroundColor Gray
    Write-Host "  - The yaw values we're reading are not actual camera data" -ForegroundColor Gray
    Write-Host ""
    Write-Host "This is the same issue as before - will likely hit a wall" -ForegroundColor Red
    return
}

# Phase 5: Second scan to narrow candidates
Write-Host ""
Write-Host "PHASE 5: Narrow Candidates" -ForegroundColor Cyan
Write-Host ""

$candidates2 = Scan-ForYaw $newYaw 2
if (-not $candidates2) {
    Write-Host "ERROR: Second scan failed" -ForegroundColor Red
    return
}

Write-Host "Narrowed to $($candidates2.Count) candidates" -ForegroundColor Green

# Phase 6: Identify addresses present in both scans
Write-Host ""
Write-Host "PHASE 6: Filter by Rotation Response" -ForegroundColor Cyan
Write-Host ""

$validCandidates = @()
foreach ($cand in $candidates2) {
    # Check if this address was also in the first scan (to eliminate false positives)
    $wasInFirstScan = $candidates1 | Where-Object { $_.AddressHex -eq $cand.AddressHex }
    if ($wasInFirstScan) {
        $validCandidates += $cand
    }
}

Write-Host "Candidates that appeared in both scans: $($validCandidates.Count)" -ForegroundColor Green
Write-Host ""

if ($validCandidates.Count -eq 0) {
    Write-Host "ERROR: No candidates matched both scans - discovery failed" -ForegroundColor Red
    return
}

Write-Host "Top 5 candidates:" -ForegroundColor Cyan
$top5 = $validCandidates | Select-Object -First 5
foreach ($i = 0; $i -lt $top5.Count; $i++) {
    $addr = $top5[$i]
    Write-Host "  $($i+1). Address: $($addr.AddressHex)" -ForegroundColor White
    Write-Host "     Value (baseline): $([Math]::Round($baselineYaw, 4))°" -ForegroundColor Gray
    Write-Host "     Value (after):    $([Math]::Round($addr.ObservedValue, 4))°" -ForegroundColor Gray
    Write-Host "     Region: $($addr.RegionBaseHex)" -ForegroundColor Gray
    Write-Host ""
}

Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Use Cheat Engine to validate candidates (watch for smooth changes)" -ForegroundColor Gray
Write-Host "2. Once confirmed, extract offset from base address" -ForegroundColor Gray
Write-Host "3. Repeat for camera pitch" -ForegroundColor Gray
