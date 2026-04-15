[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Key,
    [switch]$Json,
    [string]$Label,
    [int]$HoldMilliseconds = 700,
    [int]$WaitMilliseconds = 700,
    [int]$InterKeyDelayMilliseconds = 60,
    [int]$FocusSettleMilliseconds = 500,
    [int]$PostKeySettleMilliseconds = 150,
    [int]$WarningCountdownSeconds = 3,
    [switch]$RefreshReaderBridge,
    [switch]$NoAhkFallback,
    [switch]$SkipBackgroundFocus,
    [switch]$SkipUiClearCheck,
    [switch]$SkipLiveInputWarning
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$captureScript = Join-Path $PSScriptRoot 'capture-actor-orientation.ps1'
$keyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'
$uiClearCheckScript = Join-Path $PSScriptRoot 'assert-rift-gameplay-ui-clear.ps1'
$tempPrefix = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), ('rift-actor-orientation-{0}' -f ([Guid]::NewGuid().ToString('N'))))
$tempOutputFile = '{0}.json' -f $tempPrefix
$tempPreviousFile = '{0}.previous.json' -f $tempPrefix
$backgroundProcessName = $null
$backgroundProcessAvailable = $SkipBackgroundFocus.IsPresent

if (-not $backgroundProcessAvailable) {
    foreach ($candidateProcessName in @('cheatengine-x86_64-SSE4-AVX2', 'Codex')) {
        try {
            $null = Get-Process -Name $candidateProcessName -ErrorAction Stop | Select-Object -First 1
            $backgroundProcessName = $candidateProcessName
            $backgroundProcessAvailable = $true
            break
        }
        catch {
        }
    }

    if (-not $backgroundProcessAvailable) {
        $backgroundProcessAvailable = $false
    }
}

function Normalize-AngleRadians {
    param([double]$Radians)

    $normalized = $Radians
    while ($normalized -gt [Math]::PI) {
        $normalized -= 2.0 * [Math]::PI
    }

    while ($normalized -lt -[Math]::PI) {
        $normalized += 2.0 * [Math]::PI
    }

    return $normalized
}

function Convert-RadiansToDegrees {
    param([double]$Radians)
    return $Radians * 180.0 / [Math]::PI
}

function ConvertFrom-JsonCompat {
    param(
        [Parameter(Mandatory = $true)]
        [string]$JsonText,
        [int]$Depth = 20
    )

    if ($PSVersionTable.PSVersion.Major -ge 6) {
        return $JsonText | ConvertFrom-Json -Depth $Depth
    }

    return $JsonText | ConvertFrom-Json
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

    return ConvertFrom-JsonCompat -JsonText ([string]$json) -Depth 30
}

function Assert-UiClear {
    if ($SkipUiClearCheck) {
        return $null
    }

    $uiCheckOutput = '{0}.ui-check.json' -f $tempPrefix
    $json = & $uiClearCheckScript -Json
    if ($LASTEXITCODE -ne 0) {
        throw 'Gameplay UI clear-check failed before sending input.'
    }

    [System.IO.File]::WriteAllText($uiCheckOutput, [string]$json)
    $document = ConvertFrom-JsonCompat -JsonText ([string]$json) -Depth 20
    if (-not $document.SafeForGameplayInput) {
        $screenshot = if ($document.ScreenshotPath) { [string]$document.ScreenshotPath } else { 'n/a' }
        throw "Blocking gameplay UI detected before stimulus. Screenshot: $screenshot"
    }

    return $document
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

function Format-Nullable {
    param(
        $Value,
        [string]$Format = '0.000'
    )

    if ($null -eq $Value) {
        return 'n/a'
    }

    return ([double]$Value).ToString($Format, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Show-LiveInputWarning {
    param([int]$CountdownSeconds)

    if ($SkipLiveInputWarning) {
        return
    }

    Write-Host ''
    Write-Host '■■■ LIVE INPUT WARNING ■■■'
    Write-Host 'DO NOT TYPE, CLICK, OR PRESS ANYTHING'
    Write-Host 'WAIT UNTIL I SAY THE TEST IS DONE'

    if ($CountdownSeconds -gt 0) {
        for ($remaining = $CountdownSeconds; $remaining -ge 1; $remaining--) {
            Write-Host ("TEST STARTING IN {0}..." -f $remaining)
            Start-Sleep -Seconds 1
        }
    }

    Write-Host 'TEST STARTING NOW'
    Write-Host ''
}

$effectiveLabel = if ([string]::IsNullOrWhiteSpace($Label)) { $Key.ToLowerInvariant() } else { $Label }
$before = Invoke-Capture -CaptureLabel ("before-{0}" -f $effectiveLabel)
$uiClear = Assert-UiClear
Show-LiveInputWarning -CountdownSeconds $WarningCountdownSeconds

$keyArguments = @{
    Key = $Key
    HoldMilliseconds = $HoldMilliseconds
    InterKeyDelayMilliseconds = $InterKeyDelayMilliseconds
    FocusSettleMilliseconds = $FocusSettleMilliseconds
    PostKeySettleMilliseconds = $PostKeySettleMilliseconds
}

if (-not $backgroundProcessAvailable) {
    $keyArguments['SkipBackgroundFocus'] = $true
}
elseif (-not [string]::IsNullOrWhiteSpace($backgroundProcessName)) {
    $keyArguments['BackgroundProcessName'] = $backgroundProcessName
}

& $keyScript @keyArguments *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Stimulus key '$Key' failed."
}

Start-Sleep -Milliseconds $WaitMilliseconds
$after = Invoke-Capture -CaptureLabel ("after-{0}" -f $effectiveLabel)

$beforeEstimate = $before.ReaderOrientation.PreferredEstimate
$afterEstimate = $after.ReaderOrientation.PreferredEstimate

$yawDeltaRadians = $null
$yawDeltaDegrees = $null
if ($null -ne $beforeEstimate.YawRadians -and $null -ne $afterEstimate.YawRadians) {
    $yawDeltaRadians = Normalize-AngleRadians -Radians ([double]$afterEstimate.YawRadians - [double]$beforeEstimate.YawRadians)
    $yawDeltaDegrees = Convert-RadiansToDegrees -Radians $yawDeltaRadians
}

$pitchDeltaRadians = $null
$pitchDeltaDegrees = $null
if ($null -ne $beforeEstimate.PitchRadians -and $null -ne $afterEstimate.PitchRadians) {
    $pitchDeltaRadians = Normalize-AngleRadians -Radians ([double]$afterEstimate.PitchRadians - [double]$beforeEstimate.PitchRadians)
    $pitchDeltaDegrees = Convert-RadiansToDegrees -Radians $pitchDeltaRadians
}

$result = [pscustomobject]@{
    Mode = 'actor-orientation-stimulus'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    Label = $effectiveLabel
    Key = $Key
    HoldMilliseconds = $HoldMilliseconds
    WaitMilliseconds = $WaitMilliseconds
    InterKeyDelayMilliseconds = $InterKeyDelayMilliseconds
    FocusSettleMilliseconds = $FocusSettleMilliseconds
    PostKeySettleMilliseconds = $PostKeySettleMilliseconds
    UiClearCheck = $uiClear
    Before = $before
    After = $after
    Comparison = [pscustomobject]@{
        YawDeltaRadians = $yawDeltaRadians
        YawDeltaDegrees = $yawDeltaDegrees
        PitchDeltaRadians = $pitchDeltaRadians
        PitchDeltaDegrees = $pitchDeltaDegrees
        CoordDeltaMagnitude = Get-CoordDeltaMagnitude -BeforeCoord $before.ReaderOrientation.PlayerCoord -AfterCoord $after.ReaderOrientation.PlayerCoord
        VectorDeltaMagnitude = Get-VectorDeltaMagnitude -BeforeVector $beforeEstimate.Vector -AfterVector $afterEstimate.Vector
    }
    KeyDeliveryBackgroundProcess = $backgroundProcessName
    UsedForegroundSendInput = -not $backgroundProcessAvailable
}

try {
    if ($Json) {
        Write-Output ($result | ConvertTo-Json -Depth 40)
        return
    }

    Write-Host "Actor orientation stimulus"
    Write-Host ("Key:                         {0}" -f $result.Key)
    Write-Host ("Hold/Wait ms:                {0} / {1}" -f $result.HoldMilliseconds, $result.WaitMilliseconds)
    Write-Host ("Before yaw/pitch (deg):      {0} / {1}" -f (Format-Nullable $beforeEstimate.YawDegrees '0.000'), (Format-Nullable $beforeEstimate.PitchDegrees '0.000'))
    Write-Host ("After yaw/pitch (deg):       {0} / {1}" -f (Format-Nullable $afterEstimate.YawDegrees '0.000'), (Format-Nullable $afterEstimate.PitchDegrees '0.000'))
    Write-Host ("Yaw/pitch delta (deg):       {0} / {1}" -f (Format-Nullable $result.Comparison.YawDeltaDegrees '0.000'), (Format-Nullable $result.Comparison.PitchDeltaDegrees '0.000'))
    Write-Host ("Vector delta magnitude:      {0}" -f (Format-Nullable $result.Comparison.VectorDeltaMagnitude '0.000000'))
    Write-Host ("Coord delta magnitude:       {0}" -f (Format-Nullable $result.Comparison.CoordDeltaMagnitude '0.000000'))
}
finally {
    Remove-Item -LiteralPath $tempOutputFile, $tempPreviousFile -ErrorAction SilentlyContinue
}
