[CmdletBinding()]
param(
    [string]$OutputRoot = (Join-Path (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path 'artifacts\tooltip-projection'),
    [int]$InventoryTop = 50,
    [int]$MinRepeatedRootCount = 1,
    [int]$MinRepeatedEdgeCount = 0,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$inventoryScript = Join-Path $PSScriptRoot 'list-nameplate-proof-runs.ps1'
$promotionPipelineScript = Join-Path $PSScriptRoot 'run-nameplate-proof-promotion-pipeline.ps1'
$captureNeighborhoodScript = Join-Path $PSScriptRoot 'capture-nameplate-proof-lead-neighborhoods.ps1'
$proofWrapperScript = Join-Path $PSScriptRoot 'run-nameplate-projection-proof.ps1'

function Invoke-Inventory {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][int]$Top
    )

    $output = & pwsh -NoProfile -ExecutionPolicy Bypass -File $inventoryScript -OutputRoot $Root -Top $Top -RequireGated -Json 2>&1
    $exitCode = $LASTEXITCODE
    $text = $output -join [Environment]::NewLine
    if ($exitCode -ne 0) {
        throw "Inventory failed with exit code $exitCode`n$text"
    }

    return $text | ConvertFrom-Json -Depth 100
}

function New-CommandString {
    param([Parameter(Mandatory = $true)][string[]]$Parts)
    return ($Parts | ForEach-Object {
        if ($_ -match '\s') { '"{0}"' -f ($_ -replace '"', '\"') } else { $_ }
    }) -join ' '
}

if ($InventoryTop -le 0) {
    throw 'InventoryTop must be greater than zero.'
}
if ($MinRepeatedRootCount -lt 0) {
    throw 'MinRepeatedRootCount cannot be negative.'
}
if ($MinRepeatedEdgeCount -lt 0) {
    throw 'MinRepeatedEdgeCount cannot be negative.'
}
foreach ($requiredScript in @($inventoryScript, $promotionPipelineScript, $captureNeighborhoodScript, $proofWrapperScript)) {
    if (-not (Test-Path -LiteralPath $requiredScript -PathType Leaf)) {
        throw "Required script not found: $requiredScript"
    }
}

$resolvedOutputRoot = (Resolve-Path -LiteralPath $OutputRoot).Path
$inventory = Invoke-Inventory -Root $resolvedOutputRoot -Top $InventoryTop
$runs = @($inventory.runs)
$baselineZoomRuns = @($runs | Where-Object { [string]$_.name -match 'nameplate-baseline-zoom' })
$promotionReadyRuns = @($baselineZoomRuns | Where-Object { [bool]$_.promotionReady })
$neighborhoodRuns = @($baselineZoomRuns | Where-Object { [bool]$_.hasLeadNeighborhood })
$missingNeighborhoodRuns = @($baselineZoomRuns | Where-Object { -not [bool]$_.hasLeadNeighborhood })

$baselineRun = if ($neighborhoodRuns.Count -gt 0) { $neighborhoodRuns[0] } else { $null }
$reproofRun = $null
if ($neighborhoodRuns.Count -ge 2) {
    $reproofRun = $neighborhoodRuns[1]
}
elseif ($missingNeighborhoodRuns.Count -gt 0) {
    $reproofRun = $missingNeighborhoodRuns[0]
}

$readyForPipeline = ($null -ne $baselineRun -and $null -ne $reproofRun)
$readyForPromotionCompare = ($readyForPipeline -and [bool]$baselineRun.hasLeadNeighborhood -and [bool]$reproofRun.hasLeadNeighborhood)
$missingEvidence = [System.Collections.Generic.List[string]]::new()
if ($baselineZoomRuns.Count -lt 2) {
    $missingEvidence.Add('need-second-gated-nameplate-baseline-zoom-proof') | Out-Null
}
if ($null -eq $baselineRun) {
    $missingEvidence.Add('need-at-least-one-gated-nameplate-run-with-lead-neighborhood') | Out-Null
}
if ($null -ne $reproofRun -and -not [bool]$reproofRun.hasLeadNeighborhood) {
    $missingEvidence.Add('reproof-run-needs-lead-neighborhood-capture') | Out-Null
}
if ($promotionReadyRuns.Count -eq 0) {
    $missingEvidence.Add('no-promotion-ready-packet-yet') | Out-Null
}

$recommendedCommands = [System.Collections.Generic.List[object]]::new()
$recommendedCommands.Add([pscustomobject][ordered]@{
    name = 'inventory'
    command = New-CommandString -Parts @('pwsh', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $inventoryScript, '-OutputRoot', $resolvedOutputRoot, '-RequireGated', '-Top', $InventoryTop.ToString([System.Globalization.CultureInfo]::InvariantCulture), '-Json')
}) | Out-Null

if ($null -ne $reproofRun -and -not [bool]$reproofRun.hasLeadNeighborhood) {
    $recommendedCommands.Add([pscustomobject][ordered]@{
        name = 'capture-reproof-lead-neighborhood'
        command = New-CommandString -Parts @('pwsh', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $captureNeighborhoodScript, '-RunRoot', [string]$reproofRun.runRoot, '-Json')
    }) | Out-Null
}

if ($readyForPipeline) {
    $pipelineParts = @('pwsh', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $promotionPipelineScript, '-BaselineRunRoot', [string]$baselineRun.runRoot, '-ReproofRunRoot', [string]$reproofRun.runRoot, '-CaptureMissingNeighborhoods', '-MinRepeatedRootCount', $MinRepeatedRootCount.ToString([System.Globalization.CultureInfo]::InvariantCulture), '-MinRepeatedEdgeCount', $MinRepeatedEdgeCount.ToString([System.Globalization.CultureInfo]::InvariantCulture), '-PlanOnly', '-Json')
    $recommendedCommands.Add([pscustomobject][ordered]@{
        name = 'promotion-pipeline-plan'
        command = New-CommandString -Parts $pipelineParts
    }) | Out-Null

    $recommendedCommands.Add([pscustomobject][ordered]@{
        name = 'promotion-pipeline-run'
        command = New-CommandString -Parts @($pipelineParts | Where-Object { $_ -ne '-PlanOnly' })
    }) | Out-Null
}
else {
    $recommendedCommands.Add([pscustomobject][ordered]@{
        name = 'run-second-baseline-zoom-proof'
        command = New-CommandString -Parts @('pwsh', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $proofWrapperScript, '-CandidateAddress', '<candidate-address>', '-NameplateText', '<nameplate-text>', '-Json')
    }) | Out-Null
}

$result = [pscustomobject][ordered]@{
    ok = $true
    outputRoot = $resolvedOutputRoot
    inventory = [pscustomobject][ordered]@{
        totalGatedNameplateRuns = @($runs).Count
        gatedBaselineZoomRuns = $baselineZoomRuns.Count
        baselineZoomRunsWithNeighborhood = $neighborhoodRuns.Count
        promotionReadyRuns = $promotionReadyRuns.Count
    }
    readyForPipeline = $readyForPipeline
    readyForPromotionCompare = $readyForPromotionCompare
    missingEvidence = @($missingEvidence.ToArray() | Select-Object -Unique)
    selectedBaselineRun = $baselineRun
    selectedReproofRun = $reproofRun
    recommendedCommands = @($recommendedCommands.ToArray())
}

if ($Json) {
    $result | ConvertTo-Json -Depth 100
}
else {
    $result
}
