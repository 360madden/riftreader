[CmdletBinding()]
param(
    [string]$OutputRoot = (Join-Path (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path 'artifacts\tooltip-projection'),
    [int]$Top = 50,
    [string]$OutputFile,

    [switch]$PlanOnly,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$inventoryScript = Join-Path $PSScriptRoot 'list-nameplate-proof-runs.ps1'
$resultCheckerScript = Join-Path $PSScriptRoot 'check-nameplate-projection-proof-result.ps1'

function Invoke-JsonScript {
    param(
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $output = & pwsh -NoProfile -ExecutionPolicy Bypass -File $ScriptPath @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $text = $output -join [Environment]::NewLine
    $parsed = $null
    $parseError = $null
    try {
        if (-not [string]::IsNullOrWhiteSpace($text)) {
            $parsed = $text | ConvertFrom-Json -Depth 100
        }
    }
    catch {
        $parseError = $_.Exception.Message
    }

    return [pscustomobject][ordered]@{
        exitCode = $exitCode
        parsed = $parsed
        parseError = $parseError
        output = $text
    }
}

function ConvertTo-RunAuditSummary {
    param([object]$Run)

    if ($null -eq $Run) {
        return $null
    }

    $lastWriteTimeUtc = $null
    if ($null -ne $Run.PSObject.Properties['lastWriteTimeUtc'] -and $null -ne $Run.lastWriteTimeUtc) {
        if ($Run.lastWriteTimeUtc -is [datetime]) {
            $lastWriteTimeUtc = $Run.lastWriteTimeUtc.ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        }
        else {
            $lastWriteTimeUtc = [string]$Run.lastWriteTimeUtc
        }
    }
    $states = if ($null -ne $Run.PSObject.Properties['states'] -and $null -ne $Run.states) { @($Run.states | ForEach-Object { [string]$_ }) } else { @() }

    return [pscustomobject][ordered]@{
        name = [string]$Run.name
        runRoot = [string]$Run.runRoot
        lastWriteTimeUtc = $lastWriteTimeUtc
        sampleCount = if ($null -ne $Run.PSObject.Properties['sampleCount']) { [int]$Run.sampleCount } else { $null }
        states = @($states)
        manifestExists = ($null -ne $Run.PSObject.Properties['manifest'] -and [bool]$Run.manifest.exists)
        gatedPassed = ($null -ne $Run.PSObject.Properties['gated'] -and [bool]$Run.gated.passed)
        hasLeadNeighborhood = if ($null -ne $Run.PSObject.Properties['hasLeadNeighborhood']) { [bool]$Run.hasLeadNeighborhood } else { $false }
        hasPromotionPacket = if ($null -ne $Run.PSObject.Properties['hasPromotionPacket']) { [bool]$Run.hasPromotionPacket } else { $false }
        hasLightweightReproofReport = if ($null -ne $Run.PSObject.Properties['hasLightweightReproofReport']) { [bool]$Run.hasLightweightReproofReport } else { $false }
    }
}

function ConvertTo-InspectionSummary {
    param([object]$Inspection)

    if ($null -eq $Inspection -or $null -eq $Inspection.parsed) {
        return [pscustomobject][ordered]@{
            ok = $false
            failedCheckCount = $null
            failedCheckNames = @()
            checkerExitCode = if ($null -ne $Inspection) { [int]$Inspection.exitCode } else { $null }
            error = if ($null -ne $Inspection) { [string]$Inspection.output } else { 'inspection-not-run' }
        }
    }

    $checks = if ($Inspection.parsed.PSObject.Properties['checks']) { @($Inspection.parsed.checks) } else { @() }
    $failedChecks = @($checks | Where-Object { [string]$_.status -ne 'passed' })
    return [pscustomobject][ordered]@{
        ok = [bool]$Inspection.parsed.ok
        failedCheckCount = $failedChecks.Count
        failedCheckNames = @($failedChecks | ForEach-Object { [string]$_.name })
        checkerExitCode = [int]$Inspection.exitCode
        error = $Inspection.parseError
    }
}

if ($Top -le 0) {
    throw 'Top must be greater than zero.'
}
foreach ($requiredScript in @($inventoryScript, $resultCheckerScript)) {
    if (-not (Test-Path -LiteralPath $requiredScript -PathType Leaf)) {
        throw "Required script not found: $requiredScript"
    }
}

$resolvedOutputRoot = (Resolve-Path -LiteralPath $OutputRoot).Path
if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $stamp = [datetime]::UtcNow.ToString('yyyyMMdd-HHmmss', [System.Globalization.CultureInfo]::InvariantCulture)
    $OutputFile = Join-Path $resolvedOutputRoot ("audit\nameplate-artifact-audit-$stamp.json")
}
$resolvedOutputFile = if ([System.IO.Path]::IsPathRooted($OutputFile)) {
    $OutputFile
}
else {
    Join-Path (Get-Location).Path $OutputFile
}

$allInventoryResult = Invoke-JsonScript -ScriptPath $inventoryScript -Arguments @('-OutputRoot', $resolvedOutputRoot, '-Top', $Top.ToString([System.Globalization.CultureInfo]::InvariantCulture), '-Json')
if ($allInventoryResult.exitCode -ne 0 -or $null -eq $allInventoryResult.parsed) {
    throw "Inventory failed with exit code $($allInventoryResult.exitCode)`n$($allInventoryResult.output)"
}
$gatedInventoryResult = Invoke-JsonScript -ScriptPath $inventoryScript -Arguments @('-OutputRoot', $resolvedOutputRoot, '-Top', $Top.ToString([System.Globalization.CultureInfo]::InvariantCulture), '-RequireGated', '-Json')
if ($gatedInventoryResult.exitCode -ne 0 -or $null -eq $gatedInventoryResult.parsed) {
    throw "Gated inventory failed with exit code $($gatedInventoryResult.exitCode)`n$($gatedInventoryResult.output)"
}

$allRuns = @($allInventoryResult.parsed.runs)
$gatedRuns = @($gatedInventoryResult.parsed.runs)
$allBaselineZoomRuns = @($allRuns | Where-Object { [string]$_.name -match 'nameplate-baseline-zoom' })
$gatedBaselineZoomRuns = @($gatedRuns | Where-Object { [string]$_.name -match 'nameplate-baseline-zoom' })
$ungatedBaselineZoomRuns = @($allBaselineZoomRuns | Where-Object { -not [bool]$_.gated.passed })
$latestUngated = if ($ungatedBaselineZoomRuns.Count -gt 0) { $ungatedBaselineZoomRuns[0] } else { $null }
$latestUngatedInspection = $null
if ($null -ne $latestUngated) {
    $latestUngatedInspection = Invoke-JsonScript -ScriptPath $resultCheckerScript -Arguments @('-RunRoot', [string]$latestUngated.runRoot, '-AllowFailed', '-Json')
}
$latestUngatedInspectionSummary = ConvertTo-InspectionSummary -Inspection $latestUngatedInspection

$recommendation = if ($ungatedBaselineZoomRuns.Count -gt 0 -and $gatedBaselineZoomRuns.Count -eq 0) {
    'replace-latest-ungated-run-with-new-gated-baseline-zoom-proof'
}
elseif ($ungatedBaselineZoomRuns.Count -gt 0) {
    'inspect-or-replace-ungated-baseline-zoom-runs-before-promotion'
}
elseif ($gatedBaselineZoomRuns.Count -lt 2) {
    'capture-second-gated-baseline-zoom-proof'
}
else {
    'continue-promotion-pipeline-planning'
}

$report = [pscustomobject][ordered]@{
    mode = 'nameplate-artifact-audit'
    ok = $true
    createdUtc = [datetime]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    planOnly = [bool]$PlanOnly
    wroteReport = (-not [bool]$PlanOnly)
    outputRoot = $resolvedOutputRoot
    outputFile = $resolvedOutputFile
    controlsInput = $false
    attachesToProcess = $false
    createsArtifacts = (-not [bool]$PlanOnly)
    deletesArtifacts = $false
    counts = [pscustomobject][ordered]@{
        totalNameplateRuns = $allRuns.Count
        totalGatedNameplateRuns = $gatedRuns.Count
        totalBaselineZoomRuns = $allBaselineZoomRuns.Count
        gatedBaselineZoomRuns = $gatedBaselineZoomRuns.Count
        ungatedBaselineZoomRuns = $ungatedBaselineZoomRuns.Count
    }
    latestUngatedBaselineZoomRun = ConvertTo-RunAuditSummary -Run $latestUngated
    latestUngatedInspectionSummary = $latestUngatedInspectionSummary
    recommendation = $recommendation
    notes = @(
        'Audit is read-only against existing proof artifacts.',
        'No artifacts are deleted or modified by this command.',
        'PlanOnly does not write the audit report file.'
    )
}

if (-not [bool]$PlanOnly) {
    $outputDirectory = Split-Path -Parent $resolvedOutputFile
    if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
        New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    }
    $report | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $resolvedOutputFile -Encoding UTF8
}

if ($Json) {
    $report | ConvertTo-Json -Depth 100
}
else {
    $report
}
