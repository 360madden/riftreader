[CmdletBinding()]
param(
    [string]$OutputRoot = (Join-Path (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path 'artifacts\tooltip-projection'),
    [int]$Top = 20,
    [switch]$RequireGated,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Read-JsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -Depth 80
}

function Read-Samples {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return @()
    }

    return @(Get-Content -LiteralPath $Path | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object {
        $_ | ConvertFrom-Json -Depth 80
    })
}

function Get-GateSummary {
    param([Parameter(Mandatory = $true)][string]$RunRoot)

    $gatePath = Join-Path $RunRoot 'diffs\screenshot-gate.json'
    if (-not (Test-Path -LiteralPath $gatePath -PathType Leaf)) {
        return [pscustomobject][ordered]@{
            path = $gatePath
            exists = $false
            passed = $false
            visualGateStatus = $null
            expectedStateSequencePassed = $false
            actualStates = @()
            actualStateRoles = @()
        }
    }

    $gate = (Read-JsonFile -Path $gatePath).screenshotGate
    return [pscustomobject][ordered]@{
        path = $gatePath
        exists = $true
        passed = ([string]$gate.visualGateStatus -eq 'passed' -and [bool]$gate.allSamplesHaveUsableCapture -and $null -ne $gate.expectedStateSequence -and [bool]$gate.expectedStateSequence.passed)
        visualGateStatus = [string]$gate.visualGateStatus
        expectedStateSequencePassed = if ($null -ne $gate.expectedStateSequence) { [bool]$gate.expectedStateSequence.passed } else { $false }
        actualStates = if ($null -ne $gate.expectedStateSequence) { @($gate.expectedStateSequence.actualStates | ForEach-Object { [string]$_ }) } else { @() }
        actualStateRoles = if ($null -ne $gate.expectedStateSequence) { @($gate.expectedStateSequence.actualStateRoles | ForEach-Object { [string]$_ }) } else { @() }
    }
}

function Get-OptionalJsonBool {
    param(
        [string]$Path,
        [string]$PropertyName
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }

    $json = Read-JsonFile -Path $Path
    $property = $json.PSObject.Properties[$PropertyName]
    if ($null -eq $property) {
        return $null
    }

    return [bool]$property.Value
}

function Get-OptionalLightweightReproofReport {
    param([Parameter(Mandatory = $true)][string]$RunRoot)

    $reportPath = Join-Path $RunRoot 'diffs\nameplate-lightweight-reproof-report.json'
    if (-not (Test-Path -LiteralPath $reportPath -PathType Leaf)) {
        return [pscustomobject][ordered]@{
            path = $reportPath
            exists = $false
            diagnosticOnly = $null
            promotionReady = $null
            promotionReadiness = $null
            blockers = @()
            candidateRepeatedCount = $null
            repeatedChangingByteCount = $null
        }
    }

    $report = Read-JsonFile -Path $reportPath
    return [pscustomobject][ordered]@{
        path = $reportPath
        exists = $true
        diagnosticOnly = if ($report.PSObject.Properties['diagnosticOnly']) { [bool]$report.diagnosticOnly } else { $null }
        promotionReady = if ($report.PSObject.Properties['promotionReady']) { [bool]$report.promotionReady } else { $null }
        promotionReadiness = if ($report.PSObject.Properties['promotionReadiness']) { [string]$report.promotionReadiness } else { $null }
        blockers = if ($report.PSObject.Properties['blockers']) { @($report.blockers | ForEach-Object { [string]$_ }) } else { @() }
        candidateRepeatedCount = if ($report.PSObject.Properties['candidateOffsetCompare'] -and $null -ne $report.candidateOffsetCompare.PSObject.Properties['repeatedCount']) { $report.candidateOffsetCompare.repeatedCount } else { $null }
        repeatedChangingByteCount = if ($report.PSObject.Properties['byteWindowCompare'] -and $null -ne $report.byteWindowCompare.PSObject.Properties['counts'] -and $null -ne $report.byteWindowCompare.counts.PSObject.Properties['repeatedChanging']) { $report.byteWindowCompare.counts.repeatedChanging } else { $null }
    }
}

function Get-OptionalManifest {
    param([Parameter(Mandatory = $true)][string]$RunRoot)

    $manifestPath = Join-Path $RunRoot 'manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        return [pscustomobject][ordered]@{
            path = $manifestPath
            exists = $false
            runLabel = $null
            candidateAddress = $null
            candidateLength = $null
            tooltipText = $null
            processName = $null
            processId = $null
            createdUtc = $null
        }
    }

    $manifest = Read-JsonFile -Path $manifestPath
    $createdUtc = $null
    if ($manifest.PSObject.Properties['createdUtc']) {
        if ($manifest.createdUtc -is [datetime]) {
            $createdUtc = $manifest.createdUtc.ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        }
        else {
            $createdUtc = [string]$manifest.createdUtc
        }
    }

    return [pscustomobject][ordered]@{
        path = $manifestPath
        exists = $true
        runLabel = if ($manifest.PSObject.Properties['runLabel']) { [string]$manifest.runLabel } else { $null }
        candidateAddress = if ($manifest.PSObject.Properties['candidateAddress']) { [string]$manifest.candidateAddress } else { $null }
        candidateLength = if ($manifest.PSObject.Properties['candidateLength']) { [int]$manifest.candidateLength } else { $null }
        tooltipText = if ($manifest.PSObject.Properties['tooltipText']) { [string]$manifest.tooltipText } else { $null }
        processName = if ($manifest.PSObject.Properties['process'] -and $manifest.process.PSObject.Properties['name']) { [string]$manifest.process.name } else { $null }
        processId = if ($manifest.PSObject.Properties['process'] -and $manifest.process.PSObject.Properties['id']) { [int]$manifest.process.id } else { $null }
        createdUtc = $createdUtc
    }
}

if ($Top -le 0) {
    throw 'Top must be greater than zero.'
}

$resolvedOutputRoot = (Resolve-Path -LiteralPath $OutputRoot).Path
$directories = @(Get-ChildItem -LiteralPath $resolvedOutputRoot -Directory |
    Where-Object { $_.Name -match 'nameplate' } |
    Sort-Object LastWriteTimeUtc -Descending)

$runs = [System.Collections.Generic.List[object]]::new()
foreach ($directory in $directories) {
    $runRoot = $directory.FullName
    $samplesPath = Join-Path $runRoot 'samples.ndjson'
    $samples = @(Read-Samples -Path $samplesPath)
    $gate = Get-GateSummary -RunRoot $runRoot
    $manifest = Get-OptionalManifest -RunRoot $runRoot
    $leadNeighborhoodFile = Join-Path $runRoot 'lead-neighborhoods\nameplate-proof-lead-neighborhoods.json'
    $promotionPacketFile = Join-Path $runRoot 'lead-neighborhoods\nameplate-proof-promotion-packet.json'
    $hasLeadNeighborhood = Test-Path -LiteralPath $leadNeighborhoodFile -PathType Leaf
    $hasPromotionPacket = Test-Path -LiteralPath $promotionPacketFile -PathType Leaf
    $promotionReady = Get-OptionalJsonBool -Path $promotionPacketFile -PropertyName 'promotionReady'
    $lightweightReproofReport = Get-OptionalLightweightReproofReport -RunRoot $runRoot

    $run = [pscustomobject][ordered]@{
        name = $directory.Name
        runRoot = $runRoot
        lastWriteTimeUtc = $directory.LastWriteTimeUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        sampleCount = $samples.Count
        states = @($samples | ForEach-Object { [string]$_.state })
        stateRoles = @($samples | ForEach-Object { [string]$_.stateRole })
        manifest = $manifest
        candidateAddress = $manifest.candidateAddress
        candidateLength = $manifest.candidateLength
        nameplateText = $manifest.tooltipText
        processName = $manifest.processName
        gated = $gate
        hasLeadNeighborhood = $hasLeadNeighborhood
        leadNeighborhoodFile = if ($hasLeadNeighborhood) { $leadNeighborhoodFile } else { $null }
        hasPromotionPacket = $hasPromotionPacket
        promotionPacketFile = if ($hasPromotionPacket) { $promotionPacketFile } else { $null }
        promotionReady = $promotionReady
        hasLightweightReproofReport = [bool]$lightweightReproofReport.exists
        lightweightReproofReportFile = if ([bool]$lightweightReproofReport.exists) { [string]$lightweightReproofReport.path } else { $null }
        lightweightReproofReport = $lightweightReproofReport
    }

    if ($RequireGated -and -not [bool]$run.gated.passed) {
        continue
    }

    $runs.Add($run) | Out-Null
}

$selectedRuns = @($runs.ToArray() | Select-Object -First $Top)
$result = [pscustomobject][ordered]@{
    ok = $true
    outputRoot = $resolvedOutputRoot
    top = $Top
    requireGated = [bool]$RequireGated
    totalMatchingRuns = $runs.Count
    returnedRuns = $selectedRuns.Count
    runs = @($selectedRuns)
}

if ($Json) {
    $result | ConvertTo-Json -Depth 80
}
else {
    $result
}
