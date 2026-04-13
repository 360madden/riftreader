# ====================================================================================
# Script: Run-ManualAltSHoldCaptureFixed.ps1
# Version: 1.0.1
# Purpose: Manual Alt-S hold test with countdown, during-hold capture, optional
#          post-release capture, defensive JSON parsing, and durable artifacts.
# CharacterCount: 0
# ====================================================================================

[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$CountdownSeconds = 3,
    [int]$HoldCaptureDelayMilliseconds = 1300,
    [int]$PostReleaseDelayMilliseconds = 400,
    [int]$ReadLength = 1024,
    [string]$ArtifactRoot = 'artifacts\camera-discovery-manual-alts',
    [switch]$RefreshOwnerComponents,
    [switch]$SkipPostReleaseCapture,
    [bool]$BeepOnCue = $true,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptRoot = Join-Path $repoRoot 'scripts'
$readerProject = Join-Path $repoRoot 'reader' 'RiftReader.Reader' 'RiftReader.Reader.csproj'
$ownerComponentsScript = Join-Path $scriptRoot 'capture-player-owner-components.ps1'
$ownerComponentsFile = Join-Path $scriptRoot 'captures' 'player-owner-components.json'
$selectorTraceFile = Join-Path $scriptRoot 'captures' 'player-selector-owner-trace.json'
$artifactBase = Join-Path $repoRoot $ArtifactRoot

function Ensure-Directory {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Write-Utf8File {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][AllowEmptyString()][string]$Content
    )

    $parent = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($parent)) {
        Ensure-Directory -Path $parent
    }

    Set-Content -LiteralPath $Path -Value $Content -Encoding UTF8
}

function Add-Event {
    param(
        [Parameter(Mandatory)][string]$EventsPath,
        [Parameter(Mandatory)][string]$Phase,
        [Parameter(Mandatory)][string]$Kind,
        [object]$Data
    )

    $record = [ordered]@{
        TimestampUtc = [DateTimeOffset]::UtcNow.ToString('O')
        Phase = $Phase
        Kind = $Kind
        Data = if ($null -ne $Data) { $Data } else { [ordered]@{} }
    }

    Add-Content -LiteralPath $EventsPath -Value (($record | ConvertTo-Json -Depth 20 -Compress)) -Encoding UTF8
}

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
        [string]$CommandName = 'command'
    )

    $text = ($OutputLines |
        ForEach-Object { $_.ToString() } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join "`n"

    $startIdx = $text.IndexOf('{')
    if ($startIdx -lt 0) {
        throw "$CommandName did not return JSON. Raw output: $text"
    }

    return ($text.Substring($startIdx) | ConvertFrom-Json -Depth 50)
}

function Read-MemoryBlock {
    param(
        [Parameter(Mandatory)][string]$Address,
        [Parameter(Mandatory)][int]$Length
    )

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
    param([Parameter(Mandatory)][string]$Address)
    $bytes = Read-MemoryBlock -Address $Address -Length 8
    return [BitConverter]::ToUInt64($bytes, 0)
}

function Get-FloatsFromBytes {
    param([Parameter(Mandatory)][byte[]]$Bytes)

    $floats = @()
    for ($i = 0; $i -le ($Bytes.Length - 4); $i += 4) {
        $floats += [Math]::Round([BitConverter]::ToSingle($Bytes, $i), 6)
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
            $changes += [ordered]@{
                Region = $RegionName
                BaseAddress = $BaseAddress
                Offset = ('0x{0:X3}' -f ($i * 4))
                OffsetDec = ($i * 4)
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
        $bx = $Before[$i];     $by = $Before[$i + 1]; $bz = $Before[$i + 2]
        $ax = $After[$i];      $ay = $After[$i + 1];  $az = $After[$i + 2]
        $beforeMag = [Math]::Sqrt($bx * $bx + $by * $by + $bz * $bz)
        $afterMag = [Math]::Sqrt($ax * $ax + $ay * $ay + $az * $az)

        if ([Math]::Abs($beforeMag - 1.0) -lt 0.05 -and [Math]::Abs($afterMag - 1.0) -lt 0.05) {
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
                    DuringVector = @{ X = [Math]::Round($ax, 6); Y = [Math]::Round($ay, 6); Z = [Math]::Round($az, 6) }
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
        [float[]]$During,
        [string]$RegionName
    )

    $flips = @()
    for ($i = 0; $i -lt ($During.Length - 2); $i++) {
        $bx = $Before[$i];      $by = $Before[$i + 1]; $bz = $Before[$i + 2]
        $dx = $During[$i];      $dy = $During[$i + 1]; $dz = $During[$i + 2]
        $beforeMag = [Math]::Sqrt($bx * $bx + $by * $by + $bz * $bz)
        $duringMag = [Math]::Sqrt($dx * $dx + $dy * $dy + $dz * $dz)

        if ([Math]::Abs($beforeMag - 1.0) -lt 0.05 -and [Math]::Abs($duringMag - 1.0) -lt 0.05) {
            $dot = $bx * $dx + $by * $dy + $bz * $dz
            if ($dot -lt -0.8) {
                $flips += [ordered]@{
                    Region = $RegionName
                    Offset = ('0x{0:X3}' -f ($i * 4))
                    BeforeVector = @{ X = [Math]::Round($bx, 6); Y = [Math]::Round($by, 6); Z = [Math]::Round($bz, 6) }
                    DuringVector = @{ X = [Math]::Round($dx, 6); Y = [Math]::Round($dy, 6); Z = [Math]::Round($dz, 6) }
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
    if ($RefreshOwnerComponents) {
        $ocOutput = & $ownerComponentsScript -Json -RefreshSelectorTrace 2>&1
        return (Convert-CommandOutputToJson -OutputLines $ocOutput -CommandName 'capture-player-owner-components')
    }

    if (-not (Test-Path -LiteralPath $ownerComponentsFile)) {
        throw "Cached owner components file is missing: $ownerComponentsFile"
    }

    if (-not (Test-Path -LiteralPath $selectorTraceFile)) {
        throw "Cached selector trace file is missing: $selectorTraceFile"
    }

    return (Get-Content -LiteralPath $ownerComponentsFile -Raw | ConvertFrom-Json -Depth 40)
}

function Build-Regions {
    param([Parameter(Mandatory)][object]$OwnerComponents)

    $ownerAddress = Parse-HexUInt64 -Value ([string]$OwnerComponents.Owner.Address)
    $selectedSourceAddress = Parse-HexUInt64 -Value ([string]$OwnerComponents.Owner.SelectedSourceAddress)
    $entryCount = [int]$OwnerComponents.EntryCount

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
        Write-Host "Lead A resolution failed: $($_.Exception.Message)" -ForegroundColor DarkYellow
    }

    if ($entryCount -ge 16) {
        $entry15 = $OwnerComponents.Entries | Where-Object { [int]$_.Index -eq 15 } | Select-Object -First 1
        if ($null -ne $entry15) {
            $entry15Address = Parse-HexUInt64 -Value ([string]$entry15.Address)
            $regions += @{ Name = 'lead-B-entry15'; Address = ('0x{0:X}' -f $entry15Address); Length = $ReadLength; IsControl = $false }
        }
    }

    if ($entryCount -ge 5) {
        $entry4 = $OwnerComponents.Entries | Where-Object { [int]$_.Index -eq 4 } | Select-Object -First 1
        if ($null -ne $entry4) {
            $entry4Address = Parse-HexUInt64 -Value ([string]$entry4.Address)
            $regions += @{ Name = 'entry4'; Address = ('0x{0:X}' -f $entry4Address); Length = 512; IsControl = $false }
        }
    }

    $regions += @{ Name = 'owner-neighborhood'; Address = ('0x{0:X}' -f $ownerAddress); Length = 512; IsControl = $false }
    return $regions
}

function Capture-Snapshot {
    param(
        [Parameter(Mandatory)][string]$Label,
        [Parameter(Mandatory)][object[]]$Regions,
        [Parameter(Mandatory)][AllowEmptyCollection()][System.Collections.Generic.List[object]]$Errors
    )

    $results = @()
    foreach ($region in $Regions) {
        try {
            $bytes = Read-MemoryBlock -Address $region.Address -Length $region.Length
            $floats = Get-FloatsFromBytes -Bytes $bytes
            $results += [ordered]@{
                Name = $region.Name
                Address = $region.Address
                Length = $region.Length
                IsControl = $region.IsControl
                Success = $true
                Error = $null
                FloatCount = $floats.Count
                Floats = $floats
            }
        }
        catch {
            $message = $_.Exception.Message
            $Errors.Add([ordered]@{ Phase = $Label; Region = $region.Name; Address = $region.Address; Message = $message })
            $results += [ordered]@{
                Name = $region.Name
                Address = $region.Address
                Length = $region.Length
                IsControl = $region.IsControl
                Success = $false
                Error = $message
                FloatCount = 0
                Floats = @()
            }
        }
    }

    return $results
}

function Get-SnapshotEntry {
    param(
        [Parameter(Mandatory)][object[]]$Snapshot,
        [Parameter(Mandatory)][string]$RegionName
    )

    return ($Snapshot | Where-Object { $_.Name -eq $RegionName } | Select-Object -First 1)
}

function Try-Beep {
    param([int]$Frequency = 900, [int]$Duration = 200)
    if (-not $BeepOnCue) { return }
    try { [Console]::Beep($Frequency, $Duration) } catch {}
}

function Save-Result {
    param(
        [Parameter(Mandatory)][object]$Result,
        [Parameter(Mandatory)][string]$Path
    )

    Write-Utf8File -Path $Path -Content ($Result | ConvertTo-Json -Depth 50)
}

if (-not (Test-Path -LiteralPath $readerProject)) {
    throw "Reader project not found: $readerProject"
}

$riftProcess = Get-Process -Name $ProcessName -ErrorAction Stop | Select-Object -First 1
if ($null -eq $riftProcess) {
    throw "No process named '$ProcessName' was found."
}

Ensure-Directory -Path $artifactBase
$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$runDirectory = Join-Path $artifactBase ("run-{0}" -f $runId)
Ensure-Directory -Path $runDirectory
$eventsPath = Join-Path $runDirectory 'events.jsonl'
$resultPath = Join-Path $runDirectory 'manual-alt-s-hold.json'
Write-Utf8File -Path $eventsPath -Content ''

$errors = New-Object 'System.Collections.Generic.List[object]'
Add-Event -EventsPath $eventsPath -Phase 'suite' -Kind 'start' -Data ([ordered]@{ RunId = $runId; CountdownSeconds = $CountdownSeconds })

$ownerComponents = Load-OwnerComponents
$ownerAddress = ('0x{0:X}' -f (Parse-HexUInt64 -Value ([string]$ownerComponents.Owner.Address)))
$containerAddress = ('0x{0:X}' -f (Parse-HexUInt64 -Value ([string]$ownerComponents.Owner.ContainerAddress)))
$selectedSourceAddress = ('0x{0:X}' -f (Parse-HexUInt64 -Value ([string]$ownerComponents.Owner.SelectedSourceAddress)))
$entryCount = [int]$ownerComponents.EntryCount
$regions = Build-Regions -OwnerComponents $ownerComponents

Write-Host '=== Manual Alt-S Hold Capture ===' -ForegroundColor Cyan
Write-Host 'This test does NOT inject Alt-S.' -ForegroundColor Cyan
Write-Host 'It captures BEFORE, then DURING your manual Alt-S hold, then optionally AFTER release.' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Instructions:' -ForegroundColor Yellow
Write-Host '1. When countdown finishes, switch to the RIFT window immediately.' -ForegroundColor Yellow
Write-Host '2. Focus the game window.' -ForegroundColor Yellow
Write-Host '3. Press and HOLD Alt-S.' -ForegroundColor Yellow
Write-Host '4. Keep holding until you hear/see RELEASE NOW.' -ForegroundColor Yellow
Write-Host ''
Write-Host "Owner:            $ownerAddress" -ForegroundColor Green
Write-Host "Container:        $containerAddress" -ForegroundColor Green
Write-Host "Selected source:  $selectedSourceAddress" -ForegroundColor Green
Write-Host "Entry count:      $entryCount" -ForegroundColor Green
Write-Host "Regions scanned:  $($regions.Count)" -ForegroundColor Green
Write-Host ''

Add-Event -EventsPath $eventsPath -Phase 'before' -Kind 'start' -Data ([ordered]@{ RegionCount = $regions.Count })
$beforeSnapshot = Capture-Snapshot -Label 'before' -Regions $regions -Errors $errors
Add-Event -EventsPath $eventsPath -Phase 'before' -Kind 'finish' -Data ([ordered]@{})

Write-Host 'Countdown to manual Alt-S hold:' -ForegroundColor Yellow
for ($i = $CountdownSeconds; $i -ge 1; $i--) {
    Write-Host "  $i" -ForegroundColor Yellow
    Start-Sleep -Seconds 1
}

Try-Beep -Frequency 1100 -Duration 250
Try-Beep -Frequency 1200 -Duration 250
Write-Host ''
Write-Host 'HOLD ALT-S NOW. Keep holding until told to release.' -ForegroundColor Magenta
Add-Event -EventsPath $eventsPath -Phase 'during-hold' -Kind 'cue' -Data ([ordered]@{ HoldCaptureDelayMilliseconds = $HoldCaptureDelayMilliseconds })
Start-Sleep -Milliseconds $HoldCaptureDelayMilliseconds

Add-Event -EventsPath $eventsPath -Phase 'during-hold' -Kind 'start' -Data ([ordered]@{})
$duringSnapshot = Capture-Snapshot -Label 'during-hold' -Regions $regions -Errors $errors
Add-Event -EventsPath $eventsPath -Phase 'during-hold' -Kind 'finish' -Data ([ordered]@{})

Try-Beep -Frequency 700 -Duration 350
Try-Beep -Frequency 700 -Duration 350
Write-Host ''
Write-Host 'RELEASE ALT-S NOW.' -ForegroundColor Magenta
Add-Event -EventsPath $eventsPath -Phase 'release' -Kind 'cue' -Data ([ordered]@{})

$afterSnapshot = @()
if (-not $SkipPostReleaseCapture) {
    Start-Sleep -Milliseconds $PostReleaseDelayMilliseconds
    Add-Event -EventsPath $eventsPath -Phase 'after-release' -Kind 'start' -Data ([ordered]@{ PostReleaseDelayMilliseconds = $PostReleaseDelayMilliseconds })
    $afterSnapshot = Capture-Snapshot -Label 'after-release' -Regions $regions -Errors $errors
    Add-Event -EventsPath $eventsPath -Phase 'after-release' -Kind 'finish' -Data ([ordered]@{})
}

$beforeDuringChanges = @()
$beforeDuringFlips = @()
$beforeDuringUnitVectors = @()
$duringAfterChanges = @()

foreach ($region in $regions) {
    $before = Get-SnapshotEntry -Snapshot $beforeSnapshot -RegionName $region.Name
    $during = Get-SnapshotEntry -Snapshot $duringSnapshot -RegionName $region.Name
    if ($null -ne $before -and $null -ne $during -and $before.Success -and $during.Success) {
        $beforeDuringChanges += Diff-FloatArrays -Before $before.Floats -After $during.Floats -RegionName $region.Name -BaseAddress $region.Address
        $beforeDuringFlips += Check-180DegreeFlip -Before $before.Floats -During $during.Floats -RegionName $region.Name
        $beforeDuringUnitVectors += Find-ChangedUnitVectors -Before $before.Floats -After $during.Floats -RegionName $region.Name
    }

    if (-not $SkipPostReleaseCapture) {
        $after = Get-SnapshotEntry -Snapshot $afterSnapshot -RegionName $region.Name
        if ($null -ne $during -and $null -ne $after -and $during.Success -and $after.Success) {
            $duringAfterChanges += Diff-FloatArrays -Before $during.Floats -After $after.Floats -RegionName $region.Name -BaseAddress $region.Address
        }
    }
}

$resultObject = [ordered]@{
    Mode = 'manual-alt-s-hold-capture'
    Version = '1.0.1'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    RunId = $runId
    RepoRoot = $repoRoot
    RunDirectory = $runDirectory
    ProcessName = $ProcessName
    CountdownSeconds = $CountdownSeconds
    HoldCaptureDelayMilliseconds = $HoldCaptureDelayMilliseconds
    PostReleaseDelayMilliseconds = $PostReleaseDelayMilliseconds
    SkipPostReleaseCapture = [bool]$SkipPostReleaseCapture
    OwnerAddress = $ownerAddress
    ContainerAddress = $containerAddress
    SelectedSourceAddress = $selectedSourceAddress
    EntryCount = $entryCount
    RegionsScanned = $regions.Count
    RegionDetails = ($regions | ForEach-Object { [ordered]@{ Name = $_.Name; Address = $_.Address; Length = $_.Length; IsControl = $_.IsControl } })
    Summary = [ordered]@{
        ErrorCount = $errors.Count
        BeforeDuringTotalFloatChanges = $beforeDuringChanges.Count
        BeforeDuringFlipCandidateCount = $beforeDuringFlips.Count
        BeforeDuringChangedUnitVectorCount = $beforeDuringUnitVectors.Count
        DuringAfterTotalFloatChanges = $duringAfterChanges.Count
    }
    BeforeSnapshot = $beforeSnapshot
    DuringHoldSnapshot = $duringSnapshot
    AfterReleaseSnapshot = if ($SkipPostReleaseCapture) { @() } else { $afterSnapshot }
    BeforeDuringChanges = $beforeDuringChanges
    BeforeDuringFlipCandidates = $beforeDuringFlips
    BeforeDuringChangedUnitVectors = $beforeDuringUnitVectors
    DuringAfterChanges = $duringAfterChanges
    Errors = $errors
}

Save-Result -Result $resultObject -Path $resultPath
Add-Event -EventsPath $eventsPath -Phase 'suite' -Kind 'finish' -Data ([ordered]@{ ErrorCount = $errors.Count; BeforeDuringFlipCandidateCount = $beforeDuringFlips.Count })

Write-Host ''
Write-Host '=== Manual Alt-S Hold Capture Complete ===' -ForegroundColor Green
Write-Host "Run directory: $runDirectory" -ForegroundColor Green
Write-Host "Result file:   $resultPath" -ForegroundColor Green
Write-Host "Events file:   $eventsPath" -ForegroundColor Green
Write-Host ''
Write-Host ("Before->During float changes:   {0}" -f $beforeDuringChanges.Count) -ForegroundColor White
Write-Host ("Before->During flip candidates: {0}" -f $beforeDuringFlips.Count) -ForegroundColor White
Write-Host ("During->After float changes:    {0}" -f $duringAfterChanges.Count) -ForegroundColor White
Write-Host ("Errors recorded:                {0}" -f $errors.Count) -ForegroundColor White

if ($Json) {
    Write-Output ($resultObject | ConvertTo-Json -Depth 50)
}

# End of script
