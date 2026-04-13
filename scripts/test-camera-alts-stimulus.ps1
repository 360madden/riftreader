[CmdletBinding()]
param(
    [int]$HoldMilliseconds = 300,
    [int]$WaitMilliseconds = 500,
    [int]$ReadLength = 1024,
    [string]$ProcessName = 'rift_x64',
    [switch]$Json,
    [switch]$SkipBackgroundFocus,
    [switch]$RefreshOwnerComponents
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$readerProject = Join-Path $PSScriptRoot '..' 'reader' 'RiftReader.Reader' 'RiftReader.Reader.csproj'
$keyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'
$ownerComponentsScript = Join-Path $PSScriptRoot 'capture-player-owner-components.ps1'
$ownerComponentsFile = Join-Path $PSScriptRoot 'captures' 'player-owner-components.json'

# --- Helper Functions ---

function Parse-HexUInt64 {
    param([string]$Value)
    if ($Value -match '^0x([0-9A-Fa-f]+)$') {
        return [UInt64]::Parse($Matches[1], [System.Globalization.NumberStyles]::HexNumber)
    }
    return [UInt64]::Parse($Value, [System.Globalization.NumberStyles]::HexNumber)
}

function Read-MemoryBlock {
    param([string]$Address, [int]$Length)
    $output = & dotnet run --project $readerProject --configuration Release -- `
        --process-name $ProcessName --address $Address --length $Length --json 2>&1
    $jsonText = ($output | Where-Object { $_ -notmatch '^\s*$' }) -join "`n"
    $data = $jsonText | ConvertFrom-Json -Depth 30
    $hex = $data.BytesHex -replace ' ', ''
    $bytes = [byte[]]::new($hex.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [Convert]::ToByte($hex.Substring($i * 2, 2), 16)
    }
    return $bytes
}

function Read-Pointer {
    param([string]$Address)
    $bytes = Read-MemoryBlock -Address $Address -Length 8
    return [BitConverter]::ToUInt64($bytes, 0)
}

function Get-FloatsFromBytes {
    param([byte[]]$Bytes)
    $floats = @()
    for ($i = 0; $i -le ($Bytes.Length - 4); $i += 4) {
        $floats += [BitConverter]::ToSingle($Bytes, $i)
    }
    return $floats
}

function Classify-Float {
    param([float]$Value, [float]$Delta)
    $absVal = [Math]::Abs($Value)
    $absDelta = [Math]::Abs($Delta)

    # Orientation: normalized vector components (magnitude near 1.0, values between -1 and 1)
    if ($absVal -le 1.05 -and $absDelta -gt 0.0001 -and $absDelta -lt 2.1) {
        return 'orientation'
    }
    # Angle in radians (0 to 2*pi ~ 6.28)
    if ($absVal -le 6.4 -and $absVal -ge 0.0 -and $absDelta -gt 0.001 -and $absDelta -lt 6.4) {
        return 'angle-rad'
    }
    # Angle in degrees (0 to 360)
    if ($absVal -le 360.0 -and $absVal -ge 0.0 -and $absDelta -gt 0.01 -and $absDelta -lt 360.0) {
        return 'angle-deg'
    }
    # Large world-coordinate values (position)
    if ($absVal -gt 100.0) {
        return 'position'
    }
    return 'unknown'
}

function Diff-FloatArrays {
    param(
        [float[]]$Before,
        [float[]]$After,
        [string]$RegionName,
        [string]$BaseAddress,
        [double]$Threshold = 0.00001
    )

    $changes = @()
    for ($i = 0; $i -lt [Math]::Min($Before.Length, $After.Length); $i++) {
        $delta = $After[$i] - $Before[$i]
        if ([Math]::Abs($delta) -gt $Threshold) {
            $offset = $i * 4
            $changes += [ordered]@{
                Region = $RegionName
                BaseAddress = $BaseAddress
                Offset = ('0x{0:X3}' -f $offset)
                OffsetDec = $offset
                FloatIndex = $i
                Before = [Math]::Round($Before[$i], 6)
                After = [Math]::Round($After[$i], 6)
                Delta = [Math]::Round($delta, 6)
                AbsDelta = [Math]::Round([Math]::Abs($delta), 6)
                Classification = Classify-Float -Value $After[$i] -Delta $delta
            }
        }
    }
    return $changes
}

function Find-UnitVectors {
    param(
        [float[]]$Floats,
        [float[]]$FloatsBefore,
        [string]$RegionName,
        [double]$MagTolerance = 0.05,
        [switch]$OnlyChanged
    )

    $vectors = @()
    for ($row = 0; $row -lt ($Floats.Length - 2); $row++) {
        $a = $Floats[$row]; $b = $Floats[$row + 1]; $c = $Floats[$row + 2]
        $mag = [Math]::Sqrt($a * $a + $b * $b + $c * $c)

        if ([Math]::Abs($mag - 1.0) -lt $MagTolerance) {
            $changed = $false
            if ($null -ne $FloatsBefore) {
                for ($k = 0; $k -lt 3; $k++) {
                    if ([Math]::Abs($Floats[$row + $k] - $FloatsBefore[$row + $k]) -gt 0.00001) {
                        $changed = $true
                    }
                }
            }

            if (-not $OnlyChanged -or $changed) {
                $offset = $row * 4
                $beforeVec = if ($null -ne $FloatsBefore) {
                    @{ X = $FloatsBefore[$row]; Y = $FloatsBefore[$row + 1]; Z = $FloatsBefore[$row + 2] }
                } else { $null }

                $vectors += [ordered]@{
                    Region = $RegionName
                    Offset = ('0x{0:X3}' -f $offset)
                    OffsetDec = $offset
                    X = [Math]::Round($a, 6)
                    Y = [Math]::Round($b, 6)
                    Z = [Math]::Round($c, 6)
                    Magnitude = [Math]::Round($mag, 6)
                    Changed = $changed
                    BeforeVector = $beforeVec
                }
            }
        }
    }
    return $vectors
}

function Check-180DegreeFlip {
    param(
        [float[]]$Before,
        [float[]]$After,
        [string]$RegionName
    )

    $flips = @()
    for ($i = 0; $i -lt ($Before.Length - 2); $i++) {
        $bx = $Before[$i]; $by = $Before[$i + 1]; $bz = $Before[$i + 2]
        $ax = $After[$i]; $ay = $After[$i + 1]; $az = $After[$i + 2]
        $bMag = [Math]::Sqrt($bx*$bx + $by*$by + $bz*$bz)
        $aMag = [Math]::Sqrt($ax*$ax + $ay*$ay + $az*$az)

        # Check for sign-flipped unit vector (180-degree rotation)
        if ([Math]::Abs($bMag - 1.0) -lt 0.05 -and [Math]::Abs($aMag - 1.0) -lt 0.05) {
            $dotProduct = $bx*$ax + $by*$ay + $bz*$az
            # Dot product near -1 means ~180-degree flip
            if ($dotProduct -lt -0.8) {
                $offset = $i * 4
                $flips += [ordered]@{
                    Region = $RegionName
                    Offset = ('0x{0:X3}' -f $offset)
                    OffsetDec = $offset
                    BeforeVector = @{ X = [Math]::Round($bx, 6); Y = [Math]::Round($by, 6); Z = [Math]::Round($bz, 6) }
                    AfterVector = @{ X = [Math]::Round($ax, 6); Y = [Math]::Round($ay, 6); Z = [Math]::Round($az, 6) }
                    DotProduct = [Math]::Round($dotProduct, 6)
                    AngleDegrees = [Math]::Round([Math]::Acos([Math]::Max(-1, [Math]::Min(1, $dotProduct))) * 180.0 / [Math]::PI, 2)
                    Classification = '180-degree-flip'
                }
            }
        }
    }

    # Also check for individual float Euler angle flips (delta near pi or 180)
    for ($i = 0; $i -lt $Before.Length; $i++) {
        $delta = [Math]::Abs($After[$i] - $Before[$i])
        $offset = $i * 4
        if ($delta -gt 2.9 -and $delta -lt 3.4) {
            # Delta near pi radians
            $flips += [ordered]@{
                Region = $RegionName
                Offset = ('0x{0:X3}' -f $offset)
                OffsetDec = $offset
                Before = [Math]::Round($Before[$i], 6)
                After = [Math]::Round($After[$i], 6)
                Delta = [Math]::Round($delta, 6)
                Classification = 'euler-yaw-flip-radians'
            }
        }
        if ($delta -gt 170 -and $delta -lt 190) {
            # Delta near 180 degrees
            $flips += [ordered]@{
                Region = $RegionName
                Offset = ('0x{0:X3}' -f $offset)
                OffsetDec = $offset
                Before = [Math]::Round($Before[$i], 6)
                After = [Math]::Round($After[$i], 6)
                Delta = [Math]::Round($delta, 6)
                Classification = 'euler-yaw-flip-degrees'
            }
        }
    }

    return $flips
}

# --- Main Workflow ---

Write-Host '=== Camera Alt-S Stimulus Test ===' -ForegroundColor Cyan
Write-Host "Stimulus: Alt-S (look behind = ~180-degree camera yaw flip)" -ForegroundColor Cyan
Write-Host ''

# Step 1: Get fresh owner-component addresses
Write-Host 'Step 1: Getting fresh owner-component addresses...' -ForegroundColor Yellow

if ($RefreshOwnerComponents -or -not (Test-Path $ownerComponentsFile)) {
    Write-Host '  Running capture-player-owner-components...' -ForegroundColor Gray
    $ocJson = & $ownerComponentsScript -Json -RefreshSelectorTrace
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to capture owner components."
    }
    $ownerComponents = $ocJson | ConvertFrom-Json -Depth 30
} else {
    Write-Host "  Loading cached: $ownerComponentsFile" -ForegroundColor Gray
    $ownerComponents = Get-Content -LiteralPath $ownerComponentsFile -Raw | ConvertFrom-Json -Depth 30
}

$ownerAddress = Parse-HexUInt64 -Value ([string]$ownerComponents.Owner.Address)
$containerAddress = Parse-HexUInt64 -Value ([string]$ownerComponents.Owner.ContainerAddress)
$selectedSourceAddress = Parse-HexUInt64 -Value ([string]$ownerComponents.Owner.SelectedSourceAddress)
$entryCount = [int]$ownerComponents.EntryCount

Write-Host "  Owner:            0x$($ownerAddress.ToString('X'))" -ForegroundColor Green
Write-Host "  Container:        0x$($containerAddress.ToString('X'))" -ForegroundColor Green
Write-Host "  Selected source:  0x$($selectedSourceAddress.ToString('X'))" -ForegroundColor Green
Write-Host "  Entry count:      $entryCount" -ForegroundColor Green

# Build region list for scanning
$regions = @()

# Region: Selected source (actor orientation control - should NOT change with Alt-S)
$regions += @{
    Name = 'selected-source'
    Address = ('0x{0:X}' -f $selectedSourceAddress)
    Length = 192
    IsControl = $true
}

# Region: Lead A - Owner +0xD0 pointer chain
try {
    $ownerD0Addr = $ownerAddress + 0xD0
    $wrapperPtr = Read-Pointer -Address ('0x{0:X}' -f $ownerD0Addr)
    if ($wrapperPtr -gt 0x10000 -and $wrapperPtr -lt 0x00007FFFFFFFFFFF) {
        $wrapper100Addr = $wrapperPtr + 0x100
        $targetPtr = Read-Pointer -Address ('0x{0:X}' -f $wrapper100Addr)
        if ($targetPtr -gt 0x10000 -and $targetPtr -lt 0x00007FFFFFFFFFFF) {
            $regions += @{
                Name = 'lead-A-owner-D0-chain'
                Address = ('0x{0:X}' -f $targetPtr)
                Length = 256
                IsControl = $false
                PointerChain = "owner+0xD0(0x$($ownerD0Addr.ToString('X'))) -> 0x$($wrapperPtr.ToString('X'))+0x100 -> 0x$($targetPtr.ToString('X'))"
            }
            Write-Host "  Lead A target:    0x$($targetPtr.ToString('X')) (via owner+0xD0 chain)" -ForegroundColor Cyan

            # Also check wrapper +0x188 (second copy from prior session notes)
            $wrapper188Addr = $wrapperPtr + 0x188
            $target2Ptr = Read-Pointer -Address ('0x{0:X}' -f $wrapper188Addr)
            if ($target2Ptr -gt 0x10000 -and $target2Ptr -lt 0x00007FFFFFFFFFFF) {
                $regions += @{
                    Name = 'lead-A-wrapper-188'
                    Address = ('0x{0:X}' -f $target2Ptr)
                    Length = 256
                    IsControl = $false
                    PointerChain = "wrapper+0x188 -> 0x$($target2Ptr.ToString('X'))"
                }
                Write-Host "  Lead A copy:      0x$($target2Ptr.ToString('X')) (via wrapper+0x188)" -ForegroundColor Cyan
            }
        } else {
            Write-Host '  Lead A: wrapper+0x100 pointer invalid, skipping' -ForegroundColor DarkYellow
        }
    } else {
        Write-Host '  Lead A: owner+0xD0 pointer invalid, skipping' -ForegroundColor DarkYellow
    }
} catch {
    Write-Host "  Lead A: failed to resolve pointer chain: $_" -ForegroundColor DarkYellow
}

# Region: Lead B - Container entry 15 (if it exists)
if ($entryCount -ge 16) {
    $entry15 = $ownerComponents.Entries | Where-Object { [int]$_.Index -eq 15 } | Select-Object -First 1
    if ($null -ne $entry15) {
        $entry15Address = Parse-HexUInt64 -Value ([string]$entry15.Address)
        $regions += @{
            Name = 'lead-B-entry15'
            Address = ('0x{0:X}' -f $entry15Address)
            Length = $ReadLength
            IsControl = $false
        }
        Write-Host "  Lead B entry 15:  0x$($entry15Address.ToString('X'))" -ForegroundColor Cyan
    }
} else {
    Write-Host "  Lead B: only $entryCount entries (need 16), skipping entry 15" -ForegroundColor DarkYellow
}

# Also scan entry 4 as a secondary candidate
if ($entryCount -ge 5) {
    $entry4 = $ownerComponents.Entries | Where-Object { [int]$_.Index -eq 4 } | Select-Object -First 1
    if ($null -ne $entry4) {
        $entry4Address = Parse-HexUInt64 -Value ([string]$entry4.Address)
        $regions += @{
            Name = 'entry4'
            Address = ('0x{0:X}' -f $entry4Address)
            Length = 512
            IsControl = $false
        }
        Write-Host "  Entry 4:          0x$($entry4Address.ToString('X'))" -ForegroundColor Cyan
    }
}

# Also read owner neighborhood (+0x00 to +0x200) for undiscovered camera pointers
$regions += @{
    Name = 'owner-neighborhood'
    Address = ('0x{0:X}' -f $ownerAddress)
    Length = 512
    IsControl = $false
}

Write-Host ''
Write-Host "Scanning $($regions.Count) memory regions..." -ForegroundColor Yellow

# Step 2: Read BEFORE snapshots
Write-Host ''
Write-Host 'Step 2: Reading BEFORE snapshots...' -ForegroundColor Yellow
$beforeSnapshots = @{}
foreach ($region in $regions) {
    Write-Host "  Reading $($region.Name) at $($region.Address) ($($region.Length) bytes)..." -ForegroundColor Gray
    try {
        $bytes = Read-MemoryBlock -Address $region.Address -Length $region.Length
        $beforeSnapshots[$region.Name] = @{
            Bytes = $bytes
            Floats = Get-FloatsFromBytes -Bytes $bytes
        }
    } catch {
        Write-Host "  FAILED: $_" -ForegroundColor Red
        $beforeSnapshots[$region.Name] = $null
    }
}

# Step 3: Send Alt-S stimulus
Write-Host ''
Write-Host 'Step 3: Sending Alt-S stimulus (look behind)...' -ForegroundColor Yellow

$keyArgs = @{
    Key = 'S'
    Alt = $true
    HoldMilliseconds = $HoldMilliseconds
}

if ($SkipBackgroundFocus) {
    $keyArgs['SkipBackgroundFocus'] = $true
}

& $keyScript @keyArgs *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host '  WARNING: Alt-S via WM_SYSKEYDOWN may have failed. Check if camera flipped in game.' -ForegroundColor DarkYellow
}

Write-Host "  Waiting ${WaitMilliseconds}ms for game state to settle..." -ForegroundColor Gray
Start-Sleep -Milliseconds $WaitMilliseconds

# Step 4: Read AFTER snapshots
Write-Host ''
Write-Host 'Step 4: Reading AFTER snapshots...' -ForegroundColor Yellow
$afterSnapshots = @{}
foreach ($region in $regions) {
    if ($null -eq $beforeSnapshots[$region.Name]) { continue }
    Write-Host "  Reading $($region.Name)..." -ForegroundColor Gray
    try {
        $bytes = Read-MemoryBlock -Address $region.Address -Length $region.Length
        $afterSnapshots[$region.Name] = @{
            Bytes = $bytes
            Floats = Get-FloatsFromBytes -Bytes $bytes
        }
    } catch {
        Write-Host "  FAILED: $_" -ForegroundColor Red
        $afterSnapshots[$region.Name] = $null
    }
}

# Step 5: Analyze results
Write-Host ''
Write-Host '=== ANALYSIS ===' -ForegroundColor Cyan

$allChanges = @()
$all180Flips = @()
$allUnitVectors = @()

foreach ($region in $regions) {
    $before = $beforeSnapshots[$region.Name]
    $after = $afterSnapshots[$region.Name]
    if ($null -eq $before -or $null -eq $after) { continue }

    $regionLabel = if ($region.IsControl) { "$($region.Name) [CONTROL]" } else { $region.Name }
    Write-Host ''
    Write-Host "--- $regionLabel at $($region.Address) ---" -ForegroundColor Cyan

    # Diff floats
    $changes = Diff-FloatArrays -Before $before.Floats -After $after.Floats -RegionName $region.Name -BaseAddress $region.Address
    $allChanges += $changes

    if ($changes.Count -eq 0) {
        Write-Host '  No float changes detected.' -ForegroundColor Gray
    } else {
        Write-Host "  $($changes.Count) float(s) changed:" -ForegroundColor Green
        foreach ($c in $changes) {
            $color = switch ($c.Classification) {
                'orientation' { 'Green' }
                'angle-rad'   { 'Magenta' }
                'angle-deg'   { 'Magenta' }
                'position'    { 'Yellow' }
                default       { 'White' }
            }
            Write-Host ("    {0}  before={1,12:F6}  after={2,12:F6}  delta={3,12:F6}  [{4}]" -f `
                $c.Offset, $c.Before, $c.After, $c.Delta, $c.Classification) -ForegroundColor $color
        }
    }

    # Check for 180-degree flips (the primary signal)
    $flips = Check-180DegreeFlip -Before $before.Floats -After $after.Floats -RegionName $region.Name
    $all180Flips += $flips
    if ($flips.Count -gt 0) {
        Write-Host ''
        Write-Host "  *** 180-DEGREE FLIP CANDIDATES ***" -ForegroundColor Red
        foreach ($f in $flips) {
            if ($f.Classification -eq '180-degree-flip') {
                Write-Host ("    {0}: ({1:F4},{2:F4},{3:F4}) -> ({4:F4},{5:F4},{6:F4})  dot={7:F4}  angle={8}deg" -f `
                    $f.Offset,
                    $f.BeforeVector.X, $f.BeforeVector.Y, $f.BeforeVector.Z,
                    $f.AfterVector.X, $f.AfterVector.Y, $f.AfterVector.Z,
                    $f.DotProduct, $f.AngleDegrees) -ForegroundColor Red
            } else {
                Write-Host ("    {0}: before={1:F6}  after={2:F6}  delta={3:F6}  [{4}]" -f `
                    $f.Offset, $f.Before, $f.After, $f.Delta, $f.Classification) -ForegroundColor Red
            }
        }
    }

    # Find unit vectors (changed)
    $vectors = Find-UnitVectors -Floats $after.Floats -FloatsBefore $before.Floats -RegionName $region.Name -OnlyChanged
    $allUnitVectors += $vectors
    if ($vectors.Count -gt 0) {
        Write-Host ''
        Write-Host '  Changed unit vectors:' -ForegroundColor Green
        foreach ($v in $vectors) {
            $bv = $v.BeforeVector
            Write-Host ("    {0}: ({1:F4},{2:F4},{3:F4}) mag={4:F4}  was ({5:F4},{6:F4},{7:F4})" -f `
                $v.Offset, $v.X, $v.Y, $v.Z, $v.Magnitude,
                $bv.X, $bv.Y, $bv.Z) -ForegroundColor Green
        }
    }
}

# Step 6: Summary
Write-Host ''
Write-Host '=== SUMMARY ===' -ForegroundColor Cyan
Write-Host "Regions scanned:       $($regions.Count)" -ForegroundColor White
Write-Host "Total float changes:   $($allChanges.Count)" -ForegroundColor White
Write-Host "180-degree flips:      $($all180Flips.Count)" -ForegroundColor $(if ($all180Flips.Count -gt 0) { 'Red' } else { 'Gray' })
Write-Host "Changed unit vectors:  $($allUnitVectors.Count)" -ForegroundColor $(if ($allUnitVectors.Count -gt 0) { 'Green' } else { 'Gray' })

if ($all180Flips.Count -gt 0) {
    Write-Host ''
    Write-Host '*** CAMERA ORIENTATION CANDIDATES FOUND ***' -ForegroundColor Red
    Write-Host 'Run this script again to verify the flip reverses (Alt-S is a toggle).' -ForegroundColor Yellow
    foreach ($f in $all180Flips) {
        Write-Host "  Region: $($f.Region)  Offset: $($f.Offset)  Type: $($f.Classification)" -ForegroundColor Red
    }
} elseif ($allChanges.Count -eq 0) {
    Write-Host ''
    Write-Host 'NO CHANGES DETECTED in any region.' -ForegroundColor DarkYellow
    Write-Host 'Possible causes:' -ForegroundColor DarkYellow
    Write-Host '  1. Alt-S key injection did not work (check game visually)' -ForegroundColor DarkYellow
    Write-Host '  2. Camera data is outside scanned regions (run fallback broad scan)' -ForegroundColor DarkYellow
    Write-Host '  3. PostMessage requires WM_SYSKEYDOWN (already attempted)' -ForegroundColor DarkYellow
}

# JSON output
$resultObject = [ordered]@{
    Mode = 'camera-alts-stimulus'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    Stimulus = 'Alt-S (look behind)'
    HoldMilliseconds = $HoldMilliseconds
    WaitMilliseconds = $WaitMilliseconds
    OwnerAddress = ('0x{0:X}' -f $ownerAddress)
    ContainerAddress = ('0x{0:X}' -f $containerAddress)
    SelectedSourceAddress = ('0x{0:X}' -f $selectedSourceAddress)
    EntryCount = $entryCount
    RegionsScanned = $regions.Count
    RegionDetails = ($regions | ForEach-Object { [ordered]@{ Name = $_.Name; Address = $_.Address; Length = $_.Length; IsControl = $_.IsControl } })
    TotalFloatChanges = $allChanges.Count
    FlipCandidateCount = $all180Flips.Count
    ChangedUnitVectorCount = $allUnitVectors.Count
    Changes = $allChanges
    FlipCandidates = $all180Flips
    ChangedUnitVectors = $allUnitVectors
}

$outputFile = Join-Path $PSScriptRoot 'captures' 'camera-alts-stimulus.json'
$outputDir = Split-Path -Parent $outputFile
if (-not (Test-Path $outputDir)) { New-Item -ItemType Directory -Path $outputDir -Force | Out-Null }
$resultObject | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $outputFile -Encoding UTF8
Write-Host ''
Write-Host "Results saved to: $outputFile" -ForegroundColor Green

if ($Json) {
    Write-Output ($resultObject | ConvertTo-Json -Depth 20)
}
