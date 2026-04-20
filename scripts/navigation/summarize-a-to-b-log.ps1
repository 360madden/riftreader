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

$entries = Get-Content -LiteralPath $resolvedLogFile |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
    ForEach-Object { $_ | ConvertFrom-Json }

$sessionResults = @($entries | Where-Object { $_.step -eq 'session-result' })
$navigateSteps = @($entries | Where-Object { $_.step -eq 'navigate' })
$preflightSteps = @($entries | Where-Object { $_.step -eq 'preflight' })
$facingChecks = @($entries | Where-Object { $_.step -eq 'facing-guard' })
$lastSession = @($sessionResults | Select-Object -Last 1)
$lastFacing = @($facingChecks | Select-Object -Last 1)
$stopReasonCounts = [ordered]@{}
$lastMovementVerification = $null

foreach ($session in $sessionResults) {
    $reason = $null

    $navigation = Get-OptionalPropertyValue -Object $session -Name 'navigation'
    if ($null -ne $navigation) {
        $stopReason = Get-OptionalPropertyValue -Object $navigation -Name 'StopReason'
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
    $lastNavigation = Get-OptionalPropertyValue -Object $lastSession[0] -Name 'navigation'
    if ($null -ne $lastNavigation) {
        $lastMovementVerification = Get-OptionalPropertyValue -Object $lastNavigation -Name 'MovementVerification'
        if ($null -eq $lastMovementVerification) {
            $lastMovementVerification = Get-OptionalPropertyValue -Object $lastNavigation -Name 'movementVerification'
        }
    }
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
    lastMovementVerification = $lastMovementVerification
    lastFacingCheck = if ($lastFacing.Count -gt 0) { $lastFacing[0] } else { $null }
    stopReasonCounts = $stopReasonCounts
    recentSteps = $recent
}

$summary | ConvertTo-Json -Depth 20
