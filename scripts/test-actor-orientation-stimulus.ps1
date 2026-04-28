[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Key,
    [switch]$Json,
    [string]$Label,
    [int]$HoldMilliseconds = 700,
    [int]$WaitMilliseconds = 250,
    [switch]$RefreshReaderBridge,
    [switch]$NoAhkFallback,
    [switch]$SkipBackgroundFocus,
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$captureScript = Join-Path $PSScriptRoot 'capture-actor-orientation.ps1'
$keyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'
$tempPrefix = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), ('rift-actor-orientation-{0}' -f ([Guid]::NewGuid().ToString('N'))))
$tempOutputFile = '{0}.json' -f $tempPrefix
$tempPreviousFile = '{0}.previous.json' -f $tempPrefix
$useSkipBackgroundFocus = $SkipBackgroundFocus.IsPresent
$backgroundProcessAvailable = $false
$coordMovementThreshold = 0.01

if (-not $useSkipBackgroundFocus) {
    try {
        $null = Get-Process -Name 'cheatengine-x86_64-SSE4-AVX2' -ErrorAction Stop | Select-Object -First 1
        $backgroundProcessAvailable = $true
    }
    catch {
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

function Invoke-Capture {
    param([Parameter(Mandatory = $true)][string]$CaptureLabel)

    $captureArguments = @{
        Json = $true
        Label = $CaptureLabel
        OutputFile = $tempOutputFile
        PreviousFile = $tempPreviousFile
        RefreshReaderBridge = $true
        ProcessName = $ProcessName
    }
    if ($ProcessId -gt 0) {
        $captureArguments['ProcessId'] = $ProcessId
    }
    if ($NoAhkFallback) {
        $captureArguments['NoAhkFallback'] = $true
    }

    $json = & $captureScript @captureArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Actor orientation capture failed for '$CaptureLabel'."
    }

    return $json | ConvertFrom-Json -Depth 30
}

function Test-CoordMovementConfirmed {
    param($DeltaMagnitude)

    if ($null -eq $DeltaMagnitude) {
        return $false
    }

    return ([double]$DeltaMagnitude -gt $coordMovementThreshold)
}

function Get-PreferredLiveCoordDeltaMagnitude {
    param(
        $BeforeCapture,
        $AfterCapture
    )

    if ($null -eq $BeforeCapture -or $null -eq $AfterCapture) {
        return $null
    }

    $beforeReader = $BeforeCapture.ReaderOrientation
    $afterReader = $AfterCapture.ReaderOrientation
    if ($null -eq $beforeReader -or $null -eq $afterReader) {
        return $null
    }

    $beforeLive = $beforeReader.LiveSourceSample
    $afterLive = $afterReader.LiveSourceSample
    if ($null -eq $beforeLive -or $null -eq $afterLive) {
        return $null
    }

    $coord48Delta = Get-CoordDeltaMagnitude -BeforeCoord $beforeLive.Coord48 -AfterCoord $afterLive.Coord48
    $coord88Delta = Get-CoordDeltaMagnitude -BeforeCoord $beforeLive.Coord88 -AfterCoord $afterLive.Coord88

    if ($beforeReader.LiveSourceCoord48MatchesPlayerCoord -or $afterReader.LiveSourceCoord48MatchesPlayerCoord) {
        return $coord48Delta
    }

    if ($beforeReader.LiveSourceCoord88MatchesPlayerCoord -or $afterReader.LiveSourceCoord88MatchesPlayerCoord) {
        return $coord88Delta
    }

    if ($null -eq $coord48Delta) {
        return $coord88Delta
    }

    if ($null -eq $coord88Delta) {
        return $coord48Delta
    }

    return [Math]::Max([double]$coord48Delta, [double]$coord88Delta)
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

function Assert-ExactStimulusTarget {
    if ($ProcessId -le 0 -and [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
        throw "Actor orientation stimulus uses live input and requires -ProcessId or -TargetWindowHandle. Refusing name-only '$ProcessName' targeting."
    }
}

$effectiveLabel = if ([string]::IsNullOrWhiteSpace($Label)) { $Key.ToLowerInvariant() } else { $Label }
$before = Invoke-Capture -CaptureLabel ("before-{0}" -f $effectiveLabel)

Assert-ExactStimulusTarget
$keyArguments = @{
    Key = $Key
    HoldMilliseconds = $HoldMilliseconds
    TargetProcessName = $ProcessName
}

if ($ProcessId -gt 0) {
    $keyArguments['TargetProcessId'] = $ProcessId
}
if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
    $keyArguments['TargetWindowHandle'] = $TargetWindowHandle
}
if ($useSkipBackgroundFocus -or -not $backgroundProcessAvailable) {
    $keyArguments['SkipBackgroundFocus'] = $true
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
    ProcessName = $ProcessName
    ProcessId = if ($ProcessId -gt 0) { $ProcessId } else { $null }
    TargetWindowHandle = $TargetWindowHandle
    Label = $effectiveLabel
    Key = $Key
    HoldMilliseconds = $HoldMilliseconds
    WaitMilliseconds = $WaitMilliseconds
    Before = $before
    After = $after
    Comparison = [pscustomobject]@{
        YawDeltaRadians = $yawDeltaRadians
        YawDeltaDegrees = $yawDeltaDegrees
        PitchDeltaRadians = $pitchDeltaRadians
        PitchDeltaDegrees = $pitchDeltaDegrees
        CoordDeltaMagnitude = Get-CoordDeltaMagnitude -BeforeCoord $before.ReaderOrientation.PlayerCoord -AfterCoord $after.ReaderOrientation.PlayerCoord
        AddonCoordDeltaMagnitude = Get-CoordDeltaMagnitude -BeforeCoord $before.ReaderOrientation.PlayerCoord -AfterCoord $after.ReaderOrientation.PlayerCoord
        AddonCoordMovementConfirmed = $false
        AddonCoordSource = 'ReaderBridgeSnapshot.PlayerCoord'
        AddonSnapshotBeforeUtc = $before.ReaderOrientation.SnapshotLoadedAtUtc
        AddonSnapshotAfterUtc = $after.ReaderOrientation.SnapshotLoadedAtUtc
        PreferredLiveCoordDeltaMagnitude = Get-PreferredLiveCoordDeltaMagnitude -BeforeCapture $before -AfterCapture $after
        LiveCoord48DeltaMagnitude = Get-CoordDeltaMagnitude -BeforeCoord $before.ReaderOrientation.LiveSourceSample.Coord48 -AfterCoord $after.ReaderOrientation.LiveSourceSample.Coord48
        LiveCoord88DeltaMagnitude = Get-CoordDeltaMagnitude -BeforeCoord $before.ReaderOrientation.LiveSourceSample.Coord88 -AfterCoord $after.ReaderOrientation.LiveSourceSample.Coord88
        LiveCoordMovementConfirmed = $false
        AnyCoordMovementConfirmed = $false
        TelemetryAlignmentStatus = $null
        TelemetryBlocker = $false
        VectorDeltaMagnitude = Get-VectorDeltaMagnitude -BeforeVector $beforeEstimate.Vector -AfterVector $afterEstimate.Vector
    }
}

$result.Comparison.AddonCoordMovementConfirmed = Test-CoordMovementConfirmed -DeltaMagnitude $result.Comparison.AddonCoordDeltaMagnitude
$result.Comparison.LiveCoordMovementConfirmed = `
    (Test-CoordMovementConfirmed -DeltaMagnitude $result.Comparison.PreferredLiveCoordDeltaMagnitude) -or `
    (Test-CoordMovementConfirmed -DeltaMagnitude $result.Comparison.LiveCoord48DeltaMagnitude) -or `
    (Test-CoordMovementConfirmed -DeltaMagnitude $result.Comparison.LiveCoord88DeltaMagnitude)
$result.Comparison.AnyCoordMovementConfirmed = `
    $result.Comparison.AddonCoordMovementConfirmed -or `
    $result.Comparison.LiveCoordMovementConfirmed

if ($result.Comparison.AddonCoordMovementConfirmed -and $result.Comparison.LiveCoordMovementConfirmed) {
    $result.Comparison.TelemetryAlignmentStatus = 'aligned-success'
}
elseif ($result.Comparison.AddonCoordMovementConfirmed -or $result.Comparison.LiveCoordMovementConfirmed) {
    $result.Comparison.TelemetryAlignmentStatus = 'source-mismatch'
    $result.Comparison.TelemetryBlocker = $true
}
else {
    $result.Comparison.TelemetryAlignmentStatus = 'no-coord-movement-confirmed'
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
    Write-Host ("Addon coord delta magnitude: {0}" -f (Format-Nullable $result.Comparison.AddonCoordDeltaMagnitude '0.000000'))
    Write-Host ("Addon coord confirmed:       {0}" -f $result.Comparison.AddonCoordMovementConfirmed)
    Write-Host ("Preferred live coord delta:  {0}" -f (Format-Nullable $result.Comparison.PreferredLiveCoordDeltaMagnitude '0.000000'))
    Write-Host ("Live coord48/88 delta:       {0} / {1}" -f (Format-Nullable $result.Comparison.LiveCoord48DeltaMagnitude '0.000000'), (Format-Nullable $result.Comparison.LiveCoord88DeltaMagnitude '0.000000'))
    Write-Host ("Live coord confirmed:        {0}" -f $result.Comparison.LiveCoordMovementConfirmed)
    Write-Host ("Any coord movement seen:     {0}" -f $result.Comparison.AnyCoordMovementConfirmed)
    Write-Host ("Telemetry alignment:         {0}" -f $result.Comparison.TelemetryAlignmentStatus)
    Write-Host ("Telemetry blocker:           {0}" -f $result.Comparison.TelemetryBlocker)
}
finally {
    Remove-Item -LiteralPath $tempOutputFile, $tempPreviousFile -ErrorAction SilentlyContinue
}
