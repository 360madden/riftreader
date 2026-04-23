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
$readerTestsProject = Join-Path $repoRoot 'reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj'
$smokeRouteScript = Join-Path $PSScriptRoot 'new-forward-smoke-route.ps1'
$prototypeScript = Join-Path $PSScriptRoot 'run-a-to-b-prototype.ps1'

if (($IncludeActiveMovement -or $IncludeMisalignedAutoTurn) -and -not $IncludeLive) {
    throw "-IncludeActiveMovement and -IncludeMisalignedAutoTurn require -IncludeLive because they attach to the live Rift process."
}

$results = New-Object System.Collections.Generic.List[object]

function Invoke-SuiteStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$ScriptBlock
    )

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $output = & $ScriptBlock 2>&1
        $exitCode = 0
    }
    catch {
        $output = @($_.Exception.Message)
        $exitCode = 1
    }
    finally {
        $sw.Stop()
    }

    $results.Add([pscustomobject]@{
        Name = $Name
        ExitCode = $exitCode
        DurationSeconds = [Math]::Round($sw.Elapsed.TotalSeconds, 3)
        Output = ($output -join [Environment]::NewLine).Trim()
        Status = if ($exitCode -eq 0) { 'pass' } else { 'fail' }
    }) | Out-Null
}

Invoke-SuiteStep -Name 'navigation-dotnet-tests' -ScriptBlock {
    & dotnet test $readerTestsProject --filter 'FullyQualifiedName~WaypointNavigation'
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
