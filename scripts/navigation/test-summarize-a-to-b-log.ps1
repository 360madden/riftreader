[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-True {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$Condition,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-Equal {
    param(
        $Actual,
        $Expected,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if ($Actual -ne $Expected) {
        throw ("{0} Expected '{1}', got '{2}'." -f $Message, $Expected, $Actual)
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$summaryScript = Join-Path $repoRoot 'scripts\navigation\summarize-a-to-b-log.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-nav-summary-' + [System.Guid]::NewGuid().ToString('N'))
$sessionLog = Join-Path $tempRoot 'session.ndjson'
$fallbackLog = Join-Path $tempRoot 'fallback.ndjson'

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $navigation = [ordered]@{
        Mode = 'navigate-waypoints'
        Status = 'success'
        StopReason = 'arrived'
        PulseCount = 2
        AnchorSource = 'coord-trace-anchor'
        InitialPlanarDistance = 2.6
        FinalPlanarDistance = 1.89
        InitialPosition = [ordered]@{ X = 7260.585; Y = 875.679; Z = 3052.921 }
        FinalPosition = [ordered]@{ X = 7261.057; Y = 875.697; Z = 3053.452 }
        ElapsedMilliseconds = 421
        MovementVerification = [ordered]@{ Status = 'moved'; PlanarMoved = 0.71 }
    }
    $sessionEntry = [ordered]@{
        timestampUtc = '2026-04-30T15:00:00.0000000Z'
        step = 'session-result'
        exitCode = 0
        processName = 'rift_x64'
        waypointFile = 'C:\RIFT MODDING\RiftReader\scripts\captures\smoke-waypoints.json'
        route = [ordered]@{
            startWaypointId = 'smoke_start'
            destinationWaypointId = 'smoke_destination'
            startLabel = 'Smoke Start'
            destinationLabel = 'Smoke Destination'
        }
        arguments = @('navigate')
        output = ($navigation | ConvertTo-Json -Compress -Depth 20)
        navigation = $navigation
    }
    Set-Content -LiteralPath $sessionLog -Value ($sessionEntry | ConvertTo-Json -Compress -Depth 30) -Encoding UTF8

    $summaryOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $summaryScript -LogFile $sessionLog -RecentCount 1
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message 'summarize-a-to-b-log.ps1 failed for session fixture.'
    $summary = ($summaryOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
    $last = $summary.lastNavigationSummary

    Assert-Equal -Actual ([string]$last.status) -Expected 'success' -Message 'lastNavigationSummary.status mismatch.'
    Assert-Equal -Actual ([string]$last.stopReason) -Expected 'arrived' -Message 'lastNavigationSummary.stopReason mismatch.'
    Assert-Equal -Actual ([int]$last.pulseCount) -Expected 2 -Message 'lastNavigationSummary.pulseCount mismatch.'
    Assert-Equal -Actual ([string]$last.anchorSource) -Expected 'coord-trace-anchor' -Message 'lastNavigationSummary.anchorSource mismatch.'
    Assert-Equal -Actual ([string]$last.startWaypointId) -Expected 'smoke_start' -Message 'lastNavigationSummary.startWaypointId mismatch.'
    Assert-Equal -Actual ([string]$last.destinationWaypointId) -Expected 'smoke_destination' -Message 'lastNavigationSummary.destinationWaypointId mismatch.'
    Assert-True -Condition ([double]$last.initialPlanarDistance -gt [double]$last.finalPlanarDistance) -Message 'lastNavigationSummary should preserve improving distance.'
    Assert-True -Condition ([double]$last.planarMoved -gt 0.7 -and [double]$last.planarMoved -lt 0.72) -Message 'lastNavigationSummary.planarMoved should be computed from initial/final positions.'
    Assert-Equal -Actual ([string]$summary.stopReasonCounts.arrived) -Expected '1' -Message 'stopReasonCounts.arrived mismatch.'

    $fallbackNavigation = [ordered]@{
        Status = 'success'
        StopReason = 'arrived'
        PulseCount = 1
        AnchorSource = 'coord-trace-anchor'
        InitialPlanarDistance = 3.0
        FinalPlanarDistance = 2.5
        InitialPosition = [ordered]@{ X = 10.0; Y = 1.0; Z = 20.0 }
        FinalPosition = [ordered]@{ X = 10.3; Y = 1.0; Z = 20.4 }
        ElapsedMilliseconds = 200
        WaypointFile = 'fallback-waypoints.json'
        StartWaypointId = 'fallback_start'
        DestinationWaypointId = 'fallback_destination'
    }
    $fallbackEntry = [ordered]@{
        timestampUtc = '2026-04-30T15:01:00.0000000Z'
        step = 'navigate'
        exitCode = 0
        processName = 'rift_x64'
        arguments = @('--navigate-waypoints')
        output = "Reader banner`n$($fallbackNavigation | ConvertTo-Json -Compress -Depth 20)`nDone"
    }
    Set-Content -LiteralPath $fallbackLog -Value ($fallbackEntry | ConvertTo-Json -Compress -Depth 30) -Encoding UTF8

    $fallbackSummaryOutput = & pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $summaryScript -LogFile $fallbackLog
    Assert-True -Condition ($LASTEXITCODE -eq 0) -Message 'summarize-a-to-b-log.ps1 failed for fallback fixture.'
    $fallbackSummary = ($fallbackSummaryOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
    $fallbackLast = $fallbackSummary.lastNavigationSummary
    Assert-Equal -Actual ([string]$fallbackLast.status) -Expected 'success' -Message 'fallback lastNavigationSummary.status mismatch.'
    Assert-Equal -Actual ([string]$fallbackLast.startWaypointId) -Expected 'fallback_start' -Message 'fallback startWaypointId mismatch.'
    Assert-Equal -Actual ([string]$fallbackLast.destinationWaypointId) -Expected 'fallback_destination' -Message 'fallback destinationWaypointId mismatch.'
    Assert-True -Condition ([double]$fallbackLast.planarMoved -gt 0.49 -and [double]$fallbackLast.planarMoved -lt 0.51) -Message 'fallback planarMoved should be parsed/computed from embedded JSON.'
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host 'navigation log summary regression check passed.' -ForegroundColor Green
