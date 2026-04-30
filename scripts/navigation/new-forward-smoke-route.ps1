[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [string]$WaypointFile,
    [string]$AnchorCacheFile,
    [string]$ProofCoordAnchorFile,
    [string]$ReaderBridgeSnapshotFile,
    [switch]$IgnoreBehaviorBackedLead,
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
$ProofCoordAnchorFile = if ([string]::IsNullOrWhiteSpace($ProofCoordAnchorFile)) {
    Join-Path $repoRoot 'scripts\captures\telemetry-proof-coord-anchor.json'
}
else {
    $ProofCoordAnchorFile
}
$resolvedWaypointFile = [System.IO.Path]::GetFullPath($WaypointFile)
$resolvedProofCoordAnchorFile = [System.IO.Path]::GetFullPath($ProofCoordAnchorFile)

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

function Convert-HexStringToByteArray {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Hex
    )

    $normalized = ($Hex -replace '\s+', '').Trim()
    if ([string]::IsNullOrWhiteSpace($normalized) -or ($normalized.Length % 2) -ne 0) {
        return $null
    }

    $bytes = New-Object byte[] ($normalized.Length / 2)
    for ($index = 0; $index -lt $bytes.Length; $index++) {
        $bytes[$index] = [Convert]::ToByte($normalized.Substring($index * 2, 2), 16)
    }

    return $bytes
}

function Get-ProofCoordRelativeOffset {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$Anchor,
        [Parameter(Mandatory = $true)]
        [string]$PropertyName,
        [Parameter(Mandatory = $true)]
        [int]$DefaultValue
    )

    if (-not $Anchor.PSObject.Properties[$PropertyName] -or $null -eq $Anchor.$PropertyName) {
        return $DefaultValue
    }

    $value = [int]$Anchor.$PropertyName
    if ($value -lt 0) {
        throw "Proof coord anchor property '$PropertyName' must not be negative."
    }

    return $value
}

function Read-ProofCoordAnchorSample {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$Anchor
    )

    $coordRegionAddress = [string]$Anchor.CoordRegionAddress
    if ([string]::IsNullOrWhiteSpace($coordRegionAddress)) {
        throw "Proof coord anchor did not include CoordRegionAddress."
    }

    $coordXOffset = Get-ProofCoordRelativeOffset -Anchor $Anchor -PropertyName 'CoordXRelativeOffset' -DefaultValue 0
    $coordYOffset = Get-ProofCoordRelativeOffset -Anchor $Anchor -PropertyName 'CoordYRelativeOffset' -DefaultValue 4
    $coordZOffset = Get-ProofCoordRelativeOffset -Anchor $Anchor -PropertyName 'CoordZRelativeOffset' -DefaultValue 8
    $readLength = ([Math]::Max($coordXOffset, [Math]::Max($coordYOffset, $coordZOffset)) + 4)

    $memoryRead = Invoke-ReaderJson -Arguments @((Get-ReaderTargetArguments) + @(
        '--address', $coordRegionAddress,
        '--length', $readLength.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json'
    ))

    if ($null -eq $memoryRead -or [string]::IsNullOrWhiteSpace([string]$memoryRead.BytesHex)) {
        throw "Proof coord anchor memory read returned no bytes at $coordRegionAddress."
    }

    $bytes = Convert-HexStringToByteArray -Hex ([string]$memoryRead.BytesHex)
    if ($null -eq $bytes -or $bytes.Length -lt $readLength) {
        throw "Proof coord anchor memory read returned fewer than $readLength bytes at $coordRegionAddress."
    }

    return [pscustomobject]@{
        AddressHex = $coordRegionAddress
        CoordX = [BitConverter]::ToSingle($bytes, $coordXOffset)
        CoordY = [BitConverter]::ToSingle($bytes, $coordYOffset)
        CoordZ = [BitConverter]::ToSingle($bytes, $coordZOffset)
    }
}

function Test-CoordinateDeltaWithinTolerance {
    param(
        [Parameter(Mandatory = $true)]
        [double]$DeltaX,
        [Parameter(Mandatory = $true)]
        [double]$DeltaY,
        [Parameter(Mandatory = $true)]
        [double]$DeltaZ
    )

    return (
        [Math]::Abs($DeltaX) -le 0.25 -and
        [Math]::Abs($DeltaY) -le 0.25 -and
        [Math]::Abs($DeltaZ) -le 0.25
    )
}

function Get-ProofCoordAnchorFromCache {
    if (-not (Test-Path -LiteralPath $resolvedProofCoordAnchorFile)) {
        throw "Proof coord-anchor file not found: $resolvedProofCoordAnchorFile"
    }

    $anchor = Get-Content -LiteralPath $resolvedProofCoordAnchorFile -Raw | ConvertFrom-Json -Depth 32
    if ($null -eq $anchor) {
        throw "Proof coord-anchor file was empty or invalid: $resolvedProofCoordAnchorFile"
    }

    if ($ProcessId -gt 0 -and $anchor.PSObject.Properties['ProcessId'] -and $null -ne $anchor.ProcessId -and [int]$anchor.ProcessId -ne $ProcessId) {
        throw "Proof coord anchor targets PID $($anchor.ProcessId), but smoke-route generation targets PID $ProcessId."
    }

    if ($anchor.PSObject.Properties['ProcessName'] -and
        -not [string]::IsNullOrWhiteSpace([string]$anchor.ProcessName) -and
        -not [string]::Equals([string]$anchor.ProcessName, $ProcessName, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Proof coord anchor targets process '$($anchor.ProcessName)', but smoke-route generation targets '$ProcessName'."
    }

    if ($null -eq $anchor.Match -or $anchor.Match.CoordMatchesWithinTolerance -ne $true) {
        throw "Proof coord anchor cache is not marked as coordinate-matched. Refresh it with scripts\resolve-proof-coord-anchor.ps1 before generating a route."
    }

    return $anchor
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

$proofAnchor = Get-ProofCoordAnchorFromCache
$proofSample = Read-ProofCoordAnchorSample -Anchor $proofAnchor

$startX = [double]$proofSample.CoordX
$startY = [double]$proofSample.CoordY
$startZ = [double]$proofSample.CoordZ
$readerBridgeDeltaX = $startX - [double]$playerCoord.X
$readerBridgeDeltaY = $startY - [double]$playerCoord.Y
$readerBridgeDeltaZ = $startZ - [double]$playerCoord.Z
if (-not (Test-CoordinateDeltaWithinTolerance -DeltaX $readerBridgeDeltaX -DeltaY $readerBridgeDeltaY -DeltaZ $readerBridgeDeltaZ)) {
    throw ("Proof coord anchor sample at {0} does not match ReaderBridge player coords within 0.25 units; deltas x={1}, y={2}, z={3}. Refresh ReaderBridge and proof coord anchor before generating a route." -f
        $proofSample.AddressHex,
        $readerBridgeDeltaX.ToString('G17', [System.Globalization.CultureInfo]::InvariantCulture),
        $readerBridgeDeltaY.ToString('G17', [System.Globalization.CultureInfo]::InvariantCulture),
        $readerBridgeDeltaZ.ToString('G17', [System.Globalization.CultureInfo]::InvariantCulture))
}

$orientationArguments = @('-Json')
if ($IgnoreBehaviorBackedLead) {
    $orientationArguments += '-IgnoreBehaviorBackedLead'
}
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
        coordSource = 'proof-coord-anchor'
        proofCoordAnchorFile = $resolvedProofCoordAnchorFile
        proofCoordSourceKind = [string]$proofAnchor.CanonicalCoordSourceKind
        proofCoordRegionAddress = [string]$proofAnchor.CoordRegionAddress
        proofCoordObjectBaseAddress = [string]$proofAnchor.ObjectBaseAddress
        proofCoordGeneratedAtUtc = [string]$proofAnchor.GeneratedAtUtc
        proofCoordMatchSource = [string]$proofAnchor.MatchSource
        readerBridgeCoord = [ordered]@{
            x = [double]$playerCoord.X
            y = [double]$playerCoord.Y
            z = [double]$playerCoord.Z
            deltaX = $readerBridgeDeltaX
            deltaY = $readerBridgeDeltaY
            deltaZ = $readerBridgeDeltaZ
        }
        orientationResolutionMode = [string]$readerOrientation.ResolutionMode
        orientationIgnoredBehaviorBackedLead = [bool]$IgnoreBehaviorBackedLead
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
    coordSource = 'proof-coord-anchor'
    proofCoordSourceKind = [string]$proofAnchor.CanonicalCoordSourceKind
    proofCoordRegionAddress = [string]$proofAnchor.CoordRegionAddress
    proofCoordObjectBaseAddress = [string]$proofAnchor.ObjectBaseAddress
    orientationIgnoredBehaviorBackedLead = [bool]$IgnoreBehaviorBackedLead
    readerBridgeSnapshotSourceFile = [string]$snapshot.SourceFile
    readerBridgeExportCount = $snapshot.ExportCount
    readerBridgeDeltaX = $readerBridgeDeltaX
    readerBridgeDeltaY = $readerBridgeDeltaY
    readerBridgeDeltaZ = $readerBridgeDeltaZ
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
