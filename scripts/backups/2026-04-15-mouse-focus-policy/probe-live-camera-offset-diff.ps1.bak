[CmdletBinding()]
param(
    [switch]$Json,
    [string]$ProcessName = 'rift_x64',
    [int]$MaxHits = 6,
    [int]$RegionLength = 512,
    [int]$MousePixels = 90,
    [string[]]$BaseAddresses = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'

function Invoke-ReaderJson {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    $output = & dotnet run --project $readerProject -- @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Reader command failed: $($output -join [Environment]::NewLine)"
    }

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 60
}

if (-not ('RiftCameraDiffNative' -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class RiftCameraDiffNative
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
        [Parameter(Mandatory = $true)][UInt64]$Address,
        [Parameter(Mandatory = $true)][int]$Length
    )

    $baseAddress = [IntPtr]([Int64]$Address)
    $buffer = New-Object byte[] $Length
    $bytesRead = [IntPtr]::Zero
    $ok = [RiftCameraDiffNative]::ReadProcessMemory($Process.Handle, $baseAddress, $buffer, $Length, [ref]$bytesRead)
    if (-not $ok) {
        $lastError = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        throw "ReadProcessMemory failed at 0x{0:X} (Win32: {1})" -f $Address, $lastError
    }

    $actualLength = $bytesRead.ToInt32()
    if ($actualLength -lt 4) {
        return @()
    }

    $floatCount = [Math]::Floor($actualLength / 4)
    $floats = New-Object double[] $floatCount
    for ($index = 0; $index -lt $floatCount; $index++) {
        $value = [double][BitConverter]::ToSingle($buffer, $index * 4)
        if ([double]::IsNaN($value) -or [double]::IsInfinity($value)) {
            $value = 0.0
        }
        $floats[$index] = $value
    }

    return $floats
}

function Capture-Regions {
    param(
        [Parameter(Mandatory = $true)]$Process,
        [Parameter(Mandatory = $true)]$Regions
    )

    $snapshot = @{}
    foreach ($region in $Regions) {
        try {
            $snapshot[$region.Name] = Read-MemoryFloats -Process $Process -Address $region.Address -Length $region.Length
        }
        catch {
            $snapshot[$region.Name] = @()
        }
    }

    return $snapshot
}

function Add-RegionIfMissing {
    param(
        [Parameter(Mandatory = $true)]$Regions,
        [Parameter(Mandatory = $true)]$Seen,
        [Parameter(Mandatory = $true)][UInt64]$BaseAddress,
        [Parameter(Mandatory = $true)][int]$Length,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $key = ('0x{0:X}' -f $BaseAddress)
    if ($Seen.Add($key)) {
        $Regions.Add([pscustomobject]@{
            Name = $Name
            Address = $BaseAddress
            Length = $Length
        }) | Out-Null
    }
}

function Invoke-RmbMove {
    param(
        [Parameter(Mandatory = $true)]$Process,
        [Parameter(Mandatory = $true)][int]$Dx,
        [Parameter(Mandatory = $true)][int]$Dy
    )

    [void][RiftCameraDiffNative]::ShowWindow($Process.MainWindowHandle, [RiftCameraDiffNative]::SW_RESTORE)
    [void][RiftCameraDiffNative]::SetForegroundWindow($Process.MainWindowHandle)
    Start-Sleep -Milliseconds 200

    $rect = New-Object RiftCameraDiffNative+RECT
    if (-not [RiftCameraDiffNative]::GetWindowRect($Process.MainWindowHandle, [ref]$rect)) {
        throw 'GetWindowRect failed for the RIFT window.'
    }

    $centerX = [int](($rect.Left + $rect.Right) / 2)
    $centerY = [int](($rect.Top + $rect.Bottom) / 2)
    [void][RiftCameraDiffNative]::SetCursorPos($centerX, $centerY)
    Start-Sleep -Milliseconds 50

    [RiftCameraDiffNative]::mouse_event([RiftCameraDiffNative]::MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 60
    [RiftCameraDiffNative]::mouse_event([RiftCameraDiffNative]::MOUSEEVENTF_MOVE, $Dx, $Dy, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 120
    [RiftCameraDiffNative]::mouse_event([RiftCameraDiffNative]::MOUSEEVENTF_RIGHTUP, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 200
}

function Get-DiffCandidates {
    param(
        [Parameter(Mandatory = $true)]$BeforeMap,
        [Parameter(Mandatory = $true)]$AfterMap,
        [Parameter(Mandatory = $true)]$ReturnMap,
        [Parameter(Mandatory = $true)]$Regions,
        [Parameter(Mandatory = $true)][string]$Kind
    )

    $results = New-Object System.Collections.Generic.List[object]

    foreach ($region in $Regions) {
        $before = @($BeforeMap[$region.Name])
        $after = @($AfterMap[$region.Name])
        $returned = @($ReturnMap[$region.Name])
        $max = [Math]::Min($before.Count, [Math]::Min($after.Count, $returned.Count))

        for ($index = 0; $index -lt $max; $index++) {
            $deltaA = [double]$after[$index] - [double]$before[$index]
            $deltaB = [double]$returned[$index] - [double]$after[$index]

            if ([Math]::Abs($deltaA) -lt 0.001 -or [Math]::Abs($deltaB) -lt 0.001) {
                continue
            }

            if ([Math]::Sign($deltaA) -ne -[Math]::Sign($deltaB)) {
                continue
            }

            $sample = [double]$after[$index]
            $angleLike = ([Math]::Abs($sample) -le 6.5) -or ([Math]::Abs($sample) -le 360.0)
            $results.Add([pscustomobject]@{
                Kind = $Kind
                Region = $region.Name
                BaseAddress = ('0x{0:X}' -f $region.Address)
                Offset = ('0x{0:X3}' -f ($index * 4))
                SampleValue = $sample
                AngleLike = $angleLike
                DeltaForward = $deltaA
                DeltaReturn = $deltaB
                Magnitude = [Math]::Abs($deltaA) + [Math]::Abs($deltaB)
            }) | Out-Null
        }
    }

    return $results
}

$regions = New-Object System.Collections.Generic.List[object]
$seen = [System.Collections.Generic.HashSet[string]]::new()

if ($BaseAddresses.Count -gt 0) {
    $curatedIndex = 0
    foreach ($rawBaseAddress in $BaseAddresses) {
        if ([string]::IsNullOrWhiteSpace($rawBaseAddress)) {
            continue
        }

        $baseAddress = Parse-HexUInt64 -Value $rawBaseAddress
        Add-RegionIfMissing -Regions $regions -Seen $seen -BaseAddress $baseAddress -Length $RegionLength -Name ('curated_base_{0:D2}_{1}' -f $curatedIndex, ('0x{0:X}' -f $baseAddress))
        $curatedIndex++
    }
}
else {
    $coordScan = Invoke-ReaderJson -Arguments @(
        '--process-name', $ProcessName,
        '--scan-readerbridge-player-coords',
        '--max-hits', $MaxHits.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json')

    foreach ($hit in @($coordScan.Hits)) {
        $hitAddress = [UInt64]$hit.Address
        foreach ($offset in @(0x48, 0x88)) {
            if ($hitAddress -lt [UInt64]$offset) {
                continue
            }

            $baseAddress = $hitAddress - [UInt64]$offset
            Add-RegionIfMissing -Regions $regions -Seen $seen -BaseAddress $baseAddress -Length $RegionLength -Name ('base_{0}_from_{1}' -f ('0x{0:X}' -f $baseAddress).Substring(2), ('0x{0:X}' -f $offset).Substring(2))
        }
    }
}

if ($regions.Count -eq 0) {
    throw 'No candidate regions were collected. Provide -BaseAddresses or ensure coord hits are available.'
}

$process = Get-Process -Name $ProcessName -ErrorAction Stop |
    Where-Object { $_.MainWindowHandle -ne 0 } |
    Select-Object -First 1
if (-not $process) {
    throw "No process named '$ProcessName' with a main window was found."
}

$yawBefore = Capture-Regions -Process $process -Regions $regions
Invoke-RmbMove -Process $process -Dx $MousePixels -Dy 0
$yawAfter = Capture-Regions -Process $process -Regions $regions
Invoke-RmbMove -Process $process -Dx (-1 * $MousePixels) -Dy 0
$yawReturn = Capture-Regions -Process $process -Regions $regions

$pitchBefore = Capture-Regions -Process $process -Regions $regions
Invoke-RmbMove -Process $process -Dx 0 -Dy (-1 * $MousePixels)
$pitchAfter = Capture-Regions -Process $process -Regions $regions
Invoke-RmbMove -Process $process -Dx 0 -Dy $MousePixels
$pitchReturn = Capture-Regions -Process $process -Regions $regions

$yawCandidates = Get-DiffCandidates -BeforeMap $yawBefore -AfterMap $yawAfter -ReturnMap $yawReturn -Regions $regions -Kind 'yaw'
$pitchCandidates = Get-DiffCandidates -BeforeMap $pitchBefore -AfterMap $pitchAfter -ReturnMap $pitchReturn -Regions $regions -Kind 'pitch'

$topYaw = @($yawCandidates | Sort-Object @{ Expression = 'AngleLike'; Descending = $true }, @{ Expression = 'Magnitude'; Descending = $true } | Select-Object -First 24)
$topPitch = @($pitchCandidates | Sort-Object @{ Expression = 'AngleLike'; Descending = $true }, @{ Expression = 'Magnitude'; Descending = $true } | Select-Object -First 24)
$regionArray = @($regions.ToArray())

$document = [pscustomobject]@{
    Mode = 'live-camera-offset-diff'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    ProcessId = $process.Id
    ProcessName = $process.ProcessName
    MousePixels = $MousePixels
    RegionLength = $RegionLength
    CandidateSource = $(if ($BaseAddresses.Count -gt 0) { 'curated-base-addresses' } else { 'coord-hit-derived-bases' })
    RegionCount = $regions.Count
    Regions = $regionArray
    TopYawCandidates = $topYaw
    TopPitchCandidates = $topPitch
    Notes = @(
        'This probe uses direct raw reads plus RMB camera motion only.',
        'It does not call refresh-readerbridge-export, reloadui, or the legacy camera recovery chain.',
        'Reversible deltas suggest a candidate field changed under camera motion and returned when the motion was reversed.'
    )
}

if ($Json) {
    $document | ConvertTo-Json -Depth 20
    return
}

Write-Host "Live camera offset diff"
Write-Host ("Process:                 {0} [{1}]" -f $process.ProcessName, $process.Id)
Write-Host ("Candidate source:        {0}" -f $(if ($BaseAddresses.Count -gt 0) { 'curated-base-addresses' } else { 'coord-hit-derived-bases' }))
Write-Host ("Regions tested:          {0}" -f $regions.Count)
Write-Host ""
Write-Host "Top yaw candidates:"
foreach ($candidate in $topYaw | Select-Object -First 10) {
    Write-Host ("  {0} {1} {2} sample={3:N6} mag={4:N6}" -f $candidate.Region, $candidate.BaseAddress, $candidate.Offset, [double]$candidate.SampleValue, [double]$candidate.Magnitude)
}
Write-Host ""
Write-Host "Top pitch candidates:"
foreach ($candidate in $topPitch | Select-Object -First 10) {
    Write-Host ("  {0} {1} {2} sample={3:N6} mag={4:N6}" -f $candidate.Region, $candidate.BaseAddress, $candidate.Offset, [double]$candidate.SampleValue, [double]$candidate.Magnitude)
}
