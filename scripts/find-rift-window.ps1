Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public class Win32 {
    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
    
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
    
    [DllImport("user32.dll", SetLastError = true)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
    
    [DllImport("user32.dll", SetLastError = true)]
    public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);
    
    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    public const uint WM_MOUSEMOVE = 0x0200;
    public const uint WM_LBUTTONDOWN = 0x0201;
    public const uint WM_LBUTTONUP = 0x0202;
    public const uint WM_MOUSEWHEEL = 0x020A;
}
"@

$process = Get-Process -Name rift_x64 -ErrorAction SilentlyContinue
if ($process) {
    Write-Host "Rift process found: PID $($process.Id)"
}

# Try different class names
$classNames = @("Rift", "Rift_x64", "TrionWorldsRiftClient", "GWEN", "")
$foundWindow = [IntPtr]::Zero

foreach ($class in $classNames) {
    $hwnd = [Win32]::FindWindow($class, $null)
    if ($hwnd -ne [IntPtr]::Zero) {
        $foundWindow = $hwnd
        Write-Host "Found window with class '$class': $hwnd"
        break
    }
}

# If not found, try enum windows to find Rift
if ($foundWindow -eq [IntPtr]::Zero) {
    Write-Host "Trying EnumWindows..."
    
    $windows = @()
    
    $callback = {
        param([IntPtr]$hWnd, [IntPtr]$lParam)
        
        $title = New-Object System.Text.StringBuilder 256
        $className = New-Object System.Text.StringBuilder 256
        [Win32]::GetWindowText($hWnd, $title, 256) | Out-Null
        [Win32]::GetClassName($hWnd, $className, 256) | Out-Null
        
        $titleStr = $title.ToString()
        $classStr = $className.ToString()
        
        if ($titleStr -match "Rift" -or $classStr -match "Rift" -or $classStr -eq "GWEN") {
            $processId = 0
            [Win32]::GetWindowThreadProcessId($hWnd, [ref]$processId) | Out-Null
            
            $windows += [PSCustomObject]@{
                Handle = $hWnd
                Title = $titleStr
                ClassName = $classStr
                ProcessId = $processId
            }
        }
        
        return $true
    }
    
    Add-Type -MemberDefinition @"
        public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
"@ -Name "EnumDelegate" -Namespace "Win32Callbacks"
    
    # Actually let's simplify - just list all visible windows
    Get-Process | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero } | ForEach-Object {
        $hWnd = $_.MainWindowHandle
        $title = New-Object System.Text.StringBuilder 256
        $className = New-Object System.Text.StringBuilder 256
        [Win32]::GetWindowText($hWnd, $title, 256) | Out-Null
        [Win32]::GetClassName($hWnd, $className, 256) | Out-Null
        
        if ($title.ToString() -or $className.ToString()) {
            Write-Host "Process: $($_.Name) | Title: '$($title.ToString())' | Class: '$($className.ToString())' | HWND: $hWnd"
        }
    }
}