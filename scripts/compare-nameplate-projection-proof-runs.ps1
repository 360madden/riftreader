[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BaselineRunRoot,

    [Parameter(Mandatory = $true)]
    [string]$ReproofRunRoot,

    [string[]]$CandidateOffsets = @(),
    [int]$DefaultTopCandidateCount = 5,
    [int]$MinRepeatCount = 1,

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Normalize-CommaList {
    param([string[]]$Value)

    if ($null -eq $Value) {
        return @()
    }

    $items = [System.Collections.Generic.List[string]]::new()
    foreach ($item in $Value) {
        if ($null -eq $item) { continue }
        foreach ($part in ([string]$item -split ',')) {
            $trimmed = $part.Trim()
            if (-not [string]::IsNullOrWhiteSpace($trimmed)) {
                $items.Add($trimmed) | Out-Null
            }
        }
    }

    return @($items.ToArray())
}

function Add-Check {
    param(
        [System.Collections.Generic.List[object]]$Checks,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][bool]$Passed,
        [string]$Detail,
        [object]$Data
    )

    $Checks.Add([pscustomobject][ordered]@{
        name = $Name
        status = if ($Passed) { 'passed' } else { 'failed' }
        detail = $Detail
        data = $Data
    }) | Out-Null
}

function Resolve-RunRoot {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Resolve-Path -LiteralPath $Path).Path
}

function Read-JsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -Depth 60
}

function Convert-OffsetToInt {
    param([Parameter(Mandatory = $true)][string]$Offset)

    $trimmed = $Offset.Trim()
    if ($trimmed.StartsWith('+')) {
        $trimmed = $trimmed.Substring(1)
    }
    if ($trimmed.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        return [Convert]::ToInt32($trimmed.Substring(2), 16)
    }

    return [Convert]::ToInt32($trimmed, 10)
}

function Read-ByteAtOffset {
    param(
        [Parameter(Mandatory = $true)][string]$BytesHex,
        [Parameter(Mandatory = $true)][int]$Offset
    )

    $clean = $BytesHex -replace '[^0-9A-Fa-f]', ''
    $start = $Offset * 2
    if (($start + 2) -gt $clean.Length) {
        return $null
    }

    return [Convert]::ToInt32($clean.Substring($start, 2), 16)
}

function Read-SampleRows {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return @()
    }

    return @(Get-Content -LiteralPath $Path | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object {
        $_ | ConvertFrom-Json -Depth 60
    })
}

function Get-OffsetByteValues {
    param(
        [object[]]$Samples,
        [Parameter(Mandatory = $true)][string]$Offset
    )

    $offsetInt = Convert-OffsetToInt -Offset $Offset
    return @($Samples | ForEach-Object {
        [pscustomobject][ordered]@{
            state = [string]$_.state
            stateRole = [string]$_.stateRole
            isActiveState = [bool]$_.isActiveState
            byte = Read-ByteAtOffset -BytesHex ([string]$_.bytesHex) -Offset $offsetInt
        }
    })
}

function Get-ProofRunSummary {
    param([Parameter(Mandatory = $true)][string]$RunRoot)

    $screenshotGatePath = Join-Path $RunRoot 'diffs\screenshot-gate.json'
    $fieldCandidatesPath = Join-Path $RunRoot 'diffs\field-candidates.json'
    $scanEvidencePath = Join-Path $RunRoot 'diffs\scan-evidence.json'
    $samplesPath = Join-Path $RunRoot 'samples.ndjson'

    $screenshotGateExists = Test-Path -LiteralPath $screenshotGatePath -PathType Leaf
    $fieldCandidatesExists = Test-Path -LiteralPath $fieldCandidatesPath -PathType Leaf
    $scanEvidenceExists = Test-Path -LiteralPath $scanEvidencePath -PathType Leaf
    $samplesExist = Test-Path -LiteralPath $samplesPath -PathType Leaf

    $gate = $null
    if ($screenshotGateExists) {
        $gate = (Read-JsonFile -Path $screenshotGatePath).screenshotGate
    }

    $fieldCandidates = $null
    $candidates = @()
    if ($fieldCandidatesExists) {
        $fieldCandidates = Read-JsonFile -Path $fieldCandidatesPath
        $candidates = @($fieldCandidates.candidates)
    }

    return [pscustomobject][ordered]@{
        runRoot = $RunRoot
        screenshotGatePath = $screenshotGatePath
        fieldCandidatesPath = $fieldCandidatesPath
        scanEvidencePath = $scanEvidencePath
        samplesPath = $samplesPath
        screenshotGateExists = $screenshotGateExists
        fieldCandidatesExists = $fieldCandidatesExists
        scanEvidenceExists = $scanEvidenceExists
        samplesExist = $samplesExist
        visualGateStatus = if ($null -ne $gate) { [string]$gate.visualGateStatus } else { $null }
        allSamplesHaveUsableCapture = if ($null -ne $gate) { [bool]$gate.allSamplesHaveUsableCapture } else { $false }
        expectedStateSequencePassed = if ($null -ne $gate -and $null -ne $gate.expectedStateSequence) { [bool]$gate.expectedStateSequence.passed } else { $false }
        actualStates = if ($null -ne $gate -and $null -ne $gate.expectedStateSequence) { @($gate.expectedStateSequence.actualStates | ForEach-Object { [string]$_ }) } else { @() }
        actualStateRoles = if ($null -ne $gate -and $null -ne $gate.expectedStateSequence) { @($gate.expectedStateSequence.actualStateRoles | ForEach-Object { [string]$_ }) } else { @() }
        candidateCount = @($candidates).Count
        candidates = @($candidates)
        samples = @(Read-SampleRows -Path $samplesPath)
    }
}

function Get-CandidateAtOffset {
    param(
        [object[]]$Candidates,
        [Parameter(Mandatory = $true)][string]$Offset
    )

    $normalized = $Offset.Trim().ToUpperInvariant()
    return @($Candidates | Where-Object { ([string]$_.offset).Trim().ToUpperInvariant() -eq $normalized })
}

if ($DefaultTopCandidateCount -le 0) {
    throw 'DefaultTopCandidateCount must be greater than zero.'
}

if ($MinRepeatCount -le 0) {
    throw 'MinRepeatCount must be greater than zero.'
}

$resolvedBaselineRoot = Resolve-RunRoot -Path $BaselineRunRoot
$resolvedReproofRoot = Resolve-RunRoot -Path $ReproofRunRoot
$checks = [System.Collections.Generic.List[object]]::new()

$baseline = Get-ProofRunSummary -RunRoot $resolvedBaselineRoot
$reproof = Get-ProofRunSummary -RunRoot $resolvedReproofRoot

foreach ($run in @(
    [pscustomobject]@{ Name = 'baseline'; Summary = $baseline },
    [pscustomobject]@{ Name = 'reproof'; Summary = $reproof }
)) {
    Add-Check -Checks $checks -Name "$($run.Name)-screenshot-gate-file" -Passed ([bool]$run.Summary.screenshotGateExists) -Detail "Expected screenshot gate file: $($run.Summary.screenshotGatePath)"
    Add-Check -Checks $checks -Name "$($run.Name)-field-candidates-file" -Passed ([bool]$run.Summary.fieldCandidatesExists) -Detail "Expected field candidates file: $($run.Summary.fieldCandidatesPath)"
    Add-Check -Checks $checks -Name "$($run.Name)-samples-file" -Passed ([bool]$run.Summary.samplesExist) -Detail "Expected samples file: $($run.Summary.samplesPath)"
    Add-Check -Checks $checks -Name "$($run.Name)-visual-gate-passed" -Passed ([string]$run.Summary.visualGateStatus -eq 'passed') -Detail "visualGateStatus=$($run.Summary.visualGateStatus)"
    Add-Check -Checks $checks -Name "$($run.Name)-sequence-passed" -Passed ([bool]$run.Summary.expectedStateSequencePassed) -Detail "expectedStateSequence.passed=$($run.Summary.expectedStateSequencePassed)"
}

$candidateOffsetsList = @(Normalize-CommaList -Value $CandidateOffsets)
if ($candidateOffsetsList.Count -eq 0) {
    $candidateOffsetsList = @($baseline.candidates |
        Where-Object { [string]$_.promotionStatus -match 'candidate|strong' } |
        Select-Object -First $DefaultTopCandidateCount |
        ForEach-Object { [string]$_.offset })
}
$candidateOffsetsList = @($candidateOffsetsList | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)

Add-Check -Checks $checks -Name 'candidate-offsets-present' -Passed ($candidateOffsetsList.Count -gt 0) -Detail "candidateOffsets=$($candidateOffsetsList -join ',')"

$repeated = [System.Collections.Generic.List[object]]::new()
foreach ($offset in $candidateOffsetsList) {
    $baselineHits = @(Get-CandidateAtOffset -Candidates @($baseline.candidates) -Offset $offset)
    $reproofHits = @(Get-CandidateAtOffset -Candidates @($reproof.candidates) -Offset $offset)
    $baselineBest = $baselineHits | Select-Object -First 1
    $reproofBest = $reproofHits | Select-Object -First 1
    $repeated.Add([pscustomobject][ordered]@{
        offset = $offset
        repeated = ($baselineHits.Count -gt 0 -and $reproofHits.Count -gt 0)
        baselineHitCount = $baselineHits.Count
        reproofHitCount = $reproofHits.Count
        baselineByteValues = @(Get-OffsetByteValues -Samples @($baseline.samples) -Offset $offset)
        reproofByteValues = @(Get-OffsetByteValues -Samples @($reproof.samples) -Offset $offset)
        baselineBest = if ($null -eq $baselineBest) { $null } else { [pscustomobject][ordered]@{ type = $baselineBest.type; score = $baselineBest.score; classification = $baselineBest.classification; subtype = $baselineBest.subtype; hiddenMode = $baselineBest.hiddenMode; hoverMode = $baselineBest.hoverMode; promotionStatus = $baselineBest.promotionStatus } }
        reproofBest = if ($null -eq $reproofBest) { $null } else { [pscustomobject][ordered]@{ type = $reproofBest.type; score = $reproofBest.score; classification = $reproofBest.classification; subtype = $reproofBest.subtype; hiddenMode = $reproofBest.hiddenMode; hoverMode = $reproofBest.hoverMode; promotionStatus = $reproofBest.promotionStatus } }
    }) | Out-Null
}

$repeatRows = @($repeated.ToArray())
$repeatCount = @($repeatRows | Where-Object { [bool]$_.repeated }).Count
Add-Check -Checks $checks -Name 'minimum-repeat-count' -Passed ($repeatCount -ge $MinRepeatCount) -Detail "repeated=$repeatCount/$($candidateOffsetsList.Count), min=$MinRepeatCount" -Data ([ordered]@{ repeated = $repeatCount; total = $candidateOffsetsList.Count; minRepeatCount = $MinRepeatCount })

$failedChecks = @($checks | Where-Object { $_.status -ne 'passed' })
$result = [pscustomobject][ordered]@{
    ok = ($failedChecks.Count -eq 0)
    baselineRunRoot = $resolvedBaselineRoot
    reproofRunRoot = $resolvedReproofRoot
    candidateOffsets = @($candidateOffsetsList)
    repeatedCount = $repeatCount
    minRepeatCount = $MinRepeatCount
    baselineCandidateCount = $baseline.candidateCount
    reproofCandidateCount = $reproof.candidateCount
    repeatedCandidates = @($repeatRows)
    checks = @($checks)
}

if ($Json) {
    $result | ConvertTo-Json -Depth 60
}
else {
    $result
}

if (-not [bool]$result.ok) {
    exit 1
}
