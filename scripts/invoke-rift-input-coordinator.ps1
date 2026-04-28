[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [int]$MovementProcessId,

    [Parameter(Mandatory = $true)]
    [string]$MovementWindowHandle,

    [Parameter(Mandatory = $true)]
    [int]$BackgroundProcessId,

    [Parameter(Mandatory = $true)]
    [string]$BackgroundWindowHandle,

    [string]$BackgroundKey = 'b',
    [string]$ForegroundKey,
    [int]$HoldMilliseconds = 80,
    [int]$LockTimeoutMilliseconds = 15000,
    [string]$LockName = 'RiftReaderInputCoordinator',
    [switch]$ActiveMovementLease,
    [switch]$AllowForegroundMovementInput,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class RiftInputCoordinatorNative
{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll", SetLastError = true)]
    public static extern int GetWindowTextLength(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
}
"@

$postKeyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'

function ConvertTo-WindowHandle {
    param([Parameter(Mandatory = $true)][string]$HandleText)

    if ($HandleText.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $raw = [UInt64]::Parse($HandleText.Substring(2), [System.Globalization.NumberStyles]::AllowHexSpecifier, [System.Globalization.CultureInfo]::InvariantCulture)
        return [IntPtr]([Int64]$raw)
    }

    return [IntPtr]([Int64]::Parse($HandleText, [System.Globalization.CultureInfo]::InvariantCulture))
}

function Get-WindowTitle {
    param([Parameter(Mandatory = $true)][IntPtr]$Handle)

    $length = [RiftInputCoordinatorNative]::GetWindowTextLength($Handle)
    if ($length -le 0) {
        return ''
    }

    $builder = New-Object System.Text.StringBuilder ($length + 1)
    [void][RiftInputCoordinatorNative]::GetWindowText($Handle, $builder, $builder.Capacity)
    return $builder.ToString()
}

function Resolve-RiftWindow {
    param(
        [Parameter(Mandatory = $true)][string]$Lane,
        [Parameter(Mandatory = $true)][int]$ProcessId,
        [Parameter(Mandatory = $true)][string]$WindowHandle
    )

    $handle = ConvertTo-WindowHandle -HandleText $WindowHandle
    if ($handle -eq [IntPtr]::Zero -or -not [RiftInputCoordinatorNative]::IsWindow($handle)) {
        throw "$Lane window handle '$WindowHandle' is not a valid window."
    }

    $ownerProcessId = [uint32]0
    [void][RiftInputCoordinatorNative]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
    if ([int]$ownerProcessId -ne $ProcessId) {
        throw "$Lane window handle '$WindowHandle' belongs to PID $ownerProcessId, not PID $ProcessId."
    }

    $process = Get-Process -Id $ProcessId -ErrorAction Stop
    if (-not [string]::Equals($process.ProcessName, 'rift_x64', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Lane PID $ProcessId is '$($process.ProcessName)', not 'rift_x64'."
    }

    return [pscustomobject]@{
        Lane = $Lane
        ProcessId = $process.Id
        ProcessName = $process.ProcessName
        WindowHandle = $handle.ToInt64()
        WindowHandleHex = ('0x{0:X}' -f $handle.ToInt64())
        Title = Get-WindowTitle -Handle $handle
        IsForeground = ([RiftInputCoordinatorNative]::GetForegroundWindow() -eq $handle)
    }
}

function Assert-BackgroundKeyAllowed {
    param([string]$Key)

    if ([string]::IsNullOrWhiteSpace($Key)) {
        return
    }

    $normalized = $Key.Trim().ToUpperInvariant()
    $blocked = @(
        'W', 'A', 'S', 'D', 'Q', 'E',
        'SPACE', 'LEFT', 'RIGHT', 'UP', 'DOWN',
        '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
        '-', '=', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6',
        'F7', 'F8', 'F9', 'F10', 'F11', 'F12'
    )

    if ($blocked -contains $normalized) {
        throw "Background key '$Key' is blocked because it may move the player, turn/camera, or trigger hotbar/combat behavior."
    }
}

function Invoke-PostKey {
    param(
        [Parameter(Mandatory = $true)][object]$Window,
        [Parameter(Mandatory = $true)][string]$Key,
        [switch]$RequireForeground
    )

    $arguments = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $postKeyScript,
        '-Key', $Key,
        '-HoldMilliseconds', $HoldMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-TargetProcessName', 'rift_x64',
        '-TargetProcessId', $Window.ProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-TargetWindowHandle', $Window.WindowHandleHex,
        '-SkipBackgroundFocus'
    )

    if ($RequireForeground) {
        $arguments += '-RequireTargetForeground'
    }

    & pwsh @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "post-rift-key.ps1 failed for $($Window.Lane) lane with exit code $LASTEXITCODE."
    }
}

$movementWindow = Resolve-RiftWindow -Lane 'movement' -ProcessId $MovementProcessId -WindowHandle $MovementWindowHandle
$backgroundWindow = Resolve-RiftWindow -Lane 'background' -ProcessId $BackgroundProcessId -WindowHandle $BackgroundWindowHandle

if ($movementWindow.ProcessId -eq $backgroundWindow.ProcessId -or $movementWindow.WindowHandleHex -eq $backgroundWindow.WindowHandleHex) {
    throw 'Movement and background lanes must target different Rift windows.'
}

Assert-BackgroundKeyAllowed -Key $BackgroundKey

if (-not [string]::IsNullOrWhiteSpace($ForegroundKey) -and -not $AllowForegroundMovementInput) {
    throw 'Foreground input is blocked unless -AllowForegroundMovementInput is explicitly set.'
}

$createdNew = $false
$mutex = [System.Threading.Mutex]::new($false, $LockName, [ref]$createdNew)
$hasLock = $false

try {
    $hasLock = $mutex.WaitOne($LockTimeoutMilliseconds)
    if (-not $hasLock) {
        throw "Timed out after $LockTimeoutMilliseconds ms waiting for input coordinator lock '$LockName'."
    }

    $actions = New-Object System.Collections.Generic.List[object]
    if ($ActiveMovementLease) {
        $actions.Add([pscustomobject]@{ Lane = 'movement'; Action = 'exclusive-lease'; Key = $null }) | Out-Null
    }
    elseif (-not [string]::IsNullOrWhiteSpace($ForegroundKey)) {
        $actions.Add([pscustomobject]@{ Lane = 'movement'; Action = 'foreground-key'; Key = $ForegroundKey }) | Out-Null
    }

    if (-not [string]::IsNullOrWhiteSpace($BackgroundKey) -and -not $ActiveMovementLease) {
        $actions.Add([pscustomobject]@{ Lane = 'background'; Action = 'postmessage-key'; Key = $BackgroundKey }) | Out-Null
    }

    if (-not $DryRun) {
        foreach ($action in $actions) {
            if ($action.Lane -eq 'movement' -and $action.Action -eq 'foreground-key') {
                Invoke-PostKey -Window $movementWindow -Key $action.Key -RequireForeground
            }
            elseif ($action.Lane -eq 'background' -and $action.Action -eq 'postmessage-key') {
                Invoke-PostKey -Window $backgroundWindow -Key $action.Key
            }
        }
    }

    $mode = if ($DryRun) { 'dry-run' } else { 'execute' }

    $actionsArray = $actions.ToArray()
    $result = [ordered]@{
        mode = $mode
        lockName = $LockName
        lockAcquired = $true
        activeMovementLease = [bool]$ActiveMovementLease
        movement = $movementWindow
        background = $backgroundWindow
        actions = @($actionsArray)
        notes = @(
            'All input lanes are serialized by the coordinator mutex.',
            'Background lane blocks movement, turn, camera, hotbar, and mouse-style inputs.',
            'Active movement lease is exclusive and should not be mixed with background input.'
        )
    }

    $result | ConvertTo-Json -Depth 8
}
finally {
    if ($hasLock) {
        $mutex.ReleaseMutex()
    }

    $mutex.Dispose()
}
