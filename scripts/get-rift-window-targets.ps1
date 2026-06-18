[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ExpectedMovementProcessId,
    [string]$ExpectedMovementWindowHandle,
    [int]$ExpectedBackgroundProcessId,
    [string]$ExpectedBackgroundWindowHandle,
    [switch]$RequireTwo,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class RiftWindowTargetDiscoveryNative
{
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int maxCount);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);

    public struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }
}
"@

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

function Get-WindowTitle {
    param([Parameter(Mandatory = $true)][IntPtr]$Handle)

    $builder = [System.Text.StringBuilder]::new(512)
    [void][RiftWindowTargetDiscoveryNative]::GetWindowText($Handle, $builder, $builder.Capacity)
    return $builder.ToString()
}

function Get-RiftWindowTargets {
    param([Parameter(Mandatory = $true)][string]$Name)

    $windows = [System.Collections.Generic.List[object]]::new()
    $foreground = [RiftWindowTargetDiscoveryNative]::GetForegroundWindow()

    $callback = [RiftWindowTargetDiscoveryNative+EnumWindowsProc]{
        param([IntPtr]$Handle, [IntPtr]$Param)

        if (-not [RiftWindowTargetDiscoveryNative]::IsWindowVisible($Handle)) {
            return $true
        }

        $ownerProcessId = [uint32]0
        [void][RiftWindowTargetDiscoveryNative]::GetWindowThreadProcessId($Handle, [ref]$ownerProcessId)
        if ($ownerProcessId -eq 0) {
            return $true
        }

        $process = Get-Process -Id ([int]$ownerProcessId) -ErrorAction SilentlyContinue
        if (-not $process -or -not [string]::Equals($process.ProcessName, $Name, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }

        $rect = New-Object RiftWindowTargetDiscoveryNative+RECT
        [void][RiftWindowTargetDiscoveryNative]::GetWindowRect($Handle, [ref]$rect)
        $startTime = $null
        $moduleBaseAddressHex = $null
        $modulePath = $null
        try {
            $startTime = $process.StartTime.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        }
        catch {
            $startTime = $null
        }
        try {
            if ($null -ne $process.MainModule) {
                $moduleBaseAddressHex = ('0x{0:X}' -f $process.MainModule.BaseAddress.ToInt64())
                $modulePath = [string]$process.MainModule.FileName
            }
        }
        catch {
            $moduleBaseAddressHex = $null
            $modulePath = $null
        }

        $windows.Add([pscustomobject]@{
                ProcessId = [int]$ownerProcessId
                ProcessName = $process.ProcessName
                WindowHandle = $Handle.ToInt64()
                WindowHandleHex = ('0x{0:X}' -f $Handle.ToInt64())
                Title = Get-WindowTitle -Handle $Handle
                Foreground = ($foreground -eq $Handle)
                Left = $rect.Left
                Top = $rect.Top
                Right = $rect.Right
                Bottom = $rect.Bottom
                Width = $rect.Right - $rect.Left
                Height = $rect.Bottom - $rect.Top
                StartTime = $startTime
                ModuleBaseAddressHex = $moduleBaseAddressHex
                ModulePath = $modulePath
                Responding = $process.Responding
            }) | Out-Null

        return $true
    }

    [void][RiftWindowTargetDiscoveryNative]::EnumWindows($callback, [IntPtr]::Zero)
    return @($windows | Sort-Object Top, Left, ProcessId)
}

function Test-ExpectedTarget {
    param(
        [string]$Lane,
        [int]$ExpectedProcessId,
        [string]$ExpectedWindowHandle,
        [object[]]$Windows
    )

    if ($ExpectedProcessId -le 0 -and [string]::IsNullOrWhiteSpace($ExpectedWindowHandle)) {
        return [pscustomobject]@{
            Lane = $Lane
            Supplied = $false
            Matches = $null
            Error = $null
        }
    }

    $expectedHandleHex = $null
    if (-not [string]::IsNullOrWhiteSpace($ExpectedWindowHandle)) {
        $handle = ConvertTo-WindowHandle -HandleText $ExpectedWindowHandle
        $expectedHandleHex = ('0x{0:X}' -f $handle.ToInt64())
        if ($handle -eq [IntPtr]::Zero -or -not [RiftWindowTargetDiscoveryNative]::IsWindow($handle)) {
            return [pscustomobject]@{
                Lane = $Lane
                Supplied = $true
                Matches = $false
                Error = "Expected $Lane handle '$ExpectedWindowHandle' is not a valid window."
            }
        }
    }

    $matches = @($Windows | Where-Object {
            ($ExpectedProcessId -le 0 -or $_.ProcessId -eq $ExpectedProcessId) -and
            ([string]::IsNullOrWhiteSpace($expectedHandleHex) -or $_.WindowHandleHex -eq $expectedHandleHex)
        })

    if ($matches.Count -eq 1) {
        return [pscustomobject]@{
            Lane = $Lane
            Supplied = $true
            Matches = $true
            Error = $null
        }
    }

    return [pscustomobject]@{
        Lane = $Lane
        Supplied = $true
        Matches = $false
        Error = "Expected $Lane target did not resolve to exactly one current '$ProcessName' window."
    }
}

$normalizedProcessName = Get-NormalizedProcessName -Name $ProcessName
$windows = @(Get-RiftWindowTargets -Name $normalizedProcessName)
$movement = if ($windows.Count -ge 1) { $windows[0] } else { $null }
$background = if ($windows.Count -ge 2) { $windows[-1] } else { $null }
$expectedChecks = @(
    Test-ExpectedTarget -Lane 'movement' -ExpectedProcessId $ExpectedMovementProcessId -ExpectedWindowHandle $ExpectedMovementWindowHandle -Windows $windows
    Test-ExpectedTarget -Lane 'background' -ExpectedProcessId $ExpectedBackgroundProcessId -ExpectedWindowHandle $ExpectedBackgroundWindowHandle -Windows $windows
)

$errors = New-Object System.Collections.Generic.List[string]
if ($RequireTwo -and $windows.Count -lt 2) {
    $errors.Add("Expected at least two '$normalizedProcessName' windows, found $($windows.Count).") | Out-Null
}

foreach ($check in $expectedChecks) {
    if ($check.Supplied -and -not $check.Matches) {
        $errors.Add($check.Error) | Out-Null
    }
}

$coordinatorDryRunCommand = $null
if ($null -ne $movement -and $null -ne $background -and $movement.ProcessId -ne $background.ProcessId -and $movement.WindowHandleHex -ne $background.WindowHandleHex) {
    $coordinatorDryRunCommand = "pwsh -File scripts\invoke-rift-input-coordinator.ps1 -MovementProcessId $($movement.ProcessId) -MovementWindowHandle $($movement.WindowHandleHex) -BackgroundProcessId $($background.ProcessId) -BackgroundWindowHandle $($background.WindowHandleHex) -DryRun"
}

$result = [ordered]@{
    mode = 'rift-window-target-discovery'
    generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    processName = $normalizedProcessName
    count = $windows.Count
    movement = $movement
    background = $background
    windows = @($windows)
    expectedChecks = @($expectedChecks)
    coordinatorDryRunCommand = $coordinatorDryRunCommand
    ok = ($errors.Count -eq 0)
    errors = @($errors.ToArray())
    notes = @(
        'Read-only discovery only; this script does not focus, click, post messages, send keys, or attach a debugger.',
        'Default movement/background suggestion is sorted by window Top coordinate: uppermost as movement, lowermost as background.'
    )
}

if ($Json) {
    $result | ConvertTo-Json -Depth 8
}
else {
    Write-Host "RIFT window targets: $($windows.Count)" -ForegroundColor Cyan
    if ($windows.Count -gt 0) {
        $windows | Format-Table ProcessId, WindowHandleHex, Title, Foreground, Left, Top, Right, Bottom, StartTime, Responding -AutoSize
    }

    if ($coordinatorDryRunCommand) {
        Write-Host ''
        Write-Host 'Suggested coordinator dry-run:' -ForegroundColor Cyan
        Write-Host $coordinatorDryRunCommand
    }

    foreach ($errorMessage in $errors) {
        Write-Warning $errorMessage
    }
}

if ($errors.Count -gt 0) {
    exit 1
}
