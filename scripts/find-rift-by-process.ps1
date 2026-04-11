# Find RIFT window by process ID

$rift = Get-Process -Name rift_x64 -ErrorAction SilentlyContinue
if (-not $rift) {
    Write-Host "rift_x64 not running" -ForegroundColor Red
    exit
}

$riftPid = $rift.Id
Write-Host "RIFT PID: $riftPid" -ForegroundColor Cyan

# Get main window handle from process
$hwnd = $rift.MainWindowHandle
Write-Host "MainWindowHandle: $hwnd ($(('0x' + $hwnd.ToString('X'))))" -ForegroundColor Yellow

if ($hwnd -ne [IntPtr]::Zero) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport("user32.dll")]
    public static extern int GetClassName(IntPtr hWnd, System.Text.StringBuilder lpClassName, int nMaxCount);
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
    $sb = New-Object System.Text.StringBuilder 256
    [Win32]::GetClassName($hwnd, $sb, 256) | Out-Null
    $className = $sb.ToString()
    Write-Host "Class: $className" -ForegroundColor Green
    
    $rect = New-Object Win32+RECT
    [Win32]::GetWindowRect($hwnd, [ref]$rect) | Out-Null
    Write-Host "Rect: X=$($rect.Left) Y=$($rect.Top) W=$($rect.Right-$rect.Left) H=$($rect.Bottom-$rect.Top)" -ForegroundColor Green
}