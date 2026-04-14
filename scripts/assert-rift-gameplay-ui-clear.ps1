[CmdletBinding()]
param(
    [switch]$Json,
    [string]$ProcessName = 'rift_x64',
    [string]$TitleContains = 'RIFT',
    [string]$OutputPath,
    [switch]$FailIfBlocked
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$windowToolsScript = Join-Path $repoRoot 'tools\rift-game-mcp\helpers\window-tools.ps1'

if (-not (Test-Path -LiteralPath $windowToolsScript)) {
    throw "Window tools helper was not found: $windowToolsScript"
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $OutputPath = Join-Path $repoRoot "artifacts\ui-check\rift-ui-check-$timestamp.png"
}

Add-Type -AssemblyName System.Drawing

function Invoke-WindowCapture {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetPath
    )

    $json = & $windowToolsScript `
        -Operation capture `
        -ProcessName $ProcessName `
        -TitleContains $TitleContains `
        -OutputPath $TargetPath

    if ([string]::IsNullOrWhiteSpace([string]$json)) {
        throw "Window capture failed."
    }

    return $json | ConvertFrom-Json -Depth 10
}

function New-Rect {
    param(
        [int]$ImageWidth,
        [int]$ImageHeight,
        [double]$XFactor,
        [double]$YFactor,
        [double]$WidthFactor,
        [double]$HeightFactor
    )

    $x = [Math]::Max(0, [int][Math]::Floor($ImageWidth * $XFactor))
    $y = [Math]::Max(0, [int][Math]::Floor($ImageHeight * $YFactor))
    $width = [Math]::Max(1, [int][Math]::Floor($ImageWidth * $WidthFactor))
    $height = [Math]::Max(1, [int][Math]::Floor($ImageHeight * $HeightFactor))

    if (($x + $width) -gt $ImageWidth) {
        $width = $ImageWidth - $x
    }

    if (($y + $height) -gt $ImageHeight) {
        $height = $ImageHeight - $y
    }

    return [System.Drawing.Rectangle]::new($x, $y, $width, $height)
}

function Convert-Rect {
    param([System.Drawing.Rectangle]$Rect)

    return [pscustomobject]@{
        x = $Rect.X
        y = $Rect.Y
        width = $Rect.Width
        height = $Rect.Height
    }
}

function Test-DarkPixel {
    param([System.Drawing.Color]$Color)

    return ($Color.R -le 72) -and ($Color.G -le 82) -and ($Color.B -le 92)
}

function Test-TealPixel {
    param([System.Drawing.Color]$Color)

    return
        ($Color.R -ge 20) -and ($Color.R -le 125) -and
        ($Color.G -ge 80) -and ($Color.G -le 200) -and
        ($Color.B -ge 70) -and ($Color.B -le 190) -and
        ($Color.G -ge ($Color.R + 15)) -and
        ($Color.B -ge ($Color.R + 5)) -and
        ([Math]::Abs([int]$Color.G - [int]$Color.B) -le 75)
}

function Get-RegionStats {
    param(
        [Parameter(Mandatory = $true)]
        [System.Drawing.Bitmap]$Bitmap,

        [Parameter(Mandatory = $true)]
        [System.Drawing.Rectangle]$Rect
    )

    $darkPixels = 0
    $tealPixels = 0
    $activeRows = 0
    $maxActiveRun = 0
    $currentActiveRun = 0
    $rowTealThreshold = [Math]::Max(10, [int][Math]::Floor($Rect.Width * 0.08))
    $rowDarkThreshold = [Math]::Max(20, [int][Math]::Floor($Rect.Width * 0.20))

    for ($y = $Rect.Top; $y -lt $Rect.Bottom; $y++) {
        $rowDark = 0
        $rowTeal = 0

        for ($x = $Rect.Left; $x -lt $Rect.Right; $x++) {
            $pixel = $Bitmap.GetPixel($x, $y)

            if (Test-DarkPixel -Color $pixel) {
                $darkPixels++
                $rowDark++
            }

            if (Test-TealPixel -Color $pixel) {
                $tealPixels++
                $rowTeal++
            }
        }

        $rowIsActive = ($rowTeal -ge $rowTealThreshold) -and ($rowDark -ge $rowDarkThreshold)
        if ($rowIsActive) {
            $activeRows++
            $currentActiveRun++
            if ($currentActiveRun -gt $maxActiveRun) {
                $maxActiveRun = $currentActiveRun
            }
        }
        else {
            $currentActiveRun = 0
        }
    }

    $pixelCount = [Math]::Max(1, $Rect.Width * $Rect.Height)
    $rowCount = [Math]::Max(1, $Rect.Height)

    return [pscustomobject]@{
        darkPixelCount = $darkPixels
        tealPixelCount = $tealPixels
        darkPercent = [Math]::Round(($darkPixels * 100.0) / $pixelCount, 4)
        tealPercent = [Math]::Round(($tealPixels * 100.0) / $pixelCount, 4)
        activeRowCount = $activeRows
        activeRowPercent = [Math]::Round(($activeRows * 100.0) / $rowCount, 4)
        maxActiveRowRun = $maxActiveRun
        region = (Convert-Rect -Rect $Rect)
    }
}

$capture = Invoke-WindowCapture -TargetPath $OutputPath
$bitmap = New-Object System.Drawing.Bitmap $capture.screenshotPath

try {
    $width = $bitmap.Width
    $height = $bitmap.Height

    $centerMenuRect = New-Rect -ImageWidth $width -ImageHeight $height -XFactor 0.39 -YFactor 0.14 -WidthFactor 0.22 -HeightFactor 0.68
    $centerCoreRect = New-Rect -ImageWidth $width -ImageHeight $height -XFactor 0.42 -YFactor 0.20 -WidthFactor 0.16 -HeightFactor 0.56

    $centerMenuStats = Get-RegionStats -Bitmap $bitmap -Rect $centerMenuRect
    $centerCoreStats = Get-RegionStats -Bitmap $bitmap -Rect $centerCoreRect

    $centeredMenuCandidate =
        ([double]$centerMenuStats.tealPercent -ge 1.0) -and
        ([double]$centerMenuStats.darkPercent -ge 18.0) -and
        ([int]$centerMenuStats.maxActiveRowRun -ge [Math]::Max(40, [int][Math]::Floor($centerMenuRect.Height * 0.20))) -and
        ([double]$centerCoreStats.darkPercent -ge 22.0)

    $blockers = New-Object System.Collections.Generic.List[object]
    if ($centeredMenuCandidate) {
        $blockers.Add([pscustomobject]@{
            type = 'centered_modal_menu_candidate'
            confidence = 'medium'
            reason = 'Central screenshot region contains a tall dark panel with repeated teal button-like rows.'
            region = $centerMenuStats.region
        }) | Out-Null
    }

    $document = [pscustomobject]@{
        Mode = 'rift-gameplay-ui-clear-check'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
        ProcessName = $ProcessName
        TitleContains = $TitleContains
        Window = $capture.window
        ScreenshotPath = $capture.screenshotPath
        ImageSize = $capture.imageSize
        SafeForGameplayInput = ($blockers.Count -eq 0)
        BlockerCount = $blockers.Count
        Blockers = @($blockers.ToArray())
        Heuristics = [pscustomobject]@{
            CenterMenuRegion = $centerMenuStats
            CenterCoreRegion = $centerCoreStats
        }
        Notes = @(
            'This is a screenshot heuristic gate, not OCR or full visual understanding.',
            'It is intended to stop obvious centered modal/menu states before actor-orientation key stimuli.'
        )
    }

    if ($FailIfBlocked -and -not $document.SafeForGameplayInput) {
        $message = "Blocking UI/menu candidate detected. Screenshot: $($document.ScreenshotPath)"
        if ($Json) {
            $document | ConvertTo-Json -Depth 12 | Write-Output
        }
        throw $message
    }

    if ($Json) {
        $document | ConvertTo-Json -Depth 12 | Write-Output
        exit 0
    }

    Write-Host "Rift gameplay UI clear check"
    Write-Host ("Screenshot:                 {0}" -f $document.ScreenshotPath)
    Write-Host ("Safe for gameplay input:    {0}" -f $document.SafeForGameplayInput)
    Write-Host ("Blocker count:              {0}" -f $document.BlockerCount)
    Write-Host ("Center menu dark/teal %:    {0} / {1}" -f $centerMenuStats.darkPercent, $centerMenuStats.tealPercent)
    Write-Host ("Center menu max row run:    {0}" -f $centerMenuStats.maxActiveRowRun)
    if ($document.BlockerCount -gt 0) {
        foreach ($blocker in $document.Blockers) {
            Write-Host ("Blocker:                    {0} ({1})" -f $blocker.type, $blocker.reason)
        }
    }
}
finally {
    $bitmap.Dispose()
}
