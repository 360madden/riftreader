[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TitleContains,
    [string]$OutputPath,
    [int[]]$Flags = @(2, 0, 1),
    [int]$SampleStep = 16,
    [int]$ContentTop = 40,
    [double]$MinContentNonBlackRatio = 0.05,
    [switch]$RequireUsable,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $root = Join-Path $repoRoot 'artifacts\tooltip-projection\printwindow-screenshots'
    New-Item -ItemType Directory -Force -Path $root | Out-Null
    $OutputPath = Join-Path $root ('capture-{0}.png' -f (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
}
elseif (-not [System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath = Join-Path $repoRoot $OutputPath
}

if ($SampleStep -le 0) {
    throw 'SampleStep must be greater than zero.'
}

if ($ContentTop -lt 0) {
    throw 'ContentTop must be non-negative.'
}

if ($Flags.Count -eq 0) {
    throw 'At least one PrintWindow flag value is required.'
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

$nativeCode = @'
using System;
using System.Runtime.InteropServices;
public static class RiftPrintWindowNative {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdcBlt, uint nFlags);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
}
'@
Add-Type -TypeDefinition $nativeCode -ErrorAction SilentlyContinue
Add-Type -AssemblyName System.Drawing

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
    $bodyStart = [Math]::Min($height - 1, [Math]::Max(0, $BodyTop))
    $totalSamples = 0
    $nonBlackSamples = 0
    $bodySamples = 0
    $bodyNonBlackSamples = 0
    $sumBrightness = 0.0
    $sumBrightnessSquared = 0.0
    $bodySumBrightness = 0.0
    $bodySumBrightnessSquared = 0.0

    for ($y = 0; $y -lt $height; $y += $Step) {
        for ($x = 0; $x -lt $width; $x += $Step) {
            $color = $Bitmap.GetPixel($x, $y)
            $brightness = ([double]$color.R + [double]$color.G + [double]$color.B) / 3.0
            $isNonBlack = $brightness -gt 4.0
            $totalSamples++
            $sumBrightness += $brightness
            $sumBrightnessSquared += ($brightness * $brightness)
            if ($isNonBlack) {
                $nonBlackSamples++
            }

            if ($y -ge $bodyStart) {
                $bodySamples++
                $bodySumBrightness += $brightness
                $bodySumBrightnessSquared += ($brightness * $brightness)
                if ($isNonBlack) {
                    $bodyNonBlackSamples++
                }
            }
        }
    }

    $averageBrightness = if ($totalSamples -gt 0) { $sumBrightness / $totalSamples } else { 0.0 }
    $bodyAverageBrightness = if ($bodySamples -gt 0) { $bodySumBrightness / $bodySamples } else { 0.0 }
    $variance = if ($totalSamples -gt 0) { [Math]::Max(0.0, ($sumBrightnessSquared / $totalSamples) - ($averageBrightness * $averageBrightness)) } else { 0.0 }
    $bodyVariance = if ($bodySamples -gt 0) { [Math]::Max(0.0, ($bodySumBrightnessSquared / $bodySamples) - ($bodyAverageBrightness * $bodyAverageBrightness)) } else { 0.0 }
    $nonBlackRatio = if ($totalSamples -gt 0) { $nonBlackSamples / [double]$totalSamples } else { 0.0 }
    $bodyNonBlackRatio = if ($bodySamples -gt 0) { $bodyNonBlackSamples / [double]$bodySamples } else { 0.0 }
    $isUsable = $bodyNonBlackRatio -ge $RequiredContentNonBlackRatio

    return [pscustomobject][ordered]@{
        width = $width
        height = $height
        sampleStep = $Step
        contentTop = $bodyStart
        totalSamples = $totalSamples
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

$rect = New-Object RiftPrintWindowNative+RECT
if (-not [RiftPrintWindowNative]::GetWindowRect($process.MainWindowHandle, [ref]$rect)) {
    throw 'GetWindowRect failed.'
}

$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
if ($width -le 0 -or $height -le 0) {
    throw "Invalid window rectangle: width=$width height=$height"
}

$parent = Split-Path -Parent $OutputPath
if (-not [string]::IsNullOrWhiteSpace($parent)) {
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
}

$attempts = [System.Collections.Generic.List[object]]::new()
$bestBitmap = $null
$bestAttempt = $null

foreach ($flag in $Flags) {
    $bitmap = New-Object System.Drawing.Bitmap $width, $height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $hdc = $graphics.GetHdc()
    $ok = $false
    try {
        $ok = [RiftPrintWindowNative]::PrintWindow($process.MainWindowHandle, $hdc, [uint32]$flag)
    }
    finally {
        $graphics.ReleaseHdc($hdc)
        $graphics.Dispose()
    }

    $quality = Get-BitmapQuality -Bitmap $bitmap -Step $SampleStep -BodyTop $ContentTop -RequiredContentNonBlackRatio $MinContentNonBlackRatio
    $attempt = [pscustomobject][ordered]@{
        flag = $flag
        ok = [bool]$ok
        quality = $quality
    }
    $attempts.Add($attempt) | Out-Null

    $isBetter = $null -eq $bestAttempt -or
        [double]$quality.contentNonBlackRatio -gt [double]$bestAttempt.quality.contentNonBlackRatio -or
        ([double]$quality.contentNonBlackRatio -eq [double]$bestAttempt.quality.contentNonBlackRatio -and [double]$quality.contentBrightnessStdDev -gt [double]$bestAttempt.quality.contentBrightnessStdDev)

    if ($isBetter) {
        if ($null -ne $bestBitmap) {
            $bestBitmap.Dispose()
        }
        $bestBitmap = $bitmap
        $bestAttempt = $attempt
    }
    else {
        $bitmap.Dispose()
    }

    if ($quality.isUsable) {
        break
    }
}

if ($null -eq $bestBitmap -or $null -eq $bestAttempt) {
    throw 'PrintWindow produced no capture attempts.'
}

try {
    $bestBitmap.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
}
finally {
    $bestBitmap.Dispose()
}

$result = [pscustomobject][ordered]@{
    ok = [bool]$bestAttempt.ok
    usable = [bool]$bestAttempt.quality.isUsable
    screenshotPath = $OutputPath
    processId = $process.Id
    processName = $process.ProcessName
    windowTitle = $process.MainWindowTitle
    windowHandle = ('0x{0:X}' -f $process.MainWindowHandle.ToInt64())
    isIconic = [RiftPrintWindowNative]::IsIconic($process.MainWindowHandle)
    windowRect = [ordered]@{
        left = $rect.Left
        top = $rect.Top
        right = $rect.Right
        bottom = $rect.Bottom
        width = $width
        height = $height
    }
    method = 'PrintWindow'
    selectedFlag = $bestAttempt.flag
    quality = $bestAttempt.quality
    attempts = @($attempts)
    controlsInput = $false
}

if ($RequireUsable -and -not $result.usable) {
    $result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath ($OutputPath + '.quality.json') -Encoding UTF8
    throw "PrintWindow capture appears black/unusable. Wrote diagnostic sidecar: $OutputPath.quality.json"
}

if ($Json) {
    $result | ConvertTo-Json -Depth 12
}
else {
    Write-Host "Saved PrintWindow capture: $OutputPath"
    $result
}
