[CmdletBinding()]
param(
    [string]$OutputRoot = (Join-Path (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path 'artifacts\tooltip-projection'),
    [int]$InventoryTop = 50,
    [int]$MinRepeatedRootCount = 1,
    [int]$MinRepeatedEdgeCount = 0,
    [switch]$Execute,
    [switch]$SummaryOnly,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$plannerScript = Join-Path $PSScriptRoot 'plan-nameplate-proof-promotion.ps1'

function Get-ObjectPropertyValue {
    param(
        [object]$Object,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Invoke-Planner {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][int]$Top,
        [Parameter(Mandatory = $true)][int]$MinRoots,
        [Parameter(Mandatory = $true)][int]$MinEdges
    )

    $output = & pwsh -NoProfile -ExecutionPolicy Bypass -File $plannerScript -OutputRoot $Root -InventoryTop $Top -MinRepeatedRootCount $MinRoots -MinRepeatedEdgeCount $MinEdges -Json 2>&1
    $exitCode = $LASTEXITCODE
    $text = $output -join [Environment]::NewLine
    if ($exitCode -ne 0) {
        throw "Planner failed with exit code $exitCode`n$text"
    }

    try {
        return $text | ConvertFrom-Json -Depth 100
    }
    catch {
        throw "Planner did not return parseable JSON.`n$text"
    }
}

function ConvertTo-SummaryResult {
    param([Parameter(Mandatory = $true)][object]$Result)

    $summary = [ordered]@{
        mode = $Result.mode
        ok = $Result.ok
        outputRoot = $Result.outputRoot
        executed = $Result.executed
        controlsInput = $Result.controlsInput
        nextAction = $Result.nextAction
        recommendedCommandSafety = $Result.recommendedCommandSafety
        executionSummary = $Result.executionSummary
        operatorChecklist = @($Result.operatorChecklist)
    }

    if ($null -ne $Result.PSObject.Properties['blocker']) {
        $summary.blocker = $Result.blocker
    }
    if ($null -ne $Result.PSObject.Properties['safetyBlockers']) {
        $summary.safetyBlockers = @($Result.safetyBlockers)
    }
    if ($null -ne $Result.execution) {
        $summary.execution = [pscustomobject][ordered]@{
            commandSource = $Result.execution.commandSource
            exitCode = $Result.execution.exitCode
        }
    }
    if ($null -ne $Result.plan) {
        $summary.planSummary = [pscustomobject][ordered]@{
            readyForPipeline = $Result.plan.readyForPipeline
            readyForPromotionCompare = $Result.plan.readyForPromotionCompare
            missingEvidence = @($Result.plan.missingEvidence)
            recommendedCommandCount = @($Result.plan.recommendedCommands).Count
        }
    }

    return [pscustomobject]$summary
}

if ($InventoryTop -le 0) { throw 'InventoryTop must be greater than zero.' }
if ($MinRepeatedRootCount -lt 0) { throw 'MinRepeatedRootCount cannot be negative.' }
if ($MinRepeatedEdgeCount -lt 0) { throw 'MinRepeatedEdgeCount cannot be negative.' }
if (-not (Test-Path -LiteralPath $plannerScript -PathType Leaf)) {
    throw "Planner script not found: $plannerScript"
}

$resolvedOutputRoot = (Resolve-Path -LiteralPath $OutputRoot).Path
$plan = Invoke-Planner -Root $resolvedOutputRoot -Top $InventoryTop -MinRoots $MinRepeatedRootCount -MinEdges $MinRepeatedEdgeCount
$nextAction = $plan.nextAction
if ($null -eq $nextAction) {
    throw 'Planner did not return a nextAction.'
}

$execution = $null
if ($Execute) {
    if (-not [bool]$nextAction.safeToRunNow) {
        $result = [pscustomobject][ordered]@{
            mode = 'execute'
            ok = $false
            outputRoot = $resolvedOutputRoot
            executed = $false
            controlsInput = $false
            nextAction = $nextAction
            recommendedCommandSafety = $plan.recommendedCommandSafety
            executionSummary = $null
            operatorChecklist = @()
            execution = $null
            blocker = 'next-action-not-safe-to-run-now'
            safetyBlockers = @($nextAction.safetyBlockers)
            plan = $plan
        }
        if ($SummaryOnly) {
            $result = ConvertTo-SummaryResult -Result $result
        }
        if ($Json) { $result | ConvertTo-Json -Depth 100 } else { $result }
        exit 1
    }

    $command = [string]$nextAction.command
    $commandPartsValue = Get-ObjectPropertyValue -Object $nextAction -Name 'commandParts'
    $commandParts = if ($null -ne $commandPartsValue) { @($commandPartsValue) } else { @() }
    $commandSource = 'commandStringFallback'
    if ($commandParts.Count -gt 0) {
        $commandSource = 'commandParts'
        $commandExecutable = [string]$commandParts[0]
        $commandArguments = @($commandParts | Select-Object -Skip 1 | ForEach-Object { [string]$_ })
        $commandOutput = & $commandExecutable @commandArguments 2>&1
    }
    else {
        $commandOutput = & ([scriptblock]::Create($command)) 2>&1
    }
    $commandExitCode = $LASTEXITCODE
    $commandText = $commandOutput -join [Environment]::NewLine
    $parsedJson = $null
    if (-not [string]::IsNullOrWhiteSpace($commandText)) {
        try {
            $parsedJson = $commandText | ConvertFrom-Json -Depth 100
        }
        catch {
            $parsedJson = $null
        }
    }

    $execution = [pscustomobject][ordered]@{
        command = $command
        commandParts = @($commandParts)
        commandSource = $commandSource
        exitCode = $commandExitCode
        output = $commandText
        parsedJson = $parsedJson
    }
}

$executionSummary = $null
$operatorChecklist = $null
$operatorChecklistOutput = @()
if ($null -ne $execution -and $null -ne $execution.parsedJson) {
    $operatorChecklistValue = Get-ObjectPropertyValue -Object $execution.parsedJson -Name 'operatorChecklist'
    if ($null -ne $operatorChecklistValue) {
        $operatorChecklist = @($operatorChecklistValue)
        $operatorChecklistOutput = @($operatorChecklist)
    }

    $notesValue = Get-ObjectPropertyValue -Object $execution.parsedJson -Name 'notes'
    $notesOutput = if ($null -ne $notesValue) { @($notesValue) } else { @() }
    $parsedOk = Get-ObjectPropertyValue -Object $execution.parsedJson -Name 'ok'
    $checksValue = Get-ObjectPropertyValue -Object $execution.parsedJson -Name 'checks'
    $failedChecks = @()
    if ($null -ne $checksValue) {
        $failedChecks = @($checksValue | Where-Object { [string](Get-ObjectPropertyValue -Object $_ -Name 'status') -ne 'passed' })
    }
    $executionSummary = [pscustomobject][ordered]@{
        mode = Get-ObjectPropertyValue -Object $execution.parsedJson -Name 'mode'
        runId = Get-ObjectPropertyValue -Object $execution.parsedJson -Name 'runId'
        runRoot = Get-ObjectPropertyValue -Object $execution.parsedJson -Name 'runRoot'
        controlsInput = Get-ObjectPropertyValue -Object $execution.parsedJson -Name 'controlsInput'
        parsedOk = $parsedOk
        failedCheckCount = $failedChecks.Count
        failedCheckNames = @($failedChecks | ForEach-Object { [string](Get-ObjectPropertyValue -Object $_ -Name 'name') })
        operatorChecklistCount = $operatorChecklistOutput.Count
        notes = $notesOutput
    }
}

$result = [pscustomobject][ordered]@{
    mode = if ($Execute) { 'execute' } else { 'plan-only' }
    ok = (-not $Execute -or ($null -ne $execution -and [int]$execution.exitCode -eq 0))
    outputRoot = $resolvedOutputRoot
    executed = [bool]$Execute
    controlsInput = $false
    nextAction = $nextAction
    recommendedCommandSafety = $plan.recommendedCommandSafety
    executionSummary = $executionSummary
    operatorChecklist = $operatorChecklistOutput
    execution = $execution
    plan = $plan
}

if ($SummaryOnly) {
    $result = ConvertTo-SummaryResult -Result $result
}

if ($Json) {
    $result | ConvertTo-Json -Depth 100
}
else {
    $result
}

if (-not $result.ok) { exit 1 }
