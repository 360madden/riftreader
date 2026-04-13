# PREFERRED INPUT PRIMITIVE: Send a key to RIFT using SendInput (real keyboard input, requires foreground focus).
# Prefer this script when the live client must actually react to gameplay keys.
# Unlike post-rift-key.ps1 (PostMessage), this actually works for gameplay keys.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Key,
    [int]$HoldMilliseconds = 250,
    [string]$ProcessName = "rift_x64",
    [int]$FocusDelayMilliseconds = 200,
    [switch]$Alt,
    [switch]$Shift,
    [switch]$Ctrl,
    [switch]$NoRefocus
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RiftSendKeyNative
{
    [StructLayout(LayoutKind.Sequential)]
    public struct INPUT { public uint type; public InputUnion U; }

    [StructLayout(LayoutKind.Explicit)]
    public struct InputUnion
    {
        [FieldOffset(0)] public MOUSEINPUT mi;
        [FieldOffset(0)] public KEYBDINPUT ki;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct MOUSEINPUT
    {
        public int dx; public int dy; public uint mouseData;
        public uint dwFlags; public uint time; public IntPtr dwExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct KEYBDINPUT
    {
        public ushort wVk; public ushort wScan; public uint dwFlags;
        public uint time; public IntPtr dwExtraInfo;
    }

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern short VkKeyScan(char ch);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint GetCurrentThreadId();

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool AttachThreadInput(uint idAttach, uint idAttachTo, bool fAttach);
}
"@

$SW_RESTORE      = 9
$INPUT_KEYBOARD  = 1
$KEYEVENTF_KEYUP = 0x0002

$VK_SHIFT   = 0x10
$VK_CONTROL = 0x11
$VK_MENU    = 0x12  # Alt

$namedKeys = @{
    "SPACE"     = 0x20
    "LEFT"      = 0x25
    "UP"        = 0x26
    "RIGHT"     = 0x27
    "DOWN"      = 0x28
    "ENTER"     = 0x0D
    "RETURN"    = 0x0D
    "ESC"       = 0x1B
    "ESCAPE"    = 0x1B
    "BACKSPACE" = 0x08
    "TAB"       = 0x09
}

function New-KeyboardInput {
    param([int]$VirtualKey, [switch]$KeyUp)
    $inp = New-Object RiftSendKeyNative+INPUT
    $inp.type = $INPUT_KEYBOARD
    $inp.U.ki.wVk = [uint16]$VirtualKey
    $inp.U.ki.wScan = 0
    $inp.U.ki.dwFlags = if ($KeyUp) { $KEYEVENTF_KEYUP } else { 0 }
    $inp.U.ki.time = 0
    $inp.U.ki.dwExtraInfo = [IntPtr]::Zero
    return $inp
}

function Invoke-SendInput {
    param([RiftSendKeyNative+INPUT[]]$Inputs)
    $size = [Runtime.InteropServices.Marshal]::SizeOf([type][RiftSendKeyNative+INPUT])
    $sent = [RiftSendKeyNative]::SendInput([uint32]$Inputs.Length, $Inputs, $size)
    if ($sent -ne $Inputs.Length) {
        throw "SendInput sent $sent of $($Inputs.Length) inputs."
    }
}

function Resolve-VirtualKey {
    param([string]$KeyText)
    $upper = $KeyText.Trim().ToUpperInvariant()
    if ($namedKeys.ContainsKey($upper)) {
        return $namedKeys[$upper]
    }
    if ($KeyText.Length -eq 1) {
        $vkScan = [RiftSendKeyNative]::VkKeyScan($KeyText[0])
        if ($vkScan -eq -1) { throw "No VK mapping for '$KeyText'." }
        return $vkScan -band 0xFF
    }
    throw "Unsupported key '$KeyText'. Use a single character or named key (Space/Left/Right/Up/Down/Enter/Esc)."
}

# --- Main ---

# Find RIFT window
$riftProcess = Get-Process -Name $ProcessName -ErrorAction Stop |
    Where-Object { $_.MainWindowHandle -ne 0 } |
    Select-Object -First 1
if (-not $riftProcess) {
    throw "No process named '$ProcessName' with a main window found."
}

$hwnd = $riftProcess.MainWindowHandle

# Save current foreground window to restore later
$previousForeground = [RiftSendKeyNative]::GetForegroundWindow()

# Focus RIFT window
[void][RiftSendKeyNative]::ShowWindow($hwnd, $SW_RESTORE)

# Use AttachThreadInput to bypass Windows foreground-lock restriction
# Must attach to BOTH the current foreground window's thread AND the target thread
$fgHwnd = [RiftSendKeyNative]::GetForegroundWindow()
$targetPid = [uint32]0
$dummy = [uint32]0
$targetTid = [RiftSendKeyNative]::GetWindowThreadProcessId($hwnd, [ref]$targetPid)
$currentTid = [RiftSendKeyNative]::GetCurrentThreadId()
$fgTid = [RiftSendKeyNative]::GetWindowThreadProcessId($fgHwnd, [ref]$dummy)

[void][RiftSendKeyNative]::AttachThreadInput($currentTid, $fgTid, $true)
[void][RiftSendKeyNative]::AttachThreadInput($currentTid, $targetTid, $true)
[void][RiftSendKeyNative]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds $FocusDelayMilliseconds
[void][RiftSendKeyNative]::AttachThreadInput($currentTid, $fgTid, $false)
[void][RiftSendKeyNative]::AttachThreadInput($currentTid, $targetTid, $false)

# Verify foreground
$fg = [RiftSendKeyNative]::GetForegroundWindow()
if ($fg -ne $hwnd) {
    Write-Warning "SetForegroundWindow may not have taken - foreground is 0x$($fg.ToString('X')), expected 0x$($hwnd.ToString('X')). Proceeding anyway."
}

# Resolve key
$vk = Resolve-VirtualKey -KeyText $Key

Write-Host "[SendKey] Process:  $($riftProcess.ProcessName) [$($riftProcess.Id)]"
Write-Host "[SendKey] Window:   0x$($hwnd.ToString('X'))"
Write-Host "[SendKey] Key:      $Key (VK=0x$($vk.ToString('X2')))"
Write-Host "[SendKey] Hold:     ${HoldMilliseconds}ms"
Write-Host "[SendKey] Mods:     Alt=$Alt Shift=$Shift Ctrl=$Ctrl"

# Press modifiers
$modsDown = @()
if ($Alt)   { Invoke-SendInput @((New-KeyboardInput -VirtualKey $VK_MENU));    $modsDown += $VK_MENU;    Start-Sleep -Milliseconds 20 }
if ($Shift) { Invoke-SendInput @((New-KeyboardInput -VirtualKey $VK_SHIFT));   $modsDown += $VK_SHIFT;   Start-Sleep -Milliseconds 20 }
if ($Ctrl)  { Invoke-SendInput @((New-KeyboardInput -VirtualKey $VK_CONTROL)); $modsDown += $VK_CONTROL; Start-Sleep -Milliseconds 20 }

# Press main key
Invoke-SendInput @((New-KeyboardInput -VirtualKey $vk))
Start-Sleep -Milliseconds $HoldMilliseconds
Invoke-SendInput @((New-KeyboardInput -VirtualKey $vk -KeyUp))

# Release modifiers in reverse
for ($i = $modsDown.Length - 1; $i -ge 0; $i--) {
    Start-Sleep -Milliseconds 20
    Invoke-SendInput @((New-KeyboardInput -VirtualKey $modsDown[$i] -KeyUp))
}

# Detach thread input
if ($targetTid -ne $currentTid) {
    [void][RiftSendKeyNative]::AttachThreadInput($currentTid, $targetTid, $false)
}

# Restore previous foreground window
if (-not $NoRefocus -and $previousForeground -ne [IntPtr]::Zero -and $previousForeground -ne $hwnd) {
    Start-Sleep -Milliseconds 100
    [void][RiftSendKeyNative]::SetForegroundWindow($previousForeground)
}

Write-Host "[SendKey] SUCCESS"
exit 0
