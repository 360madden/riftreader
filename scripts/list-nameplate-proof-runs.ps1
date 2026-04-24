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
    $leadNeighborhoodFile = Join-Path $runRoot 'lead-neighborhoods\nameplate-proof-lead-neighborhoods.json'
    $promotionPacketFile = Join-Path $runRoot 'lead-neighborhoods\nameplate-proof-promotion-packet.json'
    $hasLeadNeighborhood = Test-Path -LiteralPath $leadNeighborhoodFile -PathType Leaf
    $hasPromotionPacket = Test-Path -LiteralPath $promotionPacketFile -PathType Leaf
    $promotionReady = Get-OptionalJsonBool -Path $promotionPacketFile -PropertyName 'promotionReady'

    $run = [pscustomobject][ordered]@{
        name = $directory.Name
        runRoot = $runRoot
        lastWriteTimeUtc = $directory.LastWriteTimeUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        sampleCount = $samples.Count
        states = @($samples | ForEach-Object { [string]$_.state })
        stateRoles = @($samples | ForEach-Object { [string]$_.stateRole })
        gated = $gate
        hasLeadNeighborhood = $hasLeadNeighborhood
        leadNeighborhoodFile = if ($hasLeadNeighborhood) { $leadNeighborhoodFile } else { $null }
        hasPromotionPacket = $hasPromotionPacket
        promotionPacketFile = if ($hasPromotionPacket) { $promotionPacketFile } else { $null }
        promotionReady = $promotionReady
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
