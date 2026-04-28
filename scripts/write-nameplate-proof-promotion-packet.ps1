[CmdletBinding()]
param(
    [string]$BaselineRunRoot,
    [string]$ReproofRunRoot,
    [string]$BaselineFile,
    [string]$ReproofFile,
    [string]$OutputFile,
    [int]$MinRepeatedRootCount = 1,
    [int]$MinRepeatedEdgeCount = 0,
    [int]$Top = 20,
    [switch]$AllowNotReady,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$comparatorScript = Join-Path $PSScriptRoot 'compare-nameplate-proof-lead-neighborhoods.ps1'

function Resolve-DefaultOutputFile {
    param(
        [string]$ExplicitOutputFile,
        [string]$RunRoot,
        [string]$NeighborhoodFile
    )

    if (-not [string]::IsNullOrWhiteSpace($ExplicitOutputFile)) {
        return [System.IO.Path]::GetFullPath($ExplicitOutputFile)
    }

    if (-not [string]::IsNullOrWhiteSpace($RunRoot)) {
        $resolvedRunRoot = (Resolve-Path -LiteralPath $RunRoot).Path
        return (Join-Path $resolvedRunRoot 'lead-neighborhoods\nameplate-proof-promotion-packet.json')
    }

    if (-not [string]::IsNullOrWhiteSpace($NeighborhoodFile)) {
        $resolvedNeighborhoodFile = (Resolve-Path -LiteralPath $NeighborhoodFile).Path
        return (Join-Path (Split-Path -Path $resolvedNeighborhoodFile -Parent) 'nameplate-proof-promotion-packet.json')
    }

    throw 'Unable to determine OutputFile. Provide -OutputFile, -ReproofRunRoot, or -ReproofFile.'
}

if ($MinRepeatedRootCount -lt 0) {
    throw 'MinRepeatedRootCount cannot be negative.'
}
if ($MinRepeatedEdgeCount -lt 0) {
    throw 'MinRepeatedEdgeCount cannot be negative.'
}
if ($Top -le 0) {
    throw 'Top must be greater than zero.'
}
if (-not (Test-Path -LiteralPath $comparatorScript -PathType Leaf)) {
    throw "Comparator script not found: $comparatorScript"
}

$compareArgs = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', $comparatorScript,
    '-MinRepeatedRootCount', $MinRepeatedRootCount.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-MinRepeatedEdgeCount', $MinRepeatedEdgeCount.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-Top', $Top.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-Json'
)
if (-not [string]::IsNullOrWhiteSpace($BaselineRunRoot)) { $compareArgs += @('-BaselineRunRoot', $BaselineRunRoot) }
if (-not [string]::IsNullOrWhiteSpace($ReproofRunRoot)) { $compareArgs += @('-ReproofRunRoot', $ReproofRunRoot) }
if (-not [string]::IsNullOrWhiteSpace($BaselineFile)) { $compareArgs += @('-BaselineFile', $BaselineFile) }
if (-not [string]::IsNullOrWhiteSpace($ReproofFile)) { $compareArgs += @('-ReproofFile', $ReproofFile) }

$compareOutput = & pwsh @compareArgs 2>&1
$compareExitCode = $LASTEXITCODE
$compareText = $compareOutput -join [Environment]::NewLine
$comparison = $null
try {
    $comparison = $compareText | ConvertFrom-Json -Depth 100
}
catch {
    throw "Comparator did not return parseable JSON. ExitCode=$compareExitCode`n$compareText"
}

$promotionReady = (
    $compareExitCode -eq 0 -and
    [bool]$comparison.ok -and
    $null -ne $comparison.candidateSummary -and
    [bool]$comparison.candidateSummary.promotionReady
)

$blockers = [System.Collections.Generic.List[string]]::new()
if ($compareExitCode -ne 0) { $blockers.Add(('comparator-exit-code-{0}' -f $compareExitCode)) | Out-Null }
if (-not [bool]$comparison.ok) { $blockers.Add('comparator-ok-false') | Out-Null }
if ($null -eq $comparison.candidateSummary) {
    $blockers.Add('candidate-summary-missing') | Out-Null
}
else {
    foreach ($blocker in @($comparison.candidateSummary.blockers)) {
        if (-not [string]::IsNullOrWhiteSpace([string]$blocker)) {
            $blockers.Add([string]$blocker) | Out-Null
        }
    }
    if (-not [bool]$comparison.candidateSummary.promotionReady) {
        $blockers.Add('promotion-ready-false') | Out-Null
    }
}

$resolvedOutputFile = Resolve-DefaultOutputFile -ExplicitOutputFile $OutputFile -RunRoot $ReproofRunRoot -NeighborhoodFile $ReproofFile
$packet = [pscustomobject][ordered]@{
    mode = 'nameplate-proof-promotion-packet'
    ok = $promotionReady
    promotionReady = $promotionReady
    generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    outputFile = $resolvedOutputFile
    thresholds = [pscustomobject][ordered]@{
        minRepeatedRootCount = $MinRepeatedRootCount
        minRepeatedEdgeCount = $MinRepeatedEdgeCount
        top = $Top
    }
    blockers = @($blockers.ToArray() | Select-Object -Unique)
    baselineFile = [string]$comparison.baselineFile
    reproofFile = [string]$comparison.reproofFile
    counts = $comparison.counts
    recommendedRoots = if ($null -ne $comparison.candidateSummary) { @($comparison.candidateSummary.recommendedRoots) } else { @() }
    recommendedEdges = if ($null -ne $comparison.candidateSummary) { @($comparison.candidateSummary.recommendedEdges) } else { @() }
    comparatorChecks = @($comparison.checks)
}

if (-not $promotionReady -and -not $AllowNotReady) {
    $result = [pscustomobject][ordered]@{
        ok = $false
        promotionReady = $false
        wrotePacket = $false
        outputFile = $resolvedOutputFile
        blockers = @($packet.blockers)
        counts = $packet.counts
    }
    if ($Json) { $result | ConvertTo-Json -Depth 80 } else { $result }
    exit 1
}

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}
$packet | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $resolvedOutputFile -Encoding UTF8

$result = [pscustomobject][ordered]@{
    ok = $promotionReady
    promotionReady = $promotionReady
    wrotePacket = $true
    outputFile = $resolvedOutputFile
    blockers = @($packet.blockers)
    recommendedRootCount = @($packet.recommendedRoots).Count
    recommendedEdgeCount = @($packet.recommendedEdges).Count
}

if ($Json) {
    $result | ConvertTo-Json -Depth 80
}
else {
    $result
}

if (-not $promotionReady) {
    exit 1
}
