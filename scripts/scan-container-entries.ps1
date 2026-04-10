[CmdletBinding()]
param(
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$readerProject = Join-Path $scriptDir '..' 'reader' 'RiftReader.Reader' 'RiftReader.Reader.csproj'

Write-Host "=== Container Entry Scanner ===" -ForegroundColor Cyan
Write-Host "Dumping all container entries to find camera-like data" -ForegroundColor Yellow
Write-Host ""

# Step 1: Get fresh player position and component addresses
Write-Host "Getting fresh player snapshot..." -ForegroundColor Yellow

$playerOutput = & dotnet run --project $readerProject --configuration Release -- `
    --process-name rift_x64 `
    --read-player-current `
    --json 2>&1

$jsonLines = @()
$jsonStart = $false
foreach ($line in $playerOutput) {
    if ($line -match '^\{') { $jsonStart = $true }
    if ($jsonStart) { $jsonLines += $line }
}

$playerData = ($jsonLines -join "`n") | ConvertFrom-Json -Depth 30
$playerX = [double]$playerData.Memory.CoordX
$playerY = [double]$playerData.Memory.CoordY
$playerZ = [double]$playerData.Memory.CoordZ

Write-Host "Player position: ($([Math]::Round($playerX, 2)), $([Math]::Round($playerY, 2)), $([Math]::Round($playerZ, 2)))" -ForegroundColor Green

# Step 2: Load component list from captures
$componentsFile = Join-Path $scriptDir 'captures' 'player-owner-components.json'
$components = Get-Content $componentsFile -Raw | ConvertFrom-Json -Depth 30

Write-Host "Container has $($components.EntryCount) entries" -ForegroundColor Green
Write-Host "Selected-source: $($components.Owner.SelectedSourceAddress) (index 6)" -ForegroundColor Green
Write-Host ""

# Step 3: Dump each entry and analyze
$results = @()

foreach ($entry in $components.Entries) {
    $addr = $entry.Address
    $idx = $entry.Index

    Write-Host "Entry $idx [$addr]..." -NoNewline -ForegroundColor Gray

    try {
        $dumpOutput = & dotnet run --project $readerProject --configuration Release -- `
            --process-name rift_x64 `
            --address $addr `
            --length 512 `
            --json 2>&1

        $dJsonLines = @()
        $dJsonStart = $false
        foreach ($line in $dumpOutput) {
            if ($line -match '^\{') { $dJsonStart = $true }
            if ($dJsonStart) { $dJsonLines += $line }
        }

        $dump = ($dJsonLines -join "`n") | ConvertFrom-Json -Depth 30
        $hex = $dump.BytesHex -replace ' ', ''
        $bytes = [byte[]]::new($hex.Length / 2)
        for ($i = 0; $i -lt $bytes.Length; $i++) {
            $bytes[$i] = [Convert]::ToByte($hex.Substring($i * 2, 2), 16)
        }

        # Scan for float triplets near player position
        $cameraLike = @()
        $normalizedVectors = @()

        for ($off = 0; $off -lt ($bytes.Length - 11); $off += 4) {
            $fx = [BitConverter]::ToSingle($bytes, $off)
            $fy = [BitConverter]::ToSingle($bytes, $off + 4)
            $fz = [BitConverter]::ToSingle($bytes, $off + 8)

            if ([float]::IsNaN($fx) -or [float]::IsNaN($fy) -or [float]::IsNaN($fz)) { continue }
            if ([float]::IsInfinity($fx) -or [float]::IsInfinity($fy) -or [float]::IsInfinity($fz)) { continue }

            # Check: triplet near player position (camera ~10-20 units away)
            $dx = [double]$fx - $playerX
            $dy = [double]$fy - $playerY
            $dz = [double]$fz - $playerZ
            $dist = [Math]::Sqrt($dx * $dx + $dy * $dy + $dz * $dz)

            if ($dist -gt 0.5 -and $dist -lt 50) {
                $cameraLike += [ordered]@{
                    Offset = '+0x{0:X3}' -f $off
                    X = [Math]::Round($fx, 3)
                    Y = [Math]::Round($fy, 3)
                    Z = [Math]::Round($fz, 3)
                    DistFromPlayer = [Math]::Round($dist, 2)
                }
            }

            # Check: normalized vector (magnitude ~1.0) — could be camera direction
            $mag = [Math]::Sqrt([double]$fx * [double]$fx + [double]$fy * [double]$fy + [double]$fz * [double]$fz)
            if ([Math]::Abs($mag - 1.0) -lt 0.05 -and [Math]::Abs($fx) -lt 1.1 -and [Math]::Abs($fy) -lt 1.1 -and [Math]::Abs($fz) -lt 1.1) {
                $normalizedVectors += [ordered]@{
                    Offset = '+0x{0:X3}' -f $off
                    X = [Math]::Round($fx, 4)
                    Y = [Math]::Round($fy, 4)
                    Z = [Math]::Round($fz, 4)
                    Magnitude = [Math]::Round($mag, 6)
                }
            }
        }

        $entryResult = [ordered]@{
            Index = $idx
            Address = $addr
            Roles = $entry.RoleHints
            CameraLikePositions = $cameraLike
            NormalizedVectors = $normalizedVectors
        }

        $results += $entryResult

        if ($cameraLike.Count -gt 0 -or $normalizedVectors.Count -gt 0) {
            Write-Host " FOUND: $($cameraLike.Count) positions, $($normalizedVectors.Count) normals" -ForegroundColor Green
        } else {
            Write-Host " nothing" -ForegroundColor DarkGray
        }

    } catch {
        Write-Host " ERROR: $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan

$interesting = $results | Where-Object { $_.CameraLikePositions.Count -gt 0 -or $_.NormalizedVectors.Count -gt 0 }

foreach ($r in $interesting) {
    Write-Host ""
    Write-Host "Entry $($r.Index) [$($r.Address)] roles=[$($r.Roles -join ', ')]" -ForegroundColor Yellow

    foreach ($pos in $r.CameraLikePositions) {
        Write-Host "  POSITION $($pos.Offset): ($($pos.X), $($pos.Y), $($pos.Z)) dist=$($pos.DistFromPlayer)" -ForegroundColor Green
    }
    foreach ($vec in $r.NormalizedVectors) {
        Write-Host "  NORMAL   $($vec.Offset): ($($vec.X), $($vec.Y), $($vec.Z)) mag=$($vec.Magnitude)" -ForegroundColor Cyan
    }
}

if ($Json) {
    [ordered]@{
        Mode = 'container-entry-scan'
        GeneratedAtUtc = [DateTime]::UtcNow.ToString('o')
        PlayerPosition = [ordered]@{ X = $playerX; Y = $playerY; Z = $playerZ }
        EntryCount = $components.EntryCount
        Results = $results
    } | ConvertTo-Json -Depth 20
}
