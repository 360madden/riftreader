[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('mouse-yaw', 'mouse-pitch', 'mouse-wheel', 'all')]
    [string]$Stimulus,
    [switch]$Json,
    [string]$Label,
    [int]$HoldMilliseconds = 500,
    [int]$WaitMilliseconds = 250,
    [int]$MousePixels = 60,
    [switch]$RefreshReaderBridge,
    [switch]$NoAhkFallback,
    [switch]$SkipBackgroundFocus
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$captureScript = Join-Path $PSScriptRoot 'capture-actor-orientation.ps1'
$keyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'
$windowToolsScript = Join-Path (Join-Path $PSScriptRoot '..\tools\rift-game-mcp\helpers') 'window-tools.ps1'
$tempPrefix = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), ('rift-camera-stimulus-{0}' -f ([Guid]::NewGuid().ToString('N'))))
$tempOutputFile = '{0}.json' -f $tempPrefix
$tempPreviousFile = '{0}.previous.json' -f $tempPrefix
$baselineScreenshot = '{0}.baseline.png' -f $tempPrefix
$changeScreenshot = '{0}.changed.png' -f $tempPrefix
$backgroundProcessAvailable = $SkipBackgroundFocus.IsPresent

if (-not $backgroundProcessAvailable) {
    try {
        $null = Get-Process -Name 'cheatengine-x86_64-SSE4-AVX2' -ErrorAction Stop | Select-Object -First 1
        $backgroundProcessAvailable = $true
    }
    catch {
        $backgroundProcessAvailable = $false
    }
}

function Invoke-Capture {
    param([Parameter(Mandatory = $true)][string]$CaptureLabel)

    if ($RefreshReaderBridge) {
        if ($NoAhkFallback) {
            $json = & $captureScript -Json -Label $CaptureLabel -OutputFile $tempOutputFile -PreviousFile $tempPreviousFile -RefreshReaderBridge -NoAhkFallback
        }
        else {
            $json = & $captureScript -Json -Label $CaptureLabel -OutputFile $tempOutputFile -PreviousFile $tempPreviousFile -RefreshReaderBridge
        }
    }
    else {
        $json = & $captureScript -Json -Label $CaptureLabel -OutputFile $tempOutputFile -PreviousFile $tempPreviousFile
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Actor orientation capture failed for '$CaptureLabel'."
    }

    return $json | ConvertFrom-Json -Depth 30
}

function Get-CoordDeltaMagnitude {
    param(
        $BeforeCoord,
        $AfterCoord
    )

    if ($null -eq $BeforeCoord -or $null -eq $AfterCoord) {
        return $null
    }

    if ($null -eq $BeforeCoord.X -or $null -eq $BeforeCoord.Y -or $null -eq $BeforeCoord.Z) {
        return $null
    }

    if ($null -eq $AfterCoord.X -or $null -eq $AfterCoord.Y -or $null -eq $AfterCoord.Z) {
        return $null
    }

    $dx = [double]$AfterCoord.X - [double]$BeforeCoord.X
    $dy = [double]$AfterCoord.Y - [double]$BeforeCoord.Y
    $dz = [double]$AfterCoord.Z - [double]$BeforeCoord.Z
    return [Math]::Sqrt(($dx * $dx) + ($dy * $dy) + ($dz * $dz))
}

function Get-VectorDeltaMagnitude {
    param(
        $BeforeVector,
        $AfterVector
    )

    if ($null -eq $BeforeVector -or $null -eq $AfterVector) {
        return $null
    }

    if ($null -eq $BeforeVector.X -or $null -eq $BeforeVector.Y -or $null -eq $BeforeVector.Z) {
        return $null
    }

    if ($null -eq $AfterVector.X -or $null -eq $AfterVector.Y -or $null -eq $AfterVector.Z) {
        return $null
    }

    $dx = [double]$AfterVector.X - [double]$BeforeVector.X
    $dy = [double]$AfterVector.Y - [double]$BeforeVector.Y
    $dz = [double]$AfterVector.Z - [double]$BeforeVector.Z
    return [Math]::Sqrt(($dx * $dx) + ($dy * $dy) + ($dz * $dz))
}

function Send-MouseInput {
    param(
        [ValidateSet('left', 'right', 'up', 'down', 'wheel-up', 'wheel-down')]
        [string]$Direction,
        [int]$Magnitude = 100,
        [switch]$HoldRightButton
    )

    if (-not ('RiftCameraStimulusNative' -as [type])) {
        Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class RiftCameraStimulusNative
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
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetCursorPos(int X, int Y);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern void mouse_event(uint dwFlags, int dx, int dy, uint dwData, UIntPtr dwExtraInfo);

    public const uint MOUSEEVENTF_MOVE = 0x0001;
    public const uint MOUSEEVENTF_RIGHTDOWN = 0x0008;
    public const uint MOUSEEVENTF_RIGHTUP = 0x0010;
    public const uint MOUSEEVENTF_WHEEL = 0x0800;
}
"@
    }

    $riftProcess = Get-Process -Name 'rift_x64' -ErrorAction Stop |
        Where-Object { $_.MainWindowHandle -ne 0 } |
        Select-Object -First 1
    if (-not $riftProcess) {
        throw 'No foreground-capable RIFT window was found.'
    }

    $rect = New-Object RiftCameraStimulusNative+RECT
    if (-not [RiftCameraStimulusNative]::GetWindowRect($riftProcess.MainWindowHandle, [ref]$rect)) {
        throw 'GetWindowRect failed for the RIFT window.'
    }

    $centerX = [int](($rect.Left + $rect.Right) / 2)
    $centerY = [int](($rect.Top + $rect.Bottom) / 2)
    if (-not [RiftCameraStimulusNative]::SetCursorPos($centerX, $centerY)) {
        throw 'SetCursorPos failed while centering the cursor over RIFT.'
    }

    Start-Sleep -Milliseconds 40

    if ($HoldRightButton) {
        [RiftCameraStimulusNative]::mouse_event([RiftCameraStimulusNative]::MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, [UIntPtr]::Zero)
        Start-Sleep -Milliseconds 50
    }

    switch ($Direction) {
        'right' {
            [RiftCameraStimulusNative]::mouse_event([RiftCameraStimulusNative]::MOUSEEVENTF_MOVE, $Magnitude, 0, 0, [UIntPtr]::Zero)
        }
        'left' {
            [RiftCameraStimulusNative]::mouse_event([RiftCameraStimulusNative]::MOUSEEVENTF_MOVE, -$Magnitude, 0, 0, [UIntPtr]::Zero)
        }
        'up' {
            [RiftCameraStimulusNative]::mouse_event([RiftCameraStimulusNative]::MOUSEEVENTF_MOVE, 0, -$Magnitude, 0, [UIntPtr]::Zero)
        }
        'down' {
            [RiftCameraStimulusNative]::mouse_event([RiftCameraStimulusNative]::MOUSEEVENTF_MOVE, 0, $Magnitude, 0, [UIntPtr]::Zero)
        }
        'wheel-up' {
            $wheelDelta = 120 * [Math]::Max(1, [Math]::Ceiling($Magnitude / 120.0))
            [RiftCameraStimulusNative]::mouse_event([RiftCameraStimulusNative]::MOUSEEVENTF_WHEEL, 0, 0, [uint32]$wheelDelta, [UIntPtr]::Zero)
        }
        'wheel-down' {
            $wheelDelta = 120 * [Math]::Max(1, [Math]::Ceiling($Magnitude / 120.0))
            [RiftCameraStimulusNative]::mouse_event([RiftCameraStimulusNative]::MOUSEEVENTF_WHEEL, 0, 0, [uint32](-$wheelDelta), [UIntPtr]::Zero)
        }
    }

    Start-Sleep -Milliseconds 60

    if ($HoldRightButton) {
        [RiftCameraStimulusNative]::mouse_event([RiftCameraStimulusNative]::MOUSEEVENTF_RIGHTUP, 0, 0, 0, [UIntPtr]::Zero)
        Start-Sleep -Milliseconds 30
    }
}

function Invoke-WindowToolsJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $json = & powershell -NoProfile -ExecutionPolicy Bypass -File $windowToolsScript @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "window-tools failed: $($Arguments -join ' ')"
    }

    return $json | ConvertFrom-Json -Depth 20
}

function Get-StimulusResult {
    param(
        [string]$StimulusType,
        $BeforeCapture,
        $AfterCapture
    )

    $beforeEstimate = $BeforeCapture.ReaderOrientation.PreferredEstimate
    $afterEstimate = $AfterCapture.ReaderOrientation.PreferredEstimate

    $result = [ordered]@{
        StimulusType = $StimulusType
        ActorCoordDelta = Get-CoordDeltaMagnitude $BeforeCapture.ReaderOrientation.PlayerCoord $AfterCapture.ReaderOrientation.PlayerCoord
        ActorYawBefore = $beforeEstimate.YawDegrees
        ActorYawAfter = $afterEstimate.YawDegrees
        ActorYawDelta = [double]$afterEstimate.YawDegrees - [double]$beforeEstimate.YawDegrees
        ActorPitchBefore = $beforeEstimate.PitchDegrees
        ActorPitchAfter = $afterEstimate.PitchDegrees
        ActorPitchDelta = [double]$afterEstimate.PitchDegrees - [double]$beforeEstimate.PitchDegrees
        ActorForwardVectorDelta = Get-VectorDeltaMagnitude $beforeEstimate.Vector $afterEstimate.Vector
        SelectedSourceAddress = $AfterCapture.ReaderOrientation.SelectedSourceAddress
        PreferredEstimateName = $afterEstimate.Name
        Notes = @()
    }

    # Validate: actor position should NOT change for camera-only input
    if ($null -ne $result.ActorCoordDelta -and $result.ActorCoordDelta -gt 0.1) {
        $result.Notes += "WARNING: Actor coordinate moved; input may have caused actor movement, not just camera movement"
    }

    return $result
}

# Main workflow
$results = @()

Write-Host "=== Camera Stimulus Test ===" -ForegroundColor Cyan
Write-Host "Stimulus: $Stimulus" -ForegroundColor Green
Write-Host "Hold duration: ${HoldMilliseconds}ms" -ForegroundColor Green
Write-Host "Wait after: ${WaitMilliseconds}ms" -ForegroundColor Green
Write-Host "Mouse pixels: $MousePixels" -ForegroundColor Green
Write-Host ""

$null = Invoke-WindowToolsJson -Arguments @('-Operation', 'focus', '-ProcessName', 'rift_x64')
$baselineFrame = Invoke-WindowToolsJson -Arguments @('-Operation', 'capture', '-ProcessName', 'rift_x64', '-OutputPath', $baselineScreenshot)

# Capture baseline
Write-Host "Capturing baseline..." -ForegroundColor Yellow
$baseline = Invoke-Capture "camera-stimulus-baseline"
Write-Host "  ✓ Baseline captured" -ForegroundColor Green

# Define stimuli
$stimuli = switch ($Stimulus) {
    'mouse-yaw' { @(@{ Direction = 'right'; Label = 'mouse-yaw-right' }) }
    'mouse-pitch' { @(@{ Direction = 'up'; Label = 'mouse-pitch-up' }) }
    'mouse-wheel' { @(@{ Direction = 'wheel-up'; Label = 'mouse-wheel-zoom-in' }) }
    'all' { @(
        @{ Direction = 'right'; Label = 'mouse-yaw-right' }
        @{ Direction = 'up'; Label = 'mouse-pitch-up' }
        @{ Direction = 'wheel-up'; Label = 'mouse-wheel-zoom-in' }
    ) }
}

foreach ($stimulusConfig in $stimuli) {
    Write-Host "Testing: $($stimulusConfig.Label)..." -ForegroundColor Yellow

    # Send input
    $holdRightButton = $stimulusConfig.Direction -ne 'wheel-up' -and $stimulusConfig.Direction -ne 'wheel-down'
    Send-MouseInput -Direction $stimulusConfig.Direction -Magnitude $MousePixels -HoldRightButton:$holdRightButton
    Start-Sleep -Milliseconds $HoldMilliseconds

    $visualChange = Invoke-WindowToolsJson -Arguments @(
        '-Operation', 'wait-for-change',
        '-ProcessName', 'rift_x64',
        '-BaselinePath', $baselineScreenshot,
        '-OutputPath', $changeScreenshot,
        '-TimeoutMilliseconds', '1500',
        '-PollIntervalMilliseconds', '100',
        '-ChangeThresholdPercent', '0.5'
    )

    # Capture after input
    $after = Invoke-Capture "camera-stimulus-$($stimulusConfig.Label)-after"

    # Compute delta
    $delta = Get-StimulusResult -StimulusType $stimulusConfig.Label -BeforeCapture $baseline -AfterCapture $after
    $delta | Add-Member -NotePropertyName VisualChangeObserved -NotePropertyValue ([bool]$visualChange.changed)
    $delta | Add-Member -NotePropertyName VisualChangePercent -NotePropertyValue ([double]$visualChange.changePercent)
    $delta | Add-Member -NotePropertyName VisualChangeScreenshot -NotePropertyValue $visualChange.screenshotPath
    $results += $delta

    Write-Host "  Yaw delta: $([Math]::Round($delta.ActorYawDelta, 2))°" -ForegroundColor Cyan
    Write-Host "  Pitch delta: $([Math]::Round($delta.ActorPitchDelta, 2))°" -ForegroundColor Cyan
    Write-Host "  Coord delta: $([Math]::Round($delta.ActorCoordDelta, 3)) units" -ForegroundColor Cyan
    Write-Host "  Visual change: $([Math]::Round($delta.VisualChangePercent, 3))% (changed=$($delta.VisualChangeObserved))" -ForegroundColor Cyan

    # Wait between stimuli
    Start-Sleep -Milliseconds $WaitMilliseconds
}

# Output results
$output = [ordered]@{
    Mode = 'camera-stimulus-test'
    GeneratedAtUtc = [System.DateTime]::UtcNow.ToString('o')
    Stimulus = $Stimulus
    Label = $Label
    Results = $results
    Notes = @(
        'Camera stimulus test compares actor orientation deltas in response to mouse input'
        'Expected: mouse-yaw-right should show positive yaw delta; mouse-pitch-up should show negative pitch delta'
        'Actor coordinate delta should remain ~0 (camera-only movement)'
    )
}

if ($Json) {
    $output | ConvertTo-Json -Depth 10
}
else {
    $output | Format-List
}
