# RIFT Camera Zoom via Mouse Wheel

$ErrorActionPreference = 'Stop'
$mouseFocusHelpers = Join-Path $PSScriptRoot 'mouse-focus-helpers.ps1'
. $mouseFocusHelpers

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Mouse {
    [DllImport("user32.dll")]
    public static extern void mouse_event(uint dwFlags, int dx, int dy, int dwData, int dwExtraInfo);
    public const uint MOUSEEVENTF_WHEEL = 0x0800;
}
"@

$rift = Get-RiftMainWindowProcess -ProcessName 'rift_x64'
Focus-RiftWindow -Process $rift
[void](Assert-RiftWindowFocus -Process $rift)
[void](Move-CursorToRiftWindowCenter -Process $rift)

# Scroll wheel forward (zoom in) -120 per notch, negative = forward
for ($i = 0; $i -lt 3; $i++) {
    [Mouse]::mouse_event([Mouse]::MOUSEEVENTF_WHEEL, 0, 0, -120, 0)
    Start-Sleep -Milliseconds 100
}

Write-Host "Sent 3 wheel ticks forward (zoom in) with Rift focus verified" -ForegroundColor Green
