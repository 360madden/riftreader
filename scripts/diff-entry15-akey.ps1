[CmdletBinding()]
param(
    [string]$EntryAddress = '0x1575264C000',
    [int]$ReadLength = 1024,
    [int]$TurnCount = 4,
    [string]$TurnKey = 'A',
    [int]$InterKeyDelayMs = 250,
    [int]$PostTurnWaitMs = 1500,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$readerProject = Join-Path $PSScriptRoot '..' 'reader' 'RiftReader.Reader' 'RiftReader.Reader.csproj'
$keyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'

function Read-MemoryBlock {
    param([string]$Address, [int]$Length)
    $output = & dotnet run --project $readerProject --configuration Release -- `
        --process-name rift_x64 --address $Address --length $Length --json 2>&1
    $jsonText = ($output | Where-Object { $_ -notmatch '^\s*$' }) -join "`n"
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

Write-Host '=== Entry 15 A-Key (Turn Left) Differential ===' -ForegroundColor Cyan
Write-Host "Address: $EntryAddress  Length: $ReadLength bytes  Turn: ${TurnCount}x $TurnKey" -ForegroundColor Cyan
Write-Host ''

# Step 1: Read BEFORE snapshot
Write-Host 'Reading BEFORE snapshot...' -ForegroundColor Yellow
$bytesBefore = Read-MemoryBlock -Address $EntryAddress -Length $ReadLength
$floatsBefore = Get-FloatsFromBytes -Bytes $bytesBefore
Write-Host "  Read $($bytesBefore.Length) bytes ($($floatsBefore.Length) float32 values)" -ForegroundColor Green

# Step 2: Send A key presses (turn left)
Write-Host "Sending ${TurnCount}x $TurnKey key (turn LEFT)..." -ForegroundColor Yellow
for ($i = 0; $i -lt $TurnCount; $i++) {
    & $keyScript -Key $TurnKey
    if ($i -lt ($TurnCount - 1)) {
        Start-Sleep -Milliseconds $InterKeyDelayMs
    }
}
Write-Host "Waiting ${PostTurnWaitMs}ms for game state to settle..." -ForegroundColor Yellow
Start-Sleep -Milliseconds $PostTurnWaitMs

# Step 3: Read AFTER snapshot
Write-Host 'Reading AFTER snapshot...' -ForegroundColor Yellow
$bytesAfter = Read-MemoryBlock -Address $EntryAddress -Length $ReadLength
$floatsAfter = Get-FloatsFromBytes -Bytes $bytesAfter

# Step 4: Special check for vector at +0x338
Write-Host ''
Write-Host '=== VECTOR AT +0x338 (SPECIAL CHECK) ===' -ForegroundColor Magenta
$idx338 = 0x338 / 4  # float index for offset 0x338
if ($idx338 + 2 -lt $floatsBefore.Length) {
    $bx = $floatsBefore[$idx338]; $by = $floatsBefore[$idx338 + 1]; $bz = $floatsBefore[$idx338 + 2]
    $ax = $floatsAfter[$idx338]; $ay = $floatsAfter[$idx338 + 1]; $az = $floatsAfter[$idx338 + 2]
    $magBefore = [Math]::Sqrt($bx * $bx + $by * $by + $bz * $bz)
    $magAfter = [Math]::Sqrt($ax * $ax + $ay * $ay + $az * $az)
    $changed = ([Math]::Abs($ax - $bx) -gt 0.00001) -or ([Math]::Abs($ay - $by) -gt 0.00001) -or ([Math]::Abs($az - $bz) -gt 0.00001)

    Write-Host ("  BEFORE: ({0:F6}, {1:F6}, {2:F6})  mag={3:F6}" -f $bx, $by, $bz, $magBefore)
    Write-Host ("  AFTER:  ({0:F6}, {1:F6}, {2:F6})  mag={3:F6}" -f $ax, $ay, $az, $magAfter)
    Write-Host ("  DELTA:  ({0:F6}, {1:F6}, {2:F6})" -f ($ax - $bx), ($ay - $by), ($az - $bz))
    if ($changed) {
        Write-Host '  STATUS: ** CHANGED ** -- this vector responds to A-key turn!' -ForegroundColor Green
    } else {
        Write-Host '  STATUS: unchanged' -ForegroundColor Red
    }
} else {
    Write-Host '  ERROR: offset 0x338 is beyond the read range' -ForegroundColor Red
}

# Step 5: Compare ALL float values
Write-Host ''
Write-Host '=== ALL CHANGED FLOAT VALUES ===' -ForegroundColor Cyan
Write-Host ''

$changes = @()
$unchangedCount = 0

for ($i = 0; $i -lt $floatsBefore.Length; $i++) {
    $before = $floatsBefore[$i]
    $after = $floatsAfter[$i]
    $delta = $after - $before
    $offset = $i * 4

    if ([Math]::Abs($delta) -gt 0.00001) {
        $classification = Classify-Float -Value $after -Delta $delta
        $offsetHex = '0x{0:X3}' -f $offset

        $entry = [ordered]@{
            Offset = $offsetHex
            OffsetDec = $offset
            FloatIndex = $i
            Before = [Math]::Round($before, 6)
            After = [Math]::Round($after, 6)
            Delta = [Math]::Round($delta, 6)
            AbsDelta = [Math]::Round([Math]::Abs($delta), 6)
            Classification = $classification
        }
        $changes += $entry

        $color = switch ($classification) {
            'orientation' { 'Green' }
            'angle-rad'   { 'Magenta' }
            'angle-deg'   { 'Magenta' }
            'position'    { 'Yellow' }
            default       { 'White' }
        }

        Write-Host ("  {0}  before={1,12:F6}  after={2,12:F6}  delta={3,12:F6}  [{4}]" -f `
            $offsetHex, $before, $after, $delta, $classification) -ForegroundColor $color
    }
    else {
        $unchangedCount++
    }
}

Write-Host ''
Write-Host '=== SUMMARY ===' -ForegroundColor Cyan
Write-Host "  Total float slots: $($floatsBefore.Length)" -ForegroundColor White
Write-Host "  Changed: $($changes.Count)" -ForegroundColor Green
Write-Host "  Unchanged: $unchangedCount" -ForegroundColor Gray

# Group by classification
if ($changes.Count -gt 0) {
    $groups = $changes | Group-Object { $_['Classification'] }
    foreach ($group in $groups) {
        Write-Host "  [$($group.Name)]: $($group.Count) values" -ForegroundColor Yellow
    }
}

# Highlight potential orientation candidates
$orientationChanges = @($changes | Where-Object { $_['Classification'] -eq 'orientation' })
if ($orientationChanges.Count -gt 0) {
    Write-Host ''
    Write-Host '=== ORIENTATION CANDIDATES ===' -ForegroundColor Green
    foreach ($c in $orientationChanges) {
        Write-Host ("  Offset {0}: {1:F6} -> {2:F6} (delta {3:F6})" -f `
            $c['Offset'], $c['Before'], $c['After'], $c['Delta']) -ForegroundColor Green
    }
}

$angleChanges = @($changes | Where-Object { $_['Classification'] -match 'angle' })
if ($angleChanges.Count -gt 0) {
    Write-Host ''
    Write-Host '=== ANGLE CANDIDATES ===' -ForegroundColor Magenta
    foreach ($c in $angleChanges) {
        Write-Host ("  Offset {0}: {1:F6} -> {2:F6} (delta {3:F6})" -f `
            $c['Offset'], $c['Before'], $c['After'], $c['Delta']) -ForegroundColor Magenta
    }
}

# Check for basis matrix patterns (groups of 3 consecutive floats that look like unit vectors)
Write-Host ''
Write-Host '=== BASIS MATRIX CHECK (changed unit vectors) ===' -ForegroundColor Cyan
for ($row = 0; $row -lt ($floatsAfter.Length - 2); $row++) {
    $a = $floatsAfter[$row]
    $b = $floatsAfter[$row + 1]
    $c = $floatsAfter[$row + 2]
    $mag = [Math]::Sqrt($a * $a + $b * $b + $c * $c)
    $offset = $row * 4
    $offsetHex = '0x{0:X3}' -f $offset

    # Check if this triplet is a unit vector (magnitude ~1.0) AND at least one component changed
    if ([Math]::Abs($mag - 1.0) -lt 0.05) {
        $anyChanged = $false
        for ($k = 0; $k -lt 3; $k++) {
            $delta = $floatsAfter[$row + $k] - $floatsBefore[$row + $k]
            if ([Math]::Abs($delta) -gt 0.00001) { $anyChanged = $true }
        }
        if ($anyChanged) {
            $beforeA = $floatsBefore[$row]; $beforeB = $floatsBefore[$row + 1]; $beforeC = $floatsBefore[$row + 2]
            $magBefore = [Math]::Sqrt($beforeA * $beforeA + $beforeB * $beforeB + $beforeC * $beforeC)
            Write-Host ("  Unit vector at {0}: ({1:F4}, {2:F4}, {3:F4}) mag={4:F4}  was ({5:F4}, {6:F4}, {7:F4}) mag={8:F4}" -f `
                $offsetHex, $a, $b, $c, $mag, $beforeA, $beforeB, $beforeC, $magBefore) -ForegroundColor Green
        }
    }
}

# Check nearby offsets around 0x338 for any interesting patterns
Write-Host ''
Write-Host '=== NEIGHBORHOOD AROUND +0x338 (0x320 - 0x360) ===' -ForegroundColor Cyan
$startIdx = 0x320 / 4
$endIdx = [Math]::Min(0x360 / 4, $floatsAfter.Length - 1)
for ($i = $startIdx; $i -le $endIdx; $i++) {
    $offset = $i * 4
    $offsetHex = '0x{0:X3}' -f $offset
    $before = $floatsBefore[$i]
    $after = $floatsAfter[$i]
    $delta = $after - $before
    $marker = if ([Math]::Abs($delta) -gt 0.00001) { ' ** CHANGED **' } else { '' }
    $color = if ([Math]::Abs($delta) -gt 0.00001) { 'Green' } else { 'Gray' }
    Write-Host ("  {0}  before={1,12:F6}  after={2,12:F6}  delta={3,12:F6}{4}" -f `
        $offsetHex, $before, $after, $delta, $marker) -ForegroundColor $color
}

if ($Json) {
    [ordered]@{
        Mode = 'diff-entry15-akey'
        GeneratedAtUtc = [DateTime]::UtcNow.ToString('o')
        EntryAddress = $EntryAddress
        ReadLength = $ReadLength
        TurnKey = $TurnKey
        TurnCount = $TurnCount
        TotalFloatSlots = $floatsBefore.Length
        ChangedCount = $changes.Count
        UnchangedCount = $unchangedCount
        Changes = $changes
    } | ConvertTo-Json -Depth 20
}
