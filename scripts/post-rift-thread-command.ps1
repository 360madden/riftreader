[CmdletBinding()]
param(
    [string]$Command = "/reloadui",
    [string]$TargetProcessName = "rift_x64",
    [string]$VerifyFilePath = "C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\Saved\rift315.1@gmail.com\Deepwood\Atank\SavedVariables\ReaderBridgeExport.lua",
    [string]$BackgroundProcessName = "cheatengine-x86_64-SSE4-AVX2",
    [int]$AttemptTimeoutSeconds = 10,
    [int]$InterKeyDelayMilliseconds = 20,
    [int]$FocusSettleMilliseconds = 500,
    [switch]$RequireTargetFocus,
    [switch]$SkipBackgroundFocus
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RiftPostThreadNative
{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool PostThreadMessage(uint idThread, uint Msg, IntPtr wParam, IntPtr lParam);

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
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint GetCurrentThreadId();

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool AttachThreadInput(uint idAttach, uint idAttachTo, bool fAttach);
}
"@

$WM_NULL = 0x0000
$WM_KEYDOWN = 0x0100
$WM_KEYUP = 0x0101
$WM_CHAR = 0x0102

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

    $candidate = Get-Process -Name $ProcessName -ErrorAction Stop |
        Where-Object { $_.MainWindowHandle -ne 0 } |
        Select-Object -First 1

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

    $targetHandle = [IntPtr]$Process.MainWindowHandle
    $dummyProcessId = 0
    $targetThreadId = [RiftPostThreadNative]::GetWindowThreadProcessId($targetHandle, [ref]$dummyProcessId)
    $currentThreadId = [RiftPostThreadNative]::GetCurrentThreadId()
    $foregroundHandle = [RiftPostThreadNative]::GetForegroundWindow()
    $foregroundProcessId = 0
    $foregroundThreadId = [RiftPostThreadNative]::GetWindowThreadProcessId($foregroundHandle, [ref]$foregroundProcessId)

    if ([RiftPostThreadNative]::IsIconic($targetHandle)) {
        [void][RiftPostThreadNative]::ShowWindow($Process.MainWindowHandle, $SW_RESTORE)
    }

    [void][RiftPostThreadNative]::AttachThreadInput($currentThreadId, $foregroundThreadId, $true)
    [void][RiftPostThreadNative]::AttachThreadInput($currentThreadId, $targetThreadId, $true)
    [void][RiftPostThreadNative]::SetForegroundWindow($Process.MainWindowHandle)
    [void][RiftPostThreadNative]::AttachThreadInput($currentThreadId, $foregroundThreadId, $false)
    [void][RiftPostThreadNative]::AttachThreadInput($currentThreadId, $targetThreadId, $false)
    Start-Sleep -Milliseconds $FocusSettleMilliseconds
}

function Get-ForegroundWindowInfo {
    $foregroundHandle = [RiftPostThreadNative]::GetForegroundWindow()
    $foregroundProcessId = 0
    [void][RiftPostThreadNative]::GetWindowThreadProcessId($foregroundHandle, [ref]$foregroundProcessId)

    $foregroundProcess = $null
    if ($foregroundProcessId -ne 0) {
        try {
            $foregroundProcess = Get-Process -Id $foregroundProcessId -ErrorAction Stop
        }
        catch {
            $foregroundProcess = $null
        }
    }

    return [pscustomobject]@{
        Handle = $foregroundHandle
        ProcessId = [int]$foregroundProcessId
        ProcessName = if ($null -ne $foregroundProcess) { [string]$foregroundProcess.ProcessName } else { $null }
    }
}

function Assert-TargetFocus {
    param(
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$Process
    )

    $foreground = Get-ForegroundWindowInfo
    if ($foreground.ProcessId -ne $Process.Id) {
        $foregroundName = if (-not [string]::IsNullOrWhiteSpace($foreground.ProcessName)) { $foreground.ProcessName } else { 'unknown' }
        throw ("RequireTargetFocus failed: expected Rift foreground process {0} [{1}], got {2} [{3}] handle 0x{4:X}. Activate the Rift window on the selected desktop and retry." -f $Process.ProcessName, $Process.Id, $foregroundName, $foreground.ProcessId, $foreground.Handle.ToInt64())
    }

    return $foreground
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

function New-KeyLParam {
    param(
        [Parameter(Mandatory = $true)]
        [int]$VirtualKey,

        [switch]$KeyUp
    )

    $scanCode = [RiftPostThreadNative]::MapVirtualKey([uint32]$VirtualKey, $MAPVK_VK_TO_VSC)
    $value = 1 -bor ($scanCode -shl 16)

    if ($KeyUp) {
        $value = $value -bor (1 -shl 30) -bor (1 -shl 31)
    }

    return [IntPtr]$value
}

function Post-ThreadMessageChecked {
    param(
        [Parameter(Mandatory = $true)]
        [uint32]$ThreadId,

        [Parameter(Mandatory = $true)]
        [uint32]$Message,

        [Parameter(Mandatory = $true)]
        [IntPtr]$WParam,

        [Parameter(Mandatory = $true)]
        [IntPtr]$LParam
    )

    $ok = [RiftPostThreadNative]::PostThreadMessage($ThreadId, $Message, $WParam, $LParam)
    if (-not $ok) {
        $lastError = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        throw "PostThreadMessage failed for thread $ThreadId, message 0x{0:X}, last error $lastError." -f $Message
    }
}

function Prime-ThreadQueue {
    param(
        [Parameter(Mandatory = $true)]
        [uint32]$ThreadId
    )

    Post-ThreadMessageChecked -ThreadId $ThreadId -Message $WM_NULL -WParam ([IntPtr]::Zero) -LParam ([IntPtr]::Zero)
}

function Post-ThreadKey {
    param(
        [Parameter(Mandatory = $true)]
        [uint32]$ThreadId,

        [Parameter(Mandatory = $true)]
        [int]$VirtualKey
    )

    Post-ThreadMessageChecked -ThreadId $ThreadId -Message $WM_KEYDOWN -WParam ([IntPtr]$VirtualKey) -LParam (New-KeyLParam -VirtualKey $VirtualKey)
    Start-Sleep -Milliseconds $InterKeyDelayMilliseconds
    Post-ThreadMessageChecked -ThreadId $ThreadId -Message $WM_KEYUP -WParam ([IntPtr]$VirtualKey) -LParam (New-KeyLParam -VirtualKey $VirtualKey -KeyUp)
    Start-Sleep -Milliseconds $InterKeyDelayMilliseconds
}

function Post-ThreadCharOnly {
    param(
        [Parameter(Mandatory = $true)]
        [uint32]$ThreadId,

        [Parameter(Mandatory = $true)]
        [char]$Character
    )

    Post-ThreadMessageChecked -ThreadId $ThreadId -Message $WM_CHAR -WParam ([IntPtr][int][char]$Character) -LParam ([IntPtr]1)
    Start-Sleep -Milliseconds $InterKeyDelayMilliseconds
}

function Post-ThreadCharacterAsKey {
    param(
        [Parameter(Mandatory = $true)]
        [uint32]$ThreadId,

        [Parameter(Mandatory = $true)]
        [char]$Character
    )

    $vkScan = [RiftPostThreadNative]::VkKeyScan($Character)
    if ($vkScan -eq -1) {
        throw "No virtual-key mapping was found for character '$Character'."
    }

    $virtualKey = $vkScan -band 0xFF
    $shiftState = ($vkScan -shr 8) -band 0xFF
    $modifiersDown = New-Object System.Collections.Generic.List[int]

    if (($shiftState -band 1) -ne 0) {
        Post-ThreadMessageChecked -ThreadId $ThreadId -Message $WM_KEYDOWN -WParam ([IntPtr]$VK_SHIFT) -LParam (New-KeyLParam -VirtualKey $VK_SHIFT)
        $modifiersDown.Add($VK_SHIFT)
    }

    if (($shiftState -band 2) -ne 0) {
        Post-ThreadMessageChecked -ThreadId $ThreadId -Message $WM_KEYDOWN -WParam ([IntPtr]$VK_CONTROL) -LParam (New-KeyLParam -VirtualKey $VK_CONTROL)
        $modifiersDown.Add($VK_CONTROL)
    }

    if (($shiftState -band 4) -ne 0) {
        Post-ThreadMessageChecked -ThreadId $ThreadId -Message $WM_KEYDOWN -WParam ([IntPtr]$VK_MENU) -LParam (New-KeyLParam -VirtualKey $VK_MENU)
        $modifiersDown.Add($VK_MENU)
    }

    Start-Sleep -Milliseconds $InterKeyDelayMilliseconds
    Post-ThreadMessageChecked -ThreadId $ThreadId -Message $WM_KEYDOWN -WParam ([IntPtr]$virtualKey) -LParam (New-KeyLParam -VirtualKey $virtualKey)
    Post-ThreadMessageChecked -ThreadId $ThreadId -Message $WM_CHAR -WParam ([IntPtr][int][char]$Character) -LParam ([IntPtr]1)
    Start-Sleep -Milliseconds $InterKeyDelayMilliseconds
    Post-ThreadMessageChecked -ThreadId $ThreadId -Message $WM_KEYUP -WParam ([IntPtr]$virtualKey) -LParam (New-KeyLParam -VirtualKey $virtualKey -KeyUp)

    for ($i = $modifiersDown.Count - 1; $i -ge 0; $i--) {
        Post-ThreadMessageChecked -ThreadId $ThreadId -Message $WM_KEYUP -WParam ([IntPtr]$modifiersDown[$i]) -LParam (New-KeyLParam -VirtualKey $modifiersDown[$i] -KeyUp)
    }

    Start-Sleep -Milliseconds $InterKeyDelayMilliseconds
}

function Send-ThreadCommandEnterThenType {
    param(
        [Parameter(Mandatory = $true)]
        [uint32]$ThreadId,

        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    Post-ThreadKey -ThreadId $ThreadId -VirtualKey $VK_RETURN
    foreach ($character in $Text.ToCharArray()) {
        Post-ThreadCharacterAsKey -ThreadId $ThreadId -Character $character
    }
    Post-ThreadKey -ThreadId $ThreadId -VirtualKey $VK_RETURN
}

function Send-ThreadCommandTypeThenEnter {
    param(
        [Parameter(Mandatory = $true)]
        [uint32]$ThreadId,

        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    foreach ($character in $Text.ToCharArray()) {
        Post-ThreadCharacterAsKey -ThreadId $ThreadId -Character $character
    }
    Post-ThreadKey -ThreadId $ThreadId -VirtualKey $VK_RETURN
}

function Send-ThreadCommandCharsThenEnter {
    param(
        [Parameter(Mandatory = $true)]
        [uint32]$ThreadId,

        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    foreach ($character in $Text.ToCharArray()) {
        Post-ThreadCharOnly -ThreadId $ThreadId -Character $character
    }
    Post-ThreadKey -ThreadId $ThreadId -VirtualKey $VK_RETURN
}

function Send-ThreadCommandEnterCharsEnter {
    param(
        [Parameter(Mandatory = $true)]
        [uint32]$ThreadId,

        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    Post-ThreadKey -ThreadId $ThreadId -VirtualKey $VK_RETURN
    foreach ($character in $Text.ToCharArray()) {
        Post-ThreadCharOnly -ThreadId $ThreadId -Character $character
    }
    Post-ThreadKey -ThreadId $ThreadId -VirtualKey $VK_RETURN
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
        $currentUtc = Get-FileTimestampUtc -Path $Path
        if ($currentUtc -gt $BaselineUtc) {
            return $currentUtc
        }

        Start-Sleep -Milliseconds 250
    }
    while ((Get-Date).ToUniversalTime() -lt $deadline)

    return $null
}

$targetProcess = Get-MainWindowProcess -ProcessName $TargetProcessName
$targetHandle = [IntPtr]$targetProcess.MainWindowHandle

$targetOwnerProcessId = 0
$targetThreadId = [RiftPostThreadNative]::GetWindowThreadProcessId($targetHandle, [ref]$targetOwnerProcessId)

if ($targetOwnerProcessId -ne $targetProcess.Id) {
    throw "Main window handle 0x{0:X} does not belong to process {1}." -f $targetProcess.MainWindowHandle, $targetProcess.Id
}

if ($targetThreadId -eq 0) {
    throw "No UI thread id was returned for window 0x{0:X}." -f $targetProcess.MainWindowHandle
}

Write-Host "[RiftThreadPost] Target process: $($targetProcess.ProcessName) [$($targetProcess.Id)]"
Write-Host ("[RiftThreadPost] Target window : 0x{0:X} '{1}'" -f $targetProcess.MainWindowHandle, $targetProcess.MainWindowTitle)
Write-Host "[RiftThreadPost] Target thread : $targetThreadId"

if ($RequireTargetFocus) {
    Write-Host "[RiftThreadPost] Strategy     : Focused PostThreadMessage delivery"
    Focus-Window -Process $targetProcess
    $foreground = Assert-TargetFocus -Process $targetProcess
    Write-Host ("[RiftThreadPost] Foreground   : 0x{0:X} ({1} [{2}])" -f $foreground.Handle.ToInt64(), $foreground.ProcessName, $foreground.ProcessId)
}
else {
    Write-Host "[RiftThreadPost] Strategy     : No-focus PostThreadMessage delivery"
}

if ((-not $RequireTargetFocus) -and (-not $SkipBackgroundFocus)) {
    $backgroundProcess = Get-MainWindowProcess -ProcessName $BackgroundProcessName
    Write-Host "[RiftThreadPost] Background focus target: $($backgroundProcess.ProcessName) [$($backgroundProcess.Id)]"
    Focus-Window -Process $backgroundProcess

    $foregroundHandle = [RiftPostThreadNative]::GetForegroundWindow()
    Write-Host ("[RiftThreadPost] Foreground window after redirect: 0x{0:X}" -f $foregroundHandle.ToInt64())

    if ($foregroundHandle -eq $targetHandle) {
        throw "Foreground window is still the Rift window; this test would not prove non-focused thread posting."
    }
}

Prime-ThreadQueue -ThreadId $targetThreadId

$baselineUtc = Get-FileTimestampUtc -Path $VerifyFilePath
Write-Host "[RiftThreadPost] Verify file  : $VerifyFilePath"
Write-Host "[RiftThreadPost] Baseline UTC : $($baselineUtc.ToString('yyyy-MM-ddTHH:mm:ss.fffffffZ'))"
Write-Host "[RiftThreadPost] Command      : $Command"

$strategies = @(
    @{ Name = "thread-enter-then-type"; Action = { param($threadId, $text) Send-ThreadCommandEnterThenType -ThreadId $threadId -Text $text } },
    @{ Name = "thread-type-then-enter"; Action = { param($threadId, $text) Send-ThreadCommandTypeThenEnter -ThreadId $threadId -Text $text } },
    @{ Name = "thread-enter-chars-enter"; Action = { param($threadId, $text) Send-ThreadCommandEnterCharsEnter -ThreadId $threadId -Text $text } },
    @{ Name = "thread-chars-then-enter"; Action = { param($threadId, $text) Send-ThreadCommandCharsThenEnter -ThreadId $threadId -Text $text } }
)

foreach ($strategy in $strategies) {
    Write-Host "[RiftThreadPost] Attempting strategy: $($strategy.Name)"
    & $strategy.Action $targetThreadId $Command

    $updatedUtc = Wait-ForTimestampAdvance -Path $VerifyFilePath -BaselineUtc $baselineUtc -TimeoutSeconds $AttemptTimeoutSeconds
    if ($updatedUtc) {
        Write-Host "[RiftThreadPost] SUCCESS"
        Write-Host "[RiftThreadPost] Strategy used: $($strategy.Name)"
        Write-Host "[RiftThreadPost] Updated UTC  : $($updatedUtc.ToString('yyyy-MM-ddTHH:mm:ss.fffffffZ'))"
        exit 0
    }
}

if ($RequireTargetFocus) {
    Write-Error "No verification file update was observed after posting '$Command' to focused Rift thread $targetThreadId."
}
else {
    Write-Error "No verification file update was observed after posting '$Command' to Rift thread $targetThreadId without focusing the game window."
}
exit 1
