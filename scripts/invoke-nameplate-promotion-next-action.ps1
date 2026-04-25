[CmdletBinding()]
param(
    [string]$OutputRoot = (Join-Path (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path 'artifacts\tooltip-projection'),
    [int]$InventoryTop = 50,
    [int]$MinRepeatedRootCount = 1,
    [int]$MinRepeatedEdgeCount = 0,
    [switch]$Execute,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$plannerScript = Join-Path $PSScriptRoot 'plan-nameplate-proof-promotion.ps1'

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
            nextAction = $nextAction
            blocker = 'next-action-not-safe-to-run-now'
            safetyBlockers = @($nextAction.safetyBlockers)
            plan = $plan
        }
        if ($Json) { $result | ConvertTo-Json -Depth 100 } else { $result }
        exit 1
    }

    $command = [string]$nextAction.command
    $commandOutput = & ([scriptblock]::Create($command)) 2>&1
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
        exitCode = $commandExitCode
        output = $commandText
        parsedJson = $parsedJson
    }
}

$result = [pscustomobject][ordered]@{
    mode = if ($Execute) { 'execute' } else { 'plan-only' }
    ok = (-not $Execute -or ($null -ne $execution -and [int]$execution.exitCode -eq 0))
    outputRoot = $resolvedOutputRoot
    executed = [bool]$Execute
    controlsInput = $false
    nextAction = $nextAction
    execution = $execution
    plan = $plan
}

if ($Json) {
    $result | ConvertTo-Json -Depth 100
}
else {
    $result
}

if (-not $result.ok) { exit 1 }
