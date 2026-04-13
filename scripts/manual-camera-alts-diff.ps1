# Manual camera Alt-S diff — reads memory, waits for YOU to press Alt-S, reads again, diffs
# No automated key injection — you press the key manually in RIFT
[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ScanRadiusBytes = 8192,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$readerProject = Join-Path $PSScriptRoot '..' 'reader' 'RiftReader.Reader' 'RiftReader.Reader.csproj'

# --- Helper Functions ---

function Read-MemoryBlock {
    param([string]$AddressHex, [int]$Length)
    $output = & dotnet run --project $readerProject --configuration Release -- `
        --process-name $ProcessName --address $AddressHex --length $Length --json 2>&1
    $combined = ($output | Out-String)
    $startIdx = $combined.IndexOf('{')
    if ($startIdx -lt 0) { throw "No JSON in output for address $AddressHex" }
    $data = $combined.Substring($startIdx) | ConvertFrom-Json -Depth 30
    $hex = $data.BytesHex -replace ' ', ''
    $bytes = [byte[]]::new($hex.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [Convert]::ToByte($hex.Substring($i * 2, 2), 16)
    }
    return $bytes
}

function Get-FloatsFromBytes {
    param([byte[]]$Bytes)
    $floats = [float[]]::new([Math]::Floor($Bytes.Length / 4))
    for ($i = 0; $i -lt $floats.Length; $i++) {
        $floats[$i] = [BitConverter]::ToSingle($Bytes, $i * 4)
    }
    return $floats
}

function Get-PointersFromBytes {
    param([byte[]]$Bytes)
    $ptrs = @()
    for ($i = 0; $i -le ($Bytes.Length - 8); $i += 8) {
        $val = [BitConverter]::ToUInt64($Bytes, $i)
        if ($val -gt 0x10000000000 -and $val -lt 0x00007FFFFFFFFFFF) {
            $ptrs += @{ Offset = $i; Value = $val }
        }
    }
    return $ptrs
}

# --- Main ---

Write-Host '=============================================' -ForegroundColor Cyan
Write-Host '  Camera Alt-S Manual Diff Discovery' -ForegroundColor Cyan
Write-Host '=============================================' -ForegroundColor Cyan
Write-Host ''
Write-Host 'This script reads memory regions, waits for YOU to press' -ForegroundColor Yellow
Write-Host 'Alt-S in the RIFT game window, then reads again and diffs.' -ForegroundColor Yellow
Write-Host ''

# Step 1: Get fresh coord location from read-player-current
Write-Host 'Step 1: Getting fresh player location from memory...' -ForegroundColor Yellow
$currentRaw = & dotnet run --project $readerProject --configuration Release -- `
    --process-name $ProcessName --read-player-current --json 2>&1
$currentStr = ($currentRaw | Out-String)
$startIdx = $currentStr.IndexOf('{')
$current = $currentStr.Substring($startIdx) | ConvertFrom-Json -Depth 30
$coordBaseHex = $current.Memory.AddressHex
$coordBase = [UInt64]::Parse(($coordBaseHex -replace '^0x', ''), [System.Globalization.NumberStyles]::HexNumber)

Write-Host "  Coord base: $coordBaseHex" -ForegroundColor Green
Write-Host "  Coords:     $($current.Memory.CoordX), $($current.Memory.CoordY), $($current.Memory.CoordZ)" -ForegroundColor Green
Write-Host ''

# Step 2: Find all 6 sample addresses from the signature scan (these are copies of player data in different memory regions)
Write-Host 'Step 2: Scanning for all player signature family addresses...' -ForegroundColor Yellow
$sigRaw = & dotnet run --project $readerProject --configuration Release -- `
    --process-name $ProcessName --scan-readerbridge-player-signature --scan-context 192 --max-hits 20 --json 2>&1
$sigStr = ($sigRaw | Out-String)
$sigStart = $sigStr.IndexOf('{')
$sigData = $sigStr.Substring($sigStart) | ConvertFrom-Json -Depth 30

$sampleAddresses = @()
foreach ($hit in $sigData.Hits) {
    $addr = [UInt64]::Parse(($hit.AddressHex -replace '^0x', ''), [System.Globalization.NumberStyles]::HexNumber)
    $sampleAddresses += @{ Address = $addr; Hex = $hit.AddressHex; Score = $hit.Score; Family = $hit.FamilyId }
    Write-Host "  Found: $($hit.AddressHex) score=$($hit.Score) family=$($hit.FamilyId)" -ForegroundColor Gray
}

# Step 3: Build scan regions
# For each sample address, scan a radius around it
# Also scan the region base pages where these addresses live (game data tends to cluster)
Write-Host ''
Write-Host 'Step 3: Building scan regions...' -ForegroundColor Yellow

$regions = @()
$scannedRanges = @{}

foreach ($sample in $sampleAddresses) {
    # Scan radius around each sample address
    $scanStart = $sample.Address - [UInt64]$ScanRadiusBytes
    $scanLen = $ScanRadiusBytes * 2
    $rangeKey = "$scanStart-$scanLen"
    if (-not $scannedRanges.ContainsKey($rangeKey)) {
        $scannedRanges[$rangeKey] = $true
        $regions += @{
            Name = "family-$($sample.Family)-at-$($sample.Hex)"
            AddressHex = '0x' + $scanStart.ToString('X')
            Address = $scanStart
            Length = $scanLen
            SampleAddress = $sample.Address
        }
    }
}

# Also follow pointers from the best-score hit's context
$bestHit = $sampleAddresses | Sort-Object { $_.Score } -Descending | Select-Object -First 1
if ($bestHit) {
    Write-Host "  Best hit: $($bestHit.Hex) (score $($bestHit.Score))" -ForegroundColor Green
    Write-Host "  Reading 4096 bytes around best hit to find pointer targets..." -ForegroundColor Gray

    try {
        $contextStart = $bestHit.Address - 512
        $contextBytes = Read-MemoryBlock -AddressHex ('0x' + $contextStart.ToString('X')) -Length 4096
        $pointers = Get-PointersFromBytes -Bytes $contextBytes

        $uniqueTargets = @{}
        foreach ($ptr in $pointers) {
            $target = $ptr.Value
            # Only follow pointers that point to different memory pages (not self-referencing)
            $targetPage = [Math]::Floor($target / 65536)
            $srcPage = [Math]::Floor($contextStart / 65536)
            if ($targetPage -ne $srcPage -and -not $uniqueTargets.ContainsKey($target)) {
                $uniqueTargets[$target] = $ptr.Offset
            }
        }

        $ptrCount = 0
        foreach ($target in ($uniqueTargets.Keys | Sort-Object | Select-Object -First 8)) {
            $srcOffset = $uniqueTargets[$target]
            $ptrScanStart = [UInt64]$target
            $regions += @{
                Name = "ptr-from-best+0x$($srcOffset.ToString('X3'))->0x$($target.ToString('X'))"
                AddressHex = '0x' + $ptrScanStart.ToString('X')
                Address = $ptrScanStart
                Length = 2048
                SampleAddress = $target
            }
            $ptrCount++
            Write-Host "    Pointer target: +0x$($srcOffset.ToString('X3')) -> 0x$($target.ToString('X'))" -ForegroundColor Gray
        }
        Write-Host "  Added $ptrCount pointer target regions" -ForegroundColor Green
    } catch {
        Write-Host "  Could not read context around best hit: $_" -ForegroundColor DarkYellow
    }
}

Write-Host "  Total regions to scan: $($regions.Count)" -ForegroundColor Green
Write-Host ''

# Step 4: Read BEFORE snapshots
Write-Host 'Step 4: Reading BEFORE snapshots...' -ForegroundColor Yellow
$beforeData = @{}
$failCount = 0
foreach ($r in $regions) {
    try {
        $bytes = Read-MemoryBlock -AddressHex $r.AddressHex -Length $r.Length
        $beforeData[$r.Name] = @{
            Address = $r.Address
            AddressHex = $r.AddressHex
            Length = $r.Length
            Bytes = $bytes
            Floats = Get-FloatsFromBytes -Bytes $bytes
        }
        Write-Host "  OK: $($r.Name) ($($r.Length) bytes)" -ForegroundColor Gray
    } catch {
        Write-Host "  SKIP: $($r.Name) - $_" -ForegroundColor DarkYellow
        $failCount++
    }
}
Write-Host "  Read $($beforeData.Count) regions ($failCount failed)" -ForegroundColor Green

# Step 5: WAIT FOR USER
Write-Host ''
Write-Host '=============================================' -ForegroundColor Red
Write-Host '  NOW: Switch to RIFT and press Alt-S' -ForegroundColor Red
Write-Host '  (Look Behind — should flip camera 180 deg)' -ForegroundColor Red
Write-Host '=============================================' -ForegroundColor Red
Write-Host ''
Write-Host 'Press ENTER here after you have pressed Alt-S in RIFT...' -ForegroundColor Yellow
Read-Host '>>> Waiting for you to press Alt-S in RIFT'

# Step 6: Read AFTER snapshots
Write-Host ''
Write-Host 'Step 6: Reading AFTER snapshots...' -ForegroundColor Yellow
$afterData = @{}
foreach ($name in $beforeData.Keys) {
    $before = $beforeData[$name]
    try {
        $bytes = Read-MemoryBlock -AddressHex $before.AddressHex -Length $before.Length
        $afterData[$name] = @{
            Bytes = $bytes
            Floats = Get-FloatsFromBytes -Bytes $bytes
        }
    } catch {
        Write-Host "  SKIP: $name - $_" -ForegroundColor DarkYellow
    }
}
Write-Host "  Read $($afterData.Count) regions" -ForegroundColor Green

# Step 7: Diff and analyze
Write-Host ''
Write-Host '=== ANALYSIS ===' -ForegroundColor Cyan

$allChanges = @()
$flipCandidates = @()
$eulerFlips = @()

foreach ($name in $beforeData.Keys) {
    if (-not $afterData.ContainsKey($name)) { continue }
    $before = $beforeData[$name]
    $after = $afterData[$name]
    $bf = $before.Floats
    $af = $after.Floats

    $regionChanges = @()

    # Float-by-float diff
    for ($i = 0; $i -lt [Math]::Min($bf.Length, $af.Length); $i++) {
        $delta = $af[$i] - $bf[$i]
        if ([Math]::Abs($delta) -gt 0.00001) {
            $absVal = [Math]::Abs($af[$i])
            $absDelta = [Math]::Abs($delta)

            $classification = 'unknown'
            if ($absVal -le 1.05 -and $absDelta -gt 0.0001) { $classification = 'orientation' }
            elseif ($absVal -le 6.4 -and $absDelta -gt 0.001) { $classification = 'angle-rad' }
            elseif ($absVal -le 360.0 -and $absDelta -gt 0.01) { $classification = 'angle-deg' }
            elseif ($absVal -gt 5.0 -and $absVal -lt 50.0 -and $absDelta -gt 0.1) { $classification = 'distance' }
            elseif ($absVal -gt 100.0 -and $absDelta -gt 0.01) { $classification = 'position' }

            $globalAddr = '0x' + ([UInt64]($before.Address) + [UInt64]($i * 4)).ToString('X')

            $regionChanges += [ordered]@{
                Region = $name
                BaseAddress = $before.AddressHex
                GlobalAddress = $globalAddr
                LocalOffset = ('0x{0:X3}' -f ($i * 4))
                FloatIndex = $i
                Before = [Math]::Round([double]$bf[$i], 6)
                After = [Math]::Round([double]$af[$i], 6)
                Delta = [Math]::Round([double]$delta, 6)
                AbsDelta = [Math]::Round([double]$absDelta, 6)
                Classification = $classification
            }
        }
    }

    $allChanges += $regionChanges

    # Check for 180-degree vector flips (dot product near -1)
    for ($i = 0; $i -lt ($bf.Length - 2); $i++) {
        $bx = $bf[$i]; $by = $bf[$i+1]; $bz = $bf[$i+2]
        $ax = $af[$i]; $ay = $af[$i+1]; $az = $af[$i+2]
        $bMag = [Math]::Sqrt($bx*$bx + $by*$by + $bz*$bz)
        $aMag = [Math]::Sqrt($ax*$ax + $ay*$ay + $az*$az)

        if ([Math]::Abs($bMag - 1.0) -lt 0.05 -and [Math]::Abs($aMag - 1.0) -lt 0.05) {
            $dot = $bx*$ax + $by*$ay + $bz*$az
            if ($dot -lt -0.7) {
                $angleDeg = [Math]::Acos([Math]::Max(-1, [Math]::Min(1, $dot))) * 180.0 / [Math]::PI
                $globalAddr = '0x' + ([UInt64]($before.Address) + [UInt64]($i * 4)).ToString('X')
                $flipCandidates += [ordered]@{
                    Region = $name
                    GlobalAddress = $globalAddr
                    LocalOffset = ('0x{0:X3}' -f ($i * 4))
                    BeforeVector = [ordered]@{ X = [Math]::Round($bx,6); Y = [Math]::Round($by,6); Z = [Math]::Round($bz,6) }
                    AfterVector = [ordered]@{ X = [Math]::Round($ax,6); Y = [Math]::Round($ay,6); Z = [Math]::Round($az,6) }
                    DotProduct = [Math]::Round($dot, 6)
                    AngleDegrees = [Math]::Round($angleDeg, 2)
                    Classification = '180-degree-vector-flip'
                }
            }
        }
    }

    # Check for Euler angle flips (individual float delta near pi or 180)
    for ($i = 0; $i -lt $bf.Length; $i++) {
        $absDelta = [Math]::Abs($af[$i] - $bf[$i])
        if (($absDelta -gt 2.9 -and $absDelta -lt 3.5) -or ($absDelta -gt 170 -and $absDelta -lt 190)) {
            $type = if ($absDelta -lt 10) { 'euler-yaw-radians' } else { 'euler-yaw-degrees' }
            $globalAddr = '0x' + ([UInt64]($before.Address) + [UInt64]($i * 4)).ToString('X')
            $eulerFlips += [ordered]@{
                Region = $name
                GlobalAddress = $globalAddr
                LocalOffset = ('0x{0:X3}' -f ($i * 4))
                Before = [Math]::Round([double]$bf[$i], 6)
                After = [Math]::Round([double]$af[$i], 6)
                Delta = [Math]::Round([double]$absDelta, 6)
                Classification = $type
            }
        }
    }

    # Print region summary
    if ($regionChanges.Count -gt 0 -or $flipCandidates.Count -gt 0) {
        Write-Host ''
        Write-Host "--- $name ($($regionChanges.Count) changes) ---" -ForegroundColor Cyan
        foreach ($c in $regionChanges) {
            $color = switch ($c.Classification) {
                'orientation' { 'Green' }
                'angle-rad' { 'Magenta' }
                'angle-deg' { 'Magenta' }
                'distance' { 'Red' }
                'position' { 'Yellow' }
                default { 'White' }
            }
            Write-Host ("  {0} {1}  before={2,12:F6}  after={3,12:F6}  delta={4,12:F6}  [{5}]" -f `
                $c.GlobalAddress, $c.LocalOffset, $c.Before, $c.After, $c.Delta, $c.Classification) -ForegroundColor $color
        }
    }
}

# Print flip candidates prominently
if ($flipCandidates.Count -gt 0) {
    Write-Host ''
    Write-Host '*** 180-DEGREE VECTOR FLIP CANDIDATES ***' -ForegroundColor Red
    foreach ($f in $flipCandidates) {
        $bv = $f.BeforeVector; $av = $f.AfterVector
        Write-Host ("  {0} {1}: ({2:F4},{3:F4},{4:F4}) -> ({5:F4},{6:F4},{7:F4})  dot={8:F4}  angle={9}deg" -f `
            $f.GlobalAddress, $f.LocalOffset,
            $bv.X, $bv.Y, $bv.Z,
            $av.X, $av.Y, $av.Z,
            $f.DotProduct, $f.AngleDegrees) -ForegroundColor Red
    }
}

if ($eulerFlips.Count -gt 0) {
    Write-Host ''
    Write-Host '*** EULER ANGLE FLIP CANDIDATES ***' -ForegroundColor Red
    foreach ($e in $eulerFlips) {
        Write-Host ("  {0} {1}: {2:F6} -> {3:F6}  delta={4:F6}  [{5}]" -f `
            $e.GlobalAddress, $e.LocalOffset, $e.Before, $e.After, $e.Delta, $e.Classification) -ForegroundColor Red
    }
}

# Summary
Write-Host ''
Write-Host '=== SUMMARY ===' -ForegroundColor Cyan
Write-Host "Regions scanned:          $($beforeData.Count)" -ForegroundColor White
$totalBytes = ($beforeData.Values | ForEach-Object { $_.Length } | Measure-Object -Sum).Sum
Write-Host "Total bytes scanned:      $totalBytes ($([Math]::Round($totalBytes / 1024, 1)) KB)" -ForegroundColor White
Write-Host "Total float changes:      $($allChanges.Count)" -ForegroundColor White
Write-Host "180-deg vector flips:     $($flipCandidates.Count)" -ForegroundColor $(if ($flipCandidates.Count -gt 0) { 'Red' } else { 'Gray' })
Write-Host "Euler angle flips:        $($eulerFlips.Count)" -ForegroundColor $(if ($eulerFlips.Count -gt 0) { 'Red' } else { 'Gray' })

if ($flipCandidates.Count -eq 0 -and $eulerFlips.Count -eq 0 -and $allChanges.Count -eq 0) {
    Write-Host ''
    Write-Host 'NO CHANGES DETECTED.' -ForegroundColor DarkYellow
    Write-Host 'Did you press Alt-S in RIFT? Make sure the game window was focused.' -ForegroundColor DarkYellow
    Write-Host 'If Alt-S did flip the camera, the camera data may be outside the scanned regions.' -ForegroundColor DarkYellow
    Write-Host 'Try increasing -ScanRadiusBytes (default 8192) or use Cheat Engine for a global scan.' -ForegroundColor DarkYellow
}

# Save results
$result = [ordered]@{
    Mode = 'manual-camera-alts-diff'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    CoordBase = $coordBaseHex
    RegionsScanned = $beforeData.Count
    TotalBytesScanned = $totalBytes
    TotalFloatChanges = $allChanges.Count
    VectorFlipCount = $flipCandidates.Count
    EulerFlipCount = $eulerFlips.Count
    FlipCandidates = $flipCandidates
    EulerFlips = $eulerFlips
    Changes = $allChanges
}

$outputFile = Join-Path $PSScriptRoot 'captures' 'manual-camera-alts-diff.json'
$outputDir = Split-Path -Parent $outputFile
if (-not (Test-Path $outputDir)) { New-Item -ItemType Directory -Path $outputDir -Force | Out-Null }
$result | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $outputFile -Encoding UTF8
Write-Host ''
Write-Host "Results saved to: $outputFile" -ForegroundColor Green

if ($Json) {
    Write-Output ($result | ConvertTo-Json -Depth 20)
}
