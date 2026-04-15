[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Key,
    [int]$HoldMilliseconds = 250,
    [string]$TargetProcessName = "rift_x64",
    [string]$BackgroundProcessName = "cheatengine-x86_64-SSE4-AVX2",
    [int]$InterKeyDelayMilliseconds = 60,
    [int]$FocusSettleMilliseconds = 500,
    [int]$PostKeySettleMilliseconds = 150,
    [switch]$SkipBackgroundFocus
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RiftKeyNative
{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern short VkKeyScan(char ch);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint MapVirtualKey(uint uCode, uint uMapType);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsIconic(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint GetCurrentThreadId();

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool AttachThreadInput(uint idAttach, uint idAttachTo, bool fAttach);

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct GUITHREADINFO
    {
        public int cbSize;
        public uint flags;
        public IntPtr hwndActive;
        public IntPtr hwndFocus;
        public IntPtr hwndCapture;
        public IntPtr hwndMenuOwner;
        public IntPtr hwndMoveSize;
        public IntPtr hwndCaret;
        public RECT rcCaret;
    }

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool GetGUIThreadInfo(uint idThread, ref GUITHREADINFO lpgui);

    [StructLayout(LayoutKind.Sequential)]
    public struct INPUT
    {
        public uint type;
        public InputUnion U;
    }

    [StructLayout(LayoutKind.Explicit)]
    public struct InputUnion
    {
        [FieldOffset(0)] public KEYBDINPUT ki;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct KEYBDINPUT
    {
        public ushort wVk;
        public ushort wScan;
        public uint dwFlags;
        public uint time;
        public IntPtr dwExtraInfo;
    }
}
"@

$WM_KEYDOWN = 0x0100
$WM_KEYUP = 0x0101
$MAPVK_VK_TO_VSC = 0
$SW_RESTORE = 9
$INPUT_KEYBOARD = 1
$KEYEVENTF_KEYUP = 0x0002
$VK_SHIFT = 0x10
$VK_CONTROL = 0x11
$VK_MENU = 0x12

function Get-MainWindowProcess {
    param([string]$ProcessName)

    $candidates = @()

    try {
        $candidates = @(Get-Process -Name $ProcessName -ErrorAction Stop |
            Where-Object { $_.MainWindowHandle -ne 0 })
    }
    catch {
        $candidates = @()
    }

    if ($candidates.Count -eq 0 -and $ProcessName -like 'cheatengine*') {
        $candidates = @(Get-Process -Name 'cheatengine*' -ErrorAction SilentlyContinue |
            Where-Object { $_.MainWindowHandle -ne 0 })
    }

    $candidate = $candidates | Select-Object -First 1

    if (-not $candidate) {
        throw "No process named '$ProcessName' with a main window was found."
    }
    return $candidate
}

function Focus-Window {
    param([System.Diagnostics.Process]$Process)

    $targetHandle = [IntPtr]$Process.MainWindowHandle
    $dummyProcessId = 0
    $targetThreadId = [RiftKeyNative]::GetWindowThreadProcessId($targetHandle, [ref]$dummyProcessId)
    $currentThreadId = [RiftKeyNative]::GetCurrentThreadId()
    $foregroundHandle = [RiftKeyNative]::GetForegroundWindow()
    $foregroundProcessId = 0
    $foregroundThreadId = [RiftKeyNative]::GetWindowThreadProcessId($foregroundHandle, [ref]$foregroundProcessId)

    if ([RiftKeyNative]::IsIconic($targetHandle)) {
        [void][RiftKeyNative]::ShowWindow($Process.MainWindowHandle, $SW_RESTORE)
    }
    [void][RiftKeyNative]::AttachThreadInput($currentThreadId, $foregroundThreadId, $true)
    [void][RiftKeyNative]::AttachThreadInput($currentThreadId, $targetThreadId, $true)
    [void][RiftKeyNative]::SetForegroundWindow($Process.MainWindowHandle)
    [void][RiftKeyNative]::AttachThreadInput($currentThreadId, $foregroundThreadId, $false)
    [void][RiftKeyNative]::AttachThreadInput($currentThreadId, $targetThreadId, $false)
    Start-Sleep -Milliseconds $FocusSettleMilliseconds
}

function Get-EffectiveTargetHandle {
    param(
        [IntPtr]$TopWindowHandle,
        [uint32]$TargetThreadId,
        [int]$TargetProcessId
    )

    $guiThreadInfo = New-Object RiftKeyNative+GUITHREADINFO
    $guiThreadInfo.cbSize = [Runtime.InteropServices.Marshal]::SizeOf($guiThreadInfo)

    if (-not [RiftKeyNative]::GetGUIThreadInfo($TargetThreadId, [ref]$guiThreadInfo)) {
        return $TopWindowHandle
    }

    if ($guiThreadInfo.hwndFocus -eq [IntPtr]::Zero) {
        return $TopWindowHandle
    }

    $focusOwnerProcessId = 0
    [void][RiftKeyNative]::GetWindowThreadProcessId($guiThreadInfo.hwndFocus, [ref]$focusOwnerProcessId)
    if ($focusOwnerProcessId -ne $TargetProcessId) {
        return $TopWindowHandle
    }

    return $guiThreadInfo.hwndFocus
}

function Resolve-KeyBinding {
    param([string]$KeyText)

    $namedKeys = @{
        'SPACE' = 0x20
        'LEFT' = 0x25
        'UP' = 0x26
        'RIGHT' = 0x27
        'DOWN' = 0x28
    }

    $normalized = $KeyText.Trim().ToUpperInvariant()
    if ($namedKeys.ContainsKey($normalized)) {
        return [pscustomobject]@{
            Character = $KeyText
            VirtualKey = $namedKeys[$normalized]
            ShiftState = 0
        }
    }

    if ($KeyText.Length -ne 1) {
        throw "This helper currently supports a single character key like W, A, S, D, 1, or named keys Space/Left/Up/Right/Down."
    }

    $character = $KeyText[0]
    $vkScan = [RiftKeyNative]::VkKeyScan($character)
    if ($vkScan -eq -1) {
        throw "No virtual-key mapping was found for character '$character'."
    }

    return [pscustomobject]@{
        Character = $character
        VirtualKey = $vkScan -band 0xFF
        ShiftState = ($vkScan -shr 8) -band 0xFF
    }
}

function New-KeyLParam {
    param(
        [int]$VirtualKey,
        [switch]$KeyUp
    )

    $scanCode = [RiftKeyNative]::MapVirtualKey([uint32]$VirtualKey, $MAPVK_VK_TO_VSC)
    $value = 1 -bor ($scanCode -shl 16)
    if ($KeyUp) {
        $value = $value -bor 0xC0000000
    }
    return [IntPtr]$value
}

function Post-KeyDown {
    param([IntPtr]$WindowHandle, [int]$VirtualKey)
    [void][RiftKeyNative]::PostMessage($WindowHandle, $WM_KEYDOWN, [IntPtr]$VirtualKey, (New-KeyLParam -VirtualKey $VirtualKey))
}

function Post-KeyUp {
    param([IntPtr]$WindowHandle, [int]$VirtualKey)
    [void][RiftKeyNative]::PostMessage($WindowHandle, $WM_KEYUP, [IntPtr]$VirtualKey, (New-KeyLParam -VirtualKey $VirtualKey -KeyUp))
}

function New-KeyboardInput {
    param(
        [Parameter(Mandatory = $true)]
        [int]$VirtualKey,
        [switch]$KeyUp
    )

    $input = New-Object RiftKeyNative+INPUT
    $input.type = $INPUT_KEYBOARD
    $input.U.ki.wVk = [uint16]$VirtualKey
    $input.U.ki.wScan = 0
    $input.U.ki.dwFlags = if ($KeyUp) { $KEYEVENTF_KEYUP } else { 0 }
    $input.U.ki.time = 0
    $input.U.ki.dwExtraInfo = [IntPtr]::Zero
    return $input
}

function Invoke-SendInput {
    param(
        [Parameter(Mandatory = $true)]
        [RiftKeyNative+INPUT[]]$Inputs
    )

    $size = [Runtime.InteropServices.Marshal]::SizeOf([type][RiftKeyNative+INPUT])
    $sent = [RiftKeyNative]::SendInput([uint32]$Inputs.Length, $Inputs, $size)
    if ($sent -ne $Inputs.Length) {
        throw "SendInput sent $sent of $($Inputs.Length) inputs."
    }
}

function Send-BindingInput {
    param(
        [Parameter(Mandatory = $true)]
        $Binding
    )

    $modifiersDown = New-Object System.Collections.Generic.List[int]

    if (($Binding.ShiftState -band 1) -ne 0) {
        Invoke-SendInput @((New-KeyboardInput -VirtualKey $VK_SHIFT))
        $modifiersDown.Add($VK_SHIFT)
        Start-Sleep -Milliseconds $InterKeyDelayMilliseconds
    }

    if (($Binding.ShiftState -band 2) -ne 0) {
        Invoke-SendInput @((New-KeyboardInput -VirtualKey $VK_CONTROL))
        $modifiersDown.Add($VK_CONTROL)
        Start-Sleep -Milliseconds $InterKeyDelayMilliseconds
    }

    if (($Binding.ShiftState -band 4) -ne 0) {
        Invoke-SendInput @((New-KeyboardInput -VirtualKey $VK_MENU))
        $modifiersDown.Add($VK_MENU)
        Start-Sleep -Milliseconds $InterKeyDelayMilliseconds
    }

    Invoke-SendInput @((New-KeyboardInput -VirtualKey $Binding.VirtualKey))
    Start-Sleep -Milliseconds $HoldMilliseconds
    Invoke-SendInput @((New-KeyboardInput -VirtualKey $Binding.VirtualKey -KeyUp))

    for ($i = $modifiersDown.Count - 1; $i -ge 0; $i--) {
        Start-Sleep -Milliseconds $InterKeyDelayMilliseconds
        Invoke-SendInput @((New-KeyboardInput -VirtualKey $modifiersDown[$i] -KeyUp))
    }
}

$targetProcess = Get-MainWindowProcess -ProcessName $TargetProcessName
$targetHandle = [IntPtr]$targetProcess.MainWindowHandle
$targetOwnerProcessId = 0
$targetThreadId = [RiftKeyNative]::GetWindowThreadProcessId($targetHandle, [ref]$targetOwnerProcessId)
if ($targetOwnerProcessId -ne $targetProcess.Id) {
    throw "Main window handle 0x{0:X} does not belong to process {1}." -f $targetProcess.MainWindowHandle, $targetProcess.Id
}

$effectiveTargetHandle = Get-EffectiveTargetHandle -TopWindowHandle $targetHandle -TargetThreadId $targetThreadId -TargetProcessId $targetProcess.Id
$binding = Resolve-KeyBinding -KeyText $Key

Write-Host "[RiftKey] Target process: $($targetProcess.ProcessName) [$($targetProcess.Id)]"
Write-Host ("[RiftKey] Target window : 0x{0:X} '{1}'" -f $targetProcess.MainWindowHandle, $targetProcess.MainWindowTitle)
Write-Host "[RiftKey] Target thread : $targetThreadId"
Write-Host ("[RiftKey] Input target  : 0x{0:X}" -f $effectiveTargetHandle.ToInt64())
Write-Host "[RiftKey] Key           : $Key"
Write-Host "[RiftKey] Hold ms       : $HoldMilliseconds"

if (-not $SkipBackgroundFocus) {
    $backgroundProcess = Get-MainWindowProcess -ProcessName $BackgroundProcessName
    Write-Host "[RiftKey] Background focus target: $($backgroundProcess.ProcessName) [$($backgroundProcess.Id)]"
    Focus-Window -Process $backgroundProcess
    $foregroundHandle = [RiftKeyNative]::GetForegroundWindow()
    Write-Host ("[RiftKey] Foreground window after redirect: 0x{0:X}" -f $foregroundHandle.ToInt64())
}
else {
    Write-Host "[RiftKey] Strategy      : SendInput foreground delivery"
    Focus-Window -Process $targetProcess
    $foregroundHandle = [RiftKeyNative]::GetForegroundWindow()
    Write-Host ("[RiftKey] Foreground    : 0x{0:X}" -f $foregroundHandle.ToInt64())
    Send-BindingInput -Binding $binding
    Start-Sleep -Milliseconds $PostKeySettleMilliseconds
    Write-Host "[RiftKey] SUCCESS"
    exit 0
}

$modifiersDown = New-Object System.Collections.Generic.List[int]
if (($binding.ShiftState -band 1) -ne 0) {
    Post-KeyDown -WindowHandle $effectiveTargetHandle -VirtualKey $VK_SHIFT
    $modifiersDown.Add($VK_SHIFT)
    Start-Sleep -Milliseconds $InterKeyDelayMilliseconds
}
if (($binding.ShiftState -band 2) -ne 0) {
    Post-KeyDown -WindowHandle $effectiveTargetHandle -VirtualKey $VK_CONTROL
    $modifiersDown.Add($VK_CONTROL)
    Start-Sleep -Milliseconds $InterKeyDelayMilliseconds
}
if (($binding.ShiftState -band 4) -ne 0) {
    Post-KeyDown -WindowHandle $effectiveTargetHandle -VirtualKey $VK_MENU
    $modifiersDown.Add($VK_MENU)
    Start-Sleep -Milliseconds $InterKeyDelayMilliseconds
}

Post-KeyDown -WindowHandle $effectiveTargetHandle -VirtualKey $binding.VirtualKey
Start-Sleep -Milliseconds $HoldMilliseconds
Post-KeyUp -WindowHandle $effectiveTargetHandle -VirtualKey $binding.VirtualKey

for ($i = $modifiersDown.Count - 1; $i -ge 0; $i--) {
    Start-Sleep -Milliseconds $InterKeyDelayMilliseconds
    Post-KeyUp -WindowHandle $effectiveTargetHandle -VirtualKey $modifiersDown[$i]
}

Start-Sleep -Milliseconds $PostKeySettleMilliseconds
Write-Host "[RiftKey] SUCCESS"
exit 0
