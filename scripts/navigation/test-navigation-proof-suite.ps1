[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [switch]$IncludeLive,
    [switch]$SkipRefresh,
    [switch]$IncludeActiveMovement,
    [switch]$IncludeMisalignedAutoTurn,
    [double]$MisalignedBearingOffsetDegrees = 20.0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$readerTestsProject = Join-Path $repoRoot 'reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj'
$smokeRouteScript = Join-Path $PSScriptRoot 'new-forward-smoke-route.ps1'
$prototypeScript = Join-Path $PSScriptRoot 'run-a-to-b-prototype.ps1'
$smokeRouteFile = Join-Path $PSScriptRoot 'smoke-test-waypoints.json'

if (($IncludeActiveMovement -or $IncludeMisalignedAutoTurn) -and -not $IncludeLive) {
    throw "-IncludeActiveMovement and -IncludeMisalignedAutoTurn require -IncludeLive because they attach to the live Rift process."
}

$results = New-Object System.Collections.Generic.List[object]

function Assert-ProofCondition {
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

function ConvertFrom-CommandJsonObject {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Output
    )

    $text = (@($Output) | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    $jsonStart = $text.IndexOf('{')
    if ($jsonStart -lt 0) {
        throw "Command output did not contain a JSON object. Output: $text"
    }

    return $text.Substring($jsonStart) | ConvertFrom-Json
}

function Assert-SmokeRoutePlanResult {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Plan
    )

    Assert-ProofCondition -Condition ($Plan.Mode -eq 'navigation-route-plan') -Message "Route-plan mode was '$($Plan.Mode)'."
    Assert-ProofCondition -Condition ($Plan.Status -eq 'success') -Message "Route-plan status was '$($Plan.Status)'."
    Assert-ProofCondition -Condition ($Plan.StartWaypointId -eq 'smoke_start') -Message "Route-plan start waypoint was '$($Plan.StartWaypointId)'."
    Assert-ProofCondition -Condition ($Plan.DestinationWaypointId -eq 'smoke_destination') -Message "Route-plan destination waypoint was '$($Plan.DestinationWaypointId)'."
    Assert-ProofCondition -Condition ($Plan.SegmentCount -eq 1) -Message "Expected one smoke route segment; got $($Plan.SegmentCount)."
    Assert-ProofCondition -Condition (@($Plan.WaypointIds).Count -eq 2) -Message "Expected two smoke route waypoint ids."
    Assert-ProofCondition -Condition (@($Plan.Segments).Count -eq 1) -Message "Expected one smoke route segment payload."

    $segment = @($Plan.Segments)[0]
    Assert-ProofCondition -Condition ($segment.SegmentIndex -eq 1) -Message "Smoke route segment index was $($segment.SegmentIndex)."
    Assert-ProofCondition -Condition ($segment.StartWaypointId -eq 'smoke_start') -Message "Smoke route segment start was '$($segment.StartWaypointId)'."
    Assert-ProofCondition -Condition ($segment.DestinationWaypointId -eq 'smoke_destination') -Message "Smoke route segment destination was '$($segment.DestinationWaypointId)'."
    Assert-ProofCondition -Condition ([double]$segment.PlanarDistance -gt 0.0) -Message "Smoke route segment planar distance was not positive."
    Assert-ProofCondition -Condition ([double]$segment.ArrivalRadius -gt 0.0) -Message "Smoke route segment arrival radius was not positive."
    Assert-ProofCondition -Condition (-not [string]::IsNullOrWhiteSpace([string]$segment.Pace)) -Message "Smoke route segment pace was blank."
}

function Invoke-SuiteStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$ScriptBlock
    )

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $outputItems = New-Object System.Collections.Generic.List[object]
    try {
        & $ScriptBlock 2>&1 | ForEach-Object {
            $outputItems.Add($_) | Out-Null
        }
        $exitCode = 0
    }
    catch {
        $outputItems.Add($_.Exception.Message) | Out-Null
        $exitCode = 1
    }
    finally {
        $sw.Stop()
    }

    $results.Add([pscustomobject]@{
        Name = $Name
        ExitCode = $exitCode
        DurationSeconds = [Math]::Round($sw.Elapsed.TotalSeconds, 3)
        Output = (@($outputItems.ToArray()) -join [Environment]::NewLine).Trim()
        Status = if ($exitCode -eq 0) { 'pass' } else { 'fail' }
    }) | Out-Null
}

Invoke-SuiteStep -Name 'navigation-dotnet-tests' -ScriptBlock {
    & dotnet test $readerTestsProject --filter 'FullyQualifiedName~WaypointNavigation|FullyQualifiedName~WaypointRoute|FullyQualifiedName~NavigationRoute|FullyQualifiedName~ReaderOptionsParser'
    if ($LASTEXITCODE -ne 0) {
        throw "dotnet test failed with exit code $LASTEXITCODE."
    }
}

if ($IncludeLive) {
    function New-SmokeRouteArguments {
        param([double]$BearingOffsetDegrees = 0.0)

        $arguments = @(
            '-NoLogo',
            '-NoProfile',
            '-ExecutionPolicy', 'Bypass',
            '-File', $smokeRouteScript,
            '-ProcessName', $ProcessName
        )

        if ($BearingOffsetDegrees -ne 0.0) {
            $arguments += @('-BearingOffsetDegrees', $BearingOffsetDegrees.ToString([System.Globalization.CultureInfo]::InvariantCulture))
        }

        if ($SkipRefresh) {
            $arguments += '-SkipRefresh'
        }

        return $arguments
    }

    function New-PrototypeArguments {
        param(
            [switch]$PreflightOnly,
            [switch]$AutoTurnBeforeMove
        )

        $arguments = @(
            '-NoLogo',
            '-NoProfile',
            '-ExecutionPolicy', 'Bypass',
            '-File', $prototypeScript,
            '-ProcessName', $ProcessName,
            '-UseSmokeTestFile',
            '-UseExistingWaypoints',
            '-AutoConfirm'
        )

        if ($PreflightOnly) {
            $arguments += '-PreflightOnly'
        }

        if ($AutoTurnBeforeMove) {
            $arguments += '-AutoTurnBeforeMove'
        }

        if ($SkipRefresh) {
            $arguments += '-SkipRefresh'
        }

        return $arguments
    }

    Invoke-SuiteStep -Name 'navigation-live-smoke-route' -ScriptBlock {
        $arguments = New-SmokeRouteArguments
        & pwsh @arguments
        if ($LASTEXITCODE -ne 0) {
            throw "new-forward-smoke-route.ps1 failed with exit code $LASTEXITCODE."
        }
    }

    Invoke-SuiteStep -Name 'navigation-live-route-plan' -ScriptBlock {
        $routePlanOutput = & dotnet run --project $readerProject -- `
            --process-name $ProcessName `
            --plan-navigation-route `
            --start-waypoint smoke_start `
            --destination-waypoint smoke_destination `
            --navigation-waypoint-file $smokeRouteFile `
            --json
        if ($LASTEXITCODE -ne 0) {
            throw "navigation route planning failed with exit code $LASTEXITCODE."
        }

        $routePlan = ConvertFrom-CommandJsonObject -Output $routePlanOutput
        Assert-SmokeRoutePlanResult -Plan $routePlan
    }

    Invoke-SuiteStep -Name 'navigation-live-preflight' -ScriptBlock {
        $arguments = New-PrototypeArguments -PreflightOnly
        & pwsh @arguments
        if ($LASTEXITCODE -ne 0) {
            throw "run-a-to-b-prototype.ps1 preflight failed with exit code $LASTEXITCODE."
        }
    }

    Invoke-SuiteStep -Name 'navigation-live-auto-turn-preflight' -ScriptBlock {
        $arguments = New-PrototypeArguments -PreflightOnly -AutoTurnBeforeMove
        & pwsh @arguments
        if ($LASTEXITCODE -ne 0) {
            throw "run-a-to-b-prototype.ps1 auto-turn preflight failed with exit code $LASTEXITCODE."
        }
    }

    if ($IncludeActiveMovement) {
        Invoke-SuiteStep -Name 'navigation-live-active-movement' -ScriptBlock {
            $arguments = New-PrototypeArguments
            & pwsh @arguments
            if ($LASTEXITCODE -ne 0) {
                throw "run-a-to-b-prototype.ps1 active movement failed with exit code $LASTEXITCODE."
            }
        }
    }

    if ($IncludeMisalignedAutoTurn) {
        Invoke-SuiteStep -Name 'navigation-live-misaligned-smoke-route' -ScriptBlock {
            $arguments = New-SmokeRouteArguments -BearingOffsetDegrees $MisalignedBearingOffsetDegrees
            & pwsh @arguments
            if ($LASTEXITCODE -ne 0) {
                throw "new-forward-smoke-route.ps1 misaligned route failed with exit code $LASTEXITCODE."
            }
        }

        Invoke-SuiteStep -Name 'navigation-live-misaligned-auto-turn' -ScriptBlock {
            $arguments = New-PrototypeArguments -AutoTurnBeforeMove
            & pwsh @arguments
            if ($LASTEXITCODE -ne 0) {
                throw "run-a-to-b-prototype.ps1 misaligned auto-turn movement failed with exit code $LASTEXITCODE."
            }
        }
    }
}

$failed = @($results | Where-Object { $_.ExitCode -ne 0 })
if ($failed.Count -gt 0) {
    Write-Host 'Navigation proof suite failed:' -ForegroundColor Red
    foreach ($result in $results) {
        Write-Host ("[{0}] {1} ({2}s)" -f $result.Status.ToUpperInvariant(), $result.Name, $result.DurationSeconds)
        if (-not [string]::IsNullOrWhiteSpace($result.Output)) {
            Write-Host $result.Output
        }
    }

    exit 1
}

Write-Host 'Navigation proof suite passed.' -ForegroundColor Green
foreach ($result in $results) {
    Write-Host ("[PASS] {0} ({1}s)" -f $result.Name, $result.DurationSeconds)
}
