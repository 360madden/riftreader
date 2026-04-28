[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BaselineRunRoot,

    [Parameter(Mandatory = $true)]
    [string]$ReproofRunRoot,

    [string[]]$CandidateOffsets = @(),
    [int]$MinCandidateRepeatCount = 1,
    [int]$ByteWindowStartOffset = 0,
    [int]$ByteWindowLength = 1024,
    [int]$MinRepeatedChangingByteCount = 1,
    [string]$OutputFile,

    [switch]$PlanOnly,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$resultCheckerScript = Join-Path $PSScriptRoot 'check-nameplate-projection-proof-result.ps1'
$candidateCompareScript = Join-Path $PSScriptRoot 'compare-nameplate-projection-proof-runs.ps1'
$byteWindowCompareScript = Join-Path $PSScriptRoot 'compare-nameplate-proof-byte-windows.ps1'

function Resolve-RunRoot {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Resolve-Path -LiteralPath $Path).Path
}

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

function Invoke-JsonScript {
    param(
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $previousNativeErrorPreference = $null
    $hasNativeErrorPreference = (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) -ne $null
    if ($hasNativeErrorPreference) {
        $previousNativeErrorPreference = $PSNativeCommandUseErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $false
    }
    try {
        $output = & pwsh -NoProfile -ExecutionPolicy Bypass -File $ScriptPath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        if ($hasNativeErrorPreference) {
            $PSNativeCommandUseErrorActionPreference = $previousNativeErrorPreference
        }
    }
    $text = $output -join [Environment]::NewLine
    $jsonText = $text
    $jsonStart = $text.IndexOf('{')
    $jsonEnd = $text.LastIndexOf('}')
    if ($jsonStart -ge 0 -and $jsonEnd -ge $jsonStart) {
        $jsonText = $text.Substring($jsonStart, ($jsonEnd - $jsonStart + 1))
    }
    $parsed = $null
    $parseError = $null
    try {
        if (-not [string]::IsNullOrWhiteSpace($jsonText)) {
            $parsed = $jsonText | ConvertFrom-Json -Depth 100
        }
    }
    catch {
        $parseError = $_.Exception.Message
    }

    return [pscustomobject][ordered]@{
        exitCode = $exitCode
        parsed = $parsed
        parseError = $parseError
        output = $text
    }
}

function Get-LeadNeighborhoodStatus {
    param([Parameter(Mandatory = $true)][string]$RunRoot)

    $path = Join-Path $RunRoot 'lead-neighborhoods\nameplate-proof-lead-neighborhoods.json'
    return [pscustomobject][ordered]@{
        path = $path
        exists = (Test-Path -LiteralPath $path -PathType Leaf)
    }
}

function Get-OptionalPropertyValue {
    param(
        [object]$Object,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if ($null -eq $Object -or $null -eq $Object.PSObject.Properties[$Name]) {
        return $null
    }

    return $Object.PSObject.Properties[$Name].Value
}

function Get-CheckPassed {
    param(
        [object]$CheckResult,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if ($null -eq $CheckResult -or $null -eq $CheckResult.PSObject.Properties['checks']) {
        return $null
    }

    $check = @($CheckResult.checks | Where-Object { [string]$_.name -eq $Name } | Select-Object -First 1)
    if ($check.Count -eq 0) {
        return $null
    }

    return ([string]$check[0].status -eq 'passed')
}

if ($MinCandidateRepeatCount -lt 0) {
    throw 'MinCandidateRepeatCount cannot be negative.'
}
if ($ByteWindowStartOffset -lt 0) {
    throw 'ByteWindowStartOffset must be non-negative.'
}
if ($ByteWindowLength -lt 0) {
    throw 'ByteWindowLength must be non-negative. Use 0 to compare the common window length.'
}
if ($MinRepeatedChangingByteCount -lt 0) {
    throw 'MinRepeatedChangingByteCount cannot be negative.'
}
foreach ($requiredScript in @($resultCheckerScript, $candidateCompareScript, $byteWindowCompareScript)) {
    if (-not (Test-Path -LiteralPath $requiredScript -PathType Leaf)) {
        throw "Required script not found: $requiredScript"
    }
}

$baselineRoot = Resolve-RunRoot -Path $BaselineRunRoot
$reproofRoot = Resolve-RunRoot -Path $ReproofRunRoot
$candidateOffsetList = @(Normalize-CommaList -Value $CandidateOffsets)

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = Join-Path $reproofRoot 'diffs\nameplate-lightweight-reproof-report.json'
}
$resolvedOutputFile = if ([System.IO.Path]::IsPathRooted($OutputFile)) {
    $OutputFile
}
else {
    Join-Path (Get-Location).Path $OutputFile
}

$baselineCheck = Invoke-JsonScript -ScriptPath $resultCheckerScript -Arguments @('-RunRoot', $baselineRoot, '-Json')
$reproofCheck = Invoke-JsonScript -ScriptPath $resultCheckerScript -Arguments @('-RunRoot', $reproofRoot, '-Json')

$candidateArgs = @('-BaselineRunRoot', $baselineRoot, '-ReproofRunRoot', $reproofRoot, '-MinRepeatCount', $MinCandidateRepeatCount.ToString([System.Globalization.CultureInfo]::InvariantCulture), '-Json')
if ($candidateOffsetList.Count -gt 0) {
    $candidateArgs += '-CandidateOffsets'
    $candidateArgs += ($candidateOffsetList -join ',')
}
$candidateCompare = Invoke-JsonScript -ScriptPath $candidateCompareScript -Arguments $candidateArgs

$byteArgs = @(
    '-BaselineRunRoot', $baselineRoot,
    '-ReproofRunRoot', $reproofRoot,
    '-StartOffset', $ByteWindowStartOffset.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-Length', $ByteWindowLength.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-Json'
)
$byteWindowCompare = Invoke-JsonScript -ScriptPath $byteWindowCompareScript -Arguments $byteArgs

$baselineLead = Get-LeadNeighborhoodStatus -RunRoot $baselineRoot
$reproofLead = Get-LeadNeighborhoodStatus -RunRoot $reproofRoot
$blockers = [System.Collections.Generic.List[string]]::new()

if ($null -eq $baselineCheck.parsed -or -not [bool]$baselineCheck.parsed.ok) {
    $blockers.Add('baseline-proof-gate-not-passed') | Out-Null
}
if ($null -eq $reproofCheck.parsed -or -not [bool]$reproofCheck.parsed.ok) {
    $blockers.Add('reproof-proof-gate-not-passed') | Out-Null
}
if (-not [bool]$baselineLead.exists) {
    $blockers.Add('baseline-run-missing-lead-neighborhood') | Out-Null
}
if (-not [bool]$reproofLead.exists) {
    $blockers.Add('reproof-run-missing-lead-neighborhood') | Out-Null
}
if ($null -eq $candidateCompare.parsed) {
    $blockers.Add('candidate-offset-compare-unavailable') | Out-Null
}
elseif ([int]$candidateCompare.parsed.repeatedCount -lt $MinCandidateRepeatCount) {
    $blockers.Add('insufficient-repeated-candidate-offsets') | Out-Null
}
if ($null -eq $byteWindowCompare.parsed) {
    $blockers.Add('byte-window-compare-unavailable') | Out-Null
}
elseif ([int]$byteWindowCompare.parsed.counts.repeatedChanging -lt $MinRepeatedChangingByteCount) {
    $blockers.Add('insufficient-repeated-changing-byte-offsets') | Out-Null
}

$uniqueBlockers = @($blockers.ToArray() | Select-Object -Unique)
$report = [pscustomobject][ordered]@{
    mode = 'nameplate-lightweight-reproof-report'
    ok = $true
    diagnosticOnly = $true
    promotionReady = $false
    promotionReadiness = if ($uniqueBlockers.Count -eq 0) { 'diagnostic-only-use-promotion-pipeline' } else { 'blocked' }
    blockers = $uniqueBlockers
    createdUtc = [datetime]::UtcNow.ToString('o')
    wroteReport = (-not [bool]$PlanOnly)
    planOnly = [bool]$PlanOnly
    outputFile = $resolvedOutputFile
    controlsInput = $false
    attachesToProcess = $false
    createsArtifacts = (-not [bool]$PlanOnly)
    baselineRunRoot = $baselineRoot
    reproofRunRoot = $reproofRoot
    leadNeighborhoods = [pscustomobject][ordered]@{
        baseline = $baselineLead
        reproof = $reproofLead
    }
    proofGates = [pscustomobject][ordered]@{
        baseline = if ($null -eq $baselineCheck.parsed) { $null } else { [pscustomobject][ordered]@{
            ok = [bool]$baselineCheck.parsed.ok
            visualGatePassed = Get-CheckPassed -CheckResult $baselineCheck.parsed -Name 'visual-gate-status'
            expectedStateSequencePassed = Get-CheckPassed -CheckResult $baselineCheck.parsed -Name 'expected-state-sequence-passed'
            allSamplesHaveUsableCapture = Get-CheckPassed -CheckResult $baselineCheck.parsed -Name 'all-samples-usable-capture'
            candidateCount = Get-OptionalPropertyValue -Object $baselineCheck.parsed -Name 'candidateCount'
        } }
        reproof = if ($null -eq $reproofCheck.parsed) { $null } else { [pscustomobject][ordered]@{
            ok = [bool]$reproofCheck.parsed.ok
            visualGatePassed = Get-CheckPassed -CheckResult $reproofCheck.parsed -Name 'visual-gate-status'
            expectedStateSequencePassed = Get-CheckPassed -CheckResult $reproofCheck.parsed -Name 'expected-state-sequence-passed'
            allSamplesHaveUsableCapture = Get-CheckPassed -CheckResult $reproofCheck.parsed -Name 'all-samples-usable-capture'
            candidateCount = Get-OptionalPropertyValue -Object $reproofCheck.parsed -Name 'candidateCount'
        } }
    }
    candidateOffsetCompare = [pscustomobject][ordered]@{
        exitCode = $candidateCompare.exitCode
        parseError = $candidateCompare.parseError
        ok = if ($null -eq $candidateCompare.parsed) { $false } else { [bool]$candidateCompare.parsed.ok }
        repeatedCount = if ($null -eq $candidateCompare.parsed) { $null } else { $candidateCompare.parsed.repeatedCount }
        minRepeatCount = $MinCandidateRepeatCount
        candidateOffsets = if ($null -eq $candidateCompare.parsed) { @($candidateOffsetList) } else { @($candidateCompare.parsed.candidateOffsets) }
    }
    byteWindowCompare = [pscustomobject][ordered]@{
        exitCode = $byteWindowCompare.exitCode
        parseError = $byteWindowCompare.parseError
        ok = if ($null -eq $byteWindowCompare.parsed) { $false } else { [bool]$byteWindowCompare.parsed.ok }
        minRepeatedChangingByteCount = $MinRepeatedChangingByteCount
        comparedWindow = if ($null -eq $byteWindowCompare.parsed) { $null } else { $byteWindowCompare.parsed.comparedWindow }
        counts = if ($null -eq $byteWindowCompare.parsed) { $null } else { $byteWindowCompare.parsed.counts }
    }
    evidenceNote = 'This report is diagnostic only. It never writes a promotion packet and must not be treated as promotion evidence without lead-neighborhood comparison.'
}

if (-not $PlanOnly) {
    $outputDirectory = Split-Path -Parent $resolvedOutputFile
    if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
        New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    }
    $report | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $resolvedOutputFile -Encoding UTF8
}

if ($Json) {
    $report | ConvertTo-Json -Depth 100
}
else {
    $report
}
