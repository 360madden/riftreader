[CmdletBinding()]
param(
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$readerProject = Join-Path $PSScriptRoot '..' 'reader' 'RiftReader.Reader' 'RiftReader.Reader.csproj'

function Get-PlayerCoords {
    $output = & dotnet run --project $readerProject --configuration Release -- --process-name rift_x64 --read-player-current 2>&1
    $line = $output | Select-String 'Memory coords'
    if ($line -match 'Memory coords:\s+([\d.]+),\s+([\d.]+),\s+([\d.]+)') {
        return @{ X = [float]$Matches[1]; Y = [float]$Matches[2]; Z = [float]$Matches[3] }
    }
    throw "Could not parse player coords"
}

function Scan-Float($value, $tolerance, $maxHits) {
    $output = & dotnet run --project $readerProject --configuration Release -- --process-name rift_x64 --scan-float $value --scan-tolerance $tolerance --scan-context 16 --max-hits $maxHits --json 2>&1
    return ($output | ConvertFrom-Json -Depth 30).Hits
}

function Read-FloatAt($address) {
    $output = & dotnet run --project $readerProject --configuration Release -- --process-name rift_x64 --address $address --length 4 --json 2>&1
    $data = $output | ConvertFrom-Json -Depth 30
    $hex = $data.BytesHex -replace ' ', ''
    if ($hex.Length -ge 8) {
        $bytes = [byte[]]::new(4)
        for ($i = 0; $i -lt 4; $i++) {
            $bytes[$i] = [Convert]::ToByte($hex.Substring($i * 2, 2), 16)
        }
        return [BitConverter]::ToSingle($bytes, 0)
    }
    return [float]::NaN
}

Write-Host '=== Differential Camera Scan ===' -ForegroundColor Cyan
Write-Host ''

# Step 1: Get current player position
$coords1 = Get-PlayerCoords
Write-Host "Player position 1: X=$($coords1.X) Y=$($coords1.Y) Z=$($coords1.Z)" -ForegroundColor Green

# Step 2: Scan for all addresses matching player X
Write-Host 'Scanning for player X coordinate copies...' -ForegroundColor Yellow
$xHits = Scan-Float $coords1.X 0.5 50
Write-Host "  Found $($xHits.Count) hits" -ForegroundColor Green

# Store addresses and values
$addresses = @()
foreach ($hit in $xHits) {
    $addresses += @{
        Address = $hit.AddressHex
        Value1 = [float]$hit.ObservedValue
        RegionBase = $hit.RegionBaseHex
        RegionSize = $hit.RegionSize
    }
}

# Step 3: Move player
Write-Host 'Moving player (4x W key)...' -ForegroundColor Yellow
$keyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'
for ($i = 0; $i -lt 4; $i++) {
    & $keyScript -Key W
    Start-Sleep -Milliseconds 250
}
Start-Sleep -Milliseconds 1000

# Step 4: Get new player position
$coords2 = Get-PlayerCoords
$playerDeltaX = $coords2.X - $coords1.X
Write-Host "Player position 2: X=$($coords2.X) Y=$($coords2.Y) Z=$($coords2.Z)" -ForegroundColor Green
Write-Host "Player X delta: $([Math]::Round($playerDeltaX, 3))" -ForegroundColor Green
Write-Host ''

if ([Math]::Abs($playerDeltaX) -lt 0.1) {
    Write-Host "WARNING: Player did not move significantly. Cannot determine tracking." -ForegroundColor Red
    return
}

# Step 5: Re-read each address and check if it tracked the movement
Write-Host 'Re-reading addresses and checking which tracked movement...' -ForegroundColor Yellow
Write-Host ''

$tracked = @()
$static = @()

foreach ($entry in $addresses) {
    $newVal = Read-FloatAt $entry.Address
    $delta = $newVal - $entry.Value1

    # Did this address track the player movement?
    $trackingRatio = if ([Math]::Abs($playerDeltaX) -gt 0.01) { $delta / $playerDeltaX } else { 0 }

    if ([Math]::Abs($trackingRatio - 1.0) -lt 0.2) {
        # Tracks player movement closely (ratio ~1.0)
        $tracked += [ordered]@{
            Address = $entry.Address
            Before = [Math]::Round($entry.Value1, 3)
            After = [Math]::Round($newVal, 3)
            Delta = [Math]::Round($delta, 3)
            TrackingRatio = [Math]::Round($trackingRatio, 3)
            Region = $entry.RegionBase
            RegionSize = $entry.RegionSize
            Type = 'tracks-player'
        }
        Write-Host "  TRACKS: $($entry.Address) $([Math]::Round($entry.Value1, 2)) -> $([Math]::Round($newVal, 2)) (ratio=$([Math]::Round($trackingRatio, 2))) region=$($entry.RegionBase)" -ForegroundColor Green
    }
    elseif ([Math]::Abs($delta) -lt 0.01) {
        $static += $entry.Address
    }
    else {
        # Changed but not tracking player exactly — could be camera with offset
        Write-Host "  CHANGED: $($entry.Address) $([Math]::Round($entry.Value1, 2)) -> $([Math]::Round($newVal, 2)) delta=$([Math]::Round($delta, 3)) ratio=$([Math]::Round($trackingRatio, 3)) region=$($entry.RegionBase)" -ForegroundColor Yellow
    }
}

Write-Host ''
Write-Host "Tracking player: $($tracked.Count), Static: $($static.Count)" -ForegroundColor Cyan

if ($Json) {
    [ordered]@{
        Mode = 'differential-camera-scan'
        GeneratedAtUtc = [DateTime]::UtcNow.ToString('o')
        PlayerPosition1 = $coords1
        PlayerPosition2 = $coords2
        PlayerDeltaX = [Math]::Round($playerDeltaX, 3)
        TrackedAddresses = $tracked
        StaticCount = $static.Count
    } | ConvertTo-Json -Depth 20
}
