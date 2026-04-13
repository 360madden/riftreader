# Quick camera Alt-S test — uses anchor cache address directly
# No owner-component trace needed; scans wider regions around coord base
[CmdletBinding()]
param(
    [int]$HoldMilliseconds = 300,
    [int]$WaitMilliseconds = 500,
    [string]$ProcessName = 'rift_x64',
    [switch]$Json,
    [switch]$SkipBackgroundFocus
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$readerProject = Join-Path $PSScriptRoot '..' 'reader' 'RiftReader.Reader' 'RiftReader.Reader.csproj'
$keyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'
$anchorFile = Join-Path $PSScriptRoot 'captures' 'player-current-anchor.json'

# --- Helper Functions ---

function Read-MemoryBlock {
    param([UInt64]$Address, [int]$Length)
    $addrHex = '0x{0:X}' -f $Address
    $output = & dotnet run --project $readerProject --configuration Release -- `
        --process-name $ProcessName --address $addrHex --length $Length --json 2>&1
    $jsonText = ($output | Where-Object { $_ -is [string] -and $_ -notmatch '^\s*$' -and $_ -notmatch '^RiftReader' -and $_ -notmatch '^Use this' -and $_ -notmatch '^Attached' -and $_ -notmatch '^Module:' -and $_ -notmatch '^Window:' }) -join "`n"
    # Find the JSON object
    $startIdx = $jsonText.IndexOf('{')
    if ($startIdx -lt 0) { throw "No JSON in output for address $addrHex" }
    $jsonText = $jsonText.Substring($startIdx)
    $data = $jsonText | ConvertFrom-Json -Depth 30
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

function Classify-Float {
    param([float]$Value, [float]$Delta)
    $absVal = [Math]::Abs($Value)
    $absDelta = [Math]::Abs($Delta)

    if ($absVal -le 1.05 -and $absDelta -gt 0.0001 -and $absDelta -lt 2.1) { return 'orientation' }
    if ($absVal -le 6.4 -and $absDelta -gt 0.001 -and $absDelta -lt 6.4) { return 'angle-rad' }
    if ($absVal -le 360.0 -and $absDelta -gt 0.01 -and $absDelta -lt 360.0) { return 'angle-deg' }
    if ($absVal -gt 5.0 -and $absVal -lt 50.0 -and $absDelta -gt 0.1) { return 'distance' }
    if ($absVal -gt 100.0 -and $absDelta -gt 0.01) { return 'position' }
    return 'unknown'
}

# --- Main ---

Write-Host '=== Quick Camera Alt-S Test ===' -ForegroundColor Cyan
Write-Host 'Stimulus: Alt-S (look behind = ~180-degree camera yaw flip)' -ForegroundColor Cyan
Write-Host ''

# Step 1: Get coord base from anchor cache
if (-not (Test-Path $anchorFile)) {
    Write-Host 'No anchor cache found. Running read-player-current first...' -ForegroundColor Yellow
    & dotnet run --project $readerProject --configuration Release -- `
        --process-name $ProcessName --read-player-current --json 2>&1 | Out-Null
}

$anchor = Get-Content -LiteralPath $anchorFile -Raw | ConvertFrom-Json -Depth 30
$coordBase = [UInt64]::Parse(($anchor.AddressHex -replace '^0x', ''), [System.Globalization.NumberStyles]::HexNumber)

# Selected-source component starts at coordBase - 0x48 (coord48 is at offset +0x48 in the component)
$selectedSource = $coordBase - 0x48
# Actor orientation is at selected-source + 0x60 (forward vector)

Write-Host "Coord base:        0x$($coordBase.ToString('X'))" -ForegroundColor Green
Write-Host "Selected source:   0x$($selectedSource.ToString('X'))" -ForegroundColor Green
Write-Host ''

# Define scan regions:
# 1. Selected-source +0x00 to +0xC0 (actor orientation - CONTROL, should NOT change)
# 2. Selected-source -0x200 to +0x800 (wide scan around component for camera)
# 3. Pointer chase: read pointers within selected-source, follow them

$regions = @(
    @{ Name = 'selected-source-actor'; Base = $selectedSource; Offset = 0; Length = 192; IsControl = $true }
    @{ Name = 'component-pre-header'; Base = $selectedSource; Offset = -512; Length = 512; IsControl = $false }
    @{ Name = 'component-extended'; Base = $selectedSource; Offset = 192; Length = 1856; IsControl = $false }  # +0xC0 to +0x800
)

# Also scan pointers found at 8-byte intervals in the first 256 bytes of the component
# to find objects that might contain camera data
Write-Host 'Scanning for pointer targets in selected-source header...' -ForegroundColor Yellow
$headerBytes = Read-MemoryBlock -Address $selectedSource -Length 256
$pointerTargets = @()
for ($i = 0; $i -le ($headerBytes.Length - 8); $i += 8) {
    $ptr = [BitConverter]::ToUInt64($headerBytes, $i)
    if ($ptr -gt 0x10000 -and $ptr -lt 0x00007FFFFFFFFFFF -and $ptr -ne $selectedSource) {
        $offsetHex = '0x{0:X2}' -f $i
        $pointerTargets += @{ Offset = $i; OffsetHex = $offsetHex; Pointer = $ptr }
        if ($pointerTargets.Count -le 10) {
            Write-Host "  Found pointer at +$offsetHex -> 0x$($ptr.ToString('X'))" -ForegroundColor Gray
        }
    }
}

# Add first 5 unique pointer targets as regions
$uniquePointers = $pointerTargets | Sort-Object { $_.Pointer } -Unique | Select-Object -First 5
foreach ($pt in $uniquePointers) {
    $regions += @{
        Name = "ptr-at-$($pt.OffsetHex)"
        Base = $pt.Pointer
        Offset = 0
        Length = 512
        IsControl = $false
        PointerFrom = "+$($pt.OffsetHex) -> 0x$($pt.Pointer.ToString('X'))"
    }
}

Write-Host "Total regions to scan: $($regions.Count)" -ForegroundColor Green
Write-Host ''

# Step 2: Read BEFORE snapshots
Write-Host 'Step 2: Reading BEFORE snapshots...' -ForegroundColor Yellow
$beforeData = @{}
foreach ($r in $regions) {
    $addr = [UInt64]([UInt64]$r.Base + [Int64]$r.Offset)
    $addrHex = '0x' + $addr.ToString('X')
    Write-Host "  $($r.Name) at $addrHex ($($r.Length) bytes)..." -ForegroundColor Gray
    try {
        $bytes = Read-MemoryBlock -Address $addr -Length $r.Length
        $beforeData[$r.Name] = @{
            Address = $addr
            AddressHex = $addrHex
            Bytes = $bytes
            Floats = Get-FloatsFromBytes -Bytes $bytes
        }
    } catch {
        Write-Host "    FAILED: $_" -ForegroundColor Red
    }
}

# Step 3: Send Alt-S stimulus
Write-Host ''
Write-Host 'Step 3: Sending Alt-S stimulus...' -ForegroundColor Yellow

$keyArgs = @{ Key = 'S'; Alt = $true; HoldMilliseconds = $HoldMilliseconds }
if ($SkipBackgroundFocus) { $keyArgs['SkipBackgroundFocus'] = $true }
& $keyScript @keyArgs *> $null

Write-Host "  Waiting ${WaitMilliseconds}ms..." -ForegroundColor Gray
Start-Sleep -Milliseconds $WaitMilliseconds

# Step 4: Read AFTER snapshots
Write-Host 'Step 4: Reading AFTER snapshots...' -ForegroundColor Yellow
$afterData = @{}
foreach ($r in $regions) {
    if (-not $beforeData.ContainsKey($r.Name)) { continue }
    $addr = $beforeData[$r.Name].Address
    try {
        $bytes = Read-MemoryBlock -Address $addr -Length $r.Length
        $afterData[$r.Name] = @{
            Address = $addr
            Bytes = $bytes
            Floats = Get-FloatsFromBytes -Bytes $bytes
        }
    } catch {
        Write-Host "    FAILED $($r.Name): $_" -ForegroundColor Red
    }
}

# Step 5: Analyze
Write-Host ''
Write-Host '=== ANALYSIS ===' -ForegroundColor Cyan

$allChanges = @()
$flipCandidates = @()

foreach ($r in $regions) {
    $before = $beforeData[$r.Name]
    $after = $afterData[$r.Name]
    if ($null -eq $before -or $null -eq $after) { continue }

    $label = if ($r.IsControl) { "$($r.Name) [CONTROL]" } else { $r.Name }
    $changes = @()

    for ($i = 0; $i -lt [Math]::Min($before.Floats.Length, $after.Floats.Length); $i++) {
        $delta = $after.Floats[$i] - $before.Floats[$i]
        if ([Math]::Abs($delta) -gt 0.00001) {
            $offset = $i * 4 + [Math]::Max(0, $r.Offset)
            $classification = Classify-Float -Value $after.Floats[$i] -Delta $delta
            $changes += [ordered]@{
                Region = $r.Name
                Address = $before.AddressHex
                LocalOffset = ('0x{0:X3}' -f ($i * 4))
                GlobalOffset = ('0x{0:X3}' -f $offset)
                FloatIndex = $i
                Before = [Math]::Round($before.Floats[$i], 6)
                After = [Math]::Round($after.Floats[$i], 6)
                Delta = [Math]::Round($delta, 6)
                AbsDelta = [Math]::Round([Math]::Abs($delta), 6)
                Classification = $classification
            }
        }
    }

    $allChanges += $changes

    if ($changes.Count -gt 0) {
        Write-Host ''
        Write-Host "--- $label at $($before.AddressHex) ($($changes.Count) changes) ---" -ForegroundColor Cyan
        foreach ($c in $changes) {
            $color = switch ($c.Classification) {
                'orientation' { 'Green' }
                'angle-rad'   { 'Magenta' }
                'angle-deg'   { 'Magenta' }
                'distance'    { 'Red' }
                'position'    { 'Yellow' }
                default       { 'White' }
            }
            Write-Host ("  {0}  before={1,12:F6}  after={2,12:F6}  delta={3,12:F6}  [{4}]" -f `
                $c.LocalOffset, $c.Before, $c.After, $c.Delta, $c.Classification) -ForegroundColor $color
        }
    } else {
        Write-Host "--- ${label}: no changes ---" -ForegroundColor Gray
    }

    # Check for 180-degree vector flips
    for ($i = 0; $i -lt ($before.Floats.Length - 2); $i++) {
        $bx = $before.Floats[$i]; $by = $before.Floats[$i+1]; $bz = $before.Floats[$i+2]
        $ax = $after.Floats[$i]; $ay = $after.Floats[$i+1]; $az = $after.Floats[$i+2]
        $bMag = [Math]::Sqrt($bx*$bx + $by*$by + $bz*$bz)
        $aMag = [Math]::Sqrt($ax*$ax + $ay*$ay + $az*$az)

        if ([Math]::Abs($bMag - 1.0) -lt 0.05 -and [Math]::Abs($aMag - 1.0) -lt 0.05) {
            $dot = $bx*$ax + $by*$ay + $bz*$az
            if ($dot -lt -0.8) {
                $localOff = '0x{0:X3}' -f ($i * 4)
                $flipCandidates += [ordered]@{
                    Region = $r.Name
                    Address = $before.AddressHex
                    LocalOffset = $localOff
                    Before = @{ X = [Math]::Round($bx, 6); Y = [Math]::Round($by, 6); Z = [Math]::Round($bz, 6) }
                    After = @{ X = [Math]::Round($ax, 6); Y = [Math]::Round($ay, 6); Z = [Math]::Round($az, 6) }
                    DotProduct = [Math]::Round($dot, 6)
                    AngleDeg = [Math]::Round([Math]::Acos([Math]::Max(-1, [Math]::Min(1, $dot))) * 180.0 / [Math]::PI, 2)
                }
                Write-Host "  *** 180-DEG FLIP at ${localOff}: ($([Math]::Round($bx,3)),$([Math]::Round($by,3)),$([Math]::Round($bz,3))) -> ($([Math]::Round($ax,3)),$([Math]::Round($ay,3)),$([Math]::Round($az,3))) dot=$([Math]::Round($dot,3)) ***" -ForegroundColor Red
            }
        }
    }

    # Check for Euler angle flips (delta near pi or 180)
    for ($i = 0; $i -lt $before.Floats.Length; $i++) {
        $delta = [Math]::Abs($after.Floats[$i] - $before.Floats[$i])
        if (($delta -gt 2.9 -and $delta -lt 3.4) -or ($delta -gt 170 -and $delta -lt 190)) {
            $localOff = '0x{0:X3}' -f ($i * 4)
            $type = if ($delta -lt 10) { 'euler-flip-radians' } else { 'euler-flip-degrees' }
            $flipCandidates += [ordered]@{
                Region = $r.Name
                Address = $before.AddressHex
                LocalOffset = $localOff
                Before = [Math]::Round($before.Floats[$i], 6)
                After = [Math]::Round($after.Floats[$i], 6)
                Delta = [Math]::Round($delta, 6)
                Type = $type
            }
            Write-Host "  *** EULER FLIP at ${localOff}: $([Math]::Round($before.Floats[$i],4)) -> $([Math]::Round($after.Floats[$i],4)) delta=$([Math]::Round($delta,4)) [$type] ***" -ForegroundColor Red
        }
    }
}

# Summary
Write-Host ''
Write-Host '=== SUMMARY ===' -ForegroundColor Cyan
Write-Host "Regions scanned:      $($regions.Count)" -ForegroundColor White
Write-Host "Total float changes:  $($allChanges.Count)" -ForegroundColor White
Write-Host "180-deg flip candidates: $($flipCandidates.Count)" -ForegroundColor $(if ($flipCandidates.Count -gt 0) { 'Red' } else { 'Gray' })

if ($flipCandidates.Count -gt 0) {
    Write-Host ''
    Write-Host '*** CAMERA CANDIDATES FOUND! ***' -ForegroundColor Red
    foreach ($f in $flipCandidates) {
        Write-Host "  Region=$($f.Region) Offset=$($f.LocalOffset) Address=$($f.Address)" -ForegroundColor Red
    }
} elseif ($allChanges.Count -eq 0) {
    Write-Host ''
    Write-Host 'NO CHANGES DETECTED.' -ForegroundColor DarkYellow
    Write-Host 'Alt-S may not have worked. Check game visually or try -SkipBackgroundFocus.' -ForegroundColor DarkYellow
} else {
    Write-Host ''
    Write-Host "Changes found but no 180-degree flips. Camera may be outside scanned area." -ForegroundColor DarkYellow
    Write-Host "Consider broader scan or check pointer targets manually." -ForegroundColor DarkYellow
}

# Save results
$result = [ordered]@{
    Mode = 'quick-camera-alts-test'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    CoordBase = '0x{0:X}' -f $coordBase
    SelectedSource = '0x{0:X}' -f $selectedSource
    RegionsScanned = $regions.Count
    TotalChanges = $allChanges.Count
    FlipCandidateCount = $flipCandidates.Count
    PointerTargetsFound = $pointerTargets.Count
    Changes = $allChanges
    FlipCandidates = $flipCandidates
}

$outputFile = Join-Path $PSScriptRoot 'captures' 'quick-camera-alts-test.json'
$outputDir = Split-Path -Parent $outputFile
if (-not (Test-Path $outputDir)) { New-Item -ItemType Directory -Path $outputDir -Force | Out-Null }
$result | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $outputFile -Encoding UTF8
Write-Host ''
Write-Host "Results saved to: $outputFile" -ForegroundColor Green

if ($Json) {
    Write-Output ($result | ConvertTo-Json -Depth 20)
}
