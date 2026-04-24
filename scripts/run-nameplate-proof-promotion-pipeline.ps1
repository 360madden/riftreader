[CmdletBinding()]
param(
    [string]$OutputRoot = (Join-Path (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path 'artifacts\tooltip-projection'),
    [string]$BaselineRunRoot,
    [string]$ReproofRunRoot,
    [string]$BaselineFile,
    [string]$ReproofFile,
    [string]$OutputFile,
    [int]$MinRepeatedRootCount = 1,
    [int]$MinRepeatedEdgeCount = 0,
    [int]$Top = 20,
    [switch]$CaptureMissingNeighborhoods,
    [switch]$LatestBaselineZoomPair,
    [switch]$AllowNotReady,
    [switch]$PlanOnly,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$captureNeighborhoodScript = Join-Path $PSScriptRoot 'capture-nameplate-proof-lead-neighborhoods.ps1'
$promotionPacketScript = Join-Path $PSScriptRoot 'write-nameplate-proof-promotion-packet.ps1'
$inventoryScript = Join-Path $PSScriptRoot 'list-nameplate-proof-runs.ps1'

function Resolve-DefaultNeighborhoodFile {
    param(
        [string]$RunRoot,
        [string]$File,
        [Parameter(Mandatory = $true)][string]$Label
    )

    if (-not [string]::IsNullOrWhiteSpace($File)) {
        return [System.IO.Path]::GetFullPath($File)
    }

    if (-not [string]::IsNullOrWhiteSpace($RunRoot)) {
        $resolvedRunRoot = (Resolve-Path -LiteralPath $RunRoot).Path
        return (Join-Path $resolvedRunRoot 'lead-neighborhoods\nameplate-proof-lead-neighborhoods.json')
    }

    throw "Provide either -${Label}RunRoot or -${Label}File."
}

function Invoke-JsonCommand {
    param(
        [Parameter(Mandatory = $true)][string]$File,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $output = & pwsh -NoProfile -ExecutionPolicy Bypass -File $File @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $text = $output -join [Environment]::NewLine
    $json = $null
    try {
        $json = $text | ConvertFrom-Json -Depth 100
    }
    catch {
        throw "Command did not return parseable JSON. File=$File ExitCode=$exitCode`n$text"
    }

    return [pscustomobject][ordered]@{
        exitCode = $exitCode
        json = $json
        text = $text
    }
}

function Invoke-Inventory {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][int]$Limit
    )

    $output = & pwsh -NoProfile -ExecutionPolicy Bypass -File $inventoryScript -OutputRoot $Root -Top $Limit -RequireGated -Json 2>&1
    $exitCode = $LASTEXITCODE
    $text = $output -join [Environment]::NewLine
    if ($exitCode -ne 0) {
        throw "Inventory failed with exit code $exitCode`n$text"
    }

    try {
        return $text | ConvertFrom-Json -Depth 100
    }
    catch {
        throw "Inventory did not return parseable JSON.`n$text"
    }
}

if ($MinRepeatedRootCount -lt 0) { throw 'MinRepeatedRootCount cannot be negative.' }
if ($MinRepeatedEdgeCount -lt 0) { throw 'MinRepeatedEdgeCount cannot be negative.' }
if ($Top -le 0) { throw 'Top must be greater than zero.' }
foreach ($requiredScript in @($captureNeighborhoodScript, $promotionPacketScript, $inventoryScript)) {
    if (-not (Test-Path -LiteralPath $requiredScript -PathType Leaf)) {
        throw "Required script not found: $requiredScript"
    }
}

$selectedPair = $null
if ($LatestBaselineZoomPair) {
    if (-not [string]::IsNullOrWhiteSpace($BaselineRunRoot) -or
        -not [string]::IsNullOrWhiteSpace($ReproofRunRoot) -or
        -not [string]::IsNullOrWhiteSpace($BaselineFile) -or
        -not [string]::IsNullOrWhiteSpace($ReproofFile)) {
        throw 'Do not combine -LatestBaselineZoomPair with explicit -BaselineRunRoot, -ReproofRunRoot, -BaselineFile, or -ReproofFile.'
    }

    $resolvedOutputRoot = (Resolve-Path -LiteralPath $OutputRoot).Path
    $inventory = Invoke-Inventory -Root $resolvedOutputRoot -Limit $Top
    $baselineZoomRuns = @($inventory.runs | Where-Object { [string]$_.name -match 'nameplate-baseline-zoom' })
    if ($baselineZoomRuns.Count -lt 2) {
        throw "Latest baseline/zoom pair requires at least two gated nameplate-baseline-zoom proof roots. Found $($baselineZoomRuns.Count)."
    }

    $latestRun = $baselineZoomRuns[0]
    $previousRun = $baselineZoomRuns[1]
    $BaselineRunRoot = [string]$previousRun.runRoot
    $ReproofRunRoot = [string]$latestRun.runRoot
    $selectedPair = [pscustomobject][ordered]@{
        mode = 'latest-baseline-zoom-pair'
        outputRoot = $resolvedOutputRoot
        baselineRunRoot = $BaselineRunRoot
        reproofRunRoot = $ReproofRunRoot
        baselineRunName = [string]$previousRun.name
        reproofRunName = [string]$latestRun.name
        baselineHasLeadNeighborhood = [bool]$previousRun.hasLeadNeighborhood
        reproofHasLeadNeighborhood = [bool]$latestRun.hasLeadNeighborhood
    }
}

$baselineNeighborhoodFile = Resolve-DefaultNeighborhoodFile -RunRoot $BaselineRunRoot -File $BaselineFile -Label 'Baseline'
$reproofNeighborhoodFile = Resolve-DefaultNeighborhoodFile -RunRoot $ReproofRunRoot -File $ReproofFile -Label 'Reproof'
$resolvedOutputFile = if (-not [string]::IsNullOrWhiteSpace($OutputFile)) {
    [System.IO.Path]::GetFullPath($OutputFile)
}
elseif (-not [string]::IsNullOrWhiteSpace($ReproofRunRoot)) {
    $resolvedReproofRunRoot = (Resolve-Path -LiteralPath $ReproofRunRoot).Path
    Join-Path $resolvedReproofRunRoot 'lead-neighborhoods\nameplate-proof-promotion-packet.json'
}
else {
    Join-Path (Split-Path -Path $reproofNeighborhoodFile -Parent) 'nameplate-proof-promotion-packet.json'
}

$plannedSteps = [System.Collections.Generic.List[object]]::new()
if ($CaptureMissingNeighborhoods) {
    foreach ($captureTarget in @(
        [pscustomobject]@{ Label = 'baseline'; RunRoot = $BaselineRunRoot; File = $baselineNeighborhoodFile },
        [pscustomobject]@{ Label = 'reproof'; RunRoot = $ReproofRunRoot; File = $reproofNeighborhoodFile }
    )) {
        if ([string]::IsNullOrWhiteSpace([string]$captureTarget.RunRoot)) {
            continue
        }

        if (-not (Test-Path -LiteralPath ([string]$captureTarget.File) -PathType Leaf)) {
            $plannedSteps.Add([pscustomobject][ordered]@{
                name = "capture-$($captureTarget.Label)-lead-neighborhood"
                controlsInput = $false
                attachesToProcess = -not [bool]$PlanOnly
                command = @(
                    'pwsh', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                    '-File', $captureNeighborhoodScript,
                    '-RunRoot', [string]$captureTarget.RunRoot,
                    '-OutputFile', [string]$captureTarget.File,
                    '-Json'
                )
            }) | Out-Null
        }
    }
}

$packetCommand = [System.Collections.Generic.List[string]]::new()
$packetCommand.AddRange([string[]]@(
    'pwsh', '-NoProfile', '-ExecutionPolicy', 'Bypass',
    '-File', $promotionPacketScript,
    '-BaselineFile', $baselineNeighborhoodFile,
    '-ReproofFile', $reproofNeighborhoodFile,
    '-OutputFile', $resolvedOutputFile,
    '-MinRepeatedRootCount', $MinRepeatedRootCount.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-MinRepeatedEdgeCount', $MinRepeatedEdgeCount.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-Top', $Top.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-Json'
))
if ($AllowNotReady) {
    $packetCommand.Add('-AllowNotReady') | Out-Null
}
$plannedSteps.Add([pscustomobject][ordered]@{
    name = 'write-promotion-packet'
    controlsInput = $false
    attachesToProcess = $false
    command = @($packetCommand.ToArray())
}) | Out-Null

if ($PlanOnly) {
    $result = [pscustomobject][ordered]@{
        mode = 'plan-only'
        ok = $true
        controlsInput = $false
        attachesToProcess = [bool]$CaptureMissingNeighborhoods
        baselineNeighborhoodFile = $baselineNeighborhoodFile
        reproofNeighborhoodFile = $reproofNeighborhoodFile
        outputFile = $resolvedOutputFile
        selectedPair = $selectedPair
        plannedSteps = @($plannedSteps.ToArray())
    }
    if ($Json) { $result | ConvertTo-Json -Depth 80 } else { $result }
    exit 0
}

$stepResults = [System.Collections.Generic.List[object]]::new()
if ($CaptureMissingNeighborhoods) {
    foreach ($captureTarget in @(
        [pscustomobject]@{ Label = 'baseline'; RunRoot = $BaselineRunRoot; File = $baselineNeighborhoodFile },
        [pscustomobject]@{ Label = 'reproof'; RunRoot = $ReproofRunRoot; File = $reproofNeighborhoodFile }
    )) {
        if ([string]::IsNullOrWhiteSpace([string]$captureTarget.RunRoot)) {
            continue
        }

        if (-not (Test-Path -LiteralPath ([string]$captureTarget.File) -PathType Leaf)) {
            $captureResult = Invoke-JsonCommand -File $captureNeighborhoodScript -Arguments @(
                '-RunRoot', [string]$captureTarget.RunRoot,
                '-OutputFile', [string]$captureTarget.File,
                '-Json'
            )
            $stepResults.Add([pscustomobject][ordered]@{
                name = "capture-$($captureTarget.Label)-lead-neighborhood"
                exitCode = $captureResult.exitCode
                ok = [bool]$captureResult.json.ok
                outputFile = [string]$captureResult.json.outputFile
            }) | Out-Null
            if ($captureResult.exitCode -ne 0 -or -not [bool]$captureResult.json.ok) {
                throw "Lead-neighborhood capture failed for $($captureTarget.Label)."
            }
        }
    }
}

$missingNeighborhoods = @(@($baselineNeighborhoodFile, $reproofNeighborhoodFile) | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
if ($missingNeighborhoods.Count -gt 0) {
    throw "Required lead-neighborhood artifact(s) missing. Use -CaptureMissingNeighborhoods with run roots, or create them first: $($missingNeighborhoods -join ', ')"
}

$packetArgs = @(
    '-BaselineFile', $baselineNeighborhoodFile,
    '-ReproofFile', $reproofNeighborhoodFile,
    '-OutputFile', $resolvedOutputFile,
    '-MinRepeatedRootCount', $MinRepeatedRootCount.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-MinRepeatedEdgeCount', $MinRepeatedEdgeCount.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-Top', $Top.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-Json'
)
if ($AllowNotReady) {
    $packetArgs += '-AllowNotReady'
}
$packetResult = Invoke-JsonCommand -File $promotionPacketScript -Arguments $packetArgs
$stepResults.Add([pscustomobject][ordered]@{
    name = 'write-promotion-packet'
    exitCode = $packetResult.exitCode
    ok = [bool]$packetResult.json.ok
    promotionReady = [bool]$packetResult.json.promotionReady
    wrotePacket = [bool]$packetResult.json.wrotePacket
    outputFile = [string]$packetResult.json.outputFile
}) | Out-Null

$result = [pscustomobject][ordered]@{
    mode = 'run'
    ok = ($packetResult.exitCode -eq 0 -and [bool]$packetResult.json.ok)
    controlsInput = $false
    baselineNeighborhoodFile = $baselineNeighborhoodFile
    reproofNeighborhoodFile = $reproofNeighborhoodFile
    outputFile = $resolvedOutputFile
    selectedPair = $selectedPair
    steps = @($stepResults.ToArray())
    packet = $packetResult.json
}

if ($Json) { $result | ConvertTo-Json -Depth 100 } else { $result }
if (-not $result.ok) { exit 1 }
