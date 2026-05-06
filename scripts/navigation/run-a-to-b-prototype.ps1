[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
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
    [switch]$AutoTurnBeforeMove,
    [double]$AutoTurnWithinDegrees = 7.5,
    [string]$TurnLeftKey = 'a',
    [string]$TurnRightKey = 'd',
    [int]$TurnPulseMilliseconds = 75,
    [int]$PostTurnSampleDelayMilliseconds = 150,
    [int]$MaxTurnPulses = 12,
    [double]$AutoTurnWorseningToleranceDegrees = 0.5,
    [int]$AutoTurnMaxWorseningPulses = 2,
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
$postKeyScript = Join-Path $repoRoot 'scripts\post-rift-key.ps1'
$proofCoordPreflightScript = Join-Path $repoRoot 'scripts\assert-current-proof-coord-anchor.ps1'
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

if ($AutoTurnWithinDegrees -lt 0) {
    throw "AutoTurnWithinDegrees cannot be negative."
}

if ($TurnPulseMilliseconds -le 0) {
    throw "TurnPulseMilliseconds must be positive."
}

if ($PostTurnSampleDelayMilliseconds -lt 0) {
    throw "PostTurnSampleDelayMilliseconds cannot be negative."
}

if ($MaxTurnPulses -le 0) {
    throw "MaxTurnPulses must be positive."
}

if ($AutoTurnWorseningToleranceDegrees -lt 0) {
    throw "AutoTurnWorseningToleranceDegrees cannot be negative."
}

if ($AutoTurnMaxWorseningPulses -le 0) {
    throw "AutoTurnMaxWorseningPulses must be positive."
}

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

function Get-ReaderTargetArguments {
    if ($ProcessId -gt 0) {
        return @('--pid', $ProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    }

    return @('--process-name', $ProcessName)
}

function Get-ScriptTargetArguments {
    $arguments = @()
    if ($ProcessId -gt 0) {
        $arguments += @('-ProcessId', $ProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    }
    else {
        $arguments += @('-ProcessName', $ProcessName)
    }
    if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
        $arguments += @('-TargetWindowHandle', $TargetWindowHandle)
    }

    return $arguments
}

function Get-PostKeyTargetArguments {
    $arguments = @('-TargetProcessName', $ProcessName)
    if ($ProcessId -gt 0) {
        $arguments += @('-TargetProcessId', $ProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    }
    if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
        $arguments += @('-TargetWindowHandle', $TargetWindowHandle)
    }

    return $arguments
}

function Assert-ExactMovementTarget {
    if ($ProcessId -le 0 -and [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
        throw "Navigation movement/turn input requires -ProcessId or -TargetWindowHandle. Refusing name-only '$ProcessName' targeting."
    }
}

function Invoke-ScriptJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptFile,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [Parameter(Mandatory = $true)]
        [string]$Step,
        [switch]$AllowFailureExitCode
    )

    Write-Host ""
    Write-Host "[NavPrototype] powershell -ExecutionPolicy Bypass -File $ScriptFile $($Arguments -join ' ')" -ForegroundColor DarkGray

    $nativeResult = Invoke-ProcessText -FilePath 'pwsh' -ArgumentList (@('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ScriptFile) + $Arguments)
    $exitCode = $nativeResult.ExitCode
    $text = $nativeResult.Text
    Write-SessionLog -Step $Step -ExitCode $exitCode -Arguments $Arguments -Output $text

    if ($exitCode -ne 0 -and -not $AllowFailureExitCode) {
        if (-not [string]::IsNullOrWhiteSpace($text)) {
            Write-Host $text
        }

        throw "Script command failed with exit code $exitCode."
    }

    return $text | ConvertFrom-Json
}

function Assert-ProofCoordMovementPreflight {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Reason
    )

    Assert-ExactMovementTarget
    if (-not (Test-Path -LiteralPath $proofCoordPreflightScript)) {
        throw "Proof coord anchor preflight script was not found: $proofCoordPreflightScript"
    }

    $preflight = Invoke-ScriptJson -ScriptFile $proofCoordPreflightScript -Arguments (@('-Json') + (Get-ScriptTargetArguments)) -Step ("proof-anchor-movement-preflight:{0}" -f $Reason) -AllowFailureExitCode
    if (-not [string]::Equals([string]$preflight.Status, 'valid', [System.StringComparison]::OrdinalIgnoreCase) -or
        -not [bool]$preflight.MovementAllowed) {
        $issueText = (@($preflight.Issues) | ForEach-Object { [string]$_ }) -join '; '
        if ([string]::IsNullOrWhiteSpace($issueText)) {
            $issueText = 'no issue details returned'
        }

        throw ("Proof coord anchor movement preflight failed for '{0}': {1}" -f $Reason, $issueText)
    }

    Write-Host ("[NavPrototype] Proof coord anchor movement preflight passed for {0}." -f $Reason) -ForegroundColor DarkGray
    return $preflight
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

function Get-OptionalPropertyValue {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$Document,
        [Parameter(Mandatory = $true)]
        [string]$PropertyName
    )

    $property = $Document.PSObject.Properties[$PropertyName]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Write-PreflightSummary {
    param($Preflight)

    Write-Host ""
    Write-Host "[NavPrototype] Preflight summary" -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Distance: {0:N3}" -f [double]$Preflight.PlanarDistance) -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Bearing : {0:N3} deg" -f [double]$Preflight.WorldBearingDegrees) -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Arrival : {0}" -f ($(if ($Preflight.WithinArrivalRadius) { 'inside radius' } else { 'outside radius' }))) -ForegroundColor Cyan
    if ($null -ne $Preflight.Facing) {
        $facingYawDegrees = Get-OptionalPropertyValue -Document $Preflight.Facing -PropertyName 'YawDegrees'
        $facingAbsoluteBearingDeltaDegrees = Get-OptionalPropertyValue -Document $Preflight.Facing -PropertyName 'AbsoluteBearingDeltaDegrees'
        $facingSuggestedTurnDirection = Get-OptionalPropertyValue -Document $Preflight.Facing -PropertyName 'SuggestedTurnDirection'
        $facingReason = Get-OptionalPropertyValue -Document $Preflight.Facing -PropertyName 'Reason'

        Write-Host ("[NavPrototype] Facing  : {0}" -f [string]$Preflight.Facing.Status) -ForegroundColor Cyan
        if ($null -ne $facingYawDegrees) {
            Write-Host ("[NavPrototype] Yaw     : {0:N3} deg" -f [double]$facingYawDegrees) -ForegroundColor Cyan
        }
        if ($null -ne $facingAbsoluteBearingDeltaDegrees) {
            Write-Host ("[NavPrototype] Heading : {0:N3} deg abs ({1})" -f [double]$facingAbsoluteBearingDeltaDegrees, [string]$facingSuggestedTurnDirection) -ForegroundColor Cyan
        }
        if (-not [string]::IsNullOrWhiteSpace([string]$facingReason)) {
            Write-Host ("[NavPrototype] Facing note: {0}" -f [string]$facingReason) -ForegroundColor Yellow
        }
    }
}

function Get-FacingAlignmentState {
    param($Preflight)

    $facingStatus = $null
    $facingSourceAddress = $null
    $facingBasisForwardOffset = $null
    $turnDirection = $null

    $preflightAbsoluteBearingDeltaDegrees = $null
    $preflightYawDegrees = $null
    $preflightBasisPrimaryForwardOffset = $null
    $preflightSuggestedTurnDirection = $null
    if ($null -ne $Preflight.Facing) {
        $preflightAbsoluteBearingDeltaDegrees = Get-OptionalPropertyValue -Document $Preflight.Facing -PropertyName 'AbsoluteBearingDeltaDegrees'
        $preflightYawDegrees = Get-OptionalPropertyValue -Document $Preflight.Facing -PropertyName 'YawDegrees'
        $preflightBasisPrimaryForwardOffset = Get-OptionalPropertyValue -Document $Preflight.Facing -PropertyName 'BasisPrimaryForwardOffset'
        $preflightSuggestedTurnDirection = Get-OptionalPropertyValue -Document $Preflight.Facing -PropertyName 'SuggestedTurnDirection'
    }

    if ($null -ne $Preflight.Facing -and $null -ne $preflightAbsoluteBearingDeltaDegrees) {
        $yawDegrees = $preflightYawDegrees
        $bearingDegrees = [double]$Preflight.WorldBearingDegrees
        $deltaDegrees = [double]$preflightAbsoluteBearingDeltaDegrees
        $facingStatus = [string]$Preflight.Facing.Status
        $facingSourceAddress = [string]$Preflight.Facing.SelectedSourceAddress
        $facingBasisForwardOffset = [string]$preflightBasisPrimaryForwardOffset
        $turnDirection = [string]$preflightSuggestedTurnDirection
    }
    else {
        $orientation = Invoke-ScriptJson -ScriptFile $actorOrientationScript -Arguments (@('-Json') + (Get-ScriptTargetArguments)) -Step 'actor-orientation'
        $yawDegrees = $orientation.ReaderOrientation.PreferredEstimate.YawDegrees
        if ($null -eq $yawDegrees) {
            throw "Actor orientation did not return a usable yaw for navigation alignment."
        }

        $bearingDegrees = [double]$Preflight.WorldBearingDegrees
        $signedDeltaDegrees = Normalize-Degrees -Degrees ([double]$bearingDegrees - [double]$yawDegrees)
        $deltaDegrees = [Math]::Abs($signedDeltaDegrees)
        $facingStatus = 'script-fallback'
        $facingSourceAddress = [string]$orientation.ReaderOrientation.SelectedSourceAddress
        $facingBasisForwardOffset = if ($null -ne $orientation.ReaderOrientation.BasisPrimaryForwardOffset) {
            [string]$orientation.ReaderOrientation.BasisPrimaryForwardOffset
        }
        else {
            [string]$orientation.ReaderOrientation.BasisForwardOffset
        }
        $turnDirection = if ($deltaDegrees -le 0.0001) {
            'aligned'
        }
        elseif ($signedDeltaDegrees -gt 0) {
            'left'
        }
        else {
            'right'
        }
    }

    return [pscustomobject]@{
        YawDegrees = [double]$yawDegrees
        BearingDegrees = [double]$bearingDegrees
        DeltaDegrees = [double]$deltaDegrees
        TurnDirection = $turnDirection
        SourceAddress = $facingSourceAddress
        BasisForwardOffset = $facingBasisForwardOffset
        SourceStatus = $facingStatus
    }
}

function Invoke-TurnKeyPulse {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Key,
        [Parameter(Mandatory = $true)]
        [int]$HoldMilliseconds,
        [Parameter(Mandatory = $true)]
        [int]$PulseIndex,
        [Parameter(Mandatory = $true)]
        [string]$Direction
    )

    if (-not (Test-Path -LiteralPath $postKeyScript)) {
        throw "Turn helper script was not found: $postKeyScript"
    }

    [void](Assert-ProofCoordMovementPreflight -Reason ("auto-turn-key:{0}" -f $PulseIndex))
    $scriptArguments = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $postKeyScript,
        '-Key', $Key,
        '-HoldMilliseconds', $HoldMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture)
    ) + (Get-PostKeyTargetArguments) + @(
        '-SkipBackgroundFocus',
        '-RequireTargetForeground'
    )

    Write-Host ""
    Write-Host ("[NavPrototype] Auto-turn pulse {0}: key={1} direction={2} hold={3} ms" -f $PulseIndex, $Key, $Direction, $HoldMilliseconds) -ForegroundColor Yellow

    $nativeResult = Invoke-ProcessText -FilePath 'pwsh' -ArgumentList $scriptArguments
    Write-SessionLog -Step ("auto-turn-key:{0}" -f $PulseIndex) -ExitCode $nativeResult.ExitCode -Arguments @('-Key', $Key, '-Direction', $Direction, '-HoldMilliseconds', $HoldMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture)) -Output $nativeResult.Text

    if ($nativeResult.ExitCode -ne 0) {
        if (-not [string]::IsNullOrWhiteSpace($nativeResult.Text)) {
            Write-Host $nativeResult.Text
        }

        throw ("Auto-turn key pulse failed with exit code {0}." -f $nativeResult.ExitCode)
    }
}

function Invoke-AutoTurnAlignment {
    param(
        [Parameter(Mandatory = $true)]
        $Preflight,
        [Parameter(Mandatory = $true)]
        [string[]]$PreflightArguments
    )

    if (-not $AutoTurnBeforeMove) {
        return $Preflight
    }

    $facingState = Get-FacingAlignmentState -Preflight $Preflight
    $turnSamples = New-Object System.Collections.Generic.List[object]
    if ($facingState.DeltaDegrees -le $AutoTurnWithinDegrees -or
        [string]::Equals([string]$facingState.TurnDirection, 'aligned', [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Host ("[NavPrototype] Auto-turn: no turn needed (delta {0:N3} deg, threshold {1:N3} deg)." -f [double]$facingState.DeltaDegrees, [double]$AutoTurnWithinDegrees) -ForegroundColor DarkGray
        Write-SessionLog -Step 'auto-turn' -ExitCode 0 -Arguments @('noop') -Output ("delta={0:N3}; threshold={1:N3}; turn={2}" -f [double]$facingState.DeltaDegrees, [double]$AutoTurnWithinDegrees, ([string]$facingState.TurnDirection ?? 'n/a')) -Metadata @{
            autoTurn = [ordered]@{
                pulses = 0
                thresholdDegrees = [double]$AutoTurnWithinDegrees
                deltaDegrees = [double]$facingState.DeltaDegrees
                turnDirection = $facingState.TurnDirection
                sourceAddress = $facingState.SourceAddress
                basisForwardOffset = $facingState.BasisForwardOffset
                sourceStatus = $facingState.SourceStatus
                worseningToleranceDegrees = [double]$AutoTurnWorseningToleranceDegrees
                maxWorseningPulses = $AutoTurnMaxWorseningPulses
                samples = @($turnSamples.ToArray())
            }
        }
        return $Preflight
    }

    $turnDirection = [string]$facingState.TurnDirection
    $turnKey = switch ($turnDirection) {
        'left' { $TurnLeftKey }
        'right' { $TurnRightKey }
        default {
            throw ("Auto-turn requested but the current turn direction was not usable: '{0}'." -f $turnDirection)
        }
    }

    Write-Host ""
    Write-Host ("[NavPrototype] Auto-turn enabled: target <= {0:N3} deg using '{1}' for {2}." -f [double]$AutoTurnWithinDegrees, $turnKey, $turnDirection) -ForegroundColor Yellow

    $currentPreflight = $Preflight
    $previousDeltaDegrees = [double]$facingState.DeltaDegrees
    $worseningPulseCount = 0
    for ($pulse = 1; $pulse -le $MaxTurnPulses; $pulse++) {
        Invoke-TurnKeyPulse -Key $turnKey -HoldMilliseconds $TurnPulseMilliseconds -PulseIndex $pulse -Direction $turnDirection
        Start-Sleep -Milliseconds $PostTurnSampleDelayMilliseconds

        $updatedPreflightResult = Invoke-ReaderJson -Arguments $PreflightArguments -Step ("auto-turn-preflight:{0}" -f $pulse)
        $currentPreflight = $updatedPreflightResult.Output
        $facingState = Get-FacingAlignmentState -Preflight $currentPreflight

        $turnSamples.Add([pscustomobject]@{
            Pulse = $pulse
            Key = $turnKey
            Direction = $turnDirection
            YawDegrees = [double]$facingState.YawDegrees
            DeltaDegrees = [double]$facingState.DeltaDegrees
            SourceAddress = $facingState.SourceAddress
            BasisForwardOffset = $facingState.BasisForwardOffset
            SourceStatus = $facingState.SourceStatus
        }) | Out-Null

        Write-Host ("[NavPrototype] Auto-turn pulse {0}: yaw={1:N3} deg delta={2:N3} deg ({3})" -f $pulse, [double]$facingState.YawDegrees, [double]$facingState.DeltaDegrees, ([string]$facingState.TurnDirection ?? 'n/a')) -ForegroundColor Cyan

        if ($facingState.DeltaDegrees -le $AutoTurnWithinDegrees -or
            [string]::Equals([string]$facingState.TurnDirection, 'aligned', [System.StringComparison]::OrdinalIgnoreCase)) {
            Write-SessionLog -Step 'auto-turn' -ExitCode 0 -Arguments @('complete') -Output ("pulses={0}; delta={1:N3}; threshold={2:N3}; turn={3}" -f $pulse, [double]$facingState.DeltaDegrees, [double]$AutoTurnWithinDegrees, ([string]$facingState.TurnDirection ?? 'n/a')) -Metadata @{
                autoTurn = [ordered]@{
                    pulses = $pulse
                    thresholdDegrees = [double]$AutoTurnWithinDegrees
                    deltaDegrees = [double]$facingState.DeltaDegrees
                    turnDirection = $facingState.TurnDirection
                    sourceAddress = $facingState.SourceAddress
                    basisForwardOffset = $facingState.BasisForwardOffset
                    sourceStatus = $facingState.SourceStatus
                    worseningToleranceDegrees = [double]$AutoTurnWorseningToleranceDegrees
                    maxWorseningPulses = $AutoTurnMaxWorseningPulses
                    samples = @($turnSamples.ToArray())
                }
            }

            return $currentPreflight
        }

        if ([double]$facingState.DeltaDegrees -gt ($previousDeltaDegrees + [double]$AutoTurnWorseningToleranceDegrees)) {
            $worseningPulseCount++
            Write-Host ("[NavPrototype] Auto-turn warning: delta worsened from {0:N3} to {1:N3} deg (worsening {2}/{3})." -f [double]$previousDeltaDegrees, [double]$facingState.DeltaDegrees, $worseningPulseCount, $AutoTurnMaxWorseningPulses) -ForegroundColor Yellow
        }
        else {
            $worseningPulseCount = 0
        }

        if ($worseningPulseCount -ge $AutoTurnMaxWorseningPulses) {
            Write-SessionLog -Step 'auto-turn' -ExitCode 1 -Arguments @('worsening') -Output ("delta={0:N3}; previousDelta={1:N3}; tolerance={2:N3}; turn={3}; worsening={4}" -f [double]$facingState.DeltaDegrees, [double]$previousDeltaDegrees, [double]$AutoTurnWorseningToleranceDegrees, ([string]$facingState.TurnDirection ?? 'n/a'), $worseningPulseCount) -Metadata @{
                autoTurn = [ordered]@{
                    pulses = $pulse
                    thresholdDegrees = [double]$AutoTurnWithinDegrees
                    deltaDegrees = [double]$facingState.DeltaDegrees
                    previousDeltaDegrees = [double]$previousDeltaDegrees
                    turnDirection = $facingState.TurnDirection
                    sourceAddress = $facingState.SourceAddress
                    basisForwardOffset = $facingState.BasisForwardOffset
                    sourceStatus = $facingState.SourceStatus
                    worseningToleranceDegrees = [double]$AutoTurnWorseningToleranceDegrees
                    worseningPulseCount = $worseningPulseCount
                    maxWorseningPulses = $AutoTurnMaxWorseningPulses
                    samples = @($turnSamples.ToArray())
                }
            }

            throw ("Auto-turn worsened for {0} consecutive pulses. Last delta was {1:N3} deg after starting from {2:N3} deg." -f $worseningPulseCount, [double]$facingState.DeltaDegrees, [double]$previousDeltaDegrees)
        }

        $turnDirection = [string]$facingState.TurnDirection
        $turnKey = switch ($turnDirection) {
            'left' { $TurnLeftKey }
            'right' { $TurnRightKey }
            default { $turnKey }
        }
        $previousDeltaDegrees = [double]$facingState.DeltaDegrees
    }

    Write-SessionLog -Step 'auto-turn' -ExitCode 1 -Arguments @('incomplete') -Output ("delta={0:N3}; threshold={1:N3}; turn={2}; maxPulses={3}" -f [double]$facingState.DeltaDegrees, [double]$AutoTurnWithinDegrees, ([string]$facingState.TurnDirection ?? 'n/a'), $MaxTurnPulses) -Metadata @{
        autoTurn = [ordered]@{
            pulses = $MaxTurnPulses
            thresholdDegrees = [double]$AutoTurnWithinDegrees
            deltaDegrees = [double]$facingState.DeltaDegrees
            turnDirection = $facingState.TurnDirection
            sourceAddress = $facingState.SourceAddress
            basisForwardOffset = $facingState.BasisForwardOffset
            sourceStatus = $facingState.SourceStatus
            worseningToleranceDegrees = [double]$AutoTurnWorseningToleranceDegrees
            worseningPulseCount = $worseningPulseCount
            maxWorseningPulses = $AutoTurnMaxWorseningPulses
            samples = @($turnSamples.ToArray())
        }
    }

    throw ("Auto-turn failed to reach the {0:N3} degree threshold after {1} pulses. Last delta was {2:N3} deg ({3})." -f [double]$AutoTurnWithinDegrees, $MaxTurnPulses, [double]$facingState.DeltaDegrees, ([string]$facingState.TurnDirection ?? 'n/a'))
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
            throw "Process name '$Name' matched multiple windowed processes ($ids). Use -ProcessId for navigation."
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

function Convert-ToUtcDateTimeOffset {
    param(
        [Parameter(Mandatory = $false)]
        [object]$Value
    )

    if ($null -eq $Value) {
        return $null
    }

    if ($Value -is [DateTimeOffset]) {
        return ([DateTimeOffset]$Value).ToUniversalTime()
    }

    if ($Value -is [DateTime]) {
        $dateTime = [DateTime]$Value
        if ($dateTime.Kind -eq [System.DateTimeKind]::Unspecified) {
            return ([DateTimeOffset]::new([DateTime]::SpecifyKind($dateTime, [System.DateTimeKind]::Utc))).ToUniversalTime()
        }

        return ([DateTimeOffset]$dateTime).ToUniversalTime()
    }

    return [DateTimeOffset]::Parse(
        [string]$Value,
        [System.Globalization.CultureInfo]::InvariantCulture,
        [System.Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
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

    $processState = Get-ProcessState -Name $ProcessName -Id $ProcessId
    $provenance = if ($null -ne $document.provenance) { $document.provenance } else { $document.Provenance }
    if ($null -ne $processState -and $null -ne $provenance -and $null -ne $provenance.processStartTimeUtc) {
        try {
            $routeStartTimeUtc = Convert-ToUtcDateTimeOffset -Value $provenance.processStartTimeUtc
            $currentStartTimeUtc = Convert-ToUtcDateTimeOffset -Value $processState.StartTimeUtc
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
    $parity = Invoke-ScriptJson -ScriptFile $orientationParityScript -Arguments (@('-Json') + (Get-ScriptTargetArguments)) -Step 'orientation-parity'
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

    $facingState = Get-FacingAlignmentState -Preflight $Preflight
    $yawDegrees = $facingState.YawDegrees
    $bearingDegrees = $facingState.BearingDegrees
    $deltaDegrees = $facingState.DeltaDegrees
    $turnDirection = $facingState.TurnDirection
    $facingSourceAddress = $facingState.SourceAddress
    $facingBasisForwardOffset = $facingState.BasisForwardOffset
    $facingStatus = $facingState.SourceStatus

    Write-Host ("[NavPrototype] Current yaw: {0:N3} deg" -f [double]$yawDegrees) -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Yaw delta : {0:N3} deg" -f [double]$deltaDegrees) -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Turn hint : {0}" -f ($turnDirection ?? 'n/a')) -ForegroundColor Cyan
    Write-Host ("[NavPrototype] Facing src: {0} / {1} ({2})" -f $facingSourceAddress, $facingBasisForwardOffset, $facingStatus) -ForegroundColor Cyan

    Write-SessionLog `
        -Step 'facing-guard' `
        -ExitCode 0 `
        -Arguments @('yaw-check') `
        -Output ("yaw={0:N3}; bearing={1:N3}; delta={2:N3}; threshold={3:N3}; turn={4}" -f [double]$yawDegrees, [double]$bearingDegrees, [double]$deltaDegrees, [double]$RequireFacingWithinDegrees, ($turnDirection ?? 'n/a')) `
        -Metadata @{
            facing = [ordered]@{
                yawDegrees = [double]$yawDegrees
                bearingDegrees = [double]$bearingDegrees
                deltaDegrees = [double]$deltaDegrees
                thresholdDegrees = [double]$RequireFacingWithinDegrees
                turnDirection = $turnDirection
                sourceAddress = $facingSourceAddress
                basisForwardOffset = $facingBasisForwardOffset
                sourceStatus = $facingStatus
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

    $arguments = @(Get-ReaderTargetArguments) + @(
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

    $preflightArguments = @(Get-ReaderTargetArguments) + @(
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
    $preflight = Invoke-AutoTurnAlignment -Preflight $preflight -PreflightArguments $preflightArguments
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
    [void](Assert-ProofCoordMovementPreflight -Reason 'navigate')

    $navigationArguments = @(Get-ReaderTargetArguments) + @(
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

