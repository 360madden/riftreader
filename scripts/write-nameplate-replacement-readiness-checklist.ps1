[CmdletBinding()]
param(
    [string]$OutputRoot = (Join-Path (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path 'artifacts\tooltip-projection'),
    [int]$Top = 50,
    [string]$CandidateAddress,
    [int]$CandidateLength = 1024,
    [string]$NameplateText,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$inventoryScript = Join-Path $PSScriptRoot 'list-nameplate-proof-runs.ps1'
$resultCheckerScript = Join-Path $PSScriptRoot 'check-nameplate-projection-proof-result.ps1'
$proofWrapperScript = Join-Path $PSScriptRoot 'run-nameplate-projection-proof.ps1'

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

function New-ReadinessCheck {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Status,
        [string]$Detail,
        [object]$Data
    )

    return [pscustomobject][ordered]@{
        name = $Name
        status = $Status
        detail = $Detail
        data = $Data
    }
}

function ConvertTo-RunSummary {
    param([object]$Run)

    if ($null -eq $Run) { return $null }
    return [pscustomobject][ordered]@{
        name = [string]$Run.name
        runRoot = [string]$Run.runRoot
        lastWriteTimeUtc = if ($Run.PSObject.Properties['lastWriteTimeUtc']) { [string]$Run.lastWriteTimeUtc } else { $null }
        sampleCount = if ($Run.PSObject.Properties['sampleCount']) { [int]$Run.sampleCount } else { $null }
        states = if ($Run.PSObject.Properties['states']) { @($Run.states | ForEach-Object { [string]$_ }) } else { @() }
        gatedPassed = ($Run.PSObject.Properties['gated'] -and [bool]$Run.gated.passed)
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

function Test-RealValue {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    if ($Value -match '^<[^>]+>$') { return $false }
    return $true
}

if ($Top -le 0) { throw 'Top must be greater than zero.' }
if ($CandidateLength -le 0) { throw 'CandidateLength must be greater than zero.' }
foreach ($requiredScript in @($inventoryScript, $resultCheckerScript, $proofWrapperScript)) {
    if (-not (Test-Path -LiteralPath $requiredScript -PathType Leaf)) {
        throw "Required script not found: $requiredScript"
    }
}

$resolvedOutputRoot = (Resolve-Path -LiteralPath $OutputRoot).Path
$inventoryResult = Invoke-JsonScript -ScriptPath $inventoryScript -Arguments @('-OutputRoot', $resolvedOutputRoot, '-Top', $Top.ToString([System.Globalization.CultureInfo]::InvariantCulture), '-Json')
if ($inventoryResult.exitCode -ne 0 -or $null -eq $inventoryResult.parsed) {
    throw "Inventory failed with exit code $($inventoryResult.exitCode)`n$($inventoryResult.output)"
}

$baselineZoomRuns = @($inventoryResult.parsed.runs | Where-Object { [string]$_.name -match 'nameplate-baseline-zoom' })
$ungatedBaselineZoomRuns = @($baselineZoomRuns | Where-Object { -not [bool]$_.gated.passed })
$latestUngated = if ($ungatedBaselineZoomRuns.Count -gt 0) { $ungatedBaselineZoomRuns[0] } else { $null }
$latestInspection = $null
if ($null -ne $latestUngated) {
    $latestInspection = Invoke-JsonScript -ScriptPath $resultCheckerScript -Arguments @('-RunRoot', [string]$latestUngated.runRoot, '-AllowFailed', '-Json')
}
$inspectionSummary = ConvertTo-InspectionSummary -Inspection $latestInspection

$candidateAddressReady = Test-RealValue -Value $CandidateAddress
$nameplateTextReady = Test-RealValue -Value $NameplateText
$candidateForCommand = if ($candidateAddressReady) { $CandidateAddress } else { '<fresh-candidate-address>' }
$nameplateForCommand = if ($nameplateTextReady) { $NameplateText } else { '<visible-nameplate-text>' }
$replacementPlanCommandParts = @(
    'pwsh',
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $proofWrapperScript,
    '-CandidateAddress',
    $candidateForCommand,
    '-CandidateLength',
    $CandidateLength.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-NameplateText',
    $nameplateForCommand,
    '-OutputRoot',
    $resolvedOutputRoot,
    '-PlanOnly',
    '-Json'
)

$checks = [System.Collections.Generic.List[object]]::new()
$checks.Add((New-ReadinessCheck -Name 'latest-ungated-baseline-zoom-run' -Status $(if ($null -ne $latestUngated) { 'passed' } else { 'blocked' }) -Detail $(if ($null -ne $latestUngated) { 'Latest ungated baseline/zoom run identified for replacement.' } else { 'No ungated baseline/zoom run was found to replace.' }) -Data (ConvertTo-RunSummary -Run $latestUngated))) | Out-Null
$checks.Add((New-ReadinessCheck -Name 'source-run-not-promotion-ready' -Status $(if ($null -ne $latestUngated -and -not [bool]$inspectionSummary.ok) { 'passed' } elseif ($null -ne $latestUngated) { 'warning' } else { 'blocked' }) -Detail 'Replacement should target an incomplete or failed-gate run, not a promotion-ready proof.' -Data $inspectionSummary)) | Out-Null
$checks.Add((New-ReadinessCheck -Name 'fresh-candidate-address-provided' -Status $(if ($candidateAddressReady) { 'passed' } else { 'blocked' }) -Detail 'Provide a freshly resolved candidate address before live replacement capture.' -Data ([pscustomobject][ordered]@{ value = if ($candidateAddressReady) { $CandidateAddress } else { $null } }))) | Out-Null
$checks.Add((New-ReadinessCheck -Name 'visible-nameplate-text-provided' -Status $(if ($nameplateTextReady) { 'passed' } else { 'blocked' }) -Detail 'Provide the operator-visible nameplate text before live replacement capture.' -Data ([pscustomobject][ordered]@{ value = if ($nameplateTextReady) { $NameplateText } else { $null } }))) | Out-Null
$checks.Add((New-ReadinessCheck -Name 'replacement-plan-command-ready' -Status 'passed' -Detail 'PlanOnly replacement command is available and does not attach to Rift or write artifacts.' -Data ([pscustomobject][ordered]@{ commandParts = @($replacementPlanCommandParts) }))) | Out-Null
$checks.Add((New-ReadinessCheck -Name 'live-replacement-requires-operator-approval' -Status 'blocked' -Detail 'Live replacement capture attaches to Rift and creates artifacts; run only after operator approval.' -Data ([pscustomobject][ordered]@{ attachesToProcess = $true; createsArtifacts = $true; requiresOperatorConfirmation = $true }))) | Out-Null

$blockingChecks = @($checks.ToArray() | Where-Object { [string]$_.status -eq 'blocked' -and [string]$_.name -ne 'live-replacement-requires-operator-approval' })
$readyForReplacementPlan = ($blockingChecks.Count -eq 0)

$result = [pscustomObject][ordered]@{
    mode = 'nameplate-replacement-readiness-checklist'
    ok = $true
    readyForReplacementPlan = $readyForReplacementPlan
    readyForLiveReplacement = $false
    outputRoot = $resolvedOutputRoot
    controlsInput = $false
    attachesToProcess = $false
    createsArtifacts = $false
    deletesArtifacts = $false
    latestUngatedBaselineZoomRun = ConvertTo-RunSummary -Run $latestUngated
    latestUngatedInspectionSummary = $inspectionSummary
    replacementPlanCommandParts = @($replacementPlanCommandParts)
    checks = @($checks.ToArray())
    blockers = @($blockingChecks | ForEach-Object { [string]$_.name })
    notes = @(
        'This checklist is read-only and writes no files.',
        'Use replacementPlanCommandParts first; it is PlanOnly and should not attach to Rift.',
        'Do not run live replacement capture until the operator approves an attach/artifact-writing proof run.'
    )
}

if ($Json) {
    $result | ConvertTo-Json -Depth 100
}
else {
    $result
}
