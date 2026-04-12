[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('mouse-yaw', 'mouse-pitch', 'mouse-wheel', 'all')]
    [string]$Stimulus,
    [switch]$Json,
    [string]$Label,
    [int]$HoldMilliseconds = 500,
    [int]$WaitMilliseconds = 250,
    [switch]$RefreshReaderBridge,
    [switch]$NoAhkFallback,
    [switch]$SkipBackgroundFocus
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$captureScript = Join-Path $PSScriptRoot 'capture-actor-orientation.ps1'
$keyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'
$tempPrefix = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), ('rift-camera-stimulus-{0}' -f ([Guid]::NewGuid().ToString('N'))))
$tempOutputFile = '{0}.json' -f $tempPrefix
$tempPreviousFile = '{0}.previous.json' -f $tempPrefix
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
        [int]$Magnitude = 100
    )

    $ahkScript = Join-Path $PSScriptRoot 'send-mouse-input.ahk'
    if (-not (Test-Path $ahkScript)) {
        throw "AutoHotkey script not found: $ahkScript"
    }

    # Direction maps to AHK mouse commands
    # Left/Right = horizontal yaw movement
    # Up/Down = vertical pitch movement
    # Wheel-Up/Wheel-Down = camera distance
    Add-Type -AssemblyName System.Windows.Forms
    $screen = [System.Windows.Forms.Screen]::PrimaryScreen
    $centerX = $screen.Bounds.Width / 2
    $centerY = $screen.Bounds.Height / 2

    switch ($Direction) {
        'right' {
            # Camera yaw right: move mouse right
            [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($centerX + $Magnitude, $centerY)
        }
        'left' {
            # Camera yaw left: move mouse left
            [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($centerX - $Magnitude, $centerY)
        }
        'up' {
            # Camera pitch up: move mouse up
            [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($centerX, $centerY - $Magnitude)
        }
        'down' {
            # Camera pitch down: move mouse down
            [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($centerX, $centerY + $Magnitude)
        }
        'wheel-up' {
            # Camera zoom in: scroll wheel up
            $mouseEvent = [System.Windows.Forms.MouseEventArgs]::new([System.Windows.Forms.MouseButtons]::Middle, 1, $centerX, $centerY, 120)
            # Note: Direct wheel scroll via .NET is limited; using simpler approach below
            Add-Type @"
using System;
using System.Runtime.InteropServices;

public class MouseWheel {
    [DllImport("user32.dll", SetLastError = true)]
    public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint cButtons, uint dwExtraInfo);

    public const uint MOUSEEVENTF_WHEEL = 0x0800;

    public static void ScrollWheel(int delta) {
        mouse_event(MOUSEEVENTF_WHEEL, 0, 0, (uint)delta, 0);
    }
}
"@
            [MouseWheel]::ScrollWheel($Magnitude)
        }
        'wheel-down' {
            # Camera zoom out: scroll wheel down
            Add-Type @"
using System;
using System.Runtime.InteropServices;

public class MouseWheel {
    [DllImport("user32.dll", SetLastError = true)]
    public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint cButtons, uint dwExtraInfo);

    public const uint MOUSEEVENTF_WHEEL = 0x0800;

    public static void ScrollWheel(int delta) {
        mouse_event(MOUSEEVENTF_WHEEL, 0, 0, (uint)delta, 0);
    }
}
"@
            [MouseWheel]::ScrollWheel(-$Magnitude)
        }
    }
}

function Get-StimulusResult {
    param(
        [string]$StimulusType,
        $BeforeCapture,
        $AfterCapture
    )

    $result = [ordered]@{
        StimulusType = $StimulusType
        ActorCoordDelta = Get-CoordDeltaMagnitude $BeforeCapture.ReaderOrientation.PlayerCoord $AfterCapture.ReaderOrientation.PlayerCoord
        ActorYawBefore = $BeforeCapture.ReaderOrientation.LiveSourceSample.ActorYaw.Degrees
        ActorYawAfter = $AfterCapture.ReaderOrientation.LiveSourceSample.ActorYaw.Degrees
        ActorYawDelta = [double]$AfterCapture.ReaderOrientation.LiveSourceSample.ActorYaw.Degrees - [double]$BeforeCapture.ReaderOrientation.LiveSourceSample.ActorYaw.Degrees
        ActorPitchBefore = $BeforeCapture.ReaderOrientation.LiveSourceSample.ActorPitch.Degrees
        ActorPitchAfter = $AfterCapture.ReaderOrientation.LiveSourceSample.ActorPitch.Degrees
        ActorPitchDelta = [double]$AfterCapture.ReaderOrientation.LiveSourceSample.ActorPitch.Degrees - [double]$BeforeCapture.ReaderOrientation.LiveSourceSample.ActorPitch.Degrees
        ActorForwardVectorDelta = Get-VectorDeltaMagnitude $BeforeCapture.ReaderOrientation.LiveSourceSample.ActorForwardVector $AfterCapture.ReaderOrientation.LiveSourceSample.ActorForwardVector
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
Write-Host ""

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

foreach ($stimulus in $stimuli) {
    Write-Host "Testing: $($stimulus.Label)..." -ForegroundColor Yellow

    # Send input
    Send-MouseInput -Direction $stimulus.Direction -Magnitude 50
    Start-Sleep -Milliseconds $HoldMilliseconds

    # Capture after input
    $after = Invoke-Capture "camera-stimulus-$($stimulus.Label)-after"

    # Compute delta
    $delta = Get-StimulusResult -StimulusType $stimulus.Label -BeforeCapture $baseline -AfterCapture $after
    $results += $delta

    Write-Host "  Yaw delta: $([Math]::Round($delta.ActorYawDelta, 2))°" -ForegroundColor Cyan
    Write-Host "  Pitch delta: $([Math]::Round($delta.ActorPitchDelta, 2))°" -ForegroundColor Cyan
    Write-Host "  Coord delta: $([Math]::Round($delta.ActorCoordDelta, 3)) units" -ForegroundColor Cyan

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
