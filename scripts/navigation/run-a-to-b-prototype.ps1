[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [string]$StartWaypointId = 'point_a',
    [string]$DestinationWaypointId = 'point_b',
    [string]$StartLabel = 'Point A',
    [string]$DestinationLabel = 'Point B',
    [ValidateSet('keep', 'walk', 'run')]
    [string]$Pace = 'keep',
    [string]$WaypointFile,
    [switch]$UseSmokeTestFile,
    [switch]$UseLastSuccessfulRoute,
    [switch]$UseExistingWaypoints,
    [switch]$PreflightOnly,
    [switch]$AutoConfirm,
    [switch]$ForceWaypointOverwrite,
    [switch]$SkipRefresh,
    [double]$ArrivalRadius,
    [double]$RequireFacingWithinDegrees = 45,
    [int]$MaxTravelSeconds,
    [string]$LogFile,
    [int]$ScanContextBytes = 192,
    [int]$MaxHits = 12
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')).Path 'logging-common.ps1')

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$refreshScript = Join-Path $repoRoot 'scripts\refresh-readerbridge-export.ps1'
$WaypointFile = if ([string]::IsNullOrWhiteSpace($WaypointFile)) {
    Join-Path $PSScriptRoot 'waypoints.json'
}
else {
    $WaypointFile
}
$LogFile = if ([string]::IsNullOrWhiteSpace($LogFile)) {
    Join-Path $PSScriptRoot 'logs\a-to-b-prototype.ndjson'
}
else {
    $LogFile
}
$resolvedLogFile = [System.IO.Path]::GetFullPath($LogFile)
$actorOrientationScript = Join-Path $repoRoot 'scripts\capture-actor-orientation.ps1'
$orientationParityScript = Join-Path $PSScriptRoot 'assert-orientation-reader-parity.ps1'

function Get-LastSuccessfulRoute {
    if (-not (Test-Path -LiteralPath $resolvedLogFile)) {
        throw "Cannot reuse the last successful route because the log file was not found: $resolvedLogFile"
    }

    $entries = Get-Content -LiteralPath $resolvedLogFile |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        ForEach-Object { $_ | ConvertFrom-Json }

    $entry = @($entries |
        Where-Object {
            $_.step -eq 'session-result' -and
            $_.exitCode -eq 0 -and
            $null -ne $_.route -and
            -not [string]::IsNullOrWhiteSpace([string]$_.route.startWaypointId) -and
            -not [string]::IsNullOrWhiteSpace([string]$_.route.destinationWaypointId)
        } |
        Select-Object -Last 1)

    if ($entry.Count -eq 0) {
        throw "No successful route entry was found in $resolvedLogFile"
    }

    return $entry[0]
}

if ($UseLastSuccessfulRoute) {
    $lastSuccessfulRoute = Get-LastSuccessfulRoute
    $WaypointFile = [string]$lastSuccessfulRoute.waypointFile
    $StartWaypointId = [string]$lastSuccessfulRoute.route.startWaypointId
    $DestinationWaypointId = [string]$lastSuccessfulRoute.route.destinationWaypointId
    if (-not [string]::IsNullOrWhiteSpace([string]$lastSuccessfulRoute.route.startLabel)) {
        $StartLabel = [string]$lastSuccessfulRoute.route.startLabel
    }
    if (-not [string]::IsNullOrWhiteSpace([string]$lastSuccessfulRoute.route.destinationLabel)) {
        $DestinationLabel = [string]$lastSuccessfulRoute.route.destinationLabel
    }
    $UseExistingWaypoints = $true
}

if ($UseSmokeTestFile -and -not $PSBoundParameters.ContainsKey('WaypointFile') -and -not $UseLastSuccessfulRoute) {
    $WaypointFile = Join-Path $PSScriptRoot 'smoke-test-waypoints.json'
}

if ($UseSmokeTestFile -and -not $UseLastSuccessfulRoute) {
    if (-not $PSBoundParameters.ContainsKey('StartWaypointId')) {
        $StartWaypointId = 'smoke_start'
    }
    if (-not $PSBoundParameters.ContainsKey('DestinationWaypointId')) {
        $DestinationWaypointId = 'smoke_destination'
    }
    if (-not $PSBoundParameters.ContainsKey('StartLabel')) {
        $StartLabel = 'Smoke Start'
    }
    if (-not $PSBoundParameters.ContainsKey('DestinationLabel')) {
        $DestinationLabel = 'Smoke Destination'
    }
}

$resolvedWaypointFile = [System.IO.Path]::GetFullPath($WaypointFile)
$sessionRunId = New-LogRunId -Source 'navigation-prototype'

function Write-SessionLog {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Step,
        [Parameter(Mandatory = $true)]
        [int]$ExitCode,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [string]$Output = '',
        [hashtable]$Metadata
    )

    $directory = Split-Path -Parent $resolvedLogFile
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $legacyFields = [ordered]@{
        timestampUtc = Get-LogEventTimeUtc
        step         = $Step
        exitCode     = $ExitCode
        processName  = $ProcessName
        waypointFile = $resolvedWaypointFile
        route        = [ordered]@{
            startWaypointId       = $StartWaypointId
            destinationWaypointId = $DestinationWaypointId
            startLabel            = $StartLabel
            destinationLabel      = $DestinationLabel
        }
        arguments    = $Arguments
        output       = $Output
    }

    if ($null -ne $Metadata -and $Metadata.Count -gt 0) {
        foreach ($key in $Metadata.Keys) {
            $legacyFields[$key] = $Metadata[$key]
        }
    }

    $message = switch ($Step) {
        'preflight' { 'Navigation preflight completed.' }
        'navigate' { 'Navigation command completed.' }
        'session-result' { 'Navigation session finished.' }
        'facing-guard' { 'Facing guard completed.' }
        default { "Navigation event '$Step' recorded." }
    }

    $level = if ($ExitCode -eq 0) { 'info' } elseif ($Step -eq 'navigate' -or $Step -eq 'session-result') { 'warn' } else { 'error' }

    $data = [ordered]@{
        step        = $Step
        exitCode    = $ExitCode
        processName = $ProcessName
        waypointFile = $resolvedWaypointFile
        route       = $legacyFields.route
        arguments   = $Arguments
        output      = $Output
    }

    if ($null -ne $Metadata -and $Metadata.Count -gt 0) {
        foreach ($key in $Metadata.Keys) {
            $data[$key] = $Metadata[$key]
        }
    }

    $entry = New-StructuredLogEntry `
        -Level $level `
        -Source 'navigation-prototype' `
        -RunId $sessionRunId `
        -Message $message `
        -Data $data `
        -LegacyFields $legacyFields

    Write-StructuredLogLine -Path $resolvedLogFile -Entry $entry
}

function Test-WaypointExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WaypointId
    )

    if (-not (Test-Path -LiteralPath $resolvedWaypointFile)) {
        return $false
    }

    try {
        $document = Get-Content -LiteralPath $resolvedWaypointFile -Raw | ConvertFrom-Json
        $waypoints = @($document.waypoints)
        if ($waypoints.Count -eq 0) {
            $waypoints = @($document.Waypoints)
        }

        foreach ($waypoint in $waypoints) {
            if ($null -ne $waypoint -and
                $null -ne $waypoint.id -and
                [string]::Equals([string]$waypoint.id, $WaypointId, [System.StringComparison]::OrdinalIgnoreCase)) {
                return $true
            }

            if ($null -ne $waypoint -and
                $null -ne $waypoint.Id -and
                [string]::Equals([string]$waypoint.Id, $WaypointId, [System.StringComparison]::OrdinalIgnoreCase)) {
                return $true
            }
        }
    }
    catch {
        Write-Warning ("Unable to inspect waypoint file before capture: {0}" -f $_.Exception.Message)
    }

    return $false
}

function Confirm-WaypointOverwrite {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WaypointId
    )

    if ($ForceWaypointOverwrite) {
        return
    }

    if (-not (Test-WaypointExists -WaypointId $WaypointId)) {
        return
    }

    Write-Host ""
    Write-Host "[NavPrototype] Waypoint '$WaypointId' already exists in $resolvedWaypointFile." -ForegroundColor Yellow
    $response = Read-Host "Type OVERWRITE to replace it, or anything else to stop"
    if (-not [string]::Equals($response, 'OVERWRITE', [System.StringComparison]::Ordinal)) {
        throw "Waypoint overwrite was not confirmed for '$WaypointId'."
    }
}

function Start-LiveInteractionCountdown {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Reason
    )

    Write-Host ""
    Write-Host "[NavPrototype] Live interaction pending: $Reason" -ForegroundColor Yellow
    Write-Host "[NavPrototype] Bring Rift to the foreground now. The script will preserve the current focus and start in 10 seconds." -ForegroundColor Yellow

    for ($remaining = 10; $remaining -ge 1; $remaining--) {
        Write-Host ("[NavPrototype] Starting in {0}..." -f $remaining) -ForegroundColor Yellow
        Start-Sleep -Seconds 1
    }
}

function Invoke-Refresh {
    if ($SkipRefresh) {
        return
    }

    Start-LiveInteractionCountdown -Reason "refresh ReaderBridge export via /reloadui"

    Write-Host ""
    Write-Host "[NavPrototype] Refreshing ReaderBridge export..." -ForegroundColor Cyan

    $refreshArguments = @{
        NoReader = $true
        NoAhkFallback = $true
        SkipBackgroundFocus = $true
    }

    & $refreshScript @refreshArguments
    Start-Sleep -Milliseconds 750
}

function Invoke-ProcessText {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList
    )

    $escapedArguments = foreach ($argument in $ArgumentList) {
        if ($null -eq $argument) {
            '""'
            continue
        }

        if ($argument -notmatch '[\s"]') {
            $argument
            continue
        }

        $escaped = $argument -replace '(\\*)"', '$1$1\"'
        $escaped = $escaped -replace '(\\+)$', '$1$1'
        '"' + $escaped + '"'
    }

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $FilePath
    $startInfo.Arguments = ($escapedArguments -join ' ')
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo

    try {
        [void]$process.Start()
        $stdoutText = $process.StandardOutput.ReadToEnd().TrimEnd()
        $stderrText = $process.StandardError.ReadToEnd().TrimEnd()
        $process.WaitForExit()

        $combinedText = $stdoutText
        if (-not [string]::IsNullOrWhiteSpace($stderrText)) {
            if (-not [string]::IsNullOrWhiteSpace($combinedText)) {
                $combinedText += [Environment]::NewLine
            }

            $combinedText += $stderrText
        }

        return [pscustomobject]@{
            ExitCode = $process.ExitCode
            Text = $combinedText
        }
    }
    finally {
        $process.Dispose()
    }
}

function Invoke-ReaderCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [Parameter(Mandatory = $true)]
        [string]$Step
    )

    Write-Host ""
    Write-Host "[NavPrototype] dotnet run --project $readerProject -- $($Arguments -join ' ')" -ForegroundColor DarkGray

    $nativeResult = Invoke-ProcessText -FilePath 'dotnet' -ArgumentList (@('run', '--project', $readerProject, '--') + $Arguments)
    $exitCode = $nativeResult.ExitCode
    $text = $nativeResult.Text
    Write-SessionLog -Step $Step -ExitCode $exitCode -Arguments $Arguments -Output $text

    if (-not [string]::IsNullOrWhiteSpace($text)) {
        Write-Host $text
    }

    if ($exitCode -ne 0) {
        throw "Reader command failed with exit code $exitCode."
    }
}

function Invoke-ReaderJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [Parameter(Mandatory = $true)]
        [string]$Step,
        [switch]$AllowFailureExitCode
    )

    $jsonArguments = @($Arguments)
    if (-not ($jsonArguments -contains '--json')) {
        $jsonArguments += '--json'
    }

    Write-Host ""
    Write-Host "[NavPrototype] dotnet run --project $readerProject -- $($jsonArguments -join ' ')" -ForegroundColor DarkGray

    $nativeResult = Invoke-ProcessText -FilePath 'dotnet' -ArgumentList (@('run', '--project', $readerProject, '--') + $jsonArguments)
    $exitCode = $nativeResult.ExitCode
    $text = $nativeResult.Text
    Write-SessionLog -Step $Step -ExitCode $exitCode -Arguments $jsonArguments -Output $text

    if ([string]::IsNullOrWhiteSpace($text)) {
        throw "Reader command did not produce JSON output."
    }

    $jsonStart = $text.IndexOf('{')
    $jsonEnd = $text.LastIndexOf('}')
    if ($jsonStart -lt 0 -or $jsonEnd -lt $jsonStart) {
        throw "Reader command did not produce JSON output."
    }

    $jsonPayload = $text.Substring($jsonStart, ($jsonEnd - $jsonStart) + 1)
    $document = $null
    try {
        $document = $jsonPayload | ConvertFrom-Json
    }
    catch {
        throw ("Reader command returned non-JSON output: {0}" -f $_.Exception.Message)
    }

    if ($exitCode -ne 0 -and -not $AllowFailureExitCode) {
        throw "Reader command failed with exit code $exitCode."
    }

    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = $document
        RawOutput = $text
    }
}

function Invoke-ScriptJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptFile,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [Parameter(Mandatory = $true)]
        [string]$Step
    )

    Write-Host ""
    Write-Host "[NavPrototype] powershell -ExecutionPolicy Bypass -File $ScriptFile $($Arguments -join ' ')" -ForegroundColor DarkGray

    $nativeResult = Invoke-ProcessText -FilePath 'pwsh' -ArgumentList (@('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ScriptFile) + $Arguments)
    $exitCode = $nativeResult.ExitCode
    $text = $nativeResult.Text
    Write-SessionLog -Step $Step -ExitCode $exitCode -Arguments $Arguments -Output $text

    if ($exitCode -ne 0) {
        if (-not [string]::IsNullOrWhiteSpace($text)) {
            Write-Host $text
        }

        throw "Script command failed with exit code $exitCode."
    }

    return $text | ConvertFrom-Json
}

function Normalize-Degrees {
    param([double]$Degrees)

    $normalized = $Degrees
    while ($normalized -gt 180.0) {
        $normalized -= 360.0
    }

    while ($normalized -lt -180.0) {
        $normalized += 360.0
    }

    return $normalized
}

function Write-PreflightSummary {
    param($Preflight)

    Write-Host ""
    Write-Host "[NavPrototype] Preflight summary" -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Distance: {0:N3}" -f [double]$Preflight.PlanarDistance) -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Bearing : {0:N3} deg" -f [double]$Preflight.WorldBearingDegrees) -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Arrival : {0}" -f ($(if ($Preflight.WithinArrivalRadius) { 'inside radius' } else { 'outside radius' }))) -ForegroundColor Cyan
}

function Write-NavigationSummary {
    param($NavigationResult)

    Write-Host ""
    Write-Host "[NavPrototype] Navigation summary" -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Status     : {0}" -f [string]$NavigationResult.Status) -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Stop reason: {0}" -f [string]$NavigationResult.StopReason) -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Pulses     : {0}" -f [int]$NavigationResult.PulseCount) -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Initial d  : {0:N3}" -f [double]$NavigationResult.InitialPlanarDistance) -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Final d    : {0:N3}" -f [double]$NavigationResult.FinalPlanarDistance) -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Elapsed ms : {0}" -f [long]$NavigationResult.ElapsedMilliseconds) -ForegroundColor Cyan
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

function Get-ReaderBridgePlayerCoord {
    $snapshot = Invoke-ReaderJson -Arguments @('--readerbridge-snapshot', '--json') -Step 'player-snapshot'
    $playerCoord = $snapshot.Output.Current.Player.Coord
    if ($null -eq $playerCoord -or $null -eq $playerCoord.X -or $null -eq $playerCoord.Z) {
        throw 'ReaderBridge snapshot did not expose a usable current player coordinate for route validation.'
    }

    return [pscustomobject]@{
        X = [double]$playerCoord.X
        Y = if ($null -ne $playerCoord.Y) { [double]$playerCoord.Y } else { $null }
        Z = [double]$playerCoord.Z
        Snapshot = $snapshot.Output
    }
}

function Get-WaypointDocument {
    if (-not (Test-Path -LiteralPath $resolvedWaypointFile)) {
        throw "Waypoint file not found: $resolvedWaypointFile"
    }

    return Get-Content -LiteralPath $resolvedWaypointFile -Raw | ConvertFrom-Json -Depth 20
}

function Get-WaypointById {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$Document,
        [Parameter(Mandatory = $true)]
        [string]$WaypointId
    )

    $waypoints = @($Document.waypoints)
    if ($waypoints.Count -eq 0) {
        $waypoints = @($Document.Waypoints)
    }

    foreach ($waypoint in $waypoints) {
        if ($null -eq $waypoint) {
            continue
        }

        $candidateId = if ($null -ne $waypoint.id) { [string]$waypoint.id } else { [string]$waypoint.Id }
        if ([string]::Equals($candidateId, $WaypointId, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $waypoint
        }
    }

    return $null
}

function Get-PlanarDistance {
    param(
        [double]$AX,
        [double]$AZ,
        [double]$BX,
        [double]$BZ
    )

    return [Math]::Sqrt(([Math]::Pow(($AX - $BX), 2)) + ([Math]::Pow(($AZ - $BZ), 2)))
}

function Assert-SmokeRouteFreshness {
    $isSmokeRoute = [string]::Equals(
        [System.IO.Path]::GetFileName($resolvedWaypointFile),
        'smoke-test-waypoints.json',
        [System.StringComparison]::OrdinalIgnoreCase)

    if (-not $isSmokeRoute -or -not (Test-Path -LiteralPath $resolvedWaypointFile)) {
        return
    }

    $document = Get-WaypointDocument
    $startWaypoint = Get-WaypointById -Document $document -WaypointId $StartWaypointId
    if ($null -eq $startWaypoint -or $null -eq $startWaypoint.x -or $null -eq $startWaypoint.z) {
        throw "Smoke route file '$resolvedWaypointFile' did not contain a usable start waypoint '$StartWaypointId'."
    }

    $player = Get-ReaderBridgePlayerCoord
    $movement = if ($null -ne $document.movement) { $document.movement } else { $document.Movement }
    $startRadius = if ($null -ne $movement -and $null -ne $movement.startRadius) { [double]$movement.startRadius } else { 1.5 }
    $planarDistance = Get-PlanarDistance -AX ([double]$startWaypoint.x) -AZ ([double]$startWaypoint.z) -BX $player.X -BZ $player.Z

    $issues = New-Object System.Collections.Generic.List[string]
    if ($planarDistance -gt ([Math]::Max(($startRadius * 2.0), 6.0))) {
        $issues.Add(("Current player position is {0:N3} units away from smoke_start; the checked route is stale for this session." -f $planarDistance))
    }

    $processState = Get-ProcessState -Name $ProcessName
    $provenance = if ($null -ne $document.provenance) { $document.provenance } else { $document.Provenance }
    if ($null -ne $processState -and $null -ne $provenance -and -not [string]::IsNullOrWhiteSpace([string]$provenance.processStartTimeUtc)) {
        try {
            $routeStartTimeUtc = [DateTimeOffset]::Parse([string]$provenance.processStartTimeUtc, [System.Globalization.CultureInfo]::InvariantCulture)
            $currentStartTimeUtc = [DateTimeOffset]::Parse([string]$processState.StartTimeUtc, [System.Globalization.CultureInfo]::InvariantCulture)
            $driftSeconds = [Math]::Abs(($currentStartTimeUtc - $routeStartTimeUtc).TotalSeconds)
            if ($driftSeconds -gt 1.0) {
                $issues.Add("Smoke route provenance belongs to a different Rift process start time.")
            }
        }
        catch {
            $issues.Add("Smoke route provenance contained an unreadable process start time.")
        }
    }

    Write-SessionLog -Step 'route-guard' -ExitCode $(if ($issues.Count -eq 0) { 0 } else { 1 }) -Arguments @('smoke-route-check') -Output ("planarDistance={0:N3}" -f $planarDistance) -Metadata @{
        routeGuard = [ordered]@{
            waypointFile = $resolvedWaypointFile
            startWaypointId = $StartWaypointId
            planarDistanceToStart = $planarDistance
            startRadius = $startRadius
            issues = @($issues)
        }
    }

    if ($issues.Count -gt 0) {
        throw ("Smoke route file is stale for the current session. Regenerate it with '{0}' before running movement. {1}" -f (Join-Path $PSScriptRoot 'new-forward-smoke-route.ps1'), ($issues -join ' '))
    }
}

function Assert-OrientationReaderParity {
    $parity = Invoke-ScriptJson -ScriptFile $orientationParityScript -Arguments @('-Json', '-ProcessName', $ProcessName) -Step 'orientation-parity'
    Write-Host ""
    Write-Host "[NavPrototype] Orientation parity" -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Status    : {0}" -f [string]$parity.Status) -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Source    : {0}" -f [string]$parity.Native.SelectedSourceAddress) -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Basis     : {0} / {1}" -f [string]$parity.Native.BasisPrimaryForwardOffset, [string]$parity.Native.BasisDuplicateForwardOffset) -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Yaw delta : {0:N6} deg" -f [double]$parity.YawDeltaDegrees) -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Pitch del.: {0:N6} deg" -f [double]$parity.PitchDeltaDegrees) -ForegroundColor Cyan
}

function Assert-FacingAlignment {
    param($Preflight)

    if ($RequireFacingWithinDegrees -le 0) {
        return
    }

    $orientation = Invoke-ScriptJson -ScriptFile $actorOrientationScript -Arguments @('-Json', '-ProcessName', $ProcessName) -Step 'actor-orientation'
    $yawDegrees = $orientation.ReaderOrientation.PreferredEstimate.YawDegrees
    if ($null -eq $yawDegrees) {
        throw "Actor orientation did not return a usable yaw for the facing guard."
    }

    $bearingDegrees = [double]$Preflight.WorldBearingDegrees
    $deltaDegrees = [Math]::Abs((Normalize-Degrees -Degrees ([double]$bearingDegrees - [double]$yawDegrees)))

    Write-Host ("[NavPrototype] Current yaw: {0:N3} deg" -f [double]$yawDegrees) -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Yaw delta : {0:N3} deg" -f [double]$deltaDegrees) -ForegroundColor Cyan

    Write-SessionLog `
        -Step 'facing-guard' `
        -ExitCode 0 `
        -Arguments @('yaw-check') `
        -Output ("yaw={0:N3}; bearing={1:N3}; delta={2:N3}; threshold={3:N3}" -f [double]$yawDegrees, [double]$bearingDegrees, [double]$deltaDegrees, [double]$RequireFacingWithinDegrees) `
        -Metadata @{
            facing = [ordered]@{
                yawDegrees = [double]$yawDegrees
                bearingDegrees = [double]$bearingDegrees
                deltaDegrees = [double]$deltaDegrees
                thresholdDegrees = [double]$RequireFacingWithinDegrees
            }
        }

    if ($deltaDegrees -gt $RequireFacingWithinDegrees) {
        throw ("Facing guard failed. Current yaw differs from destination bearing by {0:N3} degrees, which exceeds the {1:N3} degree threshold." -f [double]$deltaDegrees, [double]$RequireFacingWithinDegrees)
    }
}

function Wait-ForOperator {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Prompt
    )

    if ($AutoConfirm) {
        Write-Host ("[NavPrototype] AutoConfirm: {0}" -f $Prompt) -ForegroundColor DarkGray
        return
    }

    Read-Host $Prompt | Out-Null
}

function Capture-Waypoint {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WaypointId,

        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    Confirm-WaypointOverwrite -WaypointId $WaypointId
    Invoke-Refresh

    $arguments = @(
        '--process-name', $ProcessName,
        '--capture-navigation-waypoint', $WaypointId,
        '--waypoint-label', $Label,
        '--navigation-waypoint-file', $resolvedWaypointFile,
        '--scan-context', $ScanContextBytes.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--max-hits', $MaxHits.ToString([System.Globalization.CultureInfo]::InvariantCulture)
    )

    Invoke-ReaderCommand -Arguments $arguments -Step "capture-waypoint:$WaypointId"
}

$sessionResultWritten = $false

try {
    Write-Host "[NavPrototype] Waypoint file: $resolvedWaypointFile" -ForegroundColor Cyan
    Write-Host "[NavPrototype] Session log : $resolvedLogFile" -ForegroundColor Cyan
    if ($UseExistingWaypoints) {
        Write-Host "[NavPrototype] Prototype flow: use existing A/B -> return to A -> preflight -> move." -ForegroundColor Cyan
    }
    else {
        Write-Host "[NavPrototype] Prototype flow: capture A -> capture B -> return to A -> preflight -> move." -ForegroundColor Cyan

        Wait-ForOperator -Prompt "Place the character at $StartLabel ($StartWaypointId), then press Enter"
        Capture-Waypoint -WaypointId $StartWaypointId -Label $StartLabel

        Wait-ForOperator -Prompt "Move the character to $DestinationLabel ($DestinationWaypointId), then press Enter"
        Capture-Waypoint -WaypointId $DestinationWaypointId -Label $DestinationLabel
    }

    Wait-ForOperator -Prompt "Return to $StartLabel, face roughly toward $DestinationLabel, then press Enter"
    Invoke-Refresh
    Assert-SmokeRouteFreshness
    Assert-OrientationReaderParity

    $preflightArguments = @(
        '--process-name', $ProcessName,
        '--read-navigation-current',
        '--destination-waypoint', $DestinationWaypointId,
        '--navigation-waypoint-file', $resolvedWaypointFile,
        '--scan-context', $ScanContextBytes.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--max-hits', $MaxHits.ToString([System.Globalization.CultureInfo]::InvariantCulture)
    )
    if ($PSBoundParameters.ContainsKey('ArrivalRadius')) {
        $preflightArguments += @('--arrival-radius', $ArrivalRadius.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    }

    $preflightResult = Invoke-ReaderJson -Arguments $preflightArguments -Step 'preflight'
    $preflight = $preflightResult.Output
    Write-PreflightSummary -Preflight $preflight
    Assert-FacingAlignment -Preflight $preflight

    if ($PreflightOnly) {
        Write-Host ""
        Write-Host "[NavPrototype] Preflight-only mode requested. No movement input was sent." -ForegroundColor Cyan
        Write-SessionLog -Step 'session-result' -ExitCode 0 -Arguments @('preflight-only') -Output 'Preflight-only mode completed successfully.' -Metadata @{
            preflight = $preflight
            sessionMode = 'preflight-only'
        }
        $sessionResultWritten = $true
        exit 0
    }

    Wait-ForOperator -Prompt "If the preflight looks correct, press Enter to start movement. Ctrl+C to cancel"

    $navigationArguments = @(
        '--process-name', $ProcessName,
        '--navigate-waypoints',
        '--start-waypoint', $StartWaypointId,
        '--destination-waypoint', $DestinationWaypointId,
        '--navigation-waypoint-file', $resolvedWaypointFile,
        '--pace', $Pace,
        '--scan-context', $ScanContextBytes.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--max-hits', $MaxHits.ToString([System.Globalization.CultureInfo]::InvariantCulture)
    )
    if ($PSBoundParameters.ContainsKey('ArrivalRadius')) {
        $navigationArguments += @('--arrival-radius', $ArrivalRadius.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    }
    if ($PSBoundParameters.ContainsKey('MaxTravelSeconds')) {
        $navigationArguments += @('--max-travel-seconds', $MaxTravelSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    }

    $navigationResult = Invoke-ReaderJson -Arguments $navigationArguments -Step 'navigate' -AllowFailureExitCode
    $navigation = $navigationResult.Output
    Write-NavigationSummary -NavigationResult $navigation
    Write-SessionLog -Step 'session-result' -ExitCode $navigationResult.ExitCode -Arguments @('navigate') -Output $navigationResult.RawOutput -Metadata @{
        navigation = $navigation
        sessionMode = 'navigate'
    }
    $sessionResultWritten = $true

    if ($navigationResult.ExitCode -ne 0) {
        throw ("Navigation failed with stop reason '{0}'." -f [string]$navigation.StopReason)
    }
}
catch {
    if (-not $sessionResultWritten) {
        Write-SessionLog -Step 'session-result' -ExitCode 1 -Arguments @('exception') -Output $_.Exception.Message -Metadata @{
            sessionMode = 'exception'
        }
        $sessionResultWritten = $true
    }

    throw
}
