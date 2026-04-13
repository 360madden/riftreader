# EXPERIMENTAL PROBE: alternate PostMessage mouse injection test.
# Prefer test-rmb-camera.ps1 or test-camera-stimulus.ps1 for normal camera-input work.
Add-Type @"
using System;
using System.Runtime.InteropServices;

public class Win32 {
    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);

    public const uint WM_MOUSEMOVE = 0x0200;
    public const uint WM_LBUTTONDOWN = 0x0201;
    public const uint WM_LBUTTONUP = 0x0202;
    public const uint WM_MOUSEWHEEL = 0x020A;
}
"@

$hwnd = [Win32]::FindWindow("TWNClientFramework", "Rift")
if ($hwnd -ne [IntPtr]::Zero) {
    Write-Host "Found Rift window: $hwnd"
    
    # Try WM_MOUSEMOVE with some delta (simulate moving mouse right)
    # lParam: LOWORD=x, HIWORD=y
    # wParam: MK_LBUTTON (0x0001), MK_RBUTTON (0x0002), etc.
    
    # First test - send a mouse move
    $x = 700  # Move to right side of screen
    $y = 300
    $lParam = [IntPtr](($y -shl 16) -bor ($x -band 0xFFFF))
    
    $result1 = [Win32]::PostMessage($hwnd, [Win32]::WM_MOUSEMOVE, [IntPtr]::Zero, $lParam)
    Write-Host "WM_MOUSEMOVE (x=$x, y=$y): result=$result1"
    
    Start-Sleep -Milliseconds 500
    
    # Try wheel event - scroll down (zoom in)
    # wParam: HIWORD = wheel delta, LOWORD = key state
    $wheelDelta = -120  # Negative = scroll down
    $wParamWheel = [IntPtr]$wheelDelta
    $lParamWheel = [IntPtr]((300 -shl 16) -bor 500)  # x=500, y=300
    
    $result2 = [Win32]::PostMessage($hwnd, [Win32]::WM_MOUSEWHEEL, $wParamWheel, $lParamWheel)
    Write-Host "WM_MOUSEWHEEL (delta=-120): result=$result2"
    
    if ($result1 -or $result2) {
        Write-Host "`nPostMessage sent - check if camera moved in game"
    }
} else {
    Write-Host "Rift window not found"
}
