[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('mouse-yaw', 'mouse-pitch', 'mouse-wheel')]
    [string]$Stimulus,
    [string]$SelectedSourceAddress = '0x1577AC2FB60',
    [int]$HoldMilliseconds = 500,
    [int]$WaitMilliseconds = 250,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$mouseFocusHelpers = Join-Path $PSScriptRoot 'mouse-focus-helpers.ps1'
. $mouseFocusHelpers

# Parse address
$address = if ($SelectedSourceAddress -match '^0x([0-9A-Fa-f]+)$') {
    [UInt64]::Parse($Matches[1], [System.Globalization.NumberStyles]::HexNumber)
}
else {
    [UInt64]::Parse($SelectedSourceAddress, [System.Globalization.NumberStyles]::HexNumber)
}

$cameraStart = $address + 0xB8

# C# memory reader
Add-Type @"
using System;
using System.Collections.Generic;

public class MemoryCapture {
    [System.Runtime.InteropServices.DllImport("kernel32.dll")]
    private static extern bool ReadProcessMemory(
        IntPtr hProcess,
        IntPtr lpBaseAddress,
        byte[] lpBuffer,
        int nSize,
        out IntPtr lpNumberOfBytesRead);

    public static byte[] ReadMemory(IntPtr processHandle, IntPtr address, int size) {
        byte[] buffer = new byte[size];
        if (ReadProcessMemory(processHandle, address, buffer, size, out _)) {
            return buffer;
        }
        return null;
    }

    public static List<float> ReadFloatArray(IntPtr processHandle, IntPtr address, int count) {
        var result = new List<float>();
        byte[] buffer = ReadMemory(processHandle, address, count * 4);
        if (buffer != null) {
            for (int i = 0; i < count; i++) {
                result.Add(BitConverter.ToSingle(buffer, i * 4));
            }
        }
        return result;
    }
}
"@

function Send-MouseInput {
    param(
        [ValidateSet('right', 'up', 'wheel-up')]
        [string]$Direction,
        [int]$Magnitude = 50,
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$Process
    )

    Focus-RiftWindow -Process $Process
    [void](Assert-RiftWindowFocus -Process $Process)
    $center = Move-CursorToRiftWindowCenter -Process $Process

    switch ($Direction) {
        'right' {
            [void][RiftMouseFocusSharedNative]::SetCursorPos($center.X + $Magnitude, $center.Y)
        }
        'up' {
            [void][RiftMouseFocusSharedNative]::SetCursorPos($center.X, $center.Y - $Magnitude)
        }
        'wheel-up' {
            Add-Type @"
using System;
using System.Runtime.InteropServices;
public class MouseWheel {
    [DllImport("user32.dll", SetLastError = true)]
    public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint cButtons, uint dwExtraInfo);
    public const uint MOUSEEVENTF_WHEEL = 0x0800;
    public static void ScrollWheel(int delta) {
        mouse_event(MOUSEEVENTF_WHEEL, 0, 0, (uint)delta, 0);
    }
}
"@
            [MouseWheel]::ScrollWheel($Magnitude)
        }
    }
}

try {
    $riftProcess = Get-Process -Name "rift_x64" -ErrorAction Stop | Select-Object -First 1

    Write-Host "=== Camera Stimulus with Memory Capture ===" -ForegroundColor Cyan
    Write-Host "Stimulus: $Stimulus" -ForegroundColor Green
    Write-Host "Component: $SelectedSourceAddress" -ForegroundColor Green
    Write-Host ""

    # Capture baseline
    Write-Host "Capturing baseline memory..." -ForegroundColor Yellow
    $baseline = [MemoryCapture]::ReadFloatArray($riftProcess.Handle, [IntPtr]$cameraStart, 22)

    if ($baseline.Count -eq 0) {
        throw "Failed to read baseline memory"
    }

    Write-Host "  ✓ Baseline captured (22 floats)" -ForegroundColor Green

    # Send input
    Write-Host "Sending stimulus: $Stimulus" -ForegroundColor Yellow

    $inputDirection = switch ($Stimulus) {
        'mouse-yaw' { 'right' }
        'mouse-pitch' { 'up' }
        'mouse-wheel' { 'wheel-up' }
    }

    Send-MouseInput -Direction $inputDirection -Magnitude 50 -Process $riftProcess
    Start-Sleep -Milliseconds $HoldMilliseconds

    # Capture after
    Write-Host "Capturing post-stimulus memory..." -ForegroundColor Yellow
    $after = [MemoryCapture]::ReadFloatArray($riftProcess.Handle, [IntPtr]$cameraStart, 22)

    if ($after.Count -eq 0) {
        throw "Failed to read after memory"
    }

    Write-Host "  ✓ Post-stimulus captured" -ForegroundColor Green
    Write-Host ""

    # Analyze deltas
    Write-Host "Memory changes:" -ForegroundColor Yellow
    $significantDeltas = @()

    for ($i = 0; $i -lt 22; $i++) {
        $beforeVal = [float]$baseline[$i]
        $afterVal = [float]$after[$i]
        $delta = $afterVal - $beforeVal
        $percentChange = if ($beforeVal -ne 0) { ($delta / [Math]::Abs($beforeVal)) * 100 } else { if ($delta -ne 0) { 100 } else { 0 } }

        # Report significant changes
        if ([Math]::Abs($delta) -gt 0.001) {
            $offset = $i * 4
            $offsetHex = [string]::Format('0x{0:X}', $offset)
            Write-Host "  [+$offsetHex] Before: $([string]::Format('{0,12:F6}', $beforeVal)) → After: $([string]::Format('{0,12:F6}', $afterVal)) (Δ = $([string]::Format('{0,+10:F6}', $delta)))" -ForegroundColor Cyan

            $significantDeltas += [PSCustomObject]@{
                Offset = $offsetHex
                Before = $beforeVal
                After = $afterVal
                Delta = $delta
                PercentChange = $percentChange
            }
        }
    }

    if ($significantDeltas.Count -eq 0) {
        Write-Host "  No significant changes detected in camera range." -ForegroundColor Yellow
        Write-Host "  Camera may be in a different memory location or controlled differently." -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "Summary:" -ForegroundColor Green
    Write-Host "  Total offsets changed: $($significantDeltas.Count) / 22" -ForegroundColor White

    if ($Json) {
        $output = [ordered]@{
            Mode = 'camera-stimulus-memory-test'
            GeneratedAtUtc = [System.DateTime]::UtcNow.ToString('o')
            Stimulus = $Stimulus
            SelectedSourceAddress = $SelectedSourceAddress
            CameraRangeStart = [string]::Format('0x{0:X}', $cameraStart)
            BaselineFloats = $baseline
            AfterFloats = $after
            SignificantDeltas = $significantDeltas
        }
        $output | ConvertTo-Json -Depth 20
    }
}
catch {
    Write-Error "Failed: $_"
    exit 1
}
