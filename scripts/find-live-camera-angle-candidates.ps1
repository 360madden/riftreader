[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshOwnerComponents,
    [switch]$ScanAllEntries,
    [string]$ProcessName = 'rift_x64',
    [string]$OwnerComponentsFile = (Join-Path $PSScriptRoot 'captures\player-owner-components.json'),
    [int]$SelectedSourceLength = 2048,
    [int]$EntryLength = 2048,
    [int]$MousePixels = 140
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ownerComponentsScript = Join-Path $PSScriptRoot 'capture-player-owner-components.ps1'

function Convert-CommandOutputToJson {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$OutputLines,
        [string]$CommandName = 'command'
    )

    $text = ($OutputLines |
        ForEach-Object { $_.ToString() } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join [Environment]::NewLine

    $startIndex = $text.IndexOf('{')
    if ($startIndex -lt 0) {
        throw "$CommandName did not return JSON. Raw output: $text"
    }

    return ($text.Substring($startIndex) | ConvertFrom-Json -Depth 50)
}

function Load-OwnerComponents {
    if ($RefreshOwnerComponents -or -not (Test-Path -LiteralPath $OwnerComponentsFile)) {
        $output = & $ownerComponentsScript -Json -RefreshSelectorTrace 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "capture-player-owner-components failed: $($output -join [Environment]::NewLine)"
        }

        return Convert-CommandOutputToJson -OutputLines $output -CommandName 'capture-player-owner-components'
    }

    return (Get-Content -LiteralPath $OwnerComponentsFile -Raw | ConvertFrom-Json -Depth 40)
}

function Get-EntryByIndex {
    param(
        [Parameter(Mandatory = $true)]$OwnerComponents,
        [Parameter(Mandatory = $true)][int]$Index
    )

    return $OwnerComponents.Entries | Where-Object { [int]$_.Index -eq $Index } | Select-Object -First 1
}

if (-not ('RiftAngleProbeNative' -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class RiftAngleProbeNative
{
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool ReadProcessMemory(
        IntPtr hProcess,
        IntPtr lpBaseAddress,
        byte[] lpBuffer,
        int nSize,
        out IntPtr lpNumberOfBytesRead);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetCursorPos(int x, int y);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern void mouse_event(uint dwFlags, int dx, int dy, uint dwData, UIntPtr dwExtraInfo);

    public const int SW_RESTORE = 9;
    public const uint MOUSEEVENTF_MOVE = 0x0001;
    public const uint MOUSEEVENTF_RIGHTDOWN = 0x0008;
    public const uint MOUSEEVENTF_RIGHTUP = 0x0010;
}
"@
}

function Parse-HexUInt64 {
    param([Parameter(Mandatory = $true)][string]$Value)

    $normalized = $Value.Trim()
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [UInt64]::Parse($normalized, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Read-MemoryFloats {
    param(
        [Parameter(Mandatory = $true)]$Process,
        [Parameter(Mandatory = $true)][string]$Address,
        [Parameter(Mandatory = $true)][int]$Length
    )

    $baseAddress = [IntPtr]([Int64](Parse-HexUInt64 -Value $Address))
    $buffer = New-Object byte[] $Length
    $bytesRead = [IntPtr]::Zero
    $ok = [RiftAngleProbeNative]::ReadProcessMemory($Process.Handle, $baseAddress, $buffer, $Length, [ref]$bytesRead)
    if (-not $ok) {
        $lastError = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        throw "ReadProcessMemory failed at $Address (Win32: $lastError)"
    }

    $actualLength = $bytesRead.ToInt32()
    if ($actualLength -lt $Length) {
        $buffer = $buffer[0..($actualLength - 1)]
    }

    $floatCount = [Math]::Floor($buffer.Length / 4)
    $floats = New-Object double[] $floatCount
    for ($index = 0; $index -lt $floatCount; $index++) {
        $floats[$index] = [double][BitConverter]::ToSingle($buffer, $index * 4)
    }

    return $floats
}

function Capture-RegionFloats {
    param(
        [Parameter(Mandatory = $true)]$Process,
        [Parameter(Mandatory = $true)]$Regions
    )

    $snapshot = @{}
    foreach ($region in $Regions) {
        $snapshot[$region.Name] = Read-MemoryFloats -Process $Process -Address $region.Address -Length $region.Length
    }

    return $snapshot
}

function Get-DiffMap {
    param(
        [Parameter(Mandatory = $true)]$BeforeMap,
        [Parameter(Mandatory = $true)]$AfterMap,
        [Parameter(Mandatory = $true)]$Regions
    )

    $diffMap = @{}
    foreach ($region in $Regions) {
        $before = $BeforeMap[$region.Name]
        $after = $AfterMap[$region.Name]
        $regionMap = @{}

        for ($index = 0; $index -lt [Math]::Min($before.Length, $after.Length); $index++) {
            $delta = [double]$after[$index] - [double]$before[$index]
            if ([Math]::Abs($delta) -gt 0.00001) {
                $offset = '0x{0:X3}' -f ($index * 4)
                $regionMap[$offset] = [pscustomobject]@{
                    Offset = $offset
                    Before = [double]$before[$index]
                    After = [double]$after[$index]
                    Delta = $delta
                }
            }
        }

        $diffMap[$region.Name] = $regionMap
    }

    return $diffMap
}

function Test-AngleLikeValue {
    param([double]$Value)

    return (([Math]::Abs($Value) -ge 0.001 -and [Math]::Abs($Value) -le 6.5) -or
            ([Math]::Abs($Value) -gt 6.5 -and [Math]::Abs($Value) -le 360.0))
}

function Get-NullableAbs {
    param($Value)

    if ($null -eq $Value) {
        return 0.0
    }

    return [Math]::Abs([double]$Value)
}

function Invoke-RmbMove {
    param(
        [Parameter(Mandatory = $true)]$Process,
        [Parameter(Mandatory = $true)][int]$Dx,
        [Parameter(Mandatory = $true)][int]$Dy
    )

    [void][RiftAngleProbeNative]::ShowWindow($Process.MainWindowHandle, [RiftAngleProbeNative]::SW_RESTORE)
    [void][RiftAngleProbeNative]::SetForegroundWindow($Process.MainWindowHandle)
    Start-Sleep -Milliseconds 250

    $rect = New-Object RiftAngleProbeNative+RECT
    if (-not [RiftAngleProbeNative]::GetWindowRect($Process.MainWindowHandle, [ref]$rect)) {
        throw 'GetWindowRect failed for the RIFT window.'
    }

    $centerX = [int](($rect.Left + $rect.Right) / 2)
    $centerY = [int](($rect.Top + $rect.Bottom) / 2)
    if (-not [RiftAngleProbeNative]::SetCursorPos($centerX, $centerY)) {
        throw 'SetCursorPos failed while centering the cursor over RIFT.'
    }

    Start-Sleep -Milliseconds 60
    [RiftAngleProbeNative]::mouse_event([RiftAngleProbeNative]::MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 70
    [RiftAngleProbeNative]::mouse_event([RiftAngleProbeNative]::MOUSEEVENTF_MOVE, $Dx, $Dy, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 110
    [RiftAngleProbeNative]::mouse_event([RiftAngleProbeNative]::MOUSEEVENTF_RIGHTUP, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 250
}

function Get-ReversibleCandidates {
    param(
        [Parameter(Mandatory = $true)]$Regions,
        [Parameter(Mandatory = $true)]$PitchUpMap,
        [Parameter(Mandatory = $true)]$PitchDownMap,
        [Parameter(Mandatory = $true)]$YawLeftMap,
        [Parameter(Mandatory = $true)]$YawRightMap
    )

    $candidates = New-Object System.Collections.Generic.List[object]

    foreach ($region in $Regions) {
        $allOffsets = [System.Collections.Generic.HashSet[string]]::new()
        foreach ($map in @($PitchUpMap[$region.Name], $PitchDownMap[$region.Name], $YawLeftMap[$region.Name], $YawRightMap[$region.Name])) {
            foreach ($key in $map.Keys) {
                [void]$allOffsets.Add($key)
            }
        }

        foreach ($offset in $allOffsets) {
            $up = if ($PitchUpMap[$region.Name].ContainsKey($offset)) { $PitchUpMap[$region.Name][$offset] } else { $null }
            $down = if ($PitchDownMap[$region.Name].ContainsKey($offset)) { $PitchDownMap[$region.Name][$offset] } else { $null }
            $left = if ($YawLeftMap[$region.Name].ContainsKey($offset)) { $YawLeftMap[$region.Name][$offset] } else { $null }
            $right = if ($YawRightMap[$region.Name].ContainsKey($offset)) { $YawRightMap[$region.Name][$offset] } else { $null }

            $pitchReverse = $up -and $down -and ([Math]::Sign($up.Delta) -eq -[Math]::Sign($down.Delta))
            $yawReverse = $left -and $right -and ([Math]::Sign($left.Delta) -eq -[Math]::Sign($right.Delta))

            if (-not $pitchReverse -and -not $yawReverse) {
                continue
            }

            $sampleValue =
                if ($up) { [double]$up.After }
                elseif ($down) { [double]$down.After }
                elseif ($left) { [double]$left.After }
                elseif ($right) { [double]$right.After }
                else { 0.0 }

            $upDeltaValue = if ($up) { $up.Delta } else { $null }
            $downDeltaValue = if ($down) { $down.Delta } else { $null }
            $leftDeltaValue = if ($left) { $left.Delta } else { $null }
            $rightDeltaValue = if ($right) { $right.Delta } else { $null }

            $pitchMagnitude = (Get-NullableAbs $upDeltaValue) + (Get-NullableAbs $downDeltaValue)
            $yawMagnitude = (Get-NullableAbs $leftDeltaValue) + (Get-NullableAbs $rightDeltaValue)

            $classification =
                if ($pitchReverse -and -not $yawReverse) { 'pitch-only' }
                elseif ($yawReverse -and -not $pitchReverse) { 'yaw-only' }
                else { 'mixed' }

            $candidates.Add([pscustomobject]@{
                Region = $region.Name
                BaseAddress = $region.Address
                Offset = $offset
                SampleValue = $sampleValue
                AngleLike = Test-AngleLikeValue -Value $sampleValue
                Classification = $classification
                PitchReverse = [bool]$pitchReverse
                PitchMagnitude = $pitchMagnitude
                YawReverse = [bool]$yawReverse
                YawMagnitude = $yawMagnitude
                UpDelta = if ($up) { $up.Delta } else { $null }
                DownDelta = if ($down) { $down.Delta } else { $null }
                LeftDelta = if ($left) { $left.Delta } else { $null }
                RightDelta = if ($right) { $right.Delta } else { $null }
            }) | Out-Null
        }
    }

    return $candidates
}

$ownerComponents = Load-OwnerComponents
$selectedSourceAddress = [string]$ownerComponents.Owner.SelectedSourceAddress
$entry4 = Get-EntryByIndex -OwnerComponents $ownerComponents -Index 4
$entry15 = Get-EntryByIndex -OwnerComponents $ownerComponents -Index 15
if ($null -eq $entry4 -or $null -eq $entry15) {
    throw 'Entry 4 and entry 15 must both exist in the current owner-components capture.'
}

$regions = New-Object System.Collections.Generic.List[object]
$regions.Add([pscustomobject]@{ Name = 'selected-source'; Address = $selectedSourceAddress; Length = $SelectedSourceLength }) | Out-Null

if ($ScanAllEntries) {
    foreach ($entry in ($ownerComponents.Entries | Sort-Object { [int]$_.Index })) {
        $entryName = 'entry{0}' -f ([int]$entry.Index)
        if ($entryName -eq 'entry6' -and [string]$entry.Address -eq $selectedSourceAddress) {
            $entryName = 'entry6-selected'
        }

        $regions.Add([pscustomobject]@{
            Name = $entryName
            Address = [string]$entry.Address
            Length = $EntryLength
        }) | Out-Null
    }
}
else {
    $regions.Add([pscustomobject]@{ Name = 'entry4'; Address = [string]$entry4.Address; Length = $EntryLength }) | Out-Null
    $regions.Add([pscustomobject]@{ Name = 'entry15'; Address = [string]$entry15.Address; Length = $EntryLength }) | Out-Null
}

$process = Get-Process -Name $ProcessName -ErrorAction Stop |
    Where-Object { $_.MainWindowHandle -ne 0 } |
    Select-Object -First 1
if (-not $process) {
    throw "No process named '$ProcessName' with a main window was found."
}

Write-Host '=== Live Camera Angle Candidate Scan ===' -ForegroundColor Cyan
Write-Host "Process:          $($process.ProcessName) [$($process.Id)]" -ForegroundColor Green
Write-Host "Selected source:  $selectedSourceAddress" -ForegroundColor Green
Write-Host "Entry4:           $($entry4.Address)" -ForegroundColor Green
Write-Host "Entry15:          $($entry15.Address)" -ForegroundColor Green
Write-Host "Mouse pixels:     $MousePixels" -ForegroundColor Green
Write-Host ''

# Pitch up
Write-Host 'Pitch probe: up...' -ForegroundColor Yellow
$beforePitchUp = Capture-RegionFloats -Process $process -Regions $regions
Invoke-RmbMove -Process $process -Dx 0 -Dy (-1 * $MousePixels)
$afterPitchUp = Capture-RegionFloats -Process $process -Regions $regions

# Pitch down back toward baseline
Write-Host 'Pitch probe: down...' -ForegroundColor Yellow
$beforePitchDown = Capture-RegionFloats -Process $process -Regions $regions
Invoke-RmbMove -Process $process -Dx 0 -Dy $MousePixels
$afterPitchDown = Capture-RegionFloats -Process $process -Regions $regions

# Yaw left
Write-Host 'Yaw probe: left...' -ForegroundColor Yellow
$beforeYawLeft = Capture-RegionFloats -Process $process -Regions $regions
Invoke-RmbMove -Process $process -Dx (-1 * $MousePixels) -Dy 0
$afterYawLeft = Capture-RegionFloats -Process $process -Regions $regions

# Yaw right back toward baseline
Write-Host 'Yaw probe: right...' -ForegroundColor Yellow
$beforeYawRight = Capture-RegionFloats -Process $process -Regions $regions
Invoke-RmbMove -Process $process -Dx $MousePixels -Dy 0
$afterYawRight = Capture-RegionFloats -Process $process -Regions $regions

$pitchUpMap = Get-DiffMap -BeforeMap $beforePitchUp -AfterMap $afterPitchUp -Regions $regions
$pitchDownMap = Get-DiffMap -BeforeMap $beforePitchDown -AfterMap $afterPitchDown -Regions $regions
$yawLeftMap = Get-DiffMap -BeforeMap $beforeYawLeft -AfterMap $afterYawLeft -Regions $regions
$yawRightMap = Get-DiffMap -BeforeMap $beforeYawRight -AfterMap $afterYawRight -Regions $regions

$candidates = Get-ReversibleCandidates `
    -Regions $regions `
    -PitchUpMap $pitchUpMap `
    -PitchDownMap $pitchDownMap `
    -YawLeftMap $yawLeftMap `
    -YawRightMap $yawRightMap

$topPitchCandidates = $candidates |
    Where-Object { $_.PitchReverse } |
    Sort-Object @{ Expression = 'AngleLike'; Descending = $true }, @{ Expression = 'PitchMagnitude'; Descending = $true } |
    Select-Object -First 40

$topYawCandidates = $candidates |
    Where-Object { $_.YawReverse } |
    Sort-Object @{ Expression = 'AngleLike'; Descending = $true }, @{ Expression = 'YawMagnitude'; Descending = $true } |
    Select-Object -First 40

$angleLikePitchOnly = $candidates |
    Where-Object { $_.PitchReverse -and $_.AngleLike -and $_.YawMagnitude -lt ($_.PitchMagnitude * 0.25 + 0.001) } |
    Sort-Object PitchMagnitude -Descending |
    Select-Object -First 20

$document = [ordered]@{
    Mode = 'live-camera-angle-candidates'
    GeneratedAtUtc = [DateTime]::UtcNow.ToString('o')
    ProcessId = $process.Id
    ProcessName = $process.ProcessName
    SelectedSourceAddress = $selectedSourceAddress
    Regions = $regions
    TopPitchCandidates = @($topPitchCandidates)
    TopYawCandidates = @($topYawCandidates)
    AngleLikePitchOnlyCandidates = @($angleLikePitchOnly)
    Notes = @(
        'PitchReverse/YawReverse mean the value changed in opposite directions for paired up/down or left/right camera motion.'
        'AngleLike is a simple heuristic for scalars in typical radians/degrees ranges.'
        'Large entry15 triplet hits usually represent orbit-position coordinates, not direct scalar angles.'
    )
}

if ($Json) {
    $document | ConvertTo-Json -Depth 20
}
else {
    Write-Host ''
    Write-Host 'Top angle-like pitch-only candidates:' -ForegroundColor Cyan
    if ($angleLikePitchOnly.Count -eq 0) {
        Write-Host '  (none)' -ForegroundColor DarkYellow
    }
    else {
        foreach ($candidate in $angleLikePitchOnly) {
            Write-Host ("  {0} {1} {2} sample={3:N6} pitchMag={4:N6} yawMag={5:N6}" -f `
                $candidate.Region, $candidate.BaseAddress, $candidate.Offset, `
                [double]$candidate.SampleValue, [double]$candidate.PitchMagnitude, [double]$candidate.YawMagnitude) -ForegroundColor White
        }
    }

    Write-Host ''
    Write-Host 'Top yaw candidates:' -ForegroundColor Cyan
    foreach ($candidate in ($topYawCandidates | Select-Object -First 10)) {
        Write-Host ("  {0} {1} {2} class={3} sample={4:N6} yawMag={5:N6}" -f `
            $candidate.Region, $candidate.BaseAddress, $candidate.Offset, `
            $candidate.Classification, [double]$candidate.SampleValue, [double]$candidate.YawMagnitude) -ForegroundColor White
    }
}
