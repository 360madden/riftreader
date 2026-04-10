[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'

Write-Host "=== Deep Scan: Container Entry 15 (0x1575264C000) ===" -ForegroundColor Cyan
Write-Host "Dumping 2048 bytes and analyzing all float32 values" -ForegroundColor Yellow
Write-Host ""

# Known player position (approximate)
$playerX = 7421.4
$playerY = 863.59
$playerZ = 2942.34

# Step 1: Get fresh player position
Write-Host "Getting fresh player snapshot..." -ForegroundColor Yellow

$readerArgs = @('run', '--project', $readerProject, '--configuration', 'Release', '--', '--process-name', 'rift_x64', '--read-player-current', '--json')
$playerOutput = & dotnet @readerArgs 2>&1

$jsonLines = @()
$jsonStart = $false
foreach ($line in $playerOutput) {
    if ($line -match '^\{') { $jsonStart = $true }
    if ($jsonStart) { $jsonLines += $line }
}

$playerData = ($jsonLines -join "`n") | ConvertFrom-Json
$playerX = [double]$playerData.Memory.CoordX
$playerY = [double]$playerData.Memory.CoordY
$playerZ = [double]$playerData.Memory.CoordZ

Write-Host "Live player position: ($([Math]::Round($playerX, 2)), $([Math]::Round($playerY, 2)), $([Math]::Round($playerZ, 2)))" -ForegroundColor Green
Write-Host ""

# Step 2: Dump 2048 bytes from Entry 15
$entryAddr = "0x1575264C000"
Write-Host "Dumping 2048 bytes from Entry 15 [$entryAddr]..." -ForegroundColor Yellow

$dumpArgs = @('run', '--project', $readerProject, '--configuration', 'Release', '--', '--process-name', 'rift_x64', '--address', $entryAddr, '--length', '2048', '--json')
$dumpOutput = & dotnet @dumpArgs 2>&1

$dJsonLines = @()
$dJsonStart = $false
foreach ($line in $dumpOutput) {
    if ($line -match '^\{') { $dJsonStart = $true }
    if ($dJsonStart) { $dJsonLines += $line }
}

$dump = ($dJsonLines -join "`n") | ConvertFrom-Json
$hex = $dump.BytesHex -replace ' ', ''
$bytes = [byte[]]::new($hex.Length / 2)
for ($i = 0; $i -lt $bytes.Length; $i++) {
    $bytes[$i] = [Convert]::ToByte($hex.Substring($i * 2, 2), 16)
}

Write-Host "Got $($bytes.Length) bytes" -ForegroundColor Green
Write-Host ""

# Step 3: Parse ALL float32 values at every 4-byte offset
Write-Host "=== COMPLETE FLOAT32 DUMP ===" -ForegroundColor Cyan
Write-Host "Showing all non-garbage float values" -ForegroundColor Yellow
Write-Host ""

$allFloats = @()
for ($off = 0; $off -lt ($bytes.Length - 3); $off += 4) {
    $fVal = [BitConverter]::ToSingle($bytes, $off)
    $allFloats += [PSCustomObject]@{
        Offset = $off
        OffsetHex = '+0x{0:X3}' -f $off
        Value = $fVal
        RawHex = ('{0:X2}{1:X2}{2:X2}{3:X2}' -f $bytes[$off+3], $bytes[$off+2], $bytes[$off+1], $bytes[$off])
    }
}

# Also read as int64 for pointer detection
$allQwords = @()
for ($off = 0; $off -lt ($bytes.Length - 7); $off += 8) {
    $qVal = [BitConverter]::ToInt64($bytes, $off)
    $allQwords += [PSCustomObject]@{
        Offset = $off
        OffsetHex = '+0x{0:X3}' -f $off
        Value = '0x{0:X}' -f $qVal
    }
}

# Category 1: Float triplets near player position (camera position candidates)
Write-Host "--- CATEGORY 1: Position triplets near player (dist 0.5-50) ---" -ForegroundColor Magenta
$positionHits = @()
for ($off = 0; $off -lt ($bytes.Length - 11); $off += 4) {
    $fx = [BitConverter]::ToSingle($bytes, $off)
    $fy = [BitConverter]::ToSingle($bytes, $off + 4)
    $fz = [BitConverter]::ToSingle($bytes, $off + 8)

    if ([float]::IsNaN($fx) -or [float]::IsNaN($fy) -or [float]::IsNaN($fz)) { continue }
    if ([float]::IsInfinity($fx) -or [float]::IsInfinity($fy) -or [float]::IsInfinity($fz)) { continue }

    $dx = [double]$fx - $playerX
    $dy = [double]$fy - $playerY
    $dz = [double]$fz - $playerZ
    $dist = [Math]::Sqrt($dx * $dx + $dy * $dy + $dz * $dz)

    if ($dist -gt 0.5 -and $dist -lt 50) {
        $positionHits += [ordered]@{
            Offset = '+0x{0:X3}' -f $off
            X = [Math]::Round($fx, 4)
            Y = [Math]::Round($fy, 4)
            Z = [Math]::Round($fz, 4)
            DistFromPlayer = [Math]::Round($dist, 3)
        }
        Write-Host ("  {0}: ({1}, {2}, {3}) dist={4}" -f `
            ('+0x{0:X3}' -f $off), `
            [Math]::Round($fx, 4), [Math]::Round($fy, 4), [Math]::Round($fz, 4), `
            [Math]::Round($dist, 3)) -ForegroundColor Green
    }
}
if ($positionHits.Count -eq 0) { Write-Host "  (none found)" -ForegroundColor DarkGray }
Write-Host ""

# Category 1b: Exact player position matches (dist < 0.5)
Write-Host "--- CATEGORY 1b: Exact player position matches (dist < 0.5) ---" -ForegroundColor Magenta
for ($off = 0; $off -lt ($bytes.Length - 11); $off += 4) {
    $fx = [BitConverter]::ToSingle($bytes, $off)
    $fy = [BitConverter]::ToSingle($bytes, $off + 4)
    $fz = [BitConverter]::ToSingle($bytes, $off + 8)

    if ([float]::IsNaN($fx) -or [float]::IsNaN($fy) -or [float]::IsNaN($fz)) { continue }
    if ([float]::IsInfinity($fx) -or [float]::IsInfinity($fy) -or [float]::IsInfinity($fz)) { continue }

    $dx = [double]$fx - $playerX
    $dy = [double]$fy - $playerY
    $dz = [double]$fz - $playerZ
    $dist = [Math]::Sqrt($dx * $dx + $dy * $dy + $dz * $dz)

    if ($dist -lt 0.5) {
        Write-Host ("  {0}: ({1}, {2}, {3}) dist={4}" -f `
            ('+0x{0:X3}' -f $off), `
            [Math]::Round($fx, 4), [Math]::Round($fy, 4), [Math]::Round($fz, 4), `
            [Math]::Round($dist, 4)) -ForegroundColor Green
    }
}
Write-Host ""

# Category 2: Normalized vectors (magnitude ~1.0) — camera direction candidates
Write-Host "--- CATEGORY 2: Normalized vectors (magnitude 0.95-1.05) ---" -ForegroundColor Magenta
$normalHits = @()
for ($off = 0; $off -lt ($bytes.Length - 11); $off += 4) {
    $fx = [BitConverter]::ToSingle($bytes, $off)
    $fy = [BitConverter]::ToSingle($bytes, $off + 4)
    $fz = [BitConverter]::ToSingle($bytes, $off + 8)

    if ([float]::IsNaN($fx) -or [float]::IsNaN($fy) -or [float]::IsNaN($fz)) { continue }
    if ([float]::IsInfinity($fx) -or [float]::IsInfinity($fy) -or [float]::IsInfinity($fz)) { continue }

    $mag = [Math]::Sqrt([double]$fx * [double]$fx + [double]$fy * [double]$fy + [double]$fz * [double]$fz)

    if ([Math]::Abs($mag - 1.0) -lt 0.05 -and [Math]::Abs($fx) -le 1.1 -and [Math]::Abs($fy) -le 1.1 -and [Math]::Abs($fz) -le 1.1) {
        $normalHits += [ordered]@{
            Offset = '+0x{0:X3}' -f $off
            X = [Math]::Round($fx, 6)
            Y = [Math]::Round($fy, 6)
            Z = [Math]::Round($fz, 6)
            Magnitude = [Math]::Round($mag, 6)
        }
        Write-Host ("  {0}: ({1}, {2}, {3}) mag={4}" -f `
            ('+0x{0:X3}' -f $off), `
            [Math]::Round($fx, 6), [Math]::Round($fy, 6), [Math]::Round($fz, 6), `
            [Math]::Round($mag, 6)) -ForegroundColor Cyan
    }
}
if ($normalHits.Count -eq 0) { Write-Host "  (none found)" -ForegroundColor DarkGray }
Write-Host ""

# Category 3: Angles in degrees (0-360) or radians (-PI to PI)
Write-Host "--- CATEGORY 3: Angle-like scalars ---" -ForegroundColor Magenta
Write-Host "  Degrees (0-360) or Radians (-3.15 to 3.15):" -ForegroundColor Yellow
$angleHits = @()
for ($off = 0; $off -lt ($bytes.Length - 3); $off += 4) {
    $fVal = [BitConverter]::ToSingle($bytes, $off)

    if ([float]::IsNaN($fVal) -or [float]::IsInfinity($fVal)) { continue }

    $isDeg = ($fVal -ge 0 -and $fVal -le 360 -and $fVal -ne 0)
    $isRad = ($fVal -ge -3.15 -and $fVal -le 3.15 -and [Math]::Abs($fVal) -gt 0.001)

    if ($isDeg -or $isRad) {
        $label = ""
        if ($isDeg -and $fVal -gt 3.15) { $label = "DEG" }
        elseif ($isRad) { $label = "RAD(={0}deg)" -f [Math]::Round($fVal * 180 / [Math]::PI, 2) }
        else { $label = "DEG-or-RAD" }

        $angleHits += [ordered]@{
            Offset = '+0x{0:X3}' -f $off
            Value = [Math]::Round($fVal, 6)
            Type = $label
        }
    }
}

# Too many hits usually; filter to show only interesting ones
# Show all but group them
$degOnly = $angleHits | Where-Object { $_.Type -eq 'DEG' }
$radOnly = $angleHits | Where-Object { $_.Type -match 'RAD' }
$ambig = $angleHits | Where-Object { $_.Type -eq 'DEG-or-RAD' }

Write-Host "  Pure degree candidates (3.15-360):" -ForegroundColor Yellow
foreach ($a in $degOnly) {
    Write-Host ("    {0}: {1} {2}" -f $a.Offset, $a.Value, $a.Type) -ForegroundColor White
}
if ($degOnly.Count -eq 0) { Write-Host "    (none)" -ForegroundColor DarkGray }

Write-Host "  Radian candidates (-3.15 to 3.15, excluding near-zero):" -ForegroundColor Yellow
foreach ($a in $radOnly) {
    Write-Host ("    {0}: {1} {2}" -f $a.Offset, $a.Value, $a.Type) -ForegroundColor White
}
if ($radOnly.Count -eq 0) { Write-Host "    (none)" -ForegroundColor DarkGray }

Write-Host "  Ambiguous (small positive, could be either): $($ambig.Count) hits (showing first 30)" -ForegroundColor Yellow
$ambig | Select-Object -First 30 | ForEach-Object {
    Write-Host ("    {0}: {1}" -f $_.Offset, $_.Value) -ForegroundColor DarkGray
}
Write-Host ""

# Category 4: Distance scalars (5-30 range) — camera distance
Write-Host "--- CATEGORY 4: Distance scalars (5-30 range) ---" -ForegroundColor Magenta
$distHits = @()
for ($off = 0; $off -lt ($bytes.Length - 3); $off += 4) {
    $fVal = [BitConverter]::ToSingle($bytes, $off)

    if ([float]::IsNaN($fVal) -or [float]::IsInfinity($fVal)) { continue }

    if ($fVal -ge 5 -and $fVal -le 30) {
        $distHits += [ordered]@{
            Offset = '+0x{0:X3}' -f $off
            Value = [Math]::Round($fVal, 4)
        }
        Write-Host ("  {0}: {1}" -f ('+0x{0:X3}' -f $off), [Math]::Round($fVal, 4)) -ForegroundColor White
    }
}
if ($distHits.Count -eq 0) { Write-Host "  (none found)" -ForegroundColor DarkGray }
Write-Host ""

# Category 5: Large game-world coordinate singles (1000-10000 range — individual X/Y/Z)
Write-Host "--- CATEGORY 5: Game-world-range floats (500-10000) ---" -ForegroundColor Magenta
for ($off = 0; $off -lt ($bytes.Length - 3); $off += 4) {
    $fVal = [BitConverter]::ToSingle($bytes, $off)

    if ([float]::IsNaN($fVal) -or [float]::IsInfinity($fVal)) { continue }

    if ([Math]::Abs($fVal) -ge 500 -and [Math]::Abs($fVal) -le 10000) {
        Write-Host ("  {0}: {1}" -f ('+0x{0:X3}' -f $off), [Math]::Round($fVal, 4)) -ForegroundColor White
    }
}
Write-Host ""

# Category 6: Small integers as float (useful flags, counts, enums: 1-100)
Write-Host "--- CATEGORY 6: Small integer-like floats (1-100, within 0.001 of integer) ---" -ForegroundColor Magenta
for ($off = 0; $off -lt ($bytes.Length - 3); $off += 4) {
    $fVal = [BitConverter]::ToSingle($bytes, $off)

    if ([float]::IsNaN($fVal) -or [float]::IsInfinity($fVal)) { continue }

    if ($fVal -ge 1 -and $fVal -le 100 -and [Math]::Abs($fVal - [Math]::Round($fVal)) -lt 0.001) {
        Write-Host ("  {0}: {1}" -f ('+0x{0:X3}' -f $off), [Math]::Round($fVal, 4)) -ForegroundColor White
    }
}
Write-Host ""

# Full float table for manual inspection
Write-Host "=== FULL FLOAT TABLE (non-trivial values only) ===" -ForegroundColor Cyan
Write-Host "Filtering out: NaN, Inf, 0.0, denormals (<1e-30), huge (>1e15)" -ForegroundColor Yellow
Write-Host ""
Write-Host ("{0,-10} {1,-15} {2,-12}" -f "Offset", "Float Value", "Raw Hex") -ForegroundColor Gray

foreach ($f in $allFloats) {
    $v = $f.Value

    if ([float]::IsNaN($v) -or [float]::IsInfinity($v)) { continue }
    if ($v -eq 0) { continue }
    if ([Math]::Abs($v) -lt 1e-30) { continue }
    if ([Math]::Abs($v) -gt 1e15) { continue }

    $color = 'White'
    # Highlight interesting ranges
    if ([Math]::Abs($v) -ge 500 -and [Math]::Abs($v) -le 10000) { $color = 'Green' }  # game-world
    if ([Math]::Abs($v - 1.0) -lt 0.1) { $color = 'Cyan' }  # near 1.0
    if ($v -ge 5 -and $v -le 30) { $color = 'Yellow' }  # distance range

    Write-Host ("{0,-10} {1,-15} {2,-12}" -f $f.OffsetHex, [Math]::Round($v, 6), $f.RawHex) -ForegroundColor $color
}

Write-Host ""
Write-Host "=== Scan Complete ===" -ForegroundColor Cyan

# Save results to JSON
$resultJson = [ordered]@{
    Mode = 'deep-scan-entry15'
    GeneratedAtUtc = [DateTime]::UtcNow.ToString('o')
    EntryAddress = $entryAddr
    BytesDumped = $bytes.Length
    PlayerPosition = [ordered]@{ X = $playerX; Y = $playerY; Z = $playerZ }
    PositionTriplets = $positionHits
    NormalizedVectors = $normalHits
    DistanceScalars = $distHits
}

$outFile = Join-Path (Join-Path $scriptDir 'captures') 'deep-scan-entry15.json'
$resultJson | ConvertTo-Json -Depth 10 | Set-Content $outFile -Encoding UTF8
Write-Host "Results saved to $outFile" -ForegroundColor Green
