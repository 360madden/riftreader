[CmdletBinding()]
param(
    [string]$Command = "/reloadui",
    [string]$TargetProcessName = "rift_x64",
    [int]$TargetProcessId,
    [string]$TargetWindowHandle,
    [string]$TargetTitleContains,
    [string]$VerifyFilePath = "C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\Saved\rift315.1@gmail.com\Deepwood\Atank\SavedVariables\ReaderBridgeExport.lua",
    [string]$BackgroundProcessName = "",
    [int]$AttemptTimeoutSeconds = 10,
    [int]$InterKeyDelayMilliseconds = 20,
    [switch]$SkipBackgroundFocus,
    [switch]$RequireTargetForeground
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class RiftPostMessageNative
{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern int GetWindowTextLength(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

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
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

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
}
"@

$WM_KEYDOWN = 0x0100
$WM_KEYUP = 0x0101

$VK_RETURN = 0x0D
$VK_SHIFT = 0x10
$VK_CONTROL = 0x11
$VK_MENU = 0x12

$MAPVK_VK_TO_VSC = 0
$SW_RESTORE = 9

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

function Get-WindowTitle {
    param([IntPtr]$Handle)

    $length = [RiftPostMessageNative]::GetWindowTextLength($Handle)
    if ($length -le 0) {
        return ''
    }

    $builder = New-Object System.Text.StringBuilder ($length + 1)
    [void][RiftPostMessageNative]::GetWindowText($Handle, $builder, $builder.Capacity)
    return $builder.ToString()
}

function Get-MainWindowProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProcessName,
        [switch]$AllowFirstMatch
    )

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

    if ($candidates.Count -gt 1 -and -not $AllowFirstMatch) {
        $ids = ($candidates | Sort-Object Id | ForEach-Object { $_.Id }) -join ', '
        throw "Process name '$ProcessName' matched multiple windowed processes ($ids). Use -TargetProcessId or -TargetWindowHandle to avoid cross-window input."
    }

    $candidate = $candidates | Sort-Object StartTime | Select-Object -First 1

    if (-not $candidate) {
        throw "No process named '$ProcessName' with a main window was found."
    }

    return $candidate
}

function Resolve-TargetWindow {
    param(
        [string]$ProcessName,
        [int]$ProcessId,
        [string]$WindowHandle,
        [string]$TitleContains
    )

    $handle = ConvertTo-WindowHandle -HandleText $WindowHandle
    $process = $null

    if ($handle -ne [IntPtr]::Zero) {
        if (-not [RiftPostMessageNative]::IsWindow($handle)) {
            throw "Target window handle '$WindowHandle' is not a valid window."
        }

        $ownerProcessId = 0
        [void][RiftPostMessageNative]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
        if ($ProcessId -gt 0 -and $ownerProcessId -ne $ProcessId) {
            throw "Target window handle '$WindowHandle' belongs to PID $ownerProcessId, not requested PID $ProcessId."
        }

        $process = Get-Process -Id $ownerProcessId -ErrorAction Stop
        if (-not [string]::IsNullOrWhiteSpace($ProcessName)) {
            $expectedName = [System.IO.Path]::GetFileNameWithoutExtension($ProcessName)
            if (-not [string]::Equals($process.ProcessName, $expectedName, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Target window handle '$WindowHandle' belongs to process '$($process.ProcessName)' [$($process.Id)], not '$expectedName'."
            }
        }
    }
    elseif ($ProcessId -gt 0) {
        $process = Get-Process -Id $ProcessId -ErrorAction Stop
        if (-not [string]::IsNullOrWhiteSpace($ProcessName)) {
            $expectedName = [System.IO.Path]::GetFileNameWithoutExtension($ProcessName)
            if (-not [string]::Equals($process.ProcessName, $expectedName, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Requested PID $ProcessId is '$($process.ProcessName)', not '$expectedName'."
            }
        }

        $handle = [IntPtr]$process.MainWindowHandle
    }
    else {
        $process = Get-MainWindowProcess -ProcessName $ProcessName
        $handle = [IntPtr]$process.MainWindowHandle
    }

    if ($handle -eq [IntPtr]::Zero) {
        throw "Target process '$($process.ProcessName)' [$($process.Id)] does not expose a main window handle."
    }

    if (-not [RiftPostMessageNative]::IsWindow($handle)) {
        throw ("Resolved target window 0x{0:X} is not valid." -f $handle.ToInt64())
    }

    $resolvedOwnerProcessId = 0
    [void][RiftPostMessageNative]::GetWindowThreadProcessId($handle, [ref]$resolvedOwnerProcessId)
    if ($resolvedOwnerProcessId -ne $process.Id) {
        throw ("Resolved target window 0x{0:X} belongs to PID {1}, not resolved process PID {2}." -f $handle.ToInt64(), $resolvedOwnerProcessId, $process.Id)
    }

    $title = Get-WindowTitle -Handle $handle
    if (-not [string]::IsNullOrWhiteSpace($TitleContains) -and
        $title.IndexOf($TitleContains, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw "Resolved target window title '$title' does not contain '$TitleContains'."
    }

    return [pscustomobject]@{
        Process = $process
        WindowHandle = $handle
        WindowTitle = $title
    }
}

function Focus-Window {
    param(
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$Process,
        [IntPtr]$WindowHandle = [IntPtr]::Zero
    )

    $targetHandle = if ($WindowHandle -ne [IntPtr]::Zero) { $WindowHandle } else { $Process.MainWindowHandle }
    [void][RiftPostMessageNative]::ShowWindow($targetHandle, $SW_RESTORE)
    [void][RiftPostMessageNative]::SetForegroundWindow($targetHandle)
    Start-Sleep -Milliseconds 250
}

function Test-TargetProcessIsForeground {
    param(
        [Parameter(Mandatory = $true)]
        [int]$TargetProcessId
    )

    $foregroundHandle = [RiftPostMessageNative]::GetForegroundWindow()
    if ($foregroundHandle -eq [IntPtr]::Zero) {
        return $false
    }

    $foregroundProcessId = 0
    [void][RiftPostMessageNative]::GetWindowThreadProcessId($foregroundHandle, [ref]$foregroundProcessId)
    return $foregroundProcessId -eq $TargetProcessId
}

function Get-FileTimestampUtc {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Verification file was not found: $Path"
    }

    return (Get-Item -LiteralPath $Path).LastWriteTimeUtc
}

function Post-Key {
    param(
        [Parameter(Mandatory = $true)]
        [IntPtr]$WindowHandle,

        [Parameter(Mandatory = $true)]
        [int]$VirtualKey
    )

    $scanCode = [RiftPostMessageNative]::MapVirtualKey([uint32]$VirtualKey, $MAPVK_VK_TO_VSC)
    $keyDownLParam = [IntPtr](1 -bor ($scanCode -shl 16))
    $keyUpLParam = [IntPtr]((1 -bor ($scanCode -shl 16)) -bor 0xC0000000)

    [void][RiftPostMessageNative]::PostMessage($WindowHandle, $WM_KEYDOWN, [IntPtr]$VirtualKey, $keyDownLParam)
    Start-Sleep -Milliseconds $InterKeyDelayMilliseconds
    [void][RiftPostMessageNative]::PostMessage($WindowHandle, $WM_KEYUP, [IntPtr]$VirtualKey, $keyUpLParam)
    Start-Sleep -Milliseconds $InterKeyDelayMilliseconds
}

function Post-KeyDown {
    param(
        [Parameter(Mandatory = $true)]
        [IntPtr]$WindowHandle,

        [Parameter(Mandatory = $true)]
        [int]$VirtualKey
    )

    $scanCode = [RiftPostMessageNative]::MapVirtualKey([uint32]$VirtualKey, $MAPVK_VK_TO_VSC)
    $keyDownLParam = [IntPtr](1 -bor ($scanCode -shl 16))
    [void][RiftPostMessageNative]::PostMessage($WindowHandle, $WM_KEYDOWN, [IntPtr]$VirtualKey, $keyDownLParam)
    Start-Sleep -Milliseconds $InterKeyDelayMilliseconds
}

function Post-KeyUp {
    param(
        [Parameter(Mandatory = $true)]
        [IntPtr]$WindowHandle,

        [Parameter(Mandatory = $true)]
        [int]$VirtualKey
    )

    $scanCode = [RiftPostMessageNative]::MapVirtualKey([uint32]$VirtualKey, $MAPVK_VK_TO_VSC)
    $keyUpLParam = [IntPtr]((1 -bor ($scanCode -shl 16)) -bor 0xC0000000)
    [void][RiftPostMessageNative]::PostMessage($WindowHandle, $WM_KEYUP, [IntPtr]$VirtualKey, $keyUpLParam)
    Start-Sleep -Milliseconds $InterKeyDelayMilliseconds
}

function Get-EffectiveTargetHandle {
    param(
        [Parameter(Mandatory = $true)]
        [IntPtr]$TopWindowHandle,

        [Parameter(Mandatory = $true)]
        [uint32]$TargetThreadId,

        [Parameter(Mandatory = $true)]
        [int]$TargetProcessId
    )

    $guiThreadInfo = New-Object RiftPostMessageNative+GUITHREADINFO
    $guiThreadInfo.cbSize = [Runtime.InteropServices.Marshal]::SizeOf($guiThreadInfo)

    if (-not [RiftPostMessageNative]::GetGUIThreadInfo($TargetThreadId, [ref]$guiThreadInfo)) {
        return $TopWindowHandle
    }

    if ($guiThreadInfo.hwndFocus -eq [IntPtr]::Zero) {
        return $TopWindowHandle
    }

    $focusOwnerProcessId = 0
    [void][RiftPostMessageNative]::GetWindowThreadProcessId($guiThreadInfo.hwndFocus, [ref]$focusOwnerProcessId)
    if ($focusOwnerProcessId -ne $TargetProcessId) {
        return $TopWindowHandle
    }

    return $guiThreadInfo.hwndFocus
}

function Post-CharacterAsKey {
    param(
        [Parameter(Mandatory = $true)]
        [IntPtr]$WindowHandle,

        [Parameter(Mandatory = $true)]
        [char]$Character
    )

    $vkScan = [RiftPostMessageNative]::VkKeyScan($Character)
    if ($vkScan -eq -1) {
        throw "No virtual-key mapping was found for character '$Character'."
    }

    $virtualKey = $vkScan -band 0xFF
    $shiftState = ($vkScan -shr 8) -band 0xFF

    $modifiersDown = New-Object System.Collections.Generic.List[int]

    if (($shiftState -band 1) -ne 0) {
        Post-KeyDown -WindowHandle $WindowHandle -VirtualKey $VK_SHIFT
        $modifiersDown.Add($VK_SHIFT)
    }

    if (($shiftState -band 2) -ne 0) {
        Post-KeyDown -WindowHandle $WindowHandle -VirtualKey $VK_CONTROL
        $modifiersDown.Add($VK_CONTROL)
    }

    if (($shiftState -band 4) -ne 0) {
        Post-KeyDown -WindowHandle $WindowHandle -VirtualKey $VK_MENU
        $modifiersDown.Add($VK_MENU)
    }

    Post-Key -WindowHandle $WindowHandle -VirtualKey $virtualKey

    for ($i = $modifiersDown.Count - 1; $i -ge 0; $i--) {
        Post-KeyUp -WindowHandle $WindowHandle -VirtualKey $modifiersDown[$i]
    }
}

function Send-CommandStrategyEnterThenType {
    param(
        [Parameter(Mandatory = $true)]
        [IntPtr]$WindowHandle,

        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    Post-Key -WindowHandle $WindowHandle -VirtualKey $VK_RETURN
    foreach ($character in $Text.ToCharArray()) {
        Post-CharacterAsKey -WindowHandle $WindowHandle -Character $character
    }
    Post-Key -WindowHandle $WindowHandle -VirtualKey $VK_RETURN
}

function Send-CommandStrategySlashThenRest {
    param(
        [Parameter(Mandatory = $true)]
        [IntPtr]$WindowHandle,

        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    foreach ($character in $Text.ToCharArray()) {
        Post-CharacterAsKey -WindowHandle $WindowHandle -Character $character
    }
    Post-Key -WindowHandle $WindowHandle -VirtualKey $VK_RETURN
}

function Wait-ForTimestampAdvance {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [datetime]$BaselineUtc,

        [Parameter(Mandatory = $true)]
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).ToUniversalTime().AddSeconds($TimeoutSeconds)
    do {
        if (Test-Path -LiteralPath $Path) {
            $currentUtc = Get-FileTimestampUtc -Path $Path
            if ($currentUtc -gt $BaselineUtc) {
                return $currentUtc
            }
        }

        Start-Sleep -Milliseconds 250
    }
    while ((Get-Date).ToUniversalTime() -lt $deadline)

    return $null
}

$target = Resolve-TargetWindow -ProcessName $TargetProcessName -ProcessId $TargetProcessId -WindowHandle $TargetWindowHandle -TitleContains $TargetTitleContains
$targetProcess = $target.Process
$targetHandle = [IntPtr]$target.WindowHandle

$targetOwnerProcessId = 0
$targetThreadId = [RiftPostMessageNative]::GetWindowThreadProcessId($targetHandle, [ref]$targetOwnerProcessId)
if ($targetOwnerProcessId -ne $targetProcess.Id) {
    throw ("Target window handle 0x{0:X} does not belong to process {1}." -f $targetHandle.ToInt64(), $targetProcess.Id)
}

Write-Host "[RiftPost] Target process: $($targetProcess.ProcessName) [$($targetProcess.Id)]"
Write-Host ("[RiftPost] Target window : 0x{0:X} '{1}'" -f $targetHandle.ToInt64(), $target.WindowTitle)
Write-Host "[RiftPost] Target thread : $targetThreadId"

$effectiveTargetHandle = Get-EffectiveTargetHandle -TopWindowHandle $targetHandle -TargetThreadId $targetThreadId -TargetProcessId $targetProcess.Id
Write-Host ("[RiftPost] Input target  : 0x{0:X}" -f $effectiveTargetHandle.ToInt64())

if (-not $SkipBackgroundFocus -and -not [string]::IsNullOrWhiteSpace($BackgroundProcessName)) {
    $backgroundProcess = $null
    try {
        $backgroundProcess = Get-MainWindowProcess -ProcessName $BackgroundProcessName
    }
    catch {
        Write-Warning ("Background focus target '{0}' was not available; continuing without background focus. {1}" -f $BackgroundProcessName, $_.Exception.Message)
    }

    if ($backgroundProcess) {
        Write-Host "[RiftPost] Background focus target: $($backgroundProcess.ProcessName) [$($backgroundProcess.Id)]"
        Focus-Window -Process $backgroundProcess

        $foregroundHandle = [RiftPostMessageNative]::GetForegroundWindow()
        Write-Host ("[RiftPost] Foreground window after redirect: 0x{0:X}" -f $foregroundHandle.ToInt64())

        if ($foregroundHandle -eq $targetHandle) {
            throw "Foreground window is still the Rift window; this test would not prove non-focused posting."
        }
    }
}

if ($RequireTargetForeground) {
    if (-not (Test-TargetProcessIsForeground -TargetProcessId $targetProcess.Id)) {
        throw "Rift is not the foreground window. Aborting live command posting to preserve focus safety."
    }
}

$baselineUtc = Get-FileTimestampUtc -Path $VerifyFilePath
Write-Host "[RiftPost] Verify file  : $VerifyFilePath"
Write-Host "[RiftPost] Baseline UTC : $($baselineUtc.ToString('yyyy-MM-ddTHH:mm:ss.fffffffZ'))"
Write-Host "[RiftPost] Command      : $Command"

$strategies = @(
    @{ Name = "enter-then-type"; Action = { param($hwnd, $text) Send-CommandStrategyEnterThenType -WindowHandle $hwnd -Text $text } },
    @{ Name = "type-then-enter"; Action = { param($hwnd, $text) Send-CommandStrategySlashThenRest -WindowHandle $hwnd -Text $text } }
)

foreach ($strategy in $strategies) {
    Write-Host "[RiftPost] Attempting strategy: $($strategy.Name)"
    & $strategy.Action $effectiveTargetHandle $Command

    $updatedUtc = Wait-ForTimestampAdvance -Path $VerifyFilePath -BaselineUtc $baselineUtc -TimeoutSeconds $AttemptTimeoutSeconds
    if ($updatedUtc) {
        Write-Host "[RiftPost] SUCCESS"
        Write-Host "[RiftPost] Strategy used: $($strategy.Name)"
        Write-Host "[RiftPost] Updated UTC  : $($updatedUtc.ToString('yyyy-MM-ddTHH:mm:ss.fffffffZ'))"
        exit 0
    }
}

Write-Error "No verification file update was observed after posting '$Command' to the Rift window without focusing it."
exit 1
