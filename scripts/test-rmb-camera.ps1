# RIFT Camera Control - Step by step with pauses

$ErrorActionPreference = 'Stop'
$mouseFocusHelpers = Join-Path $PSScriptRoot 'mouse-focus-helpers.ps1'
. $mouseFocusHelpers

# Get RIFT process and window
$rift = Get-RiftMainWindowProcess -ProcessName 'rift_x64'
Focus-RiftWindow -Process $rift
[void](Assert-RiftWindowFocus -Process $rift)

$hwnd = $rift.MainWindowHandle
Write-Host "=== Step 1: Found RIFT ===" -ForegroundColor Cyan
Write-Host "  PID: $($rift.Id), HWND: $hwnd"
Write-Host "  Focus verified on Rift foreground window" -ForegroundColor Green

Add-Type @"
using System; using System.Runtime.InteropServices;
public class Mouse {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, int dx, int dy, int dwData, int dwExtraInfo);
    public const uint MOUSEEVENTF_RIGHTDOWN = 0x0008;
    public const uint MOUSEEVENTF_RIGHTUP = 0x0010;
    public const uint MOUSEEVENTF_MOVE = 0x0001;
}
"@

# Move cursor to window
Write-Host "`n=== Step 2: Move cursor to window center ===" -ForegroundColor Cyan
$center = Move-CursorToRiftWindowCenter -Process $rift
$centerX = $center.X
$centerY = $center.Y
Write-Host "  Cursor at ($centerX, $centerY)"
Write-Host "  LOOK AT SCREEN NOW - cursor should be in game" -ForegroundColor Yellow

Read-Host "Press Enter to hold RMB..."

# Hold RMB
Write-Host "`n=== Step 3: Holding RMB (right mouse button) ===" -ForegroundColor Cyan
Focus-RiftWindow -Process $rift
[void](Assert-RiftWindowFocus -Process $rift)
[Mouse]::mouse_event([Mouse]::MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
Write-Host "  RMB held down"

Read-Host "Press Enter to move mouse..."

# Move while holding
Write-Host "`n=== Step 4: Moving mouse while holding RMB ===" -ForegroundColor Cyan
Focus-RiftWindow -Process $rift
[void](Assert-RiftWindowFocus -Process $rift)
for ($i = 0; $i -lt 5; $i++) {
    [Mouse]::mouse_event([Mouse]::MOUSEEVENTF_MOVE, 50, 0, 0, 0)
    Write-Host "  Move $i : 50 pixels right"
    Start-Sleep -Milliseconds 200
}

Read-Host "Press Enter to release RMB..."

# Release RMB
Write-Host "`n=== Step 5: Releasing RMB ===" -ForegroundColor Cyan
Focus-RiftWindow -Process $rift
[void](Assert-RiftWindowFocus -Process $rift)
[Mouse]::mouse_event([Mouse]::MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
Write-Host "  RMB released"

Write-Host "`n=== DONE ===" -ForegroundColor Green
Write-Host "Camera should have rotated right" -ForegroundColor Green
