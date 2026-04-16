if (-not ('RiftMouseFocusSharedNative' -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class RiftMouseFocusSharedNative
{
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsIconic(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetCursorPos(int X, int Y);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint GetCurrentThreadId();

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool AttachThreadInput(uint idAttach, uint idAttachTo, bool fAttach);

    public const int SW_RESTORE = 9;
}
"@
}

function Get-RiftMainWindowProcess {
    param(
        [string]$ProcessName = 'rift_x64'
    )

    $process = Get-Process -Name $ProcessName -ErrorAction Stop |
        Where-Object { $_.MainWindowHandle -ne 0 } |
        Select-Object -First 1

    if (-not $process) {
        throw "Mouse input requires a Rift process with a main window. No process named '$ProcessName' with a main window was found."
    }

    return $process
}

function Get-RiftForegroundWindowInfo {
    $foregroundHandle = [RiftMouseFocusSharedNative]::GetForegroundWindow()
    $foregroundProcessId = 0
    [void][RiftMouseFocusSharedNative]::GetWindowThreadProcessId($foregroundHandle, [ref]$foregroundProcessId)

    $foregroundProcess = $null
    if ($foregroundProcessId -ne 0) {
        try {
            $foregroundProcess = Get-Process -Id $foregroundProcessId -ErrorAction Stop
        }
        catch {
            $foregroundProcess = $null
        }
    }

    [pscustomobject]@{
        Handle = $foregroundHandle
        ProcessId = [int]$foregroundProcessId
        ProcessName = if ($null -ne $foregroundProcess) { [string]$foregroundProcess.ProcessName } else { $null }
    }
}

function Focus-RiftWindow {
    param(
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$Process,
        [int]$FocusSettleMilliseconds = 250
    )

    $targetHandle = [IntPtr]$Process.MainWindowHandle
    if ($targetHandle -eq [IntPtr]::Zero) {
        throw "Mouse input requires a main window handle for '$($Process.ProcessName)'."
    }

    $dummyProcessId = 0
    $targetThreadId = [RiftMouseFocusSharedNative]::GetWindowThreadProcessId($targetHandle, [ref]$dummyProcessId)
    $currentThreadId = [RiftMouseFocusSharedNative]::GetCurrentThreadId()
    $foregroundHandle = [RiftMouseFocusSharedNative]::GetForegroundWindow()
    $foregroundProcessId = 0
    $foregroundThreadId = [RiftMouseFocusSharedNative]::GetWindowThreadProcessId($foregroundHandle, [ref]$foregroundProcessId)

    if ([RiftMouseFocusSharedNative]::IsIconic($targetHandle)) {
        [void][RiftMouseFocusSharedNative]::ShowWindow($targetHandle, [RiftMouseFocusSharedNative]::SW_RESTORE)
    }

    [void][RiftMouseFocusSharedNative]::AttachThreadInput($currentThreadId, $foregroundThreadId, $true)
    [void][RiftMouseFocusSharedNative]::AttachThreadInput($currentThreadId, $targetThreadId, $true)
    [void][RiftMouseFocusSharedNative]::SetForegroundWindow($targetHandle)
    [void][RiftMouseFocusSharedNative]::AttachThreadInput($currentThreadId, $foregroundThreadId, $false)
    [void][RiftMouseFocusSharedNative]::AttachThreadInput($currentThreadId, $targetThreadId, $false)
    Start-Sleep -Milliseconds $FocusSettleMilliseconds
}

function Assert-RiftWindowFocus {
    param(
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$Process
    )

    $foreground = Get-RiftForegroundWindowInfo
    if ($foreground.ProcessId -ne $Process.Id) {
        $foregroundName = if (-not [string]::IsNullOrWhiteSpace($foreground.ProcessName)) { $foreground.ProcessName } else { 'unknown' }
        throw ("Mouse input requires a clean focused Rift window. Expected {0} [{1}] in foreground, got {2} [{3}] handle 0x{4:X}. Activate the Rift window on the selected desktop and retry." -f $Process.ProcessName, $Process.Id, $foregroundName, $foreground.ProcessId, $foreground.Handle.ToInt64())
    }

    return $foreground
}

function Get-RiftWindowRect {
    param(
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$Process
    )

    $rect = New-Object RiftMouseFocusSharedNative+RECT
    if (-not [RiftMouseFocusSharedNative]::GetWindowRect([IntPtr]$Process.MainWindowHandle, [ref]$rect)) {
        throw 'GetWindowRect failed for the RIFT window.'
    }

    return $rect
}

function Move-CursorToRiftWindowCenter {
    param(
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$Process,
        [int]$OffsetX = 0,
        [int]$OffsetY = 0
    )

    $rect = Get-RiftWindowRect -Process $Process
    $centerX = [int](($rect.Left + $rect.Right) / 2) + $OffsetX
    $centerY = [int](($rect.Top + $rect.Bottom) / 2) + $OffsetY

    if (-not [RiftMouseFocusSharedNative]::SetCursorPos($centerX, $centerY)) {
        throw 'SetCursorPos failed while centering the cursor over RIFT.'
    }

    [pscustomobject]@{
        X = $centerX
        Y = $centerY
    }
}
