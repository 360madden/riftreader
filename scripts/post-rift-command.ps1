[CmdletBinding()]
param(
    [string]$Command = "/reloadui",
    [string]$TargetProcessName = "rift_x64",
    [string]$VerifyFilePath = "C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\Saved\rift315.1@gmail.com\Deepwood\Atank\SavedVariables\ReaderBridgeExport.lua",
    [string]$BackgroundProcessName = "cheatengine-x86_64-SSE4-AVX2",
    [int]$AttemptTimeoutSeconds = 10,
    [int]$InterKeyDelayMilliseconds = 20,
    [switch]$SkipBackgroundFocus,
    [switch]$SkipVerify
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RiftPostMessageNative
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

function Get-MainWindowProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProcessName
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

    $candidate = $candidates | Select-Object -First 1

    if (-not $candidate) {
        throw "No process named '$ProcessName' with a main window was found."
    }

    return $candidate
}

function Focus-Window {
    param(
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$Process
    )

    [void][RiftPostMessageNative]::ShowWindow($Process.MainWindowHandle, $SW_RESTORE)
    [void][RiftPostMessageNative]::SetForegroundWindow($Process.MainWindowHandle)
    Start-Sleep -Milliseconds 250
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

$targetProcess = Get-MainWindowProcess -ProcessName $TargetProcessName
$targetHandle = [IntPtr]$targetProcess.MainWindowHandle

$targetOwnerProcessId = 0
$targetThreadId = [RiftPostMessageNative]::GetWindowThreadProcessId($targetHandle, [ref]$targetOwnerProcessId)
if ($targetOwnerProcessId -ne $targetProcess.Id) {
    throw "Main window handle 0x{0:X} does not belong to process {1}." -f $targetProcess.MainWindowHandle, $targetProcess.Id
}

Write-Host "[RiftPost] Target process: $($targetProcess.ProcessName) [$($targetProcess.Id)]"
Write-Host ("[RiftPost] Target window : 0x{0:X} '{1}'" -f $targetProcess.MainWindowHandle, $targetProcess.MainWindowTitle)
Write-Host "[RiftPost] Target thread : $targetThreadId"

$effectiveTargetHandle = Get-EffectiveTargetHandle -TopWindowHandle $targetHandle -TargetThreadId $targetThreadId -TargetProcessId $targetProcess.Id
Write-Host ("[RiftPost] Input target  : 0x{0:X}" -f $effectiveTargetHandle.ToInt64())

if (-not $SkipBackgroundFocus) {
    $backgroundProcess = Get-MainWindowProcess -ProcessName $BackgroundProcessName
    Write-Host "[RiftPost] Background focus target: $($backgroundProcess.ProcessName) [$($backgroundProcess.Id)]"
    Focus-Window -Process $backgroundProcess

    $foregroundHandle = [RiftPostMessageNative]::GetForegroundWindow()
    Write-Host ("[RiftPost] Foreground window after redirect: 0x{0:X}" -f $foregroundHandle.ToInt64())

    if ($foregroundHandle -eq $targetHandle) {
        throw "Foreground window is still the Rift window; this test would not prove non-focused posting."
    }
}

$baselineUtc = $null
if (-not $SkipVerify) {
    $baselineUtc = Get-FileTimestampUtc -Path $VerifyFilePath
    Write-Host "[RiftPost] Verify file  : $VerifyFilePath"
    Write-Host "[RiftPost] Baseline UTC : $($baselineUtc.ToString('yyyy-MM-ddTHH:mm:ss.fffffffZ'))"
}
else {
    Write-Host "[RiftPost] Verify mode  : skipped"
}
Write-Host "[RiftPost] Command      : $Command"

$strategies = @(
    @{ Name = "enter-then-type"; Action = { param($hwnd, $text) Send-CommandStrategyEnterThenType -WindowHandle $hwnd -Text $text } },
    @{ Name = "type-then-enter"; Action = { param($hwnd, $text) Send-CommandStrategySlashThenRest -WindowHandle $hwnd -Text $text } }
)

foreach ($strategy in $strategies) {
    Write-Host "[RiftPost] Attempting strategy: $($strategy.Name)"
    & $strategy.Action $effectiveTargetHandle $Command

    if ($SkipVerify) {
        Write-Host "[RiftPost] SUCCESS"
        Write-Host "[RiftPost] Strategy used: $($strategy.Name)"
        Write-Host "[RiftPost] Verification : skipped by request"
        exit 0
    }

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
