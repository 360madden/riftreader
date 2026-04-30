[CmdletBinding()]
param(
    [string]$LogFile,
    [int]$RecentCount = 10
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

$summary | ConvertTo-Json -Depth 20
