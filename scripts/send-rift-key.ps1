# Send a key to RIFT using SendInput (real keyboard input, requires foreground focus).
# Supports VirtualKey and ScanCode modes. Use ScanCode when a game ignores VK-based SendInput.
# Movement still requires RIFT to be in gameplay input mode, not chat/text-entry mode.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Key,
    [int]$HoldMilliseconds = 250,
    [string]$ProcessName = "rift_x64",
    [int]$TargetProcessId,
    [string]$TargetWindowHandle,
    [int]$FocusDelayMilliseconds = 200,
    [switch]$Alt,
    [switch]$Shift,
    [switch]$Ctrl,
    [switch]$NoRefocus,
    [ValidateSet("VirtualKey", "ScanCode")]
    [string]$InputMode = "VirtualKey"
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
    public static extern uint MapVirtualKey(uint uCode, uint uMapType);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint GetCurrentThreadId();

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool AttachThreadInput(uint idAttach, uint idAttachTo, bool fAttach);
}
"@

$SW_RESTORE            = 9
$INPUT_KEYBOARD        = 1
$KEYEVENTF_EXTENDEDKEY = 0x0001
$KEYEVENTF_KEYUP       = 0x0002
$KEYEVENTF_SCANCODE    = 0x0008
$MAPVK_VK_TO_VSC       = 0

$extendedVirtualKeys = @(
    0x21, # PAGE UP
    0x22, # PAGE DOWN
    0x23, # END
    0x24, # HOME
    0x25, # LEFT
    0x26, # UP
    0x27, # RIGHT
    0x28, # DOWN
    0x2D, # INSERT
    0x2E  # DELETE
)

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
    param([int]$VirtualKey, [switch]$KeyUp, [string]$Mode = "VirtualKey")

    $inp = New-Object RiftSendKeyNative+INPUT
    $inp.type = $INPUT_KEYBOARD
    $inp.U.ki.time = 0
    $inp.U.ki.dwExtraInfo = [IntPtr]::Zero

    if ($Mode -eq "ScanCode") {
        $scanCode = [RiftSendKeyNative]::MapVirtualKey([uint32]$VirtualKey, [uint32]$MAPVK_VK_TO_VSC)
        if ($scanCode -eq 0) {
            throw "No scan-code mapping was found for virtual key $VirtualKey."
        }

        $flags = $KEYEVENTF_SCANCODE
        if ($extendedVirtualKeys -contains $VirtualKey) {
            $flags = $flags -bor $KEYEVENTF_EXTENDEDKEY
        }
        if ($KeyUp) {
            $flags = $flags -bor $KEYEVENTF_KEYUP
        }

        $inp.U.ki.wVk = 0
        $inp.U.ki.wScan = [uint16]$scanCode
        $inp.U.ki.dwFlags = [uint32]$flags
        return $inp
    }

    $inp.U.ki.wVk = [uint16]$VirtualKey
    $inp.U.ki.wScan = 0
    $inp.U.ki.dwFlags = if ($KeyUp) { $KEYEVENTF_KEYUP } else { 0 }
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

function Get-NormalizedProcessName {
    param([string]$Name)

    if ([string]::IsNullOrWhiteSpace($Name)) {
        return $Name
    }

    $trimmed = $Name.Trim()
    if ($trimmed.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
        return $trimmed.Substring(0, $trimmed.Length - 4)
    }

    return $trimmed
}

function ConvertTo-WindowHandle {
    param([string]$HandleText)

    if ([string]::IsNullOrWhiteSpace($HandleText)) {
        return [IntPtr]::Zero
    }

    if ($HandleText.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $raw = [UInt64]::Parse($HandleText.Substring(2), [System.Globalization.NumberStyles]::AllowHexSpecifier, [System.Globalization.CultureInfo]::InvariantCulture)
        return [IntPtr]([Int64]$raw)
    }

    return [IntPtr]([Int64]::Parse($HandleText, [System.Globalization.CultureInfo]::InvariantCulture))
}

function Resolve-TargetProcess {
    param(
        [string]$Name,
        [int]$ProcessId,
        [string]$WindowHandle
    )

    $normalizedName = Get-NormalizedProcessName -Name $Name
    $handle = ConvertTo-WindowHandle -HandleText $WindowHandle

    if ($handle -ne [IntPtr]::Zero) {
        if (-not [RiftSendKeyNative]::IsWindow($handle)) {
            throw "Target window handle '$WindowHandle' is not a valid window."
        }

        $ownerProcessId = [uint32]0
        [void][RiftSendKeyNative]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
        if ($ownerProcessId -eq 0) {
            throw "Target window handle '$WindowHandle' did not resolve to a process id."
        }

        if ($ProcessId -gt 0 -and [int]$ownerProcessId -ne $ProcessId) {
            throw "Target window handle '$WindowHandle' belongs to PID $ownerProcessId, not PID $ProcessId."
        }

        $process = Get-Process -Id ([int]$ownerProcessId) -ErrorAction Stop
        if (-not [string]::IsNullOrWhiteSpace($normalizedName) -and
            -not [string]::Equals($process.ProcessName, $normalizedName, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Target window handle '$WindowHandle' belongs to '$($process.ProcessName)' [PID $ownerProcessId], not '$Name'."
        }

        return [pscustomobject]@{
            Process = $process
            WindowHandle = $handle
        }
    }

    if ($ProcessId -gt 0) {
        $process = Get-Process -Id $ProcessId -ErrorAction Stop
        if (-not [string]::IsNullOrWhiteSpace($normalizedName) -and
            -not [string]::Equals($process.ProcessName, $normalizedName, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Target PID $ProcessId is '$($process.ProcessName)', not '$Name'."
        }

        if ($process.MainWindowHandle -eq 0 -or -not [RiftSendKeyNative]::IsWindow($process.MainWindowHandle)) {
            throw "Target PID $ProcessId does not expose a valid main window handle."
        }

        return [pscustomobject]@{
            Process = $process
            WindowHandle = [IntPtr]$process.MainWindowHandle
        }
    }

    $matches = @(Get-Process -Name $normalizedName -ErrorAction Stop | Where-Object { $_.MainWindowHandle -ne 0 })
    if ($matches.Count -gt 1) {
        $ids = ($matches | Sort-Object Id | ForEach-Object { $_.Id }) -join ', '
        throw "Process name '$normalizedName' matched multiple windowed processes ($ids). Use -TargetProcessId or -TargetWindowHandle to avoid cross-window input."
    }

    $process = $matches | Select-Object -First 1
    if (-not $process) {
        throw "No process named '$normalizedName' with a main window found."
    }

    return [pscustomobject]@{
        Process = $process
        WindowHandle = [IntPtr]$process.MainWindowHandle
    }
}

# --- Main ---

$target = Resolve-TargetProcess -Name $ProcessName -ProcessId $TargetProcessId -WindowHandle $TargetWindowHandle
$riftProcess = $target.Process
$hwnd = [IntPtr]$target.WindowHandle

# Save current foreground window to restore later
$previousForeground = [RiftSendKeyNative]::GetForegroundWindow()

# Focus RIFT window
[void][RiftSendKeyNative]::ShowWindow($hwnd, $SW_RESTORE)

# Use AttachThreadInput trick for more reliable SetForegroundWindow
$targetPid = [uint32]0
$targetTid = [RiftSendKeyNative]::GetWindowThreadProcessId($hwnd, [ref]$targetPid)
$currentTid = [RiftSendKeyNative]::GetCurrentThreadId()

if ($targetTid -ne $currentTid) {
    [void][RiftSendKeyNative]::AttachThreadInput($currentTid, $targetTid, $true)
}

[void][RiftSendKeyNative]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds $FocusDelayMilliseconds

# Verify foreground
$fg = [RiftSendKeyNative]::GetForegroundWindow()
if ($fg -ne $hwnd) {
    Write-Warning "SetForegroundWindow may not have taken - foreground is 0x$($fg.ToString('X')), expected 0x$($hwnd.ToString('X'))."
}

# Resolve key
$vk = Resolve-VirtualKey -KeyText $Key

Write-Host "[SendKey] Process:  $($riftProcess.ProcessName) [$($riftProcess.Id)]"
Write-Host "[SendKey] Window:   0x$($hwnd.ToString('X'))"
Write-Host "[SendKey] Key:      $Key (VK=0x$($vk.ToString('X2')))"
Write-Host "[SendKey] Hold:     ${HoldMilliseconds}ms"
Write-Host "[SendKey] InputMode: $InputMode"
Write-Host "[SendKey] Mods:     Alt=$Alt Shift=$Shift Ctrl=$Ctrl"

# Press modifiers
$modsDown = @()
if ($Alt)   { Invoke-SendInput @((New-KeyboardInput -VirtualKey $VK_MENU -Mode $InputMode));    $modsDown += $VK_MENU;    Start-Sleep -Milliseconds 20 }
if ($Shift) { Invoke-SendInput @((New-KeyboardInput -VirtualKey $VK_SHIFT -Mode $InputMode));   $modsDown += $VK_SHIFT;   Start-Sleep -Milliseconds 20 }
if ($Ctrl)  { Invoke-SendInput @((New-KeyboardInput -VirtualKey $VK_CONTROL -Mode $InputMode)); $modsDown += $VK_CONTROL; Start-Sleep -Milliseconds 20 }

# Press main key
Invoke-SendInput @((New-KeyboardInput -VirtualKey $vk -Mode $InputMode))
Start-Sleep -Milliseconds $HoldMilliseconds
Invoke-SendInput @((New-KeyboardInput -VirtualKey $vk -KeyUp -Mode $InputMode))

# Release modifiers in reverse
for ($i = $modsDown.Length - 1; $i -ge 0; $i--) {
    Start-Sleep -Milliseconds 20
    Invoke-SendInput @((New-KeyboardInput -VirtualKey $modsDown[$i] -KeyUp -Mode $InputMode))
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
