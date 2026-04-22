[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [string]$WaypointFile,
    [string]$AnchorCacheFile,
    [string]$ReaderBridgeSnapshotFile,
    [string]$StartWaypointId = 'smoke_start',
    [string]$DestinationWaypointId = 'smoke_destination',
    [string]$StartLabel = 'Smoke Start',
    [string]$DestinationLabel = 'Smoke Destination',
    [double]$DistanceForward = 3.0,
    [double]$ArrivalRadius = 5.0,
    [int]$ForwardPulseMilliseconds = 250,
    [int]$PostPulseSampleDelayMilliseconds = 150,
    [double]$StartRadius = 1.5,
    [int]$NoProgressWindowMilliseconds = 3000,
    [double]$MinimumProgressDistance = 0.1,
    [double]$WrongWayToleranceDistance = 1.0,
    [int]$MaxTravelSeconds = 12,
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
    & $refreshScript -NoReader -NoAhkFallback -SkipBackgroundFocus
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
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $process = Get-Process -Name $Name -ErrorAction SilentlyContinue | Select-Object -First 1
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

$orientation = Invoke-ScriptJson -ScriptFile $actorOrientationScript -Arguments @(
    '-Json',
    '-ProcessName', $ProcessName
)
$processState = Get-ProcessState -Name $ProcessName

$yawRadians = $orientation.ReaderOrientation.PreferredEstimate.YawRadians
if ($null -eq $yawRadians) {
    throw "Actor orientation did not return a usable yaw."
}

$destinationX = $startX + ([Math]::Cos([double]$yawRadians) * $DistanceForward)
$destinationY = $startY
$destinationZ = $startZ + ([Math]::Sin([double]$yawRadians) * $DistanceForward)

$document = [ordered]@{
    schemaVersion = 1
    provenance    = [ordered]@{
        kind = 'smoke-route'
        generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        processName = $ProcessName
        processId = $processState.Id
        processStartTimeUtc = $processState.StartTimeUtc
        processResponding = $processState.Responding
        readerBridgeSnapshotSourceFile = [string]$snapshot.SourceFile
        readerBridgeExportCount = $snapshot.ExportCount
        orientationResolutionMode = [string]$orientation.ReaderOrientation.ResolutionMode
        selectedSourceAddress = [string]$orientation.ReaderOrientation.SelectedSourceAddress
        basisPrimaryForwardOffset = [string]$orientation.ReaderOrientation.BasisPrimaryForwardOffset
        basisDuplicateForwardOffset = [string]$orientation.ReaderOrientation.BasisDuplicateForwardOffset
        yawDegrees = [double]$orientation.ReaderOrientation.PreferredEstimate.YawDegrees
        distanceForward = $DistanceForward
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
    processName = $ProcessName
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
    yawRadians = [double]$yawRadians
    yawDegrees = [double]$orientation.ReaderOrientation.PreferredEstimate.YawDegrees
    distanceForward = $DistanceForward
    destinationX = $destinationX
    destinationY = $destinationY
    destinationZ = $destinationZ
    arrivalRadius = $ArrivalRadius
} | ConvertTo-Json -Depth 10
