[CmdletBinding()]
param(
    [string]$RunRoot,

    [switch]$Latest,
    [string]$OutputRoot,

    [string[]]$ExpectedStates = @('baseline1', 'zoom1', 'baseline2', 'zoom2'),
    [string[]]$ExpectedStateRoles = @('baseline', 'active', 'baseline', 'active'),

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

function Test-SequenceEqual {
    param(
        [string[]]$Actual,
        [string[]]$Expected
    )

    if ($Actual.Count -ne $Expected.Count) {
        return $false
    }

    for ($i = 0; $i -lt $Expected.Count; $i++) {
        if ($Actual[$i] -ne $Expected[$i]) {
            return $false
        }
    }

    return $true
}

if ($Latest -and -not [string]::IsNullOrWhiteSpace($RunRoot)) {
    throw 'Use either -RunRoot or -Latest, not both.'
}

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $repoRoot 'artifacts\tooltip-projection'
}
elseif (-not [System.IO.Path]::IsPathRooted($OutputRoot)) {
    $OutputRoot = Join-Path $repoRoot $OutputRoot
}

if ($Latest) {
    $resolvedOutputRoot = (Resolve-Path -LiteralPath $OutputRoot).Path
    $latestRun = Get-ChildItem -LiteralPath $resolvedOutputRoot -Directory -Filter '*-nameplate-baseline-zoom' |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $latestRun) {
        throw "No nameplate baseline/zoom runs found under $resolvedOutputRoot."
    }
    $resolvedRunRoot = $latestRun.FullName
}
elseif (-not [string]::IsNullOrWhiteSpace($RunRoot)) {
    $resolvedRunRoot = (Resolve-Path -LiteralPath $RunRoot).Path
}
else {
    throw 'RunRoot is required unless -Latest is used.'
}

$screenshotGatePath = Join-Path $resolvedRunRoot 'diffs\screenshot-gate.json'
$fieldCandidatesPath = Join-Path $resolvedRunRoot 'diffs\field-candidates.json'
$scanEvidencePath = Join-Path $resolvedRunRoot 'diffs\scan-evidence.json'
$expectedStatesList = @(Normalize-CommaList -Value $ExpectedStates)
$expectedRolesList = @(Normalize-CommaList -Value $ExpectedStateRoles)
$checks = [System.Collections.Generic.List[object]]::new()

if ($expectedRolesList.Count -ne $expectedStatesList.Count) {
    throw "ExpectedStateRoles count ($($expectedRolesList.Count)) must match ExpectedStates count ($($expectedStatesList.Count))."
}

$screenshotGateExists = Test-Path -LiteralPath $screenshotGatePath -PathType Leaf
Add-Check -Checks $checks -Name 'screenshot-gate-file' -Passed $screenshotGateExists -Detail "Expected screenshot gate file: $screenshotGatePath"

$gateDocument = $null
$gate = $null
if ($screenshotGateExists) {
    $gateDocument = Get-Content -LiteralPath $screenshotGatePath -Raw | ConvertFrom-Json -Depth 40
    $gate = $gateDocument.screenshotGate
}

if ($null -ne $gate) {
    Add-Check -Checks $checks -Name 'visual-gate-status' -Passed ([string]$gate.visualGateStatus -eq 'passed') -Detail "visualGateStatus=$($gate.visualGateStatus)" -Data ([ordered]@{ visualGateStatus = $gate.visualGateStatus })
    Add-Check -Checks $checks -Name 'all-samples-usable-capture' -Passed ([bool]$gate.allSamplesHaveUsableCapture) -Detail "allSamplesHaveUsableCapture=$($gate.allSamplesHaveUsableCapture)" -Data ([ordered]@{ sampleCount = $gate.sampleCount; usableVisualCount = $gate.usableVisualCount })

    $rows = @($gate.rows)
    $allRowsUsable = ($rows.Count -gt 0 -and @($rows | Where-Object {
        [bool]$_.captureRecordExists -and
        [bool]$_.screenshotOutputExists -and
        [bool]$_.ok -and
        [bool]$_.usable
    }).Count -eq $rows.Count)
    Add-Check -Checks $checks -Name 'rows-have-usable-visual-evidence' -Passed $allRowsUsable -Detail "usable rows=$(@($rows | Where-Object { [bool]$_.usable }).Count)/$($rows.Count)"

    $sequence = $gate.expectedStateSequence
    Add-Check -Checks $checks -Name 'expected-state-sequence-present' -Passed ($null -ne $sequence) -Detail 'Expected state sequence audit must be present in screenshot-gate.json.'

    if ($null -ne $sequence) {
        $actualStates = @($sequence.actualStates | ForEach-Object { [string]$_ })
        $actualRoles = @($sequence.actualStateRoles | ForEach-Object { [string]$_ })
        Add-Check -Checks $checks -Name 'expected-state-sequence-passed' -Passed ([bool]$sequence.passed) -Detail "expectedStateSequence.passed=$($sequence.passed)"
        Add-Check -Checks $checks -Name 'expected-states-match' -Passed (Test-SequenceEqual -Actual $actualStates -Expected $expectedStatesList) -Detail "actualStates=$($actualStates -join ',')" -Data ([ordered]@{ expected = @($expectedStatesList); actual = @($actualStates) })
        Add-Check -Checks $checks -Name 'expected-state-roles-match' -Passed (Test-SequenceEqual -Actual $actualRoles -Expected $expectedRolesList) -Detail "actualStateRoles=$($actualRoles -join ',')" -Data ([ordered]@{ expected = @($expectedRolesList); actual = @($actualRoles) })
    }
}

$fieldCandidatesExists = Test-Path -LiteralPath $fieldCandidatesPath -PathType Leaf
$scanEvidenceExists = Test-Path -LiteralPath $scanEvidencePath -PathType Leaf
Add-Check -Checks $checks -Name 'field-candidates-file' -Passed $fieldCandidatesExists -Detail "Expected field candidates file: $fieldCandidatesPath"
Add-Check -Checks $checks -Name 'scan-evidence-file' -Passed $scanEvidenceExists -Detail "Expected scan evidence file: $scanEvidencePath"

$candidateCount = $null
if ($fieldCandidatesExists) {
    $fieldCandidates = Get-Content -LiteralPath $fieldCandidatesPath -Raw | ConvertFrom-Json -Depth 40
    $candidateCount = @($fieldCandidates.candidates).Count
}

$failedChecks = @($checks | Where-Object { $_.status -ne 'passed' })
$result = [pscustomobject][ordered]@{
    ok = ($failedChecks.Count -eq 0)
    runRoot = $resolvedRunRoot
    screenshotGate = $screenshotGatePath
    fieldCandidates = $fieldCandidatesPath
    scanEvidence = $scanEvidencePath
    candidateCount = $candidateCount
    checks = @($checks)
}

if ($Json) {
    $result | ConvertTo-Json -Depth 40
}
else {
    $result
}

if (-not [bool]$result.ok) {
    exit 1
}
