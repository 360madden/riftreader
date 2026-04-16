# EXPERIMENTAL PROBE: PostMessage mouse injection test.
# Historical experiment only. Canonical mouse-input work now requires clean
# Rift window acquisition plus verified focus; do not treat background
# PostMessage as a normal mouse fallback.
Add-Type @"
using System;
using System.Runtime.InteropServices;

public class Win32 {
    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
    
    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr FindWindowEx(IntPtr hwndParent, IntPtr hwndChildAfter, string lpszClass, string lpszWindow);

    public const uint WM_MOUSEMOVE = 0x0200;
    public const uint WM_LBUTTONDOWN = 0x0201;
    public const uint WM_LBUTTONUP = 0x0202;
    public const uint WM_MOUSEWHEEL = 0x020A;
}
"@

$hwnd = [Win32]::FindWindow("Rift", $null)
if ($hwnd -ne [IntPtr]::Zero) {
    Write-Host "Found Rift window: $hwnd"
    
    # Try WM_MOUSEMOVE
    $result1 = [Win32]::PostMessage($hwnd, [Win32]::WM_MOUSEMOVE, [IntPtr]::Zero, [IntPtr]::MakeInt32(600, 300))
    Write-Host "WM_MOUSEMOVE result: $result1"
    
    Start-Sleep -Milliseconds 500
    
    # Try WM_LBUTTONDOWN + WM_LBUTTONUP
    $result2 = [Win32]::PostMessage($hwnd, [Win32]::WM_LBUTTONDOWN, [IntPtr]::Zero, [IntPtr]::MakeInt32(500, 300))
    Start-Sleep -Milliseconds 100
    $result3 = [Win32]::PostMessage($hwnd, [Win32]::WM_LBUTTONUP, [IntPtr]::Zero, [IntPtr]::MakeInt32(500, 300))
    Write-Host "WM_LBUTTONDOWN/UP result: $result2 / $result3"
} else {
    Write-Host "Rift window not found"
}
