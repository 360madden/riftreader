[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [string]$WaypointFile,
    [string]$AnchorCacheFile,
    [string]$ReaderBridgeSnapshotFile,
    [string]$StartWaypointId = 'smoke_start',
    [string]$DestinationWaypointId = 'smoke_destination',
    [string]$StartLabel = 'Smoke Start',
    [string]$DestinationLabel = 'Smoke Destination',
    [double]$DistanceForward = 2.6,
    [double]$BearingOffsetDegrees = 0.0,
    [double]$ArrivalRadius = 2.1,
    [int]$ForwardPulseMilliseconds = 250,
    [int]$PostPulseSampleDelayMilliseconds = 150,
    [double]$StartRadius = 1.5,
    [int]$NoProgressWindowMilliseconds = 3000,
    [double]$MinimumProgressDistance = 0.05,
    [double]$WrongWayToleranceDistance = 1.0,
    [int]$MaxTravelSeconds = 20,
    [int]$ScanContextBytes = 192,
    [int]$MaxHits = 12,
    [switch]$SkipRefresh
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$actorOrientationScript = Join-Path $repoRoot 'scripts\capture-actor-orientation.ps1'
$refreshScript = Join-Path $repoRoot 'scripts\refresh-readerbridge-export.ps1'
$WaypointFile = if ([string]::IsNullOrWhiteSpace($WaypointFile)) {
    Join-Path $PSScriptRoot 'smoke-test-waypoints.json'
}
else {
    $WaypointFile
}
$AnchorCacheFile = if ([string]::IsNullOrWhiteSpace($AnchorCacheFile)) {
    Join-Path $repoRoot 'scripts\captures\player-current-anchor.json'
}
else {
    $AnchorCacheFile
}
$resolvedWaypointFile = [System.IO.Path]::GetFullPath($WaypointFile)

function Invoke-ReaderJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & dotnet run --project $readerProject -- @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Reader command failed (`$LASTEXITCODE=$exitCode): $($output -join [Environment]::NewLine)"
    }

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json
}

function Get-ReaderTargetArguments {
    if ($ProcessId -gt 0) {
        return @('--pid', $ProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    }

    return @('--process-name', $ProcessName)
}

function Start-LiveInteractionCountdown {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Reason
    )

    Write-Host ""
    Write-Host "[SmokeRoute] Live interaction pending: $Reason" -ForegroundColor Yellow
    Write-Host "[SmokeRoute] Bring Rift to the foreground now. The script will preserve the current focus and start in 10 seconds." -ForegroundColor Yellow

    for ($remaining = 10; $remaining -ge 1; $remaining--) {
        Write-Host ("[SmokeRoute] Starting in {0}..." -f $remaining) -ForegroundColor Yellow
        Start-Sleep -Seconds 1
    }
}

function Invoke-Refresh {
    if ($SkipRefresh) {
        return
    }

    Start-LiveInteractionCountdown -Reason 'refresh ReaderBridge export via /reloadui'

    Write-Host ""
    Write-Host "[SmokeRoute] Refreshing ReaderBridge export..." -ForegroundColor Cyan
    $refreshArguments = @{
        NoReader = $true
        NoAhkFallback = $true
        SkipBackgroundFocus = $true
        ProcessName = $ProcessName
    }
    if ($ProcessId -gt 0) {
        $refreshArguments['ProcessId'] = $ProcessId
    }
    if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
        $refreshArguments['TargetWindowHandle'] = $TargetWindowHandle
    }

    & $refreshScript @refreshArguments
    Start-Sleep -Milliseconds 750
}

function Invoke-ScriptJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptFile,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & pwsh -NoProfile -ExecutionPolicy Bypass -File $ScriptFile @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Script command failed (`$LASTEXITCODE=$exitCode): $($output -join [Environment]::NewLine)"
    }

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json
}

function Get-ProcessState {
    param(
        [string]$Name,
        [int]$Id
    )

    $process = if ($Id -gt 0) {
        Get-Process -Id $Id -ErrorAction SilentlyContinue
    }
    else {
        $matches = @(Get-Process -Name $Name -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 })
        if ($matches.Count -gt 1) {
            $ids = ($matches | Sort-Object Id | ForEach-Object { $_.Id }) -join ', '
            throw "Process name '$Name' matched multiple windowed processes ($ids). Use -ProcessId for route generation."
        }

        $matches | Select-Object -First 1
    }

    if ($null -eq $process) {
        return $null
    }

    $startTimeUtc = $null
    try {
        $startTimeUtc = $process.StartTime.ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    }
    catch {
        $startTimeUtc = $null
    }

    return [pscustomobject]@{
        Name = $process.ProcessName
        Id = $process.Id
        StartTimeUtc = $startTimeUtc
        Responding = $process.Responding
        MainWindowTitle = $process.MainWindowTitle
    }
}

function Get-OrientationOffsetValue {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$OrientationDocument,
        [Parameter(Mandatory = $true)]
        [string]$PrimaryPropertyName,
        [string]$FallbackPropertyName
    )

    if ($OrientationDocument.PSObject.Properties[$PrimaryPropertyName]) {
        $value = [string]$OrientationDocument.$PrimaryPropertyName
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            return $value
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($FallbackPropertyName) -and $OrientationDocument.PSObject.Properties[$FallbackPropertyName]) {
        $value = [string]$OrientationDocument.$FallbackPropertyName
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            return $value
        }
    }

    return $null
}

function Normalize-Radians {
    param([double]$Radians)

    $normalized = $Radians
    while ($normalized -gt [Math]::PI) {
        $normalized -= 2.0 * [Math]::PI
    }

    while ($normalized -le -[Math]::PI) {
        $normalized += 2.0 * [Math]::PI
    }

    return $normalized
}

function Convert-RadiansToDegrees {
    param([double]$Radians)

    return $Radians * 180.0 / [Math]::PI
}

function Get-NavigationBearingRadians {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$PreferredEstimate
    )

    $vector = if ($PreferredEstimate.PSObject.Properties['Vector']) { $PreferredEstimate.Vector } else { $null }
    if ($null -ne $vector -and
        $null -ne $vector.X -and
        $null -ne $vector.Z) {
        $vectorX = [double]$vector.X
        $vectorZ = [double]$vector.Z
        if ([double]::IsFinite($vectorX) -and
            [double]::IsFinite($vectorZ) -and
            ([Math]::Sqrt(($vectorX * $vectorX) + ($vectorZ * $vectorZ)) -gt [double]::Epsilon)) {
            return [Math]::Atan2($vectorX, $vectorZ)
        }
    }

    if ($null -ne $PreferredEstimate.YawRadians) {
        return Normalize-Radians -Radians (([Math]::PI / 2.0) - [double]$PreferredEstimate.YawRadians)
    }

    throw "Actor orientation did not return a usable movement-space navigation bearing."
}

if ($DistanceForward -le 0) {
    throw "DistanceForward must be positive."
}

Invoke-Refresh

$snapshotArguments = @('--readerbridge-snapshot', '--json')
if (-not [string]::IsNullOrWhiteSpace($ReaderBridgeSnapshotFile)) {
    $snapshotArguments += @('--readerbridge-snapshot-file', [System.IO.Path]::GetFullPath($ReaderBridgeSnapshotFile))
}

$snapshot = Invoke-ReaderJson -Arguments $snapshotArguments
$playerCoord = $snapshot.Current.Player.Coord
if ($null -eq $playerCoord -or
    $null -eq $playerCoord.X -or
    $null -eq $playerCoord.Y -or
    $null -eq $playerCoord.Z) {
    throw "ReaderBridge snapshot did not include a usable current player coordinate."
}

$startX = [double]$playerCoord.X
$startY = [double]$playerCoord.Y
$startZ = [double]$playerCoord.Z

$orientationArguments = @('-Json')
if ($ProcessId -gt 0) {
    $orientationArguments += @('-ProcessId', $ProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
}
else {
    $orientationArguments += @('-ProcessName', $ProcessName)
}
if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
    $orientationArguments += @('-TargetWindowHandle', $TargetWindowHandle)
}

$orientation = Invoke-ScriptJson -ScriptFile $actorOrientationScript -Arguments $orientationArguments
$processState = Get-ProcessState -Name $ProcessName -Id $ProcessId
if ($null -eq $processState) {
    throw "No target Rift process was found for route generation."
}
$readerOrientation = $orientation.ReaderOrientation
$basisPrimaryForwardOffset = Get-OrientationOffsetValue -OrientationDocument $readerOrientation -PrimaryPropertyName 'BasisPrimaryForwardOffset' -FallbackPropertyName 'BasisForwardOffset'
$basisDuplicateForwardOffset = Get-OrientationOffsetValue -OrientationDocument $readerOrientation -PrimaryPropertyName 'BasisDuplicateForwardOffset' -FallbackPropertyName ''

$preferredEstimate = $readerOrientation.PreferredEstimate
if ($null -eq $preferredEstimate) {
    throw "Actor orientation did not return a preferred estimate."
}

$yawRadians = $preferredEstimate.YawRadians
$navigationBearingRadians = Get-NavigationBearingRadians -PreferredEstimate $preferredEstimate
$destinationYawRadians = [double]$navigationBearingRadians + ([Math]::PI * ($BearingOffsetDegrees / 180.0))
$destinationX = $startX + ([Math]::Cos($destinationYawRadians) * $DistanceForward)
$destinationY = $startY
$destinationZ = $startZ + ([Math]::Sin($destinationYawRadians) * $DistanceForward)

$document = [ordered]@{
    schemaVersion = 1
    provenance    = [ordered]@{
        kind = 'smoke-route'
        generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        processName = $processState.Name
        processId = $processState.Id
        processStartTimeUtc = $processState.StartTimeUtc
        processResponding = $processState.Responding
        readerBridgeSnapshotSourceFile = [string]$snapshot.SourceFile
        readerBridgeExportCount = $snapshot.ExportCount
        orientationResolutionMode = [string]$readerOrientation.ResolutionMode
        selectedSourceAddress = [string]$readerOrientation.SelectedSourceAddress
        basisPrimaryForwardOffset = $basisPrimaryForwardOffset
        basisDuplicateForwardOffset = $basisDuplicateForwardOffset
        yawDegrees = [double]$readerOrientation.PreferredEstimate.YawDegrees
        navigationBearingDegrees = Convert-RadiansToDegrees -Radians $navigationBearingRadians
        distanceForward = $DistanceForward
        bearingOffsetDegrees = $BearingOffsetDegrees
        notes = @(
            'Generated from the current live player position and live actor-facing reader.',
            'Regenerate this smoke route after a Rift restart, zone move, or major position change before treating it as a current-session validation route.'
        )
    }
    movement      = [ordered]@{
        forwardKey = 'w'
        runKey = $null
        walkKey = $null
        defaultPace = 'keep'
        forwardPulseMilliseconds = $ForwardPulseMilliseconds
        postPulseSampleDelayMilliseconds = $PostPulseSampleDelayMilliseconds
        startRadius = $StartRadius
        defaultArrivalRadius = $ArrivalRadius
        noProgressWindowMilliseconds = $NoProgressWindowMilliseconds
        minimumProgressDistance = $MinimumProgressDistance
        wrongWayToleranceDistance = $WrongWayToleranceDistance
        maxTravelSeconds = $MaxTravelSeconds
    }
    waypoints     = @(
        [ordered]@{
            id = $StartWaypointId
            label = $StartLabel
            x = $startX
            y = $startY
            z = $startZ
            arrivalRadius = $ArrivalRadius
            pace = 'keep'
        },
        [ordered]@{
            id = $DestinationWaypointId
            label = $DestinationLabel
            x = $destinationX
            y = $destinationY
            z = $destinationZ
            arrivalRadius = $ArrivalRadius
            pace = 'keep'
        }
    )
}

$directory = Split-Path -Parent $resolvedWaypointFile
if (-not [string]::IsNullOrWhiteSpace($directory)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

$json = $document | ConvertTo-Json -Depth 20
[System.IO.File]::WriteAllText($resolvedWaypointFile, $json)

[pscustomobject]@{
    mode = 'new-forward-smoke-route'
    processName = $processState.Name
    processId = $processState.Id
    processStartTimeUtc = $processState.StartTimeUtc
    waypointFile = $resolvedWaypointFile
    startWaypointId = $StartWaypointId
    destinationWaypointId = $DestinationWaypointId
    startX = $startX
    startY = $startY
    startZ = $startZ
    coordSource = 'readerbridge-snapshot'
    readerBridgeSnapshotSourceFile = [string]$snapshot.SourceFile
    readerBridgeExportCount = $snapshot.ExportCount
    yawRadians = if ($null -ne $yawRadians) { [double]$yawRadians } else { $null }
    yawDegrees = [double]$readerOrientation.PreferredEstimate.YawDegrees
    navigationBearingRadians = [double]$navigationBearingRadians
    navigationBearingDegrees = Convert-RadiansToDegrees -Radians $navigationBearingRadians
    bearingOffsetDegrees = $BearingOffsetDegrees
    basisPrimaryForwardOffset = $basisPrimaryForwardOffset
    basisDuplicateForwardOffset = $basisDuplicateForwardOffset
    distanceForward = $DistanceForward
    destinationX = $destinationX
    destinationY = $destinationY
    destinationZ = $destinationZ
    arrivalRadius = $ArrivalRadius
} | ConvertTo-Json -Depth 10
