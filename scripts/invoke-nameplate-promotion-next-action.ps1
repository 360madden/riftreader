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
        actionRouting = $Result.actionRouting
        recommendedCommandSafety = $Result.recommendedCommandSafety
        recommendedCommandGroups = $Result.recommendedCommandGroups
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

function ConvertTo-CompactRecommendedCommand {
    param([object]$Command)

    if ($null -eq $Command) { return $null }
    return [pscustomobject][ordered]@{
        name = [string](Get-ObjectPropertyValue -Object $Command -Name 'name')
        safeToRunNow = [bool](Get-ObjectPropertyValue -Object $Command -Name 'safeToRunNow')
        createsArtifacts = [bool](Get-ObjectPropertyValue -Object $Command -Name 'createsArtifacts')
        attachesToProcess = [bool](Get-ObjectPropertyValue -Object $Command -Name 'attachesToProcess')
        requiresOperatorConfirmation = [bool](Get-ObjectPropertyValue -Object $Command -Name 'requiresOperatorConfirmation')
        safetyBlockers = @((Get-ObjectPropertyValue -Object $Command -Name 'safetyBlockers') | ForEach-Object { [string]$_ })
    }
}

function Find-RecommendedCommandByName {
    param(
        [Parameter(Mandatory = $true)][object]$Plan,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $commandsValue = Get-ObjectPropertyValue -Object $Plan -Name 'recommendedCommands'
    foreach ($command in @($commandsValue)) {
        if ([string](Get-ObjectPropertyValue -Object $command -Name 'name') -eq $Name) {
            return $command
        }
    }
    return $null
}

function New-ActionRouting {
    param(
        [Parameter(Mandatory = $true)][object]$Plan,
        [Parameter(Mandatory = $true)][object]$NextAction,
        [string]$PreferredSafeCommandName,
        [string]$PreferredSafeCommandReason
    )

    $nextActionSafeToRunNow = [bool](Get-ObjectPropertyValue -Object $NextAction -Name 'safeToRunNow')
    $nextActionSafetyBlockers = @((Get-ObjectPropertyValue -Object $NextAction -Name 'safetyBlockers') | ForEach-Object { [string]$_ })
    $preferredCommand = $null
    $preferredReason = 'no-safe-no-write-command'

    if (-not [string]::IsNullOrWhiteSpace($PreferredSafeCommandName)) {
        $preferredCommand = Find-RecommendedCommandByName -Plan $Plan -Name $PreferredSafeCommandName
        if ($null -ne $preferredCommand) {
            $preferredReason = if ([string]::IsNullOrWhiteSpace($PreferredSafeCommandReason)) { 'explicit-safe-command-preference' } else { $PreferredSafeCommandReason }
        }
    }

    if ($null -eq $preferredCommand -and $nextActionSafeToRunNow) {
        $preferredCommand = $NextAction
        $preferredReason = 'next-action-is-safe'
    }
    elseif ($null -eq $preferredCommand) {
        $groups = Get-ObjectPropertyValue -Object $Plan -Name 'recommendedCommandGroups'
        $safeNoWriteNames = @((Get-ObjectPropertyValue -Object $groups -Name 'safeNoWrite') | ForEach-Object { [string]$_ })
        $preferredSafeName = @($safeNoWriteNames | Where-Object { $_ -ne 'inventory' } | Select-Object -First 1)[0]
        if ([string]::IsNullOrWhiteSpace($preferredSafeName)) {
            $preferredSafeName = @($safeNoWriteNames | Select-Object -First 1)[0]
        }
        if (-not [string]::IsNullOrWhiteSpace($preferredSafeName)) {
            $preferredCommand = Find-RecommendedCommandByName -Plan $Plan -Name $preferredSafeName
            if ($null -ne $preferredCommand) {
                $preferredReason = 'first-safe-no-write-recommended-command'
            }
        }
    }

    $preferredCompact = ConvertTo-CompactRecommendedCommand -Command $preferredCommand
    return [pscustomobject][ordered]@{
        nextActionName = [string](Get-ObjectPropertyValue -Object $NextAction -Name 'name')
        nextActionSafeToRunNow = $nextActionSafeToRunNow
        blockedReason = if ($nextActionSafeToRunNow) { $null } else { 'next-action-not-safe-to-run-now' }
        safetyBlockers = $nextActionSafetyBlockers
        preferredSafeCommandName = if ($null -ne $preferredCompact) { [string]$preferredCompact.name } else { $null }
        preferredSafeCommandReason = $preferredReason
        preferredSafeCommand = $preferredCompact
    }
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
$actionRouting = New-ActionRouting -Plan $plan -NextAction $nextAction

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
            actionRouting = $actionRouting
            recommendedCommandSafety = $plan.recommendedCommandSafety
            recommendedCommandGroups = $plan.recommendedCommandGroups
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

if ($Execute -and [string]$nextAction.name -eq 'inspect-latest-ungated-baseline-zoom-run' -and $null -ne $executionSummary -and $false -eq [bool]$executionSummary.parsedOk) {
    $actionRouting = New-ActionRouting -Plan $plan -NextAction $nextAction -PreferredSafeCommandName 'replacement-readiness-checklist' -PreferredSafeCommandReason 'ungated-inspection-completed'
}

$result = [pscustomobject][ordered]@{
    mode = if ($Execute) { 'execute' } else { 'plan-only' }
    ok = (-not $Execute -or ($null -ne $execution -and [int]$execution.exitCode -eq 0))
    outputRoot = $resolvedOutputRoot
    executed = [bool]$Execute
    controlsInput = $false
    nextAction = $nextAction
    actionRouting = $actionRouting
    recommendedCommandSafety = $plan.recommendedCommandSafety
    recommendedCommandGroups = $plan.recommendedCommandGroups
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
