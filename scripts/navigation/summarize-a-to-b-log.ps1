[CmdletBinding()]
param(
    [string]$LogFile,
    [int]$RecentCount = 10,
    [string]$MarkdownFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$LogFile = if ([string]::IsNullOrWhiteSpace($LogFile)) {
    Join-Path $PSScriptRoot 'logs\a-to-b-prototype.ndjson'
}
else {
    $LogFile
}

$resolvedLogFile = [System.IO.Path]::GetFullPath($LogFile)

if (-not (Test-Path -LiteralPath $resolvedLogFile)) {
    throw "Log file was not found: $resolvedLogFile"
}

function Get-OptionalPropertyValue {
    param(
        $Object,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $Object) {
        return $null
    }

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Get-EntryPropertyValue {
    param(
        $Entry,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $value = Get-OptionalPropertyValue -Object $Entry -Name $Name
    if ($null -ne $value) {
        return $value
    }

    $data = Get-OptionalPropertyValue -Object $Entry -Name 'data'
    return Get-OptionalPropertyValue -Object $data -Name $Name
}

function Get-FirstPropertyValue {
    param(
        $Object,
        [Parameter(Mandatory = $true)]
        [string[]]$Names
    )

    foreach ($name in $Names) {
        $value = Get-OptionalPropertyValue -Object $Object -Name $name
        if ($null -ne $value) {
            return $value
        }
    }

    return $null
}

function ConvertFrom-EmbeddedJsonObject {
    param([string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $null
    }

    $jsonStart = $Text.IndexOf('{')
    $jsonEnd = $Text.LastIndexOf('}')
    if ($jsonStart -lt 0 -or $jsonEnd -lt $jsonStart) {
        return $null
    }

    try {
        return $Text.Substring($jsonStart, ($jsonEnd - $jsonStart) + 1) | ConvertFrom-Json -Depth 80
    }
    catch {
        return $null
    }
}

function Convert-ToDoubleOrNull {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    try {
        return [double]$Value
    }
    catch {
        return $null
    }
}

function Get-PlanarMoved {
    param(
        $InitialPosition,
        $FinalPosition
    )

    $initialX = Convert-ToDoubleOrNull (Get-FirstPropertyValue -Object $InitialPosition -Names @('X', 'x'))
    $initialZ = Convert-ToDoubleOrNull (Get-FirstPropertyValue -Object $InitialPosition -Names @('Z', 'z'))
    $finalX = Convert-ToDoubleOrNull (Get-FirstPropertyValue -Object $FinalPosition -Names @('X', 'x'))
    $finalZ = Convert-ToDoubleOrNull (Get-FirstPropertyValue -Object $FinalPosition -Names @('Z', 'z'))

    if ($null -eq $initialX -or $null -eq $initialZ -or $null -eq $finalX -or $null -eq $finalZ) {
        return $null
    }

    return [Math]::Sqrt([Math]::Pow($finalX - $initialX, 2) + [Math]::Pow($finalZ - $initialZ, 2))
}

function Format-MarkdownValue {
    param($Value)

    if ($null -eq $Value) {
        return ''
    }

    if ($Value -is [double] -or $Value -is [float] -or $Value -is [decimal]) {
        return ([double]$Value).ToString('G17', [System.Globalization.CultureInfo]::InvariantCulture)
    }

    return ([string]$Value).Replace('|', '\|').Replace("`r", ' ').Replace("`n", ' ')
}

function Add-MarkdownRow {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [Parameter(Mandatory = $true)]
        [string]$Fact,
        $Value
    )

    $Lines.Add(('| {0} | {1} |' -f (Format-MarkdownValue -Value $Fact), (Format-MarkdownValue -Value $Value)))
}

function Convert-NavigationSummaryToMarkdown {
    param(
        [Parameter(Mandatory = $true)]
        $Summary
    )

    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add('# A/B navigation log summary')
    $lines.Add('')
    $lines.Add(('_Generated: {0}_' -f ([DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture))))
    $lines.Add('')
    $lines.Add('## Run counts')
    $lines.Add('')
    $lines.Add('| Fact | Value |')
    $lines.Add('|---|---|')
    Add-MarkdownRow -Lines $lines -Fact 'Log file' -Value $Summary.logFile
    Add-MarkdownRow -Lines $lines -Fact 'Total entries' -Value $Summary.totalEntries
    Add-MarkdownRow -Lines $lines -Fact 'Sessions' -Value $Summary.sessionCount
    Add-MarkdownRow -Lines $lines -Fact 'Successful sessions' -Value $Summary.successfulSessions
    Add-MarkdownRow -Lines $lines -Fact 'Failed sessions' -Value $Summary.failedSessions
    Add-MarkdownRow -Lines $lines -Fact 'Preflights' -Value $Summary.preflightCount
    Add-MarkdownRow -Lines $lines -Fact 'Navigation calls' -Value $Summary.navigateCount
    Add-MarkdownRow -Lines $lines -Fact 'Facing checks' -Value $Summary.facingCheckCount

    $navigation = $Summary.lastNavigationSummary
    if ($null -ne $navigation) {
        $lines.Add('')
        $lines.Add('## Latest navigation result')
        $lines.Add('')
        $lines.Add('| Fact | Value |')
        $lines.Add('|---|---|')
        Add-MarkdownRow -Lines $lines -Fact 'Status' -Value $navigation.status
        Add-MarkdownRow -Lines $lines -Fact 'Stop reason' -Value $navigation.stopReason
        Add-MarkdownRow -Lines $lines -Fact 'Pulse count' -Value $navigation.pulseCount
        Add-MarkdownRow -Lines $lines -Fact 'Anchor source' -Value $navigation.anchorSource
        Add-MarkdownRow -Lines $lines -Fact 'Initial planar distance' -Value $navigation.initialPlanarDistance
        Add-MarkdownRow -Lines $lines -Fact 'Final planar distance' -Value $navigation.finalPlanarDistance
        Add-MarkdownRow -Lines $lines -Fact 'Planar moved' -Value $navigation.planarMoved
        Add-MarkdownRow -Lines $lines -Fact 'Elapsed milliseconds' -Value $navigation.elapsedMilliseconds
        Add-MarkdownRow -Lines $lines -Fact 'Start waypoint' -Value $navigation.startWaypointId
        Add-MarkdownRow -Lines $lines -Fact 'Destination waypoint' -Value $navigation.destinationWaypointId
        Add-MarkdownRow -Lines $lines -Fact 'Waypoint file' -Value $navigation.waypointFile
    }

    $lastFacing = $Summary.lastFacingCheck
    $facing = if ($null -ne $lastFacing) { Get-EntryPropertyValue -Entry $lastFacing -Name 'facing' } else { $null }
    if ($null -ne $facing) {
        $lines.Add('')
        $lines.Add('## Latest facing guard')
        $lines.Add('')
        $lines.Add('| Fact | Value |')
        $lines.Add('|---|---|')
        Add-MarkdownRow -Lines $lines -Fact 'Yaw degrees' -Value (Get-FirstPropertyValue -Object $facing -Names @('yawDegrees', 'YawDegrees'))
        Add-MarkdownRow -Lines $lines -Fact 'Bearing degrees' -Value (Get-FirstPropertyValue -Object $facing -Names @('bearingDegrees', 'BearingDegrees'))
        Add-MarkdownRow -Lines $lines -Fact 'Delta degrees' -Value (Get-FirstPropertyValue -Object $facing -Names @('deltaDegrees', 'DeltaDegrees'))
        Add-MarkdownRow -Lines $lines -Fact 'Threshold degrees' -Value (Get-FirstPropertyValue -Object $facing -Names @('thresholdDegrees', 'ThresholdDegrees'))
        Add-MarkdownRow -Lines $lines -Fact 'Turn direction' -Value (Get-FirstPropertyValue -Object $facing -Names @('turnDirection', 'TurnDirection'))
        Add-MarkdownRow -Lines $lines -Fact 'Source address' -Value (Get-FirstPropertyValue -Object $facing -Names @('sourceAddress', 'SourceAddress'))
        Add-MarkdownRow -Lines $lines -Fact 'Basis forward offset' -Value (Get-FirstPropertyValue -Object $facing -Names @('basisForwardOffset', 'BasisForwardOffset'))
    }

    if ($Summary.stopReasonCounts.Count -gt 0) {
        $lines.Add('')
        $lines.Add('## Stop reasons')
        $lines.Add('')
        $lines.Add('| Stop reason | Count |')
        $lines.Add('|---|---:|')
        foreach ($key in $Summary.stopReasonCounts.Keys) {
            $lines.Add(('| {0} | {1} |' -f (Format-MarkdownValue -Value $key), (Format-MarkdownValue -Value $Summary.stopReasonCounts[$key])))
        }
    }

    $lines.Add('')
    return ($lines -join [Environment]::NewLine)
}

function Get-NavigationObjectFromEntry {
    param($Entry)

    $navigation = Get-EntryPropertyValue -Entry $Entry -Name 'navigation'
    if ($null -ne $navigation) {
        return $navigation
    }

    $output = Get-EntryPropertyValue -Entry $Entry -Name 'output'
    if ($null -eq $output) {
        return $null
    }

    return ConvertFrom-EmbeddedJsonObject -Text ([string]$output)
}

function New-NavigationSummary {
    param($Entry)

    if ($null -eq $Entry) {
        return $null
    }

    $navigation = Get-NavigationObjectFromEntry -Entry $Entry
    if ($null -eq $navigation) {
        return $null
    }

    $route = Get-EntryPropertyValue -Entry $Entry -Name 'route'
    $waypointFile = Get-EntryPropertyValue -Entry $Entry -Name 'waypointFile'
    if ([string]::IsNullOrWhiteSpace([string]$waypointFile)) {
        $waypointFile = Get-FirstPropertyValue -Object $navigation -Names @('WaypointFile', 'waypointFile')
    }

    $initialPosition = Get-FirstPropertyValue -Object $navigation -Names @('InitialPosition', 'initialPosition')
    $finalPosition = Get-FirstPropertyValue -Object $navigation -Names @('FinalPosition', 'finalPosition')
    $planarMoved = Get-FirstPropertyValue -Object $navigation -Names @('PlanarMoved', 'planarMoved')
    if ($null -eq $planarMoved) {
        $planarMoved = Get-PlanarMoved -InitialPosition $initialPosition -FinalPosition $finalPosition
    }

    return [ordered]@{
        status = Get-FirstPropertyValue -Object $navigation -Names @('Status', 'status')
        stopReason = Get-FirstPropertyValue -Object $navigation -Names @('StopReason', 'stopReason')
        pulseCount = Get-FirstPropertyValue -Object $navigation -Names @('PulseCount', 'pulseCount', 'TotalPulseCount', 'totalPulseCount')
        anchorSource = Get-FirstPropertyValue -Object $navigation -Names @('AnchorSource', 'anchorSource')
        initialPlanarDistance = Get-FirstPropertyValue -Object $navigation -Names @('InitialPlanarDistance', 'initialPlanarDistance')
        finalPlanarDistance = Get-FirstPropertyValue -Object $navigation -Names @('FinalPlanarDistance', 'finalPlanarDistance')
        planarMoved = $planarMoved
        initialPosition = $initialPosition
        finalPosition = $finalPosition
        elapsedMilliseconds = Get-FirstPropertyValue -Object $navigation -Names @('ElapsedMilliseconds', 'elapsedMilliseconds')
        movementVerification = Get-FirstPropertyValue -Object $navigation -Names @('MovementVerification', 'movementVerification')
        waypointFile = $waypointFile
        startWaypointId = if ($null -ne $route) { Get-FirstPropertyValue -Object $route -Names @('startWaypointId', 'StartWaypointId') } else { Get-FirstPropertyValue -Object $navigation -Names @('StartWaypointId', 'startWaypointId') }
        destinationWaypointId = if ($null -ne $route) { Get-FirstPropertyValue -Object $route -Names @('destinationWaypointId', 'DestinationWaypointId') } else { Get-FirstPropertyValue -Object $navigation -Names @('DestinationWaypointId', 'destinationWaypointId') }
    }
}

$entries = Get-Content -LiteralPath $resolvedLogFile |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
    ForEach-Object { $_ | ConvertFrom-Json -Depth 80 }

$sessionResults = @($entries | Where-Object { $_.step -eq 'session-result' })
$navigateSteps = @($entries | Where-Object { $_.step -eq 'navigate' })
$preflightSteps = @($entries | Where-Object { $_.step -eq 'preflight' })
$facingChecks = @($entries | Where-Object { $_.step -eq 'facing-guard' })
$lastSession = @($sessionResults | Select-Object -Last 1)
$lastFacing = @($facingChecks | Select-Object -Last 1)
$stopReasonCounts = [ordered]@{}
$lastMovementVerification = $null
$lastNavigationSummary = $null

foreach ($session in $sessionResults) {
    $reason = $null

    $navigation = Get-EntryPropertyValue -Entry $session -Name 'navigation'
    if ($null -ne $navigation) {
        $stopReason = Get-FirstPropertyValue -Object $navigation -Names @('StopReason', 'stopReason')
        if ($null -ne $stopReason) {
            $reason = [string]$stopReason
        }
    }

    if ([string]::IsNullOrWhiteSpace($reason)) {
        continue
    }

    if (-not $stopReasonCounts.Contains($reason)) {
        $stopReasonCounts[$reason] = 0
    }

    $stopReasonCounts[$reason]++
}

if ($lastSession.Count -gt 0) {
    $lastNavigation = Get-EntryPropertyValue -Entry $lastSession[0] -Name 'navigation'
    if ($null -ne $lastNavigation) {
        $lastMovementVerification = Get-FirstPropertyValue -Object $lastNavigation -Names @('MovementVerification', 'movementVerification')
    }

    $lastNavigationSummary = New-NavigationSummary -Entry $lastSession[0]
}

if ($null -eq $lastNavigationSummary -and $navigateSteps.Count -gt 0) {
    $lastNavigate = @($navigateSteps | Select-Object -Last 1)
    if ($lastNavigate.Count -gt 0) {
        $lastNavigationSummary = New-NavigationSummary -Entry $lastNavigate[0]
        if ($null -ne $lastNavigationSummary -and $null -eq $lastMovementVerification) {
            $lastMovementVerification = $lastNavigationSummary.movementVerification
        }
    }
}

if ($null -ne $lastNavigationSummary -and $null -eq $lastMovementVerification) {
    $lastMovementVerification = $lastNavigationSummary.movementVerification
}

$recent = @($entries | Select-Object -Last $RecentCount)

$summary = [ordered]@{
    mode = 'a-to-b-log-summary'
    logFile = $resolvedLogFile
    totalEntries = $entries.Count
    sessionCount = $sessionResults.Count
    successfulSessions = @($sessionResults | Where-Object { $_.exitCode -eq 0 }).Count
    failedSessions = @($sessionResults | Where-Object { $_.exitCode -ne 0 }).Count
    preflightCount = $preflightSteps.Count
    navigateCount = $navigateSteps.Count
    facingCheckCount = $facingChecks.Count
    lastSession = if ($lastSession.Count -gt 0) { $lastSession[0] } else { $null }
    lastNavigationSummary = $lastNavigationSummary
    lastMovementVerification = $lastMovementVerification
    lastFacingCheck = if ($lastFacing.Count -gt 0) { $lastFacing[0] } else { $null }
    stopReasonCounts = $stopReasonCounts
    recentSteps = $recent
}

if (-not [string]::IsNullOrWhiteSpace($MarkdownFile)) {
    $resolvedMarkdownFile = [System.IO.Path]::GetFullPath($MarkdownFile)
    $directory = Split-Path -Parent $resolvedMarkdownFile
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $markdown = Convert-NavigationSummaryToMarkdown -Summary ([pscustomobject]$summary)
    [System.IO.File]::WriteAllText($resolvedMarkdownFile, $markdown)
    $summary.markdownFile = $resolvedMarkdownFile
}

$summary | ConvertTo-Json -Depth 20
