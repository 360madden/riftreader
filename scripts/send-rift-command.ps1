[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$ChatCommand,

    [string]$ProcessName = "rift_x64",
    [int]$TargetProcessId,
    [string]$TargetWindowHandle,
    [int]$HoldMilliseconds = 80,
    [int]$FocusDelayMilliseconds = 200,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Display help if requested
if ($Help) {
    Write-Host "Usage: send-rift-command.ps1 -ChatCommand <command> [-ProcessName <name>] [-TargetProcessId <pid>] [-TargetWindowHandle <hwnd>] [-HoldMilliseconds <ms>] [-FocusDelayMilliseconds <ms>] [-Help]"
    Write-Host ""
    Write-Host "Parameters:"
    Write-Host "  -ChatCommand                The chat command to send to Rift (e.g., '/reloadui', '/help')"
    Write-Host "  -ProcessName                Target process name (default: 'rift_x64')"
    Write-Host "  -TargetProcessId            Exact target process id. Use with multiple clients."
    Write-Host "  -TargetWindowHandle         Exact target window handle, decimal or hex."
    Write-Host "  -HoldMilliseconds           How long to hold each key (default: 80)"
    Write-Host "  -FocusDelayMilliseconds     Delay after focusing the window (default: 200)"
    Write-Host "  -Help                       Display this help message"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\send-rift-command.ps1 -ChatCommand '/reloadui'"
    Write-Host "  .\send-rift-command.ps1 -ChatCommand '/test' -ProcessName 'rift_x64' -TargetProcessId 12345 -TargetWindowHandle 0xABCDEF -HoldMilliseconds 100"
    exit 0
}

# Validate that ChatCommand is provided if Help is not requested
if ([string]::IsNullOrWhiteSpace($ChatCommand)) {
    Write-Error "ChatCommand parameter is required. Use -Help for usage information."
    exit 1
}

# ---------------------------------------------------------------------------
# Win32 P/Invoke — minimal set needed for keyboard input
# Struct layout and function signatures copied from tools/rift-game-mcp/helpers/window-tools.ps1
# ---------------------------------------------------------------------------
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RiftSendCommand
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
        public ushort wVk; public ushort wScan;
        public uint dwFlags; public uint time; public IntPtr dwExtraInfo;
    }

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern short VkKeyScan(char ch);

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

$SW_RESTORE      = 9
$INPUT_KEYBOARD  = 1
$KEYEVENTF_KEYUP = 0x0002

$namedKeys = @{
    "ENTER"     = 0x0D
    "RETURN"    = 0x0D
    "ESC"       = 0x1B
    "ESCAPE"    = 0x1B
    "SPACE"     = 0x20
    "BACKSPACE" = 0x08
    "TAB"       = 0x09
}

# ---------------------------------------------------------------------------
# Helpers — same logic as window-tools.ps1
# ---------------------------------------------------------------------------
function New-KeyboardInput {
    param([int]$VirtualKey, [switch]$KeyUp)
    $inp = New-Object RiftSendCommand+INPUT
    $inp.type        = $INPUT_KEYBOARD
    $inp.U.ki.wVk    = [uint16]$VirtualKey
    $inp.U.ki.wScan  = 0
    $inp.U.ki.dwFlags = if ($KeyUp) { $KEYEVENTF_KEYUP } else { 0 }
    $inp.U.ki.time   = 0
    $inp.U.ki.dwExtraInfo = [IntPtr]::Zero
    return $inp
}

function Invoke-SendInput {
    param([RiftSendCommand+INPUT[]]$Inputs)
    $size = [Runtime.InteropServices.Marshal]::SizeOf([type][RiftSendCommand+INPUT])
    $sent = [RiftSendCommand]::SendInput([uint32]$Inputs.Length, $Inputs, $size)
    if ($sent -ne $Inputs.Length) {
        throw "SendInput sent $sent of $($Inputs.Length) inputs."
    }
}

function Send-Chord {
    param([string]$Chord)

    $upper = $Chord.ToUpperInvariant()
    if ($namedKeys.ContainsKey($upper)) {
        Invoke-SendInput @((New-KeyboardInput -VirtualKey $namedKeys[$upper]))
        Start-Sleep -Milliseconds 10
        Invoke-SendInput @((New-KeyboardInput -VirtualKey $namedKeys[$upper] -KeyUp))
        return
    }

    if ($Chord.Length -eq 1) {
        $ch      = $Chord[0]
        $vkScan  = [RiftSendCommand]::VkKeyScan($ch)
        if ($vkScan -eq -1) { throw "No VK mapping for '$ch'." }
        $vk      = $vkScan -band 0xFF
        $shift   = ($vkScan -shr 8) -band 0xFF
        $needShift = ($shift -band 1) -ne 0

        if ($needShift) { Invoke-SendInput @((New-KeyboardInput -VirtualKey 0x10)) }   # SHIFT down
        Invoke-SendInput @((New-KeyboardInput -VirtualKey $vk))
        Start-Sleep -Milliseconds $HoldMilliseconds
        Invoke-SendInput @((New-KeyboardInput -VirtualKey $vk -KeyUp))
        if ($needShift) { Invoke-SendInput @((New-KeyboardInput -VirtualKey 0x10 -KeyUp)) }
        return
    }

    throw "Unsupported chord '$Chord'. Use a single character or a named key."
}

function Send-ChatCommand {
    param([string]$Text)

    # Open chat
    Send-Chord "ENTER"
    Start-Sleep -Milliseconds 80

    # Type each character
    foreach ($ch in $Text.ToCharArray()) {
        Send-Chord ([string]$ch)
        Start-Sleep -Milliseconds 30
    }

    # Submit
    Start-Sleep -Milliseconds 50
    Send-Chord "ENTER"
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
        if (-not [RiftSendCommand]::IsWindow($handle)) {
            throw "Target window handle '$WindowHandle' is not a valid window."
        }

        $ownerProcessId = [uint32]0
        [void][RiftSendCommand]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
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

        if ($process.MainWindowHandle -eq 0 -or -not [RiftSendCommand]::IsWindow($process.MainWindowHandle)) {
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
        throw "Process name '$normalizedName' matched multiple windowed processes ($ids). Use -TargetProcessId or -TargetWindowHandle to avoid cross-window command input."
    }

    $process = $matches | Select-Object -First 1
    if (-not $process) {
        throw "No windowed '$normalizedName' process found. Is RIFT running?"
    }

    return [pscustomobject]@{
        Process = $process
        WindowHandle = [IntPtr]$process.MainWindowHandle
    }
}

# ---------------------------------------------------------------------------
# Main — resolve exact target when supplied, focus, send
# ---------------------------------------------------------------------------
try {
    $target = Resolve-TargetProcess -Name $ProcessName -ProcessId $TargetProcessId -WindowHandle $TargetWindowHandle
    $proc = $target.Process
    $hwnd = [IntPtr]$target.WindowHandle
    Write-Host "Found $ProcessName (PID $($proc.Id)) HWND 0x$($hwnd.ToString('X'))"

    # Restore if minimised
    [void][RiftSendCommand]::ShowWindow($hwnd, $SW_RESTORE)
    Start-Sleep -Milliseconds 80

    # Use AttachThreadInput to bypass Windows foreground-lock restriction
    $fgHwnd     = [RiftSendCommand]::GetForegroundWindow()
    $dummy      = 0
    $targetTid  = [RiftSendCommand]::GetWindowThreadProcessId($hwnd, [ref]$dummy)
    $currentTid = [RiftSendCommand]::GetCurrentThreadId()
    $fgTid      = [RiftSendCommand]::GetWindowThreadProcessId($fgHwnd, [ref]$dummy)

    [void][RiftSendCommand]::AttachThreadInput($currentTid, $fgTid, $true)
    [void][RiftSendCommand]::AttachThreadInput($currentTid, $targetTid, $true)
    [void][RiftSendCommand]::SetForegroundWindow($hwnd)
    Start-Sleep -Milliseconds $FocusDelayMilliseconds
    [void][RiftSendCommand]::AttachThreadInput($currentTid, $fgTid, $false)
    [void][RiftSendCommand]::AttachThreadInput($currentTid, $targetTid, $false)

    $fg = [RiftSendCommand]::GetForegroundWindow()
    if ($fg -ne $hwnd) {
        Write-Warning "SetForegroundWindow did not take - foreground is 0x$($fg.ToString('X')), expected 0x$($hwnd.ToString('X')). Proceeding anyway."
    }

    Write-Host "Sending: $ChatCommand"
    Send-ChatCommand -Text $ChatCommand
    Write-Host "Done."
} catch {
    Write-Error "Failed to send command '$ChatCommand': $_"
    exit 1
}
