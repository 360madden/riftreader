[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('yaw', 'pitch', 'zoom')]
    [string]$Stimulus,
    [string]$Address = '0x1577AC2FB60'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Convert address
$baseAddr = [UInt64]::Parse($Address.TrimStart('0x'), [System.Globalization.NumberStyles]::HexNumber)
$cameraAddr = $baseAddr + 0xB8

Write-Host "=== Simple Camera Memory Test ===" -ForegroundColor Cyan
Write-Host "Testing: $Stimulus stimulus" -ForegroundColor Green
Write-Host "Camera memory start: $('{0:X}' -f $cameraAddr)" -ForegroundColor Green
Write-Host ""

# Add P/Invoke
Add-Type -TypeDefinition @"
using System;
using System.Diagnostics;

public class MemReader {
    [System.Runtime.InteropServices.DllImport("kernel32.dll")]
    static extern bool ReadProcessMemory(IntPtr hProcess, IntPtr lpBaseAddress, byte[] lpBuffer, int nSize, out IntPtr lpNumberOfBytesRead);

    public static byte[] Read(IntPtr proc, IntPtr addr, int len) {
        byte[] buf = new byte[len];
        ReadProcessMemory(proc, addr, buf, len, out _);
        return buf;
    }
}
"@

$proc = (Get-Process -Name "rift_x64")[0].Handle

# Read 88 bytes (22 floats)
Write-Host "Reading baseline..." -ForegroundColor Yellow
$baseline = [MemReader]::Read($proc, [IntPtr]$cameraAddr, 88)
Write-Host "Baseline: $($baseline.Length) bytes read" -ForegroundColor Green

# Send input
Write-Host "Sending input..." -ForegroundColor Yellow
Add-Type -AssemblyName System.Windows.Forms

$input_map = @{
    'yaw' = { [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point(800, 400) }
    'pitch' = { [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point(400, 300) }
    'zoom' = {
        Add-Type @"
using System.Runtime.InteropServices;
public class MW {
    [DllImport("user32.dll")]
    public static extern void mouse_event(uint f, uint dx, uint dy, uint btn, uint info);
    public static void Wheel(int d) { mouse_event(0x0800, 0, 0, (uint)d, 0); }
}
"@
        [MW]::Wheel(120)
    }
}

& $input_map[$Stimulus]
Start-Sleep -Milliseconds 500

# Read after
Write-Host "Reading after-state..." -ForegroundColor Yellow
$after = [MemReader]::Read($proc, [IntPtr]$cameraAddr, 88)
Write-Host "After: $($after.Length) bytes read" -ForegroundColor Green

# Compare
Write-Host ""
Write-Host "Memory changes:" -ForegroundColor Cyan
$changed = 0

for ($i = 0; $i -lt 88; $i += 4) {
    $before = [BitConverter]::ToSingle($baseline, $i)
    $aft = [BitConverter]::ToSingle($after, $i)
    $delta = $aft - $before

    if ([Math]::Abs($delta) -gt 0.001) {
        Write-Host "  Offset +0x$([string]::Format('{0:X2}', $i)): $($before.ToString('F6')) → $($aft.ToString('F6')) (Δ = $($delta.ToString('+0.000000;-0.000000')))" -ForegroundColor White
        $changed++
    }
}

if ($changed -eq 0) {
    Write-Host "  (No significant changes detected)" -ForegroundColor Yellow
}
else {
    Write-Host ""
    Write-Host "Found $changed offset(s) with significant changes" -ForegroundColor Green
}
