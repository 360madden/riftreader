# ====================================================================================
# Script: test-camera-alts-stimulus-safe.ps1
# Version: 1.0.0
# Purpose: Safer Alt-S camera stimulus test with defensive reader JSON parsing.
# CharacterCount: 0
# ====================================================================================

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

function Parse-HexUInt64 {
    param([string]$Value)

    $normalized = $Value.Trim()
    if ($normalized -match '^0x([0-9A-Fa-f]+)$') {
        return [UInt64]::Parse($Matches[1], [System.Globalization.NumberStyles]::HexNumber)
    }

    return [UInt64]::Parse($normalized, [System.Globalization.NumberStyles]::HexNumber)
}

function Convert-CommandOutputToJson {
    param(
        [object[]]$OutputLines,
        [string]$CommandName = 'reader'
    )

    $text = ($OutputLines |
        ForEach-Object { $_.ToString() } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join "`n"

    $startIdx = $text.IndexOf('{')
    if ($startIdx -lt 0) {
        throw "$CommandName did not return JSON. Raw output: $text"
    }

    $jsonText = $text.Substring($startIdx)
    return $jsonText | ConvertFrom-Json -Depth 40
}

function Read-MemoryBlock {
    param([string]$Address, [int]$Length)

    $output = & dotnet run --project $readerProject --configuration Release -- `
        --process-name $ProcessName --address $Address --length $Length --json 2>&1
    $data = Convert-CommandOutputToJson -OutputLines $output -CommandName "memory read $Address"

    if (-not $data.PSObject.Properties['BytesHex']) {
        throw "Reader JSON for $Address did not include BytesHex."
    }

    $hex = ([string]$data.BytesHex -replace ' ', '')
    if ([string]::IsNullOrWhiteSpace($hex)) {
        throw "Reader JSON for $Address returned empty BytesHex."
    }

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
    if ($absVal -le 6.4 -and $absVal -ge 0.0 -and $absDelta -gt 0.001 -and $absDelta -lt 6.4) { return 'angle-rad' }
    if ($absVal -le 360.0 -and $absVal -ge 0.0 -and $absDelta -gt 0.01 -and $absDelta -lt 360.0) { return 'angle-deg' }
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

function Find-ChangedUnitVectors {
    param(
        [float[]]$Before,
        [float[]]$After,
        [string]$RegionName
    )

    $vectors = @()
    for ($i = 0; $i -lt ($After.Length - 2); $i++) {
        $bx = $Before[$i]; $by = $Before[$i + 1]; $bz = $Before[$i + 2]
        $ax = $After[$i];  $ay = $After[$i + 1];  $az = $After[$i + 2]

        $beforeMag = [Math]::Sqrt($bx * $bx + $by * $by + $bz * $bz)
        $afterMag = [Math]::Sqrt($ax * $ax + $ay * $ay + $az * $az)

        if ([Math]::Abs($afterMag - 1.0) -lt 0.05 -and [Math]::Abs($beforeMag - 1.0) -lt 0.05) {
            $changed = (
                [Math]::Abs($ax - $bx) -gt 0.00001 -or
                [Math]::Abs($ay - $by) -gt 0.00001 -or
                [Math]::Abs($az - $bz) -gt 0.00001
            )

            if ($changed) {
                $vectors += [ordered]@{
                    Region = $RegionName
                    Offset = ('0x{0:X3}' -f ($i * 4))
                    BeforeVector = @{ X = [Math]::Round($bx, 6); Y = [Math]::Round($by, 6); Z = [Math]::Round($bz, 6) }
                    AfterVector = @{ X = [Math]::Round($ax, 6); Y = [Math]::Round($ay, 6); Z = [Math]::Round($az, 6) }
                    Magnitude = [Math]::Round($afterMag, 6)
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
        $ax = $After[$i];  $ay = $After[$i + 1];  $az = $After[$i + 2]

        $beforeMag = [Math]::Sqrt($bx * $bx + $by * $by + $bz * $bz)
        $afterMag = [Math]::Sqrt($ax * $ax + $ay * $ay + $az * $az)

        if ([Math]::Abs($beforeMag - 1.0) -lt 0.05 -and [Math]::Abs($afterMag - 1.0) -lt 0.05) {
            $dot = $bx * $ax + $by * $ay + $bz * $az
            if ($dot -lt -0.8) {
                $flips += [ordered]@{
                    Region = $RegionName
                    Offset = ('0x{0:X3}' -f ($i * 4))
                    BeforeVector = @{ X = [Math]::Round($bx, 6); Y = [Math]::Round($by, 6); Z = [Math]::Round($bz, 6) }
                    AfterVector = @{ X = [Math]::Round($ax, 6); Y = [Math]::Round($ay, 6); Z = [Math]::Round($az, 6) }
                    DotProduct = [Math]::Round($dot, 6)
                    AngleDegrees = [Math]::Round([Math]::Acos([Math]::Max(-1, [Math]::Min(1, $dot))) * 180.0 / [Math]::PI, 2)
                    Classification = '180-degree-flip'
                }
            }
        }
    }

    return $flips
}

function Load-OwnerComponents {
    $mustRefresh = $RefreshOwnerComponents -or -not (Test-Path -LiteralPath $ownerComponentsFile)
    $refreshReason = $null

    if (-not $mustRefresh) {
        $cached = Get-Content -LiteralPath $ownerComponentsFile -Raw | ConvertFrom-Json -Depth 30
        try {
            $probeAddress = [string]$cached.Owner.SelectedSourceAddress
            $probeBytes = Read-MemoryBlock -Address $probeAddress -Length 16
            if ($probeBytes.Length -lt 16) {
                $mustRefresh = $true
                $refreshReason = "cached selected-source probe at $probeAddress returned only $($probeBytes.Length) bytes"
            }
            else {
                return $cached
            }
        }
        catch {
            $mustRefresh = $true
            $refreshReason = "cached selected-source probe failed: $($_.Exception.Message)"
        }
    }

    if ($mustRefresh) {
        if ($refreshReason) {
            Write-Host "Refreshing owner components because $refreshReason" -ForegroundColor Yellow
        }

        $ocOutput = & $ownerComponentsScript -Json -RefreshSelectorTrace 2>&1
        $ownerComponents = Convert-CommandOutputToJson -OutputLines $ocOutput -CommandName 'capture-player-owner-components'
        return $ownerComponents
    }

    return (Get-Content -LiteralPath $ownerComponentsFile -Raw | ConvertFrom-Json -Depth 30)
}

$errors = @()
$beforeSnapshots = @{}
$afterSnapshots = @{}

Write-Host '=== Camera Alt-S Stimulus Test (Safe) ===' -ForegroundColor Cyan
Write-Host 'Stimulus: Alt-S (look behind = ~180-degree camera yaw flip)' -ForegroundColor Cyan
Write-Host ''

$ownerComponents = Load-OwnerComponents
$ownerAddress = Parse-HexUInt64 -Value ([string]$ownerComponents.Owner.Address)
$containerAddress = Parse-HexUInt64 -Value ([string]$ownerComponents.Owner.ContainerAddress)
$selectedSourceAddress = Parse-HexUInt64 -Value ([string]$ownerComponents.Owner.SelectedSourceAddress)
$entryCount = [int]$ownerComponents.EntryCount

Write-Host "Owner:            0x$($ownerAddress.ToString('X'))" -ForegroundColor Green
Write-Host "Container:        0x$($containerAddress.ToString('X'))" -ForegroundColor Green
Write-Host "Selected source:  0x$($selectedSourceAddress.ToString('X'))" -ForegroundColor Green
Write-Host "Entry count:      $entryCount" -ForegroundColor Green

$regions = @(
    @{ Name = 'selected-source'; Address = ('0x{0:X}' -f $selectedSourceAddress); Length = 192; IsControl = $true }
)

try {
    $ownerD0Addr = ('0x{0:X}' -f ($ownerAddress + 0xD0))
    $wrapperPtr = Read-Pointer -Address $ownerD0Addr
    if ($wrapperPtr -gt 0x10000 -and $wrapperPtr -lt 0x00007FFFFFFFFFFF) {
        $targetPtr = Read-Pointer -Address ('0x{0:X}' -f ($wrapperPtr + 0x100))
        if ($targetPtr -gt 0x10000 -and $targetPtr -lt 0x00007FFFFFFFFFFF) {
            $regions += @{ Name = 'lead-A-owner-D0-chain'; Address = ('0x{0:X}' -f $targetPtr); Length = 256; IsControl = $false }
        }
    }
}
catch {
    $errors += [ordered]@{ Phase = 'lead-a-resolution'; Message = $_.Exception.Message }
    Write-Host "Lead A resolution failed: $($_.Exception.Message)" -ForegroundColor DarkYellow
}

if ($entryCount -ge 16) {
    $entry15 = $ownerComponents.Entries | Where-Object { [int]$_.Index -eq 15 } | Select-Object -First 1
    if ($null -ne $entry15) {
        $entry15Address = Parse-HexUInt64 -Value ([string]$entry15.Address)
        $regions += @{ Name = 'lead-B-entry15'; Address = ('0x{0:X}' -f $entry15Address); Length = $ReadLength; IsControl = $false }
    }
}

if ($entryCount -ge 5) {
    $entry4 = $ownerComponents.Entries | Where-Object { [int]$_.Index -eq 4 } | Select-Object -First 1
    if ($null -ne $entry4) {
        $entry4Address = Parse-HexUInt64 -Value ([string]$entry4.Address)
        $regions += @{ Name = 'entry4'; Address = ('0x{0:X}' -f $entry4Address); Length = 512; IsControl = $false }
    }
}

$regions += @{ Name = 'owner-neighborhood'; Address = ('0x{0:X}' -f $ownerAddress); Length = 512; IsControl = $false }

Write-Host ''
Write-Host "Scanning $($regions.Count) memory regions..." -ForegroundColor Yellow
Write-Host ''
Write-Host 'Step 1: Reading BEFORE snapshots...' -ForegroundColor Yellow

foreach ($region in $regions) {
    try {
        $bytes = Read-MemoryBlock -Address $region.Address -Length $region.Length
        $beforeSnapshots[$region.Name] = @{
            Bytes = $bytes
            Floats = Get-FloatsFromBytes -Bytes $bytes
        }
    }
    catch {
        $errors += [ordered]@{ Phase = 'before-read'; Region = $region.Name; Address = $region.Address; Message = $_.Exception.Message }
        $beforeSnapshots[$region.Name] = $null
        Write-Host "FAILED $($region.Name): $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ''
Write-Host 'Step 2: Sending Alt-S stimulus...' -ForegroundColor Yellow
$keyArgs = @{ Key = 'S'; Alt = $true; HoldMilliseconds = $HoldMilliseconds }
if ($SkipBackgroundFocus) { $keyArgs['SkipBackgroundFocus'] = $true }

try {
    & $keyScript @keyArgs *> $null
    if ($LASTEXITCODE -ne 0) {
        $errors += [ordered]@{ Phase = 'stimulus'; Stimulus = 'Alt-S'; Message = "post-rift-key exit code $LASTEXITCODE" }
    }
}
catch {
    $errors += [ordered]@{ Phase = 'stimulus'; Stimulus = 'Alt-S'; Message = $_.Exception.Message }
}

Start-Sleep -Milliseconds $WaitMilliseconds

Write-Host ''
Write-Host 'Step 3: Reading AFTER snapshots...' -ForegroundColor Yellow
foreach ($region in $regions) {
    if ($null -eq $beforeSnapshots[$region.Name]) { continue }

    try {
        $bytes = Read-MemoryBlock -Address $region.Address -Length $region.Length
        $afterSnapshots[$region.Name] = @{
            Bytes = $bytes
            Floats = Get-FloatsFromBytes -Bytes $bytes
        }
    }
    catch {
        $errors += [ordered]@{ Phase = 'after-read'; Region = $region.Name; Address = $region.Address; Message = $_.Exception.Message }
        $afterSnapshots[$region.Name] = $null
        Write-Host "FAILED $($region.Name): $($_.Exception.Message)" -ForegroundColor Red
    }
}

$allChanges = @()
$allFlips = @()
$allUnitVectors = @()

foreach ($region in $regions) {
    $before = $beforeSnapshots[$region.Name]
    $after = $afterSnapshots[$region.Name]
    if ($null -eq $before -or $null -eq $after) { continue }

    $changes = Diff-FloatArrays -Before $before.Floats -After $after.Floats -RegionName $region.Name -BaseAddress $region.Address
    $flips = Check-180DegreeFlip -Before $before.Floats -After $after.Floats -RegionName $region.Name
    $vectors = Find-ChangedUnitVectors -Before $before.Floats -After $after.Floats -RegionName $region.Name

    $allChanges += $changes
    $allFlips += $flips
    $allUnitVectors += $vectors
}

$resultObject = [ordered]@{
    Mode = 'camera-alts-stimulus-safe'
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
    FlipCandidateCount = $allFlips.Count
    ChangedUnitVectorCount = $allUnitVectors.Count
    Changes = $allChanges
    FlipCandidates = $allFlips
    ChangedUnitVectors = $allUnitVectors
    Errors = $errors
}

$outputFile = Join-Path $PSScriptRoot 'captures' 'camera-alts-stimulus-safe.json'
$resultObject | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $outputFile -Encoding UTF8

Write-Host ''
Write-Host "Results saved to: $outputFile" -ForegroundColor Green

if ($Json) {
    Write-Output ($resultObject | ConvertTo-Json -Depth 30)
}

# End of script
