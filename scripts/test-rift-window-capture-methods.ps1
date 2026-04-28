[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TitleContains,
    [string]$OutputRoot,
    [int]$SampleStep = 16,
    [int]$ContentTop = 40,
    [double]$MinContentNonBlackRatio = 0.05,
    [ValidateRange(1, 20)]
    [int]$DesktopDuplicationAttempts = 3,
    [switch]$SkipDesktopDuplication,
    [switch]$RequireAnyUsable,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $repoRoot 'artifacts\tooltip-projection\capture-diagnostics'
}
elseif (-not [System.IO.Path]::IsPathRooted($OutputRoot)) {
    $OutputRoot = Join-Path $repoRoot $OutputRoot
}

if ($SampleStep -le 0) {
    throw 'SampleStep must be greater than zero.'
}

if ($ContentTop -lt 0) {
    throw 'ContentTop must be non-negative.'
}

$nativeCode = @'
using System;
using System.Runtime.InteropServices;
public static class RiftCaptureDiagnosticNative {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X; public int Y; }

  [DllImport("user32.dll", SetLastError=true)] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
  [DllImport("user32.dll", SetLastError=true)] public static extern bool GetClientRect(IntPtr hWnd, out RECT lpRect);
  [DllImport("user32.dll", SetLastError=true)] public static extern bool ClientToScreen(IntPtr hWnd, ref POINT point);
  [DllImport("user32.dll", SetLastError=true)] public static extern IntPtr GetWindowDC(IntPtr hWnd);
  [DllImport("user32.dll", SetLastError=true)] public static extern IntPtr GetDC(IntPtr hWnd);
  [DllImport("user32.dll", SetLastError=true)] public static extern int ReleaseDC(IntPtr hWnd, IntPtr hDC);
  [DllImport("user32.dll", SetLastError=true)] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdcBlt, uint nFlags);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll", SetLastError=true)] public static extern bool GetWindowDisplayAffinity(IntPtr hWnd, out uint affinity);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, System.Text.StringBuilder className, int maxCount);
  [DllImport("user32.dll", SetLastError=true)] public static extern long GetWindowLongPtr(IntPtr hWnd, int index);
  [DllImport("dwmapi.dll", PreserveSig=true)] public static extern int DwmGetWindowAttribute(IntPtr hwnd, int attribute, out int value, int valueSize);
  [DllImport("gdi32.dll", SetLastError=true)] public static extern bool BitBlt(IntPtr hdcDest, int nXDest, int nYDest, int nWidth, int nHeight, IntPtr hdcSrc, int nXSrc, int nYSrc, int dwRop);
}
'@
Add-Type -TypeDefinition $nativeCode -ErrorAction SilentlyContinue
Add-Type -AssemblyName System.Drawing

function Convert-RectToObject {
    param(
        [int]$Left,
        [int]$Top,
        [int]$Right,
        [int]$Bottom
    )

    [ordered]@{
        left = $Left
        top = $Top
        right = $Right
        bottom = $Bottom
        width = $Right - $Left
        height = $Bottom - $Top
    }
}

function Get-BitmapQuality {
    param(
        [Parameter(Mandatory = $true)]
        [System.Drawing.Bitmap]$Bitmap,
        [int]$Step,
        [int]$BodyTop,
        [double]$RequiredContentNonBlackRatio
    )

    $width = $Bitmap.Width
    $height = $Bitmap.Height
    $effectiveBodyTop = [Math]::Min($BodyTop, [Math]::Max(0, $height - 1))

    $samples = 0
    $nonBlackSamples = 0
    $brightnessSum = 0.0
    $brightnessSquaredSum = 0.0
    $bodySamples = 0
    $bodyNonBlackSamples = 0
    $bodyBrightnessSum = 0.0
    $bodyBrightnessSquaredSum = 0.0

    for ($y = 0; $y -lt $height; $y += $Step) {
        for ($x = 0; $x -lt $width; $x += $Step) {
            $color = $Bitmap.GetPixel($x, $y)
            $brightness = ([double]$color.R + [double]$color.G + [double]$color.B) / 3.0
            $isNonBlack = $brightness -gt 8.0

            $samples++
            $brightnessSum += $brightness
            $brightnessSquaredSum += ($brightness * $brightness)
            if ($isNonBlack) {
                $nonBlackSamples++
            }

            if ($y -ge $effectiveBodyTop) {
                $bodySamples++
                $bodyBrightnessSum += $brightness
                $bodyBrightnessSquaredSum += ($brightness * $brightness)
                if ($isNonBlack) {
                    $bodyNonBlackSamples++
                }
            }
        }
    }

    $nonBlackRatio = if ($samples -gt 0) { [double]$nonBlackSamples / [double]$samples } else { 0.0 }
    $averageBrightness = if ($samples -gt 0) { $brightnessSum / [double]$samples } else { 0.0 }
    $variance = if ($samples -gt 0) {
        [Math]::Max(0.0, ($brightnessSquaredSum / [double]$samples) - ($averageBrightness * $averageBrightness))
    }
    else {
        0.0
    }

    $bodyNonBlackRatio = if ($bodySamples -gt 0) { [double]$bodyNonBlackSamples / [double]$bodySamples } else { 0.0 }
    $bodyAverageBrightness = if ($bodySamples -gt 0) { $bodyBrightnessSum / [double]$bodySamples } else { 0.0 }
    $bodyVariance = if ($bodySamples -gt 0) {
        [Math]::Max(0.0, ($bodyBrightnessSquaredSum / [double]$bodySamples) - ($bodyAverageBrightness * $bodyAverageBrightness))
    }
    else {
        0.0
    }

    $isUsable = $bodyNonBlackRatio -ge $RequiredContentNonBlackRatio -and $bodyAverageBrightness -gt 4.0

    [ordered]@{
        width = $width
        height = $height
        sampleStep = $Step
        contentTop = $effectiveBodyTop
        totalSamples = $samples
        nonBlackSamples = $nonBlackSamples
        nonBlackRatio = [Math]::Round($nonBlackRatio, 6)
        averageBrightness = [Math]::Round($averageBrightness, 3)
        brightnessStdDev = [Math]::Round([Math]::Sqrt($variance), 3)
        contentSamples = $bodySamples
        contentNonBlackSamples = $bodyNonBlackSamples
        contentNonBlackRatio = [Math]::Round($bodyNonBlackRatio, 6)
        contentAverageBrightness = [Math]::Round($bodyAverageBrightness, 3)
        contentBrightnessStdDev = [Math]::Round([Math]::Sqrt($bodyVariance), 3)
        minContentNonBlackRatio = $RequiredContentNonBlackRatio
        isLikelyBlack = -not $isUsable
        isUsable = $isUsable
    }
}

function Save-CaptureAttempt {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Method,
        [Parameter(Mandatory = $true)]
        [string]$ImageDirectory,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Capture
    )

    $safeMethod = $Method -replace '[^A-Za-z0-9_.-]', '_'
    $imagePath = Join-Path $ImageDirectory "$safeMethod.png"
    $bitmap = $null
    $ok = $false
    $exceptionText = $null
    $lastError = 0

    try {
        $captureResult = & $Capture
        $bitmap = $captureResult.Bitmap
        $ok = [bool]$captureResult.Ok
        $lastError = [int]$captureResult.LastError

        if ($null -eq $bitmap) {
            throw "Capture method $Method did not return a bitmap."
        }

        $bitmap.Save($imagePath, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    catch {
        $exceptionText = $_.Exception.Message
    }

    $quality = $null
    if ($null -ne $bitmap) {
        $quality = Get-BitmapQuality -Bitmap $bitmap -Step $SampleStep -BodyTop $ContentTop -RequiredContentNonBlackRatio $MinContentNonBlackRatio
        $bitmap.Dispose()
    }

    [pscustomobject][ordered]@{
        method = $Method
        ok = $ok
        path = if (Test-Path -LiteralPath $imagePath) { $imagePath } else { $null }
        exception = $exceptionText
        lastError = $lastError
        quality = $quality
    }
}

function Save-DotnetCaptureAttempt {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Method,
        [Parameter(Mandatory = $true)]
        [string]$ImageDirectory
    )

    $safeMethod = $Method -replace '[^A-Za-z0-9_.-]', '_'
    $imagePath = Join-Path $ImageDirectory "$safeMethod.bmp"
    $jsonPath = Join-Path $ImageDirectory "$safeMethod.json"
    $wrapper = Join-Path $PSScriptRoot 'capture-rift-window-wgc.ps1'
    $ok = $false
    $exceptionText = $null
    $report = $null

    try {
        if (-not (Test-Path -LiteralPath $wrapper)) {
            throw "WGC/Desktop Duplication wrapper not found: $wrapper"
        }

        $args = @(
            '-NoProfile',
            '-ExecutionPolicy', 'Bypass',
            '-File', $wrapper,
            '-DesktopDuplication',
            '-Attempts', $DesktopDuplicationAttempts.ToString([Globalization.CultureInfo]::InvariantCulture),
            '-TimeoutMs', '1000',
            '-Json'
        )

        if ($PSBoundParameters.ContainsKey('ProcessId')) {
            $args += @('-ProcessId', $ProcessId.ToString([Globalization.CultureInfo]::InvariantCulture))
        }
        elseif (-not [string]::IsNullOrWhiteSpace($ProcessName)) {
            $args += @('-ProcessName', $ProcessName)
        }

        if (-not [string]::IsNullOrWhiteSpace($TitleContains)) {
            $args += @('-TitleContains', $TitleContains)
        }

        $text = & pwsh @args
        $text | Set-Content -LiteralPath $jsonPath -Encoding UTF8
        $report = $text | ConvertFrom-Json
        $ok = [bool]$report.Ok
        if ($ok -and -not [string]::IsNullOrWhiteSpace([string]$report.Output) -and (Test-Path -LiteralPath ([string]$report.Output))) {
            Copy-Item -LiteralPath ([string]$report.Output) -Destination $imagePath -Force
        }
    }
    catch {
        $exceptionText = $_.Exception.Message
    }

    $quality = $null
    if ($null -ne $report) {
        $quality = [ordered]@{
            width = [int]$report.Width
            height = [int]$report.Height
            sampleStep = $null
            contentTop = $ContentTop
            totalSamples = $null
            nonBlackSamples = $null
            nonBlackRatio = [Math]::Round([double](1.0 - [double]$report.BlackPixelRatio), 6)
            averageBrightness = $null
            brightnessStdDev = [Math]::Round([double]$report.LumaStdDev, 3)
            contentSamples = $null
            contentNonBlackSamples = $null
            contentNonBlackRatio = [Math]::Round([double](1.0 - [double]$report.ContentBlackPixelRatio), 6)
            contentAverageBrightness = $null
            contentBrightnessStdDev = [Math]::Round([double]$report.ContentLumaStdDev, 3)
            minContentNonBlackRatio = $MinContentNonBlackRatio
            isLikelyBlack = -not [bool]$report.Usable
            isUsable = [bool]$report.Usable
            captureMethod = $report.CaptureMethod
            quality = $report.Quality
        }
    }

    [pscustomobject][ordered]@{
        method = $Method
        ok = $ok
        path = if (Test-Path -LiteralPath $imagePath) { $imagePath } elseif ($null -ne $report -and -not [string]::IsNullOrWhiteSpace([string]$report.Output)) { [string]$report.Output } else { $null }
        exception = $exceptionText
        lastError = 0
        quality = $quality
        jsonPath = if (Test-Path -LiteralPath $jsonPath) { $jsonPath } else { $null }
    }
}

$processes = if ($PSBoundParameters.ContainsKey('ProcessId')) {
    @(Get-Process -Id $ProcessId -ErrorAction Stop)
}
else {
    @(Get-Process -Name $ProcessName -ErrorAction Stop)
}

if (-not [string]::IsNullOrWhiteSpace($TitleContains)) {
    $processes = @($processes | Where-Object { $_.MainWindowTitle -like "*$TitleContains*" })
}

$windowedProcesses = @($processes | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero })
if (-not $PSBoundParameters.ContainsKey('ProcessId') -and $windowedProcesses.Count -gt 1) {
    $ids = ($windowedProcesses | Sort-Object Id | ForEach-Object { $_.Id }) -join ', '
    throw "Process name '$ProcessName' matched multiple windowed processes ($ids). Use -ProcessId for capture isolation."
}

$process = @($windowedProcesses | Select-Object -First 1)
if ($process.Count -eq 0) {
    throw 'No matching process with a main window handle was found.'
}
$process = $process[0]
$hWnd = $process.MainWindowHandle
$foregroundHwnd = [RiftCaptureDiagnosticNative]::GetForegroundWindow()
$displayAffinity = [uint32]0
$displayAffinityOk = [RiftCaptureDiagnosticNative]::GetWindowDisplayAffinity($hWnd, [ref]$displayAffinity)
$dwmCloaked = 0
$dwmCloakedHr = [RiftCaptureDiagnosticNative]::DwmGetWindowAttribute($hWnd, 14, [ref]$dwmCloaked, 4)
$windowClassName = [System.Text.StringBuilder]::new(256)
[RiftCaptureDiagnosticNative]::GetClassName($hWnd, $windowClassName, $windowClassName.Capacity) | Out-Null

$windowRectNative = New-Object RiftCaptureDiagnosticNative+RECT
if (-not [RiftCaptureDiagnosticNative]::GetWindowRect($hWnd, [ref]$windowRectNative)) {
    throw "GetWindowRect failed with error $([System.Runtime.InteropServices.Marshal]::GetLastWin32Error())."
}

$clientRectNative = New-Object RiftCaptureDiagnosticNative+RECT
if (-not [RiftCaptureDiagnosticNative]::GetClientRect($hWnd, [ref]$clientRectNative)) {
    throw "GetClientRect failed with error $([System.Runtime.InteropServices.Marshal]::GetLastWin32Error())."
}

$clientOrigin = New-Object RiftCaptureDiagnosticNative+POINT
$clientOrigin.X = 0
$clientOrigin.Y = 0
if (-not [RiftCaptureDiagnosticNative]::ClientToScreen($hWnd, [ref]$clientOrigin)) {
    throw "ClientToScreen failed with error $([System.Runtime.InteropServices.Marshal]::GetLastWin32Error())."
}

$windowWidth = $windowRectNative.Right - $windowRectNative.Left
$windowHeight = $windowRectNative.Bottom - $windowRectNative.Top
$clientWidth = $clientRectNative.Right - $clientRectNative.Left
$clientHeight = $clientRectNative.Bottom - $clientRectNative.Top
if ($windowWidth -le 0 -or $windowHeight -le 0 -or $clientWidth -le 0 -or $clientHeight -le 0) {
    throw "Invalid capture dimensions: window=$windowWidth x $windowHeight client=$clientWidth x $clientHeight"
}

$runRoot = Join-Path $OutputRoot ('{0}-capture-methods' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$imageDirectory = Join-Path $runRoot 'images'
New-Item -ItemType Directory -Force -Path $imageDirectory | Out-Null

$attempts = [System.Collections.Generic.List[object]]::new()

foreach ($flag in @(2, 0, 1)) {
    $method = "PrintWindowFlag$flag"
    $attempts.Add((Save-CaptureAttempt -Method $method -ImageDirectory $imageDirectory -Capture {
        $bitmap = New-Object System.Drawing.Bitmap $windowWidth, $windowHeight
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $hdc = $graphics.GetHdc()
        try {
            $ok = [RiftCaptureDiagnosticNative]::PrintWindow($hWnd, $hdc, [uint32]$flag)
            $lastError = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
        }
        finally {
            $graphics.ReleaseHdc($hdc)
            $graphics.Dispose()
        }

        [pscustomobject]@{
            Bitmap = $bitmap
            Ok = $ok
            LastError = $lastError
        }
    })) | Out-Null
}

$attempts.Add((Save-CaptureAttempt -Method 'WindowDcBitBlt' -ImageDirectory $imageDirectory -Capture {
    $bitmap = New-Object System.Drawing.Bitmap $windowWidth, $windowHeight
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $hdcDest = $graphics.GetHdc()
    $hdcSrc = [RiftCaptureDiagnosticNative]::GetWindowDC($hWnd)
    try {
        $ok = $false
        if ($hdcSrc -ne [IntPtr]::Zero) {
            $ok = [RiftCaptureDiagnosticNative]::BitBlt($hdcDest, 0, 0, $windowWidth, $windowHeight, $hdcSrc, 0, 0, 0x00CC0020)
        }
        $lastError = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
    }
    finally {
        if ($hdcSrc -ne [IntPtr]::Zero) {
            [RiftCaptureDiagnosticNative]::ReleaseDC($hWnd, $hdcSrc) | Out-Null
        }
        $graphics.ReleaseHdc($hdcDest)
        $graphics.Dispose()
    }

    [pscustomobject]@{
        Bitmap = $bitmap
        Ok = $ok
        LastError = $lastError
    }
})) | Out-Null

$attempts.Add((Save-CaptureAttempt -Method 'ClientDcBitBlt' -ImageDirectory $imageDirectory -Capture {
    $bitmap = New-Object System.Drawing.Bitmap $clientWidth, $clientHeight
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $hdcDest = $graphics.GetHdc()
    $hdcSrc = [RiftCaptureDiagnosticNative]::GetDC($hWnd)
    try {
        $ok = $false
        if ($hdcSrc -ne [IntPtr]::Zero) {
            $ok = [RiftCaptureDiagnosticNative]::BitBlt($hdcDest, 0, 0, $clientWidth, $clientHeight, $hdcSrc, 0, 0, 0x00CC0020)
        }
        $lastError = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
    }
    finally {
        if ($hdcSrc -ne [IntPtr]::Zero) {
            [RiftCaptureDiagnosticNative]::ReleaseDC($hWnd, $hdcSrc) | Out-Null
        }
        $graphics.ReleaseHdc($hdcDest)
        $graphics.Dispose()
    }

    [pscustomobject]@{
        Bitmap = $bitmap
        Ok = $ok
        LastError = $lastError
    }
})) | Out-Null

$attempts.Add((Save-CaptureAttempt -Method 'ScreenDcBitBltClient' -ImageDirectory $imageDirectory -Capture {
    $bitmap = New-Object System.Drawing.Bitmap $clientWidth, $clientHeight
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $hdcDest = $graphics.GetHdc()
    $hdcSrc = [RiftCaptureDiagnosticNative]::GetDC([IntPtr]::Zero)
    try {
        $ok = $false
        if ($hdcSrc -ne [IntPtr]::Zero) {
            $ok = [RiftCaptureDiagnosticNative]::BitBlt($hdcDest, 0, 0, $clientWidth, $clientHeight, $hdcSrc, $clientOrigin.X, $clientOrigin.Y, 0x00CC0020)
        }
        $lastError = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
    }
    finally {
        if ($hdcSrc -ne [IntPtr]::Zero) {
            [RiftCaptureDiagnosticNative]::ReleaseDC([IntPtr]::Zero, $hdcSrc) | Out-Null
        }
        $graphics.ReleaseHdc($hdcDest)
        $graphics.Dispose()
    }

    [pscustomobject]@{
        Bitmap = $bitmap
        Ok = $ok
        LastError = $lastError
    }
})) | Out-Null

$attempts.Add((Save-CaptureAttempt -Method 'CopyFromScreenClient' -ImageDirectory $imageDirectory -Capture {
    $bitmap = New-Object System.Drawing.Bitmap $clientWidth, $clientHeight
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CopyFromScreen($clientOrigin.X, $clientOrigin.Y, 0, 0, [System.Drawing.Size]::new($clientWidth, $clientHeight))
        $ok = $true
        $lastError = 0
    }
    finally {
        $graphics.Dispose()
    }

    [pscustomobject]@{
        Bitmap = $bitmap
        Ok = $ok
        LastError = $lastError
    }
})) | Out-Null

if (-not $SkipDesktopDuplication) {
    $attempts.Add((Save-DotnetCaptureAttempt -Method 'DXGIDesktopDuplication' -ImageDirectory $imageDirectory)) | Out-Null
}

$best = @($attempts |
    Where-Object { $null -ne $_.quality } |
    Sort-Object `
        @{ Expression = { [bool]$_.quality.isUsable }; Descending = $true },
        @{ Expression = { [double]$_.quality.contentNonBlackRatio }; Descending = $true },
        @{ Expression = { [double]$_.quality.contentBrightnessStdDev }; Descending = $true } |
    Select-Object -First 1)

$summary = [pscustomobject][ordered]@{
    ok = $true
    usable = if ($null -ne $best) { [bool]$best.quality.isUsable } else { $false }
    bestMethod = if ($null -ne $best) { $best.method } else { $null }
    runRoot = $runRoot
    processId = $process.Id
    processName = $process.ProcessName
    windowTitle = $process.MainWindowTitle
    windowHandle = ('0x{0:X}' -f $hWnd.ToInt64())
    windowClassName = $windowClassName.ToString()
    isIconic = [RiftCaptureDiagnosticNative]::IsIconic($hWnd)
    isVisible = [RiftCaptureDiagnosticNative]::IsWindowVisible($hWnd)
    isForeground = $foregroundHwnd -eq $hWnd
    foregroundWindowHandle = ('0x{0:X}' -f $foregroundHwnd.ToInt64())
    displayAffinityOk = $displayAffinityOk
    displayAffinity = $displayAffinity
    dwmCloakedHResult = ('0x{0:X8}' -f $dwmCloakedHr)
    dwmCloaked = $dwmCloaked
    windowStyle = ('0x{0:X}' -f [RiftCaptureDiagnosticNative]::GetWindowLongPtr($hWnd, -16))
    windowExStyle = ('0x{0:X}' -f [RiftCaptureDiagnosticNative]::GetWindowLongPtr($hWnd, -20))
    windowRect = Convert-RectToObject -Left $windowRectNative.Left -Top $windowRectNative.Top -Right $windowRectNative.Right -Bottom $windowRectNative.Bottom
    clientRect = Convert-RectToObject -Left $clientOrigin.X -Top $clientOrigin.Y -Right ($clientOrigin.X + $clientWidth) -Bottom ($clientOrigin.Y + $clientHeight)
    controlsInput = $false
    attempts = @($attempts)
}

$summaryPath = Join-Path $runRoot 'summary.json'
$summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

if ($RequireAnyUsable -and -not $summary.usable) {
    throw "No usable Rift capture method found. Wrote diagnostics to: $runRoot"
}

if ($Json) {
    $summary | ConvertTo-Json -Depth 12
}
else {
    Write-Host "Wrote Rift capture diagnostics: $summaryPath"
    $summary
}
