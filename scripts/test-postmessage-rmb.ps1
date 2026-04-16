# EXPERIMENTAL PROBE: PostMessage right-button hold test.
# Historical experiment only. Canonical mouse-input work now requires clean
# Rift window acquisition plus verified focus; do not treat PostMessage RMB as
# the primary mouse-input path.
Add-Type @"
using System; using System.Runtime.InteropServices;
public class Win32 {
    [DllImport("user32.dll")] 
    public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")] 
    public static extern bool SetCursorPos(int X, int Y);
    public const uint WM_RBUTTONDOWN = 0x0204;
    public const uint WM_RBUTTONUP = 0x0205;
    public const uint WM_MOUSEMOVE = 0x0200;
    public const int MK_RBUTTON = 0x0010;
}
"@

$rift = Get-Process -Name rift_x64 -ErrorAction SilentlyContinue
$hwnd = $rift.MainWindowHandle

# Step 1: PostMessage RMB down
Write-Host "=== STEP 1: PostMessage WM_RBUTTONDOWN ===" -ForegroundColor Cyan

# lParam = (y << 16) | x, wParam = key state
$lParam = [IntPtr]((300 -shl 16) -bor 300)
$wParam = [IntPtr][Win32]::MK_RBUTTON

[Win32]::PostMessage($hwnd, [Win32]::WM_RBUTTONDOWN, $wParam, $lParam) | Out-Null
Write-Host "Sent - RMB should be held down now" -ForegroundColor Green

Write-Host "`n=== Tell me: do you see cursor showing RMB is held? ===" -ForegroundColor Yellow
