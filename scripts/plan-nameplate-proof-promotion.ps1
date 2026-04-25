[CmdletBinding()]
param(
    [string]$OutputRoot = (Join-Path (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path 'artifacts\tooltip-projection'),
    [int]$InventoryTop = 50,
    [int]$MinRepeatedRootCount = 1,
    [int]$MinRepeatedEdgeCount = 0,
    [switch]$SummaryOnly,
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
        if ($_ -match '[\s''"`;|&<>(){}\[\]$]') { "'{0}'" -f ($_ -replace "'", "''") } else { $_ }
    }) -join ' '
}

function New-RecommendedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$Parts,
        [object]$Seed,
        [bool]$AttachesToProcess = $false,
        [bool]$CreatesArtifacts = $false,
        [bool]$RequiresOperatorConfirmation = $false
    )

    $safetyBlockers = [System.Collections.Generic.List[string]]::new()
    if ($AttachesToProcess) { $safetyBlockers.Add('attaches-to-process') | Out-Null }
    if ($CreatesArtifacts) { $safetyBlockers.Add('creates-artifacts') | Out-Null }
    if ($RequiresOperatorConfirmation) { $safetyBlockers.Add('requires-operator-confirmation') | Out-Null }

    $properties = [ordered]@{
        name = $Name
        command = New-CommandString -Parts $Parts
        commandParts = @($Parts)
        controlsInput = $false
        attachesToProcess = $AttachesToProcess
        createsArtifacts = $CreatesArtifacts
        requiresOperatorConfirmation = $RequiresOperatorConfirmation
        safeToRunNow = ($safetyBlockers.Count -eq 0)
        safetyBlockers = @($safetyBlockers.ToArray())
    }
    if ($PSBoundParameters.ContainsKey('Seed')) {
        $properties.seed = $Seed
    }

    return [pscustomobject]$properties
}

function Get-RunProofSeed {
    param([object]$Run)

    if ($null -eq $Run) {
        return $null
    }

    $candidateAddress = [string]$Run.candidateAddress
    $nameplateText = [string]$Run.nameplateText
    if ([string]::IsNullOrWhiteSpace($candidateAddress) -or [string]::IsNullOrWhiteSpace($nameplateText)) {
        return $null
    }

    return [pscustomobject][ordered]@{
        sourceRunRoot = [string]$Run.runRoot
        sourceRunName = [string]$Run.name
        candidateAddress = $candidateAddress
        candidateLength = if ($null -ne $Run.candidateLength) { [int]$Run.candidateLength } else { $null }
        nameplateText = $nameplateText
        processName = if ($null -ne $Run.processName) { [string]$Run.processName } else { $null }
        staleRisk = 'CandidateAddress comes from a prior proof manifest; replace it with a freshly resolved live candidate if the process, UI object, or hovered nameplate changed.'
    }
}

function ConvertTo-RunSummary {
    param([object]$Run)

    if ($null -eq $Run) {
        return $null
    }

    return [pscustomobject][ordered]@{
        name = [string]$Run.name
        runRoot = [string]$Run.runRoot
        candidateAddress = if ($null -ne $Run.candidateAddress) { [string]$Run.candidateAddress } else { $null }
        nameplateText = if ($null -ne $Run.nameplateText) { [string]$Run.nameplateText } else { $null }
        hasLeadNeighborhood = [bool]$Run.hasLeadNeighborhood
        hasPromotionPacket = [bool]$Run.hasPromotionPacket
        promotionReady = if ($null -ne $Run.promotionReady) { [bool]$Run.promotionReady } else { $null }
        hasLightweightReproofReport = if ($null -ne $Run.PSObject.Properties['hasLightweightReproofReport']) { [bool]$Run.hasLightweightReproofReport } else { $false }
        lightweightPromotionReadiness = if ($null -ne $Run.PSObject.Properties['lightweightReproofReport'] -and $null -ne $Run.lightweightReproofReport.PSObject.Properties['promotionReadiness']) { [string]$Run.lightweightReproofReport.promotionReadiness } else { $null }
        lightweightBlockers = if ($null -ne $Run.PSObject.Properties['lightweightReproofReport'] -and $null -ne $Run.lightweightReproofReport.PSObject.Properties['blockers']) { @($Run.lightweightReproofReport.blockers | ForEach-Object { [string]$_ }) } else { @() }
    }
}

function New-NextAction {
    param(
        [Parameter(Mandatory = $true)][object]$Command,
        [Parameter(Mandatory = $true)][string]$Reason,
        [bool]$AttachesToProcess = $false,
        [bool]$CreatesArtifacts = $false,
        [bool]$RequiresOperatorConfirmation = $false
    )

    if (-not $PSBoundParameters.ContainsKey('AttachesToProcess') -and $null -ne $Command.PSObject.Properties['attachesToProcess']) {
        $AttachesToProcess = [bool]$Command.attachesToProcess
    }
    if (-not $PSBoundParameters.ContainsKey('CreatesArtifacts') -and $null -ne $Command.PSObject.Properties['createsArtifacts']) {
        $CreatesArtifacts = [bool]$Command.createsArtifacts
    }
    if (-not $PSBoundParameters.ContainsKey('RequiresOperatorConfirmation') -and $null -ne $Command.PSObject.Properties['requiresOperatorConfirmation']) {
        $RequiresOperatorConfirmation = [bool]$Command.requiresOperatorConfirmation
    }

    $safetyBlockers = [System.Collections.Generic.List[string]]::new()
    if ($AttachesToProcess) { $safetyBlockers.Add('attaches-to-process') | Out-Null }
    if ($CreatesArtifacts) { $safetyBlockers.Add('creates-artifacts') | Out-Null }
    if ($RequiresOperatorConfirmation) { $safetyBlockers.Add('requires-operator-confirmation') | Out-Null }

    return [pscustomobject][ordered]@{
        name = [string]$Command.name
        command = [string]$Command.command
        commandParts = if ($null -ne $Command.PSObject.Properties['commandParts']) { @($Command.commandParts) } else { @() }
        reason = $Reason
        controlsInput = $false
        attachesToProcess = $AttachesToProcess
        createsArtifacts = $CreatesArtifacts
        requiresOperatorConfirmation = $RequiresOperatorConfirmation
        safeToRunNow = ($safetyBlockers.Count -eq 0)
        safetyBlockers = @($safetyBlockers.ToArray())
    }
}

function ConvertTo-PlanSummaryResult {
    param([Parameter(Mandatory = $true)][object]$Result)

    return [pscustomobject][ordered]@{
        ok = $Result.ok
        outputRoot = $Result.outputRoot
        inventory = $Result.inventory
        readyForPipeline = $Result.readyForPipeline
        readyForPromotionCompare = $Result.readyForPromotionCompare
        missingEvidence = @($Result.missingEvidence)
        selectedBaselineRun = ConvertTo-RunSummary -Run $Result.selectedBaselineRun
        selectedReproofRun = ConvertTo-RunSummary -Run $Result.selectedReproofRun
        selectedProofSeed = $Result.selectedProofSeed
        nextAction = $Result.nextAction
        recommendedCommandSafety = $Result.recommendedCommandSafety
        recommendedCommands = @($Result.recommendedCommands | ForEach-Object {
            [pscustomobject][ordered]@{
                name = [string]$_.name
                controlsInput = [bool]$_.controlsInput
                attachesToProcess = [bool]$_.attachesToProcess
                createsArtifacts = [bool]$_.createsArtifacts
                requiresOperatorConfirmation = [bool]$_.requiresOperatorConfirmation
                safeToRunNow = [bool]$_.safeToRunNow
                safetyBlockers = @($_.safetyBlockers)
            }
        })
    }
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
$lightweightDiagnosticRuns = @($baselineZoomRuns | Where-Object { [bool]$_.hasLightweightReproofReport })
$proofSeedSourceRun = if ($baselineZoomRuns.Count -gt 0) { $baselineZoomRuns[0] } else { $null }
$proofSeed = Get-RunProofSeed -Run $proofSeedSourceRun

$baselineRun = $null
$reproofRun = $null
if ($baselineZoomRuns.Count -ge 2) {
    $reproofRun = $baselineZoomRuns[0]
    $baselineRun = $baselineZoomRuns[1]
}
elseif ($baselineZoomRuns.Count -eq 1) {
    $baselineRun = $baselineZoomRuns[0]
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
if ($null -ne $baselineRun -and -not [bool]$baselineRun.hasLeadNeighborhood) {
    $missingEvidence.Add('baseline-run-needs-lead-neighborhood-capture') | Out-Null
}
if ($null -ne $reproofRun -and -not [bool]$reproofRun.hasLeadNeighborhood) {
    $missingEvidence.Add('reproof-run-needs-lead-neighborhood-capture') | Out-Null
}
if ($promotionReadyRuns.Count -eq 0) {
    $missingEvidence.Add('no-promotion-ready-packet-yet') | Out-Null
}

$recommendedCommands = [System.Collections.Generic.List[object]]::new()
$recommendedCommands.Add((New-RecommendedCommand -Name 'inventory' -Parts @('pwsh', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $inventoryScript, '-OutputRoot', $resolvedOutputRoot, '-RequireGated', '-Top', $InventoryTop.ToString([System.Globalization.CultureInfo]::InvariantCulture), '-Json'))) | Out-Null

foreach ($captureTarget in @(
    [pscustomobject]@{ Name = 'capture-baseline-lead-neighborhood'; Run = $baselineRun },
    [pscustomobject]@{ Name = 'capture-reproof-lead-neighborhood'; Run = $reproofRun }
)) {
    if ($null -ne $captureTarget.Run -and -not [bool]$captureTarget.Run.hasLeadNeighborhood) {
        $recommendedCommands.Add((New-RecommendedCommand -Name ([string]$captureTarget.Name) -Parts @('pwsh', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $captureNeighborhoodScript, '-RunRoot', [string]$captureTarget.Run.runRoot, '-Json') -AttachesToProcess $true -CreatesArtifacts $true)) | Out-Null
    }
}

if ($readyForPipeline) {
    $latestPairParts = @('pwsh', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $promotionPipelineScript, '-OutputRoot', $resolvedOutputRoot, '-LatestBaselineZoomPair', '-CaptureMissingNeighborhoods', '-MinRepeatedRootCount', $MinRepeatedRootCount.ToString([System.Globalization.CultureInfo]::InvariantCulture), '-MinRepeatedEdgeCount', $MinRepeatedEdgeCount.ToString([System.Globalization.CultureInfo]::InvariantCulture), '-PlanOnly', '-Json')
    $recommendedCommands.Add((New-RecommendedCommand -Name 'promotion-pipeline-latest-pair-plan' -Parts $latestPairParts)) | Out-Null

    $recommendedCommands.Add((New-RecommendedCommand -Name 'promotion-pipeline-latest-pair-run' -Parts @($latestPairParts | Where-Object { $_ -ne '-PlanOnly' }) -AttachesToProcess (-not $readyForPromotionCompare) -CreatesArtifacts $true)) | Out-Null

    $pipelineParts = @('pwsh', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $promotionPipelineScript, '-BaselineRunRoot', [string]$baselineRun.runRoot, '-ReproofRunRoot', [string]$reproofRun.runRoot, '-CaptureMissingNeighborhoods', '-MinRepeatedRootCount', $MinRepeatedRootCount.ToString([System.Globalization.CultureInfo]::InvariantCulture), '-MinRepeatedEdgeCount', $MinRepeatedEdgeCount.ToString([System.Globalization.CultureInfo]::InvariantCulture), '-PlanOnly', '-Json')
    $recommendedCommands.Add((New-RecommendedCommand -Name 'promotion-pipeline-plan' -Parts $pipelineParts)) | Out-Null

    $recommendedCommands.Add((New-RecommendedCommand -Name 'promotion-pipeline-run' -Parts @($pipelineParts | Where-Object { $_ -ne '-PlanOnly' }) -AttachesToProcess (-not $readyForPromotionCompare) -CreatesArtifacts $true)) | Out-Null
}
else {
    if ($null -ne $proofSeed) {
        $secondProofParts = @('pwsh', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $proofWrapperScript, '-CandidateAddress', $proofSeed.candidateAddress)
        if ($null -ne $proofSeed.candidateLength -and [int]$proofSeed.candidateLength -gt 0 -and [int]$proofSeed.candidateLength -ne 1024) {
            $secondProofParts += @('-CandidateLength', ([int]$proofSeed.candidateLength).ToString([System.Globalization.CultureInfo]::InvariantCulture))
        }
        $secondProofParts += @('-NameplateText', $proofSeed.nameplateText, '-OutputRoot', $resolvedOutputRoot, '-Json')
        $recommendedCommands.Add((New-RecommendedCommand -Name 'run-second-baseline-zoom-proof-plan' -Parts @($secondProofParts + '-PlanOnly') -Seed $proofSeed)) | Out-Null
        $recommendedCommands.Add((New-RecommendedCommand -Name 'run-second-baseline-zoom-proof' -Parts $secondProofParts -Seed $proofSeed -AttachesToProcess $true -CreatesArtifacts $true -RequiresOperatorConfirmation $true)) | Out-Null
    }
    else {
        $secondProofParts = @('pwsh', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $proofWrapperScript, '-CandidateAddress', '<candidate-address>', '-NameplateText', '<nameplate-text>', '-Json')
        $recommendedCommands.Add((New-RecommendedCommand -Name 'run-second-baseline-zoom-proof-plan' -Parts @($secondProofParts + '-PlanOnly') -Seed $null)) | Out-Null
        $recommendedCommands.Add((New-RecommendedCommand -Name 'run-second-baseline-zoom-proof' -Parts $secondProofParts -Seed $null -AttachesToProcess $true -CreatesArtifacts $true -RequiresOperatorConfirmation $true)) | Out-Null
    }
}

$commandsByName = @{}
foreach ($recommendedCommand in @($recommendedCommands.ToArray())) {
    $commandsByName[[string]$recommendedCommand.name] = $recommendedCommand
}

$recommendedCommandItems = @($recommendedCommands.ToArray())
$unsafeRecommendedCommands = @($recommendedCommandItems | Where-Object { -not [bool]$_.safeToRunNow })
$recommendedCommandSafety = [pscustomobject][ordered]@{
    total = $recommendedCommandItems.Count
    safeToRunNow = @($recommendedCommandItems | Where-Object { [bool]$_.safeToRunNow }).Count
    unsafe = $unsafeRecommendedCommands.Count
    controlsInput = @($recommendedCommandItems | Where-Object { [bool]$_.controlsInput }).Count
    attachesToProcess = @($recommendedCommandItems | Where-Object { [bool]$_.attachesToProcess }).Count
    createsArtifacts = @($recommendedCommandItems | Where-Object { [bool]$_.createsArtifacts }).Count
    requiresOperatorConfirmation = @($recommendedCommandItems | Where-Object { [bool]$_.requiresOperatorConfirmation }).Count
    unsafeNames = @($unsafeRecommendedCommands | ForEach-Object { [string]$_.name })
}

$nextAction = $null
if (-not $readyForPipeline -and $commandsByName.ContainsKey('run-second-baseline-zoom-proof-plan')) {
    $nextAction = New-NextAction -Command $commandsByName['run-second-baseline-zoom-proof-plan'] -Reason 'Second gated baseline/zoom proof is missing; run the plan-only command first and inspect operatorChecklist before live capture.'
}
elseif ($commandsByName.ContainsKey('capture-baseline-lead-neighborhood')) {
    $nextAction = New-NextAction -Command $commandsByName['capture-baseline-lead-neighborhood'] -Reason 'Selected baseline proof is missing lead-neighborhood evidence required for promotion comparison.' -AttachesToProcess $true -CreatesArtifacts $true
}
elseif ($commandsByName.ContainsKey('capture-reproof-lead-neighborhood')) {
    $nextAction = New-NextAction -Command $commandsByName['capture-reproof-lead-neighborhood'] -Reason 'Selected reproof is missing lead-neighborhood evidence required for promotion comparison.' -AttachesToProcess $true -CreatesArtifacts $true
}
elseif ($readyForPipeline -and $commandsByName.ContainsKey('promotion-pipeline-latest-pair-plan')) {
    $nextAction = New-NextAction -Command $commandsByName['promotion-pipeline-latest-pair-plan'] -Reason 'Two gated baseline/zoom proofs exist; plan the latest-pair promotion pipeline before any packet write.'
}
elseif ($commandsByName.ContainsKey('inventory')) {
    $nextAction = New-NextAction -Command $commandsByName['inventory'] -Reason 'Refresh gated proof inventory.'
}

$result = [pscustomobject][ordered]@{
    ok = $true
    outputRoot = $resolvedOutputRoot
    inventory = [pscustomobject][ordered]@{
        totalGatedNameplateRuns = @($runs).Count
        gatedBaselineZoomRuns = $baselineZoomRuns.Count
        baselineZoomRunsWithNeighborhood = $neighborhoodRuns.Count
        baselineZoomRunsWithLightweightDiagnostic = $lightweightDiagnosticRuns.Count
        promotionReadyRuns = $promotionReadyRuns.Count
    }
    readyForPipeline = $readyForPipeline
    readyForPromotionCompare = $readyForPromotionCompare
    missingEvidence = @($missingEvidence.ToArray() | Select-Object -Unique)
    selectedBaselineRun = $baselineRun
    selectedReproofRun = $reproofRun
    selectedProofSeed = $proofSeed
    nextAction = $nextAction
    recommendedCommandSafety = $recommendedCommandSafety
    recommendedCommands = $recommendedCommandItems
}

if ($SummaryOnly) {
    $result = ConvertTo-PlanSummaryResult -Result $result
}

if ($Json) {
    $result | ConvertTo-Json -Depth 100
}
else {
    $result
}
