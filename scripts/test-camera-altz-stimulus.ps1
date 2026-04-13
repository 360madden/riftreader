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

# --- Helper Functions (shared with test-camera-alts-stimulus.ps1) ---

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

    if ($absVal -le 1.05 -and $absDelta -gt 0.0001 -and $absDelta -lt 2.1) { return 'orientation' }
    if ($absVal -le 6.4 -and $absDelta -gt 0.001 -and $absDelta -lt 6.4) { return 'angle-rad' }
    if ($absVal -le 360.0 -and $absDelta -gt 0.01 -and $absDelta -lt 360.0) { return 'angle-deg' }
    if ($absVal -gt 5.0 -and $absVal -lt 50.0 -and $absDelta -gt 0.1) { return 'distance' }
    if ($absVal -gt 100.0) { return 'position' }
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

# --- Main Workflow ---

Write-Host '=== Camera Alt-Z Stimulus Test (Zoom Cross-Validation) ===' -ForegroundColor Cyan
Write-Host "Stimulus: Alt-Z (alternate zoom toggle)" -ForegroundColor Cyan
Write-Host "Expected: distance/zoom scalar changes, direction vector stays the same" -ForegroundColor Cyan
Write-Host ''

# Step 1: Get fresh owner-component addresses
Write-Host 'Step 1: Getting fresh owner-component addresses...' -ForegroundColor Yellow

if ($RefreshOwnerComponents -or -not (Test-Path $ownerComponentsFile)) {
    $ocJson = & $ownerComponentsScript -Json -RefreshSelectorTrace
    if ($LASTEXITCODE -ne 0) { throw "Failed to capture owner components." }
    $ownerComponents = $ocJson | ConvertFrom-Json -Depth 30
} else {
    $ownerComponents = Get-Content -LiteralPath $ownerComponentsFile -Raw | ConvertFrom-Json -Depth 30
}

$ownerAddress = Parse-HexUInt64 -Value ([string]$ownerComponents.Owner.Address)
$containerAddress = Parse-HexUInt64 -Value ([string]$ownerComponents.Owner.ContainerAddress)
$selectedSourceAddress = Parse-HexUInt64 -Value ([string]$ownerComponents.Owner.SelectedSourceAddress)
$entryCount = [int]$ownerComponents.EntryCount

Write-Host "  Owner:            0x$($ownerAddress.ToString('X'))" -ForegroundColor Green
Write-Host "  Entry count:      $entryCount" -ForegroundColor Green

# Build same regions as Alt-S test for cross-comparison
$regions = @()

# Selected source (control)
$regions += @{ Name = 'selected-source'; Address = ('0x{0:X}' -f $selectedSourceAddress); Length = 192; IsControl = $true }

# Lead A
try {
    $wrapperPtr = Read-Pointer -Address ('0x{0:X}' -f ($ownerAddress + 0xD0))
    if ($wrapperPtr -gt 0x10000 -and $wrapperPtr -lt 0x00007FFFFFFFFFFF) {
        $targetPtr = Read-Pointer -Address ('0x{0:X}' -f ($wrapperPtr + 0x100))
        if ($targetPtr -gt 0x10000 -and $targetPtr -lt 0x00007FFFFFFFFFFF) {
            $regions += @{ Name = 'lead-A-owner-D0-chain'; Address = ('0x{0:X}' -f $targetPtr); Length = 256; IsControl = $false }
            Write-Host "  Lead A target:    0x$($targetPtr.ToString('X'))" -ForegroundColor Cyan
        }
    }
} catch {
    Write-Host "  Lead A: pointer chain failed: $_" -ForegroundColor DarkYellow
}

# Lead B - entry 15
if ($entryCount -ge 16) {
    $entry15 = $ownerComponents.Entries | Where-Object { [int]$_.Index -eq 15 } | Select-Object -First 1
    if ($null -ne $entry15) {
        $entry15Address = Parse-HexUInt64 -Value ([string]$entry15.Address)
        $regions += @{ Name = 'lead-B-entry15'; Address = ('0x{0:X}' -f $entry15Address); Length = $ReadLength; IsControl = $false }
        Write-Host "  Lead B entry 15:  0x$($entry15Address.ToString('X'))" -ForegroundColor Cyan
    }
}

# Entry 4
if ($entryCount -ge 5) {
    $entry4 = $ownerComponents.Entries | Where-Object { [int]$_.Index -eq 4 } | Select-Object -First 1
    if ($null -ne $entry4) {
        $entry4Address = Parse-HexUInt64 -Value ([string]$entry4.Address)
        $regions += @{ Name = 'entry4'; Address = ('0x{0:X}' -f $entry4Address); Length = 512; IsControl = $false }
    }
}

# Owner neighborhood
$regions += @{ Name = 'owner-neighborhood'; Address = ('0x{0:X}' -f $ownerAddress); Length = 512; IsControl = $false }

Write-Host ''
Write-Host "Scanning $($regions.Count) memory regions..." -ForegroundColor Yellow

# Step 2: Read BEFORE
Write-Host 'Step 2: Reading BEFORE snapshots...' -ForegroundColor Yellow
$beforeSnapshots = @{}
foreach ($region in $regions) {
    try {
        $bytes = Read-MemoryBlock -Address $region.Address -Length $region.Length
        $beforeSnapshots[$region.Name] = @{ Bytes = $bytes; Floats = Get-FloatsFromBytes -Bytes $bytes }
    } catch {
        Write-Host "  FAILED $($region.Name): $_" -ForegroundColor Red
    }
}

# Step 3: Send Alt-Z stimulus
Write-Host ''
Write-Host 'Step 3: Sending Alt-Z stimulus (alternate zoom)...' -ForegroundColor Yellow

$keyArgs = @{ Key = 'Z'; Alt = $true; HoldMilliseconds = $HoldMilliseconds }
if ($SkipBackgroundFocus) { $keyArgs['SkipBackgroundFocus'] = $true }

& $keyScript @keyArgs *> $null
Start-Sleep -Milliseconds $WaitMilliseconds

# Step 4: Read AFTER
Write-Host 'Step 4: Reading AFTER snapshots...' -ForegroundColor Yellow
$afterSnapshots = @{}
foreach ($region in $regions) {
    if (-not $beforeSnapshots.ContainsKey($region.Name)) { continue }
    try {
        $bytes = Read-MemoryBlock -Address $region.Address -Length $region.Length
        $afterSnapshots[$region.Name] = @{ Bytes = $bytes; Floats = Get-FloatsFromBytes -Bytes $bytes }
    } catch {
        Write-Host "  FAILED $($region.Name): $_" -ForegroundColor Red
    }
}

# Step 5: Analyze - focus on distance/zoom changes
Write-Host ''
Write-Host '=== ANALYSIS ===' -ForegroundColor Cyan

$allChanges = @()
$distanceCandidates = @()

foreach ($region in $regions) {
    $before = $beforeSnapshots[$region.Name]
    $after = $afterSnapshots[$region.Name]
    if ($null -eq $before -or $null -eq $after) { continue }

    $regionLabel = if ($region.IsControl) { "$($region.Name) [CONTROL]" } else { $region.Name }
    Write-Host ''
    Write-Host "--- $regionLabel at $($region.Address) ---" -ForegroundColor Cyan

    $changes = Diff-FloatArrays -Before $before.Floats -After $after.Floats -RegionName $region.Name -BaseAddress $region.Address
    $allChanges += $changes

    if ($changes.Count -eq 0) {
        Write-Host '  No float changes detected.' -ForegroundColor Gray
    } else {
        Write-Host "  $($changes.Count) float(s) changed:" -ForegroundColor Green
        foreach ($c in $changes) {
            $color = switch ($c.Classification) {
                'distance'    { 'Red' }
                'orientation' { 'Green' }
                'angle-rad'   { 'Magenta' }
                'angle-deg'   { 'Magenta' }
                'position'    { 'Yellow' }
                default       { 'White' }
            }
            Write-Host ("    {0}  before={1,12:F6}  after={2,12:F6}  delta={3,12:F6}  [{4}]" -f `
                $c.Offset, $c.Before, $c.After, $c.Delta, $c.Classification) -ForegroundColor $color

            # Flag distance candidates (zoom typically changes a value in 5-50 range)
            if ($c.Classification -eq 'distance') {
                $distanceCandidates += $c
            }
        }
    }
}

# Summary
Write-Host ''
Write-Host '=== SUMMARY ===' -ForegroundColor Cyan
Write-Host "Regions scanned:        $($regions.Count)" -ForegroundColor White
Write-Host "Total float changes:    $($allChanges.Count)" -ForegroundColor White
Write-Host "Distance candidates:    $($distanceCandidates.Count)" -ForegroundColor $(if ($distanceCandidates.Count -gt 0) { 'Red' } else { 'Gray' })

if ($distanceCandidates.Count -gt 0) {
    Write-Host ''
    Write-Host '*** CAMERA DISTANCE/ZOOM CANDIDATES FOUND ***' -ForegroundColor Red
    foreach ($d in $distanceCandidates) {
        Write-Host "  Region: $($d.Region)  Offset: $($d.Offset)  Before: $($d.Before)  After: $($d.After)  Delta: $($d.Delta)" -ForegroundColor Red
    }
    Write-Host ''
    Write-Host 'Cross-validate: If these offsets are in the same region/entry as Alt-S orientation changes,' -ForegroundColor Yellow
    Write-Host 'then that region is the camera struct.' -ForegroundColor Yellow
}

# JSON output
$resultObject = [ordered]@{
    Mode = 'camera-altz-stimulus'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    Stimulus = 'Alt-Z (alternate zoom)'
    HoldMilliseconds = $HoldMilliseconds
    WaitMilliseconds = $WaitMilliseconds
    OwnerAddress = ('0x{0:X}' -f $ownerAddress)
    ContainerAddress = ('0x{0:X}' -f $containerAddress)
    SelectedSourceAddress = ('0x{0:X}' -f $selectedSourceAddress)
    EntryCount = $entryCount
    RegionsScanned = $regions.Count
    TotalFloatChanges = $allChanges.Count
    DistanceCandidateCount = $distanceCandidates.Count
    Changes = $allChanges
    DistanceCandidates = $distanceCandidates
}

$outputFile = Join-Path $PSScriptRoot 'captures' 'camera-altz-stimulus.json'
$outputDir = Split-Path -Parent $outputFile
if (-not (Test-Path $outputDir)) { New-Item -ItemType Directory -Path $outputDir -Force | Out-Null }
$resultObject | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $outputFile -Encoding UTF8
Write-Host ''
Write-Host "Results saved to: $outputFile" -ForegroundColor Green

if ($Json) {
    Write-Output ($resultObject | ConvertTo-Json -Depth 20)
}
