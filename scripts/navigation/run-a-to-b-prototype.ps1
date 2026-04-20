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

    $entry = [ordered]@{
        timestampUtc = (Get-Date).ToUniversalTime().ToString('o')
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
            $entry[$key] = $Metadata[$key]
        }
    }

    Add-Content -LiteralPath $resolvedLogFile -Value (($entry | ConvertTo-Json -Compress -Depth 8))
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
