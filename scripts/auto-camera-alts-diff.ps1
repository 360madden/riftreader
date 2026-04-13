# Automated camera Alt-S diff — sends Alt-S via PostMessage, reads before/after, diffs
# Scans broadly around all player signature family addresses + pointer targets
[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ScanRadiusBytes = 8192,
    [int]$HoldMilliseconds = 300,
    [int]$WaitMilliseconds = 1000,
    [switch]$Json,
    [switch]$SkipBackgroundFocus
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$readerProject = Join-Path $PSScriptRoot '..' 'reader' 'RiftReader.Reader' 'RiftReader.Reader.csproj'
$keyScript = Join-Path $PSScriptRoot 'send-rift-key.ps1'

# --- Helper Functions ---

function Read-MemoryBlock {
    param([string]$AddressHex, [int]$Length)
    $output = & dotnet run --project $readerProject --configuration Release -- `
        --process-name $ProcessName --address $AddressHex --length $Length --json 2>&1
    $combined = ($output | Out-String)
    $startIdx = $combined.IndexOf('{')
    if ($startIdx -lt 0) { throw "No JSON for $AddressHex" }
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
Write-Host '  Automated Camera Alt-S Diff Discovery' -ForegroundColor Cyan
Write-Host '=============================================' -ForegroundColor Cyan
Write-Host ''

# Step 1: Locate all player data addresses via signature scan
Write-Host 'Step 1: Scanning for all player signature family addresses...' -ForegroundColor Yellow
$sigRaw = & dotnet run --project $readerProject --configuration Release -- `
    --process-name $ProcessName --scan-readerbridge-player-signature --scan-context 512 --max-hits 20 --json 2>&1
$sigStr = ($sigRaw | Out-String)
$sigStart = $sigStr.IndexOf('{')
if ($sigStart -lt 0) {
    Write-Host '' -ForegroundColor Red
    Write-Host 'ERROR: Signature scan returned no JSON.' -ForegroundColor Red
    Write-Host 'Make sure RIFT is running, you are logged in, and ReaderBridge export is fresh.' -ForegroundColor Red
    Write-Host '' -ForegroundColor Yellow
    Write-Host 'Scanner output:' -ForegroundColor Yellow
    Write-Host $sigStr -ForegroundColor Gray
    Write-Host '' -ForegroundColor Yellow
    Write-Host 'Try: /reloadui in RIFT, then: scripts\read-player-current.cmd' -ForegroundColor Yellow
    exit 1
}
$sigData = $sigStr.Substring($sigStart) | ConvertFrom-Json -Depth 30

Write-Host "  Found $($sigData.HitCount) hits in $($sigData.FamilyCount) families" -ForegroundColor Green

# Build region list from all hits
$regions = @()
$scannedPages = @{}

foreach ($hit in $sigData.Hits) {
    $addr = [UInt64]::Parse(($hit.AddressHex -replace '^0x', ''), [System.Globalization.NumberStyles]::HexNumber)
    $scanStart = $addr - [UInt64]$ScanRadiusBytes
    $scanLen = $ScanRadiusBytes * 2
    $pageKey = [Math]::Floor($scanStart / 65536)

    if (-not $scannedPages.ContainsKey($pageKey)) {
        $scannedPages[$pageKey] = $true
        $regions += @{
            Name = "sig-$($hit.FamilyId)-$($hit.AddressHex)"
            AddressHex = '0x' + $scanStart.ToString('X')
            Address = $scanStart
            Length = $scanLen
        }
        Write-Host "  Region: $($hit.AddressHex) (score=$($hit.Score), family=$($hit.FamilyId))" -ForegroundColor Gray
    }
}

# Step 2: Follow pointers from the best-scoring hit's extended context
$bestHit = $sigData.Hits | Sort-Object { $_.Score } -Descending | Select-Object -First 1
if ($bestHit -and $bestHit.Context) {
    Write-Host ''
    Write-Host 'Step 2: Following pointers from best hit context...' -ForegroundColor Yellow

    $contextHex = $bestHit.Context.BytesHex -replace ' ', ''
    $contextBytes = [byte[]]::new($contextHex.Length / 2)
    for ($i = 0; $i -lt $contextBytes.Length; $i++) {
        $contextBytes[$i] = [Convert]::ToByte($contextHex.Substring($i * 2, 2), 16)
    }

    $contextBase = [UInt64]::Parse(($bestHit.Context.WindowStart -replace '^0x', ''), [System.Globalization.NumberStyles]::HexNumber)
    $pointers = Get-PointersFromBytes -Bytes $contextBytes

    $uniqueTargets = @{}
    foreach ($ptr in $pointers) {
        $target = $ptr.Value
        $targetPage = [Math]::Floor($target / 65536)
        $srcPage = [Math]::Floor($contextBase / 65536)
        if ($targetPage -ne $srcPage -and -not $uniqueTargets.ContainsKey($target) -and -not $scannedPages.ContainsKey($targetPage)) {
            $uniqueTargets[$target] = $ptr.Offset
        }
    }

    $ptrTargets = $uniqueTargets.Keys | Sort-Object | Select-Object -First 12
    foreach ($target in $ptrTargets) {
        $srcOffset = $uniqueTargets[$target]
        $regions += @{
            Name = "ptr-best+0x$($srcOffset.ToString('X3'))->0x$($target.ToString('X'))"
            AddressHex = '0x' + ([UInt64]$target).ToString('X')
            Address = [UInt64]$target
            Length = 4096
        }
        Write-Host "  Pointer: ctx+0x$($srcOffset.ToString('X3')) -> 0x$($target.ToString('X'))" -ForegroundColor Gray
    }

    # Also read 2 levels deep: follow pointers from the first-level targets
    Write-Host '  Following second-level pointers...' -ForegroundColor Gray
    $level2Count = 0
    foreach ($target in ($ptrTargets | Select-Object -First 6)) {
        try {
            $l1Bytes = Read-MemoryBlock -AddressHex ('0x' + ([UInt64]$target).ToString('X')) -Length 512
            $l1Ptrs = Get-PointersFromBytes -Bytes $l1Bytes
            foreach ($l1ptr in ($l1Ptrs | Select-Object -First 4)) {
                $l2Target = $l1ptr.Value
                $l2Page = [Math]::Floor($l2Target / 65536)
                if (-not $scannedPages.ContainsKey($l2Page)) {
                    $scannedPages[$l2Page] = $true
                    $regions += @{
                        Name = "l2-0x$($target.ToString('X'))+0x$($l1ptr.Offset.ToString('X3'))->0x$($l2Target.ToString('X'))"
                        AddressHex = '0x' + $l2Target.ToString('X')
                        Address = $l2Target
                        Length = 2048
                    }
                    $level2Count++
                }
            }
        } catch {
            # Skip unreadable targets
        }
    }
    Write-Host "  Added $level2Count second-level pointer regions" -ForegroundColor Green
}

Write-Host ''
Write-Host "Total regions to scan: $($regions.Count)" -ForegroundColor Green

# Step 3: Read BEFORE snapshots
Write-Host ''
Write-Host 'Step 3: Reading BEFORE snapshots...' -ForegroundColor Yellow
$beforeData = @{}
$readCount = 0
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
        $readCount++
    } catch {
        # Skip unreadable regions silently
    }
}
Write-Host "  Successfully read $readCount of $($regions.Count) regions" -ForegroundColor Green

# Step 4: Send Alt-S stimulus
Write-Host ''
Write-Host 'Step 4: Sending Alt-S stimulus...' -ForegroundColor Yellow

$keyArgs = @{
    Key = 'S'
    Alt = $true
    HoldMilliseconds = $HoldMilliseconds
}

& $keyScript @keyArgs
Write-Host "  Waiting ${WaitMilliseconds}ms for game state to settle..." -ForegroundColor Gray
Start-Sleep -Milliseconds $WaitMilliseconds

# Step 5: Read AFTER snapshots
Write-Host ''
Write-Host 'Step 5: Reading AFTER snapshots...' -ForegroundColor Yellow
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
        # Skip
    }
}
Write-Host "  Read $($afterData.Count) regions" -ForegroundColor Green

# Step 6: Diff and analyze
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
                GlobalAddress = $globalAddr
                LocalOffset = ('0x{0:X3}' -f ($i * 4))
                Before = [Math]::Round([double]$bf[$i], 6)
                After = [Math]::Round([double]$af[$i], 6)
                Delta = [Math]::Round([double]$delta, 6)
                AbsDelta = [Math]::Round([double]$absDelta, 6)
                Classification = $classification
            }
        }
    }

    $allChanges += $regionChanges

    # 180-degree vector flip detection
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
                }
            }
        }
    }

    # Euler angle flips
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

    # Print significant regions
    if ($regionChanges.Count -gt 0) {
        Write-Host ''
        Write-Host "--- $name ($($regionChanges.Count) changes) ---" -ForegroundColor Cyan
        foreach ($c in ($regionChanges | Sort-Object { $_.AbsDelta } -Descending | Select-Object -First 20)) {
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
        if ($regionChanges.Count -gt 20) {
            Write-Host "  ... and $($regionChanges.Count - 20) more" -ForegroundColor Gray
        }
    }
}

# Print flip candidates prominently
if ($flipCandidates.Count -gt 0) {
    Write-Host ''
    Write-Host '=========================================' -ForegroundColor Red
    Write-Host '  180-DEGREE VECTOR FLIP CANDIDATES' -ForegroundColor Red
    Write-Host '=========================================' -ForegroundColor Red
    foreach ($f in $flipCandidates) {
        $bv = $f.BeforeVector; $av = $f.AfterVector
        Write-Host ("  {0} {1}: ({2:F4},{3:F4},{4:F4}) -> ({5:F4},{6:F4},{7:F4})  dot={8:F4}  angle={9}deg" -f `
            $f.GlobalAddress, $f.LocalOffset,
            $bv.X, $bv.Y, $bv.Z,
            $av.X, $av.Y, $av.Z,
            $f.DotProduct, $f.AngleDegrees) -ForegroundColor Red
        Write-Host "    Region: $($f.Region)" -ForegroundColor DarkYellow
    }
}

if ($eulerFlips.Count -gt 0) {
    Write-Host ''
    Write-Host '=========================================' -ForegroundColor Red
    Write-Host '  EULER ANGLE FLIP CANDIDATES' -ForegroundColor Red
    Write-Host '=========================================' -ForegroundColor Red
    foreach ($e in $eulerFlips) {
        Write-Host ("  {0} {1}: {2:F6} -> {3:F6}  delta={4:F6}  [{5}]" -f `
            $e.GlobalAddress, $e.LocalOffset, $e.Before, $e.After, $e.Delta, $e.Classification) -ForegroundColor Red
        Write-Host "    Region: $($e.Region)" -ForegroundColor DarkYellow
    }
}

# Summary
Write-Host ''
Write-Host '=== SUMMARY ===' -ForegroundColor Cyan
$totalBytes = 0
foreach ($v in $beforeData.Values) { $totalBytes += $v.Length }
Write-Host "Regions scanned:          $($beforeData.Count)" -ForegroundColor White
Write-Host "Total bytes scanned:      $totalBytes ($([Math]::Round($totalBytes / 1024, 1)) KB)" -ForegroundColor White
Write-Host "Total float changes:      $($allChanges.Count)" -ForegroundColor White
Write-Host "180-deg vector flips:     $($flipCandidates.Count)" -ForegroundColor $(if ($flipCandidates.Count -gt 0) { 'Red' } else { 'Gray' })
Write-Host "Euler angle flips:        $($eulerFlips.Count)" -ForegroundColor $(if ($eulerFlips.Count -gt 0) { 'Red' } else { 'Gray' })

if ($flipCandidates.Count -eq 0 -and $eulerFlips.Count -eq 0) {
    if ($allChanges.Count -gt 0) {
        Write-Host ''
        Write-Host 'Changes found but no 180-degree flips detected.' -ForegroundColor DarkYellow
        Write-Host 'Camera data may be outside the scanned neighborhood.' -ForegroundColor DarkYellow
        Write-Host 'Try -ScanRadiusBytes 32768 for wider coverage.' -ForegroundColor DarkYellow
    } else {
        Write-Host ''
        Write-Host 'NO CHANGES DETECTED AT ALL.' -ForegroundColor DarkYellow
        Write-Host 'Either Alt-S did not work, or camera data is in a completely different memory region.' -ForegroundColor DarkYellow
    }
}

# Save results
$result = [ordered]@{
    Mode = 'auto-camera-alts-diff'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    Stimulus = 'Alt-S (look behind)'
    HoldMilliseconds = $HoldMilliseconds
    WaitMilliseconds = $WaitMilliseconds
    RegionsScanned = $beforeData.Count
    TotalBytesScanned = $totalBytes
    TotalFloatChanges = $allChanges.Count
    VectorFlipCount = $flipCandidates.Count
    EulerFlipCount = $eulerFlips.Count
    FlipCandidates = $flipCandidates
    EulerFlips = $eulerFlips
    AllChanges = $allChanges
}

$outputFile = Join-Path $PSScriptRoot 'captures' 'auto-camera-alts-diff.json'
$outputDir = Split-Path -Parent $outputFile
if (-not (Test-Path $outputDir)) { New-Item -ItemType Directory -Path $outputDir -Force | Out-Null }
$result | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $outputFile -Encoding UTF8
Write-Host ''
Write-Host "Results saved to: $outputFile" -ForegroundColor Green

if ($Json) {
    Write-Output ($result | ConvertTo-Json -Depth 20)
}
