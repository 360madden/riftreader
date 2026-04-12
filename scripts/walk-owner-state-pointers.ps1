[CmdletBinding()]
param(
    [switch]$Json,
    [string]$OwnerAddress = '0x1576A38AA10',
    [string]$StateRecordAddress = '0x1576A38AAD8',
    [int]$OwnerReadLength = 256,
    [int]$StateReadLength = 256,
    [int]$FollowReadLength = 512,
    [string]$OutputFile = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $scriptDir) { $scriptDir = (Get-Location).Path }

$repoRoot = (Resolve-Path (Join-Path $scriptDir '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = Join-Path $scriptDir 'captures\walk-owner-state-pointers.json'
}
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

# Expected player position for proximity checks
$expectedPlayerX = 7421.4
$expectedPlayerY = 863.59
$expectedPlayerZ = 2942.34

# Heap pointers on Win64 typically fall in 0x10000000000 - 0x7FFFFFFFFFFF range
# The owner is at 0x1576A38AA10, so pointers should be in similar range
$minPointer = [UInt64]::Parse('10000000000', [System.Globalization.NumberStyles]::HexNumber)
$maxPointer = [UInt64]::Parse('7FFFFFFFFFFF', [System.Globalization.NumberStyles]::HexNumber)

function Invoke-ReaderRaw {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & dotnet run --project $readerProject --configuration Release -- @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Reader failed (exit=$LASTEXITCODE): $($output -join [Environment]::NewLine)"
    }

    # Extract JSON from output (skip non-JSON lines)
    $jsonLines = @()
    $jsonStart = $false
    foreach ($line in $output) {
        $lineStr = [string]$line
        if ($lineStr -match '^\s*[\{\[]') { $jsonStart = $true }
        if ($jsonStart) { $jsonLines += $lineStr }
    }

    return ($jsonLines -join "`n") | ConvertFrom-Json
}

function Read-MemoryBytes {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Address,

        [Parameter(Mandatory = $true)]
        [int]$Length
    )

    $addrHex = '0x{0:X}' -f $Address
    $result = Invoke-ReaderRaw -Arguments @(
        '--process-name', 'rift_x64',
        '--address', $addrHex,
        '--length', $Length.ToString(),
        '--json')

    $hex = ([string]$result.BytesHex) -replace '\s+', ''
    if ([string]::IsNullOrWhiteSpace($hex) -or ($hex.Length % 2) -ne 0) {
        return @()
    }

    $buffer = New-Object byte[] ($hex.Length / 2)
    for ($i = 0; $i -lt $buffer.Length; $i++) {
        $buffer[$i] = [Convert]::ToByte($hex.Substring($i * 2, 2), 16)
    }

    return $buffer
}

function Test-PlausiblePointer {
    param([UInt64]$Value)
    return ($Value -ge $script:minPointer) -and ($Value -lt $script:maxPointer)
}

function Extract-Pointers {
    param(
        [byte[]]$Bytes,
        [UInt64]$BaseAddress
    )

    $pointers = @()
    for ($off = 0; $off -le ($Bytes.Length - 8); $off += 8) {
        $val = [BitConverter]::ToUInt64($Bytes, $off)
        if ($val -ne 0 -and (Test-PlausiblePointer -Value $val)) {
            $pointers += [ordered]@{
                Offset      = $off
                OffsetHex   = '+0x{0:X}' -f $off
                SourceAddr  = '0x{0:X}' -f ($BaseAddress + [UInt64]$off)
                PointerHex  = '0x{0:X}' -f $val
                PointerDec  = $val
            }
        }
    }
    return $pointers
}

function Analyze-FloatData {
    param(
        [byte[]]$Bytes,
        [string]$Label,
        [string]$Address
    )

    $coordMatches = [System.Collections.Generic.List[object]]::new()
    $normalizedVectors = [System.Collections.Generic.List[object]]::new()
    $angleValues = [System.Collections.Generic.List[object]]::new()

    for ($off = 0; $off -lt ($Bytes.Length - 11); $off += 4) {
        $fx = [BitConverter]::ToSingle($Bytes, $off)
        $fy = [BitConverter]::ToSingle($Bytes, $off + 4)
        $fz = [BitConverter]::ToSingle($Bytes, $off + 8)

        if ([float]::IsNaN($fx) -or [float]::IsNaN($fy) -or [float]::IsNaN($fz)) { continue }
        if ([float]::IsInfinity($fx) -or [float]::IsInfinity($fy) -or [float]::IsInfinity($fz)) { continue }

        # Check for position near player (camera position candidate)
        $dx = [double]$fx - $expectedPlayerX
        $dy = [double]$fy - $expectedPlayerY
        $dz = [double]$fz - $expectedPlayerZ
        $dist = [Math]::Sqrt($dx * $dx + $dy * $dy + $dz * $dz)

        if ($dist -lt 100 -and [Math]::Abs($fx) -gt 1.0 -and [Math]::Abs($fz) -gt 1.0) {
            $coordMatches.Add([ordered]@{
                Offset          = '+0x{0:X3}' -f $off
                X               = [Math]::Round($fx, 4)
                Y               = [Math]::Round($fy, 4)
                Z               = [Math]::Round($fz, 4)
                DistFromPlayer  = [Math]::Round($dist, 3)
                ExactMatch      = ($dist -lt 0.5)
            }) | Out-Null
        }

        # Check for normalized vector (magnitude ~1.0) -- camera direction candidate
        $mag = [Math]::Sqrt([double]$fx * [double]$fx + [double]$fy * [double]$fy + [double]$fz * [double]$fz)
        if ([Math]::Abs($mag - 1.0) -lt 0.05 -and
            [Math]::Abs($fx) -le 1.1 -and [Math]::Abs($fy) -le 1.1 -and [Math]::Abs($fz) -le 1.1) {
            $normalizedVectors.Add([ordered]@{
                Offset    = '+0x{0:X3}' -f $off
                X         = [Math]::Round($fx, 6)
                Y         = [Math]::Round($fy, 6)
                Z         = [Math]::Round($fz, 6)
                Magnitude = [Math]::Round($mag, 6)
            }) | Out-Null
        }
    }

    # Scan for individual angle-like floats (degrees 0-360 or radians -pi to pi)
    for ($off = 0; $off -lt ($Bytes.Length - 3); $off += 4) {
        $fv = [BitConverter]::ToSingle($Bytes, $off)
        if ([float]::IsNaN($fv) -or [float]::IsInfinity($fv)) { continue }

        $isDegrees = ($fv -gt 0.0 -and $fv -lt 360.0)
        $isRadians = ($fv -gt -3.15 -and $fv -lt 3.15 -and [Math]::Abs($fv) -gt 0.01)

        if ($isDegrees -or $isRadians) {
            $type = if ($isDegrees -and $isRadians) { 'deg-or-rad' }
                    elseif ($isDegrees) { 'degrees' }
                    else { 'radians' }

            # Only include if it looks like a plausible yaw/pitch (not just any small number)
            # Filter: skip values that are obviously integer-like or tiny
            $absVal = [Math]::Abs($fv)
            if ($absVal -gt 0.05 -or $type -eq 'degrees') {
                $angleValues.Add([ordered]@{
                    Offset      = '+0x{0:X3}' -f $off
                    Value       = [Math]::Round($fv, 6)
                    AsDegrees   = [Math]::Round($fv, 3)
                    AsRadians   = [Math]::Round($fv, 6)
                    AsDegFromRad = [Math]::Round($fv * 180.0 / [Math]::PI, 3)
                    Type        = $type
                }) | Out-Null
            }
        }
    }

    return [ordered]@{
        Label             = $Label
        Address           = $Address
        ByteCount         = $Bytes.Length
        CoordMatches      = @($coordMatches.ToArray())
        NormalizedVectors = @($normalizedVectors.ToArray())
        AngleValueCount   = $angleValues.Count
        AngleValues       = @($angleValues.ToArray() | Select-Object -First 30)
    }
}

# ---- Main Execution ----

Write-Host "=== Walk Owner-State Pointers ===" -ForegroundColor Cyan
Write-Host "Owner:       $OwnerAddress" -ForegroundColor Gray
Write-Host "StateRecord: $StateRecordAddress" -ForegroundColor Gray
Write-Host "Expected player pos: ($expectedPlayerX, $expectedPlayerY, $expectedPlayerZ)" -ForegroundColor Gray
Write-Host ""

function Parse-HexAddress {
    param([string]$Value)
    $clean = $Value.Trim()
    if ($clean.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $clean = $clean.Substring(2)
    }
    return [UInt64]::Parse($clean, [System.Globalization.NumberStyles]::HexNumber)
}

$ownerAddr = Parse-HexAddress -Value $OwnerAddress
$stateAddr = Parse-HexAddress -Value $StateRecordAddress

# Step 1: Read state record
Write-Host "Reading state record ($StateReadLength bytes)..." -ForegroundColor Yellow
$stateBytes = Read-MemoryBytes -Address $stateAddr -Length $StateReadLength
Write-Host "  Got $($stateBytes.Length) bytes" -ForegroundColor Green

$statePointers = @(Extract-Pointers -Bytes $stateBytes -BaseAddress $stateAddr)
Write-Host "  Found $($statePointers.Count) plausible pointers" -ForegroundColor Green

# Step 2: Read owner object
Write-Host "Reading owner object ($OwnerReadLength bytes)..." -ForegroundColor Yellow
$ownerBytes = Read-MemoryBytes -Address $ownerAddr -Length $OwnerReadLength
Write-Host "  Got $($ownerBytes.Length) bytes" -ForegroundColor Green

$ownerPointers = @(Extract-Pointers -Bytes $ownerBytes -BaseAddress $ownerAddr)
Write-Host "  Found $($ownerPointers.Count) plausible pointers" -ForegroundColor Green

# Merge unique pointers from both sources
$allTargets = @{}
foreach ($ptr in $statePointers) {
    $key = [string]$ptr.PointerHex
    if (-not $allTargets.ContainsKey($key)) {
        $allTargets[$key] = [ordered]@{
            PointerHex = $key
            PointerDec = $ptr.PointerDec
            Sources    = @()
        }
    }
    $allTargets[$key].Sources += [ordered]@{
        From   = 'state-record'
        Offset = [string]$ptr.OffsetHex
    }
}

foreach ($ptr in $ownerPointers) {
    $key = [string]$ptr.PointerHex
    if (-not $allTargets.ContainsKey($key)) {
        $allTargets[$key] = [ordered]@{
            PointerHex = $key
            PointerDec = $ptr.PointerDec
            Sources    = @()
        }
    }
    $allTargets[$key].Sources += [ordered]@{
        From   = 'owner-object'
        Offset = [string]$ptr.OffsetHex
    }
}

# Exclude the state record and owner themselves from follow targets
$skipSet = @{}
$skipSet[('0x{0:X}' -f $ownerAddr)] = $true
$skipSet[('0x{0:X}' -f $stateAddr)] = $true

$targets = @($allTargets.Values | Where-Object { -not $skipSet.ContainsKey([string]$_.PointerHex) })
Write-Host ""
Write-Host "Unique follow targets (excluding self-refs): $($targets.Count)" -ForegroundColor Cyan

# Step 3: Follow each pointer and analyze
$followResults = @()
$targetIndex = 0

foreach ($target in $targets) {
    $targetIndex++
    $addrHex = [string]$target.PointerHex
    $addrVal = [UInt64]$target.PointerDec
    $srcLabels = ($target.Sources | ForEach-Object { "$($_.From)$($_.Offset)" }) -join ', '

    Write-Host "[$targetIndex/$($targets.Count)] Following $addrHex (from $srcLabels)..." -NoNewline -ForegroundColor Gray

    try {
        $destBytes = Read-MemoryBytes -Address $addrVal -Length $FollowReadLength
        $analysis = Analyze-FloatData -Bytes $destBytes -Label "target-$targetIndex" -Address $addrHex

        $destPointers = Extract-Pointers -Bytes $destBytes -BaseAddress $addrVal

        $followResult = [ordered]@{
            TargetIndex      = $targetIndex
            Address          = $addrHex
            Sources          = @($target.Sources)
            BytesRead        = $destBytes.Length
            PointerCount     = $destPointers.Count
            CoordMatches     = $analysis.CoordMatches
            NormalizedVectors = $analysis.NormalizedVectors
            AngleValueCount  = $analysis.AngleValueCount
            TopAngles        = @($analysis.AngleValues | Select-Object -First 15)
            ChildPointers    = @($destPointers | Select-Object -First 16)
        }

        $followResults += $followResult

        $hits = @()
        if ($analysis.CoordMatches.Count -gt 0) { $hits += "$($analysis.CoordMatches.Count) coords" }
        if ($analysis.NormalizedVectors.Count -gt 0) { $hits += "$($analysis.NormalizedVectors.Count) normals" }
        if ($analysis.AngleValueCount -gt 0) { $hits += "$($analysis.AngleValueCount) angles" }

        if ($hits.Count -gt 0) {
            Write-Host " FOUND: $($hits -join ', ')" -ForegroundColor Green
        }
        else {
            Write-Host " nothing" -ForegroundColor DarkGray
        }
    }
    catch {
        Write-Host " ERROR: $($_.Exception.Message)" -ForegroundColor Red
        $followResults += [ordered]@{
            TargetIndex = $targetIndex
            Address     = $addrHex
            Sources     = @($target.Sources)
            Error       = $_.Exception.Message
        }
    }
}

# Summary
Write-Host ""
Write-Host "=== RESULTS SUMMARY ===" -ForegroundColor Cyan

$interesting = @($followResults | Where-Object {
    ($_.CoordMatches -and $_.CoordMatches.Count -gt 0) -or
    ($_.NormalizedVectors -and $_.NormalizedVectors.Count -gt 0)
})

if ($interesting.Count -eq 0) {
    Write-Host "No coord matches or normalized vectors found at any pointer target." -ForegroundColor Yellow
}
else {
    foreach ($r in $interesting) {
        Write-Host ""
        Write-Host "TARGET $($r.Address) (from $($r.Sources | ForEach-Object { "$($_.From)$($_.Offset)" }))" -ForegroundColor Yellow

        foreach ($coord in $r.CoordMatches) {
            $matchTag = if ($coord.ExactMatch) { " *** EXACT MATCH ***" } else { "" }
            Write-Host "  COORD $($coord.Offset): ($($coord.X), $($coord.Y), $($coord.Z)) dist=$($coord.DistFromPlayer)$matchTag" -ForegroundColor Green
        }
        foreach ($vec in $r.NormalizedVectors) {
            Write-Host "  NORMAL $($vec.Offset): ($($vec.X), $($vec.Y), $($vec.Z)) mag=$($vec.Magnitude)" -ForegroundColor Cyan
        }
    }
}

# Build output document
$document = [ordered]@{
    Mode             = 'walk-owner-state-pointers'
    GeneratedAtUtc   = [DateTimeOffset]::UtcNow.ToString('O')
    ExpectedPlayer   = [ordered]@{ X = $expectedPlayerX; Y = $expectedPlayerY; Z = $expectedPlayerZ }
    OwnerObject      = [ordered]@{
        Address      = $OwnerAddress
        BytesRead    = $ownerBytes.Length
        PointerCount = $ownerPointers.Count
        Pointers     = @($ownerPointers)
    }
    StateRecord      = [ordered]@{
        Address      = $StateRecordAddress
        BytesRead    = $stateBytes.Length
        PointerCount = $statePointers.Count
        Pointers     = @($statePointers)
    }
    UniqueTargets    = $targets.Count
    FollowResults    = @($followResults)
    InterestingCount = $interesting.Count
}

$outDir = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outDir)) {
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}

$jsonText = $document | ConvertTo-Json -Depth 24
Set-Content -LiteralPath $resolvedOutputFile -Value $jsonText -Encoding UTF8

Write-Host ""
Write-Host "Output saved to: $resolvedOutputFile" -ForegroundColor Green

if ($Json) {
    $document | ConvertTo-Json -Depth 24
}
