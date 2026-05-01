[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BundleDirectory,

    [string]$OutputJsonFile,

    [string]$OutputMarkdownFile,

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$schemaVersion = 1

function Write-Utf8TextAtomic {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Content
    )

    $directory = Split-Path -Path $Path -Parent
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $tempPath = '{0}.{1}.tmp' -f $Path, ([Guid]::NewGuid().ToString('N'))
    try {
        [System.IO.File]::WriteAllText($tempPath, $Content, [System.Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $tempPath -Destination $Path -Force
    }
    finally {
        if (Test-Path -LiteralPath $tempPath) {
            Remove-Item -LiteralPath $tempPath -Force
        }
    }
}

function Read-JsonFileOrNull {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -Depth 80
}

function Get-PropertyValue {
    param(
        [object]$InputObject,

        [Parameter(Mandatory = $true)]
        [string[]]$Names
    )

    if ($null -eq $InputObject) {
        return $null
    }

    foreach ($name in $Names) {
        if ($InputObject -is [System.Collections.IDictionary]) {
            if ($InputObject.Contains($name)) {
                return $InputObject[$name]
            }
        }
        else {
            $property = $InputObject.PSObject.Properties[$name]
            if ($null -ne $property) {
                return $property.Value
            }
        }
    }

    return $null
}

function ConvertTo-IntOrNull {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    try {
        return [int]::Parse($text, [System.Globalization.CultureInfo]::InvariantCulture)
    }
    catch {
        return $null
    }
}

function ConvertTo-DoubleOrNull {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    try {
        $number = [double]::Parse($text, [System.Globalization.CultureInfo]::InvariantCulture)
        if ([double]::IsNaN($number) -or [double]::IsInfinity($number)) {
            return $null
        }

        return $number
    }
    catch {
        return $null
    }
}

function ConvertTo-DisplayValue {
    param([object]$Value)

    if ($null -eq $Value) {
        return ''
    }

    if ($Value -is [bool]) {
        return $Value.ToString().ToLowerInvariant()
    }

    if ($Value -is [double] -or $Value -is [float] -or $Value -is [decimal]) {
        return ([double]$Value).ToString('G8', [System.Globalization.CultureInfo]::InvariantCulture)
    }

    return [string]$Value
}

function Add-Message {
    param(
        [System.Collections.Generic.List[string]]$Messages,

        [string]$Message
    )

    if (-not [string]::IsNullOrWhiteSpace($Message)) {
        $Messages.Add($Message) | Out-Null
    }
}

function New-MarkdownStatus {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Status
    )

    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add('# Coordinate bundle status') | Out-Null
    $lines.Add('') | Out-Null
    $lines.Add('| Field | Value |') | Out-Null
    $lines.Add('|---|---|') | Out-Null
    $lines.Add("| Overall status | `$(ConvertTo-DisplayValue $Status.status)` |") | Out-Null
    $lines.Add("| Promotion allowed | `$(ConvertTo-DisplayValue $Status.promotion.allowed)` |") | Out-Null
    $lines.Add("| Capture status | `$(ConvertTo-DisplayValue $Status.capture.status)` |") | Out-Null
    $lines.Add("| Capture fresh | `$(ConvertTo-DisplayValue $Status.capture.fresh)` |") | Out-Null
    $lines.Add("| Scoring status | `$(ConvertTo-DisplayValue $Status.scoring.status)` |") | Out-Null
    $lines.Add("| Promotion status | `$(ConvertTo-DisplayValue $Status.promotion.status)` |") | Out-Null
    $lines.Add("| Selected candidate | `$(ConvertTo-DisplayValue $Status.promotion.selectedCandidateId)` |") | Out-Null
    $lines.Add("| Classification | `$(ConvertTo-DisplayValue $Status.promotion.classification)` |") | Out-Null
    $lines.Add("| Score | `$(ConvertTo-DisplayValue $Status.promotion.score)` |") | Out-Null
    $lines.Add("| Truth surface | `$(ConvertTo-DisplayValue $Status.truthSurface.authoritativeTruthSurface)` |") | Out-Null
    $lines.Add("| SavedVariables freshness | `$(ConvertTo-DisplayValue $Status.savedVariables.freshnessClassification)` |") | Out-Null
    $lines.Add('') | Out-Null
    $lines.Add('## Blockers') | Out-Null
    $lines.Add('') | Out-Null
    if (@($Status.blockers).Count -eq 0) {
        $lines.Add('- None') | Out-Null
    }
    else {
        foreach ($blocker in @($Status.blockers)) {
            $lines.Add("- $blocker") | Out-Null
        }
    }

    if (@($Status.warnings).Count -gt 0) {
        $lines.Add('') | Out-Null
        $lines.Add('## Warnings') | Out-Null
        $lines.Add('') | Out-Null
        foreach ($warning in @($Status.warnings)) {
            $lines.Add("- $warning") | Out-Null
        }
    }

    $lines.Add('') | Out-Null
    $lines.Add('## Artifact paths') | Out-Null
    $lines.Add('') | Out-Null
    $lines.Add("| Artifact | Path | Exists |") | Out-Null
    $lines.Add("|---|---|---|") | Out-Null
    foreach ($artifact in @($Status.artifacts)) {
        $lines.Add("| $($artifact.name) | `$($artifact.path)` | `$(ConvertTo-DisplayValue $artifact.exists)` |") | Out-Null
    }

    return ($lines -join [Environment]::NewLine)
}

$resolvedBundleDirectory = [System.IO.Path]::GetFullPath($BundleDirectory)
if (-not (Test-Path -LiteralPath $resolvedBundleDirectory)) {
    throw "Bundle directory not found: $resolvedBundleDirectory"
}

if ([string]::IsNullOrWhiteSpace($OutputJsonFile)) {
    $OutputJsonFile = Join-Path $resolvedBundleDirectory 'coordinate-bundle-status.json'
}

if ([string]::IsNullOrWhiteSpace($OutputMarkdownFile)) {
    $OutputMarkdownFile = Join-Path $resolvedBundleDirectory 'coordinate-bundle-status.md'
}

$paths = [ordered]@{
    liveCoords = Join-Path $resolvedBundleDirectory 'live-coords.ndjson'
    chromalinkCaptureSummary = Join-Path $resolvedBundleDirectory 'chromalink-live-coords-capture-summary.json'
    chromalinkFreshnessPreflight = Join-Path $resolvedBundleDirectory 'chromalink-freshness-preflight.json'
    candidateScores = Join-Path $resolvedBundleDirectory 'candidate-trajectory-scores.json'
    promotionGate = Join-Path $resolvedBundleDirectory 'promotion-gate.json'
    promotionGateSummary = Join-Path $resolvedBundleDirectory 'promotion-gate-summary.json'
    truthSurface = Join-Path $resolvedBundleDirectory 'truth-surface.json'
    savedVariablesFreshness = Join-Path $resolvedBundleDirectory 'savedvariables-freshness.json'
}

$liveCoordLineCount = 0
if (Test-Path -LiteralPath $paths.liveCoords) {
    $liveCoordLineCount = @((Get-Content -LiteralPath $paths.liveCoords -ErrorAction Stop) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }).Count
}

$captureDocument = Read-JsonFileOrNull -Path $paths.chromalinkCaptureSummary
$preflightDocument = Read-JsonFileOrNull -Path $paths.chromalinkFreshnessPreflight
$scoresDocument = Read-JsonFileOrNull -Path $paths.candidateScores
$gateDocument = Read-JsonFileOrNull -Path $paths.promotionGate
$promotionSummaryDocument = Read-JsonFileOrNull -Path $paths.promotionGateSummary
$truthSurfaceDocument = Read-JsonFileOrNull -Path $paths.truthSurface
$savedVariablesFreshnessDocument = Read-JsonFileOrNull -Path $paths.savedVariablesFreshness

$selectedCandidate = Get-PropertyValue -InputObject $gateDocument -Names @('selectedCandidate')
if ($null -eq $selectedCandidate -and $null -ne $scoresDocument) {
    $selectedCandidate = Get-PropertyValue -InputObject $scoresDocument -Names @('bestCandidate')
}

$blockers = [System.Collections.Generic.List[string]]::new()
$warnings = [System.Collections.Generic.List[string]]::new()

$captureStatus = if ($null -ne $captureDocument) {
    [string](Get-PropertyValue -InputObject $captureDocument -Names @('status'))
}
elseif (Test-Path -LiteralPath $paths.liveCoords) {
    'live-coords-present-no-capture-summary'
}
else {
    'missing'
}
$captureFresh = if ($null -ne $captureDocument) {
    [bool](Get-PropertyValue -InputObject $captureDocument -Names @('fresh'))
}
elseif ($null -ne $preflightDocument) {
    [bool](Get-PropertyValue -InputObject $preflightDocument -Names @('fresh'))
}
else {
    $false
}
$captureExported = if ($null -ne $captureDocument) {
    [bool](Get-PropertyValue -InputObject $captureDocument -Names @('exported'))
}
else {
    (Test-Path -LiteralPath $paths.liveCoords)
}

$scoreStatus = [string](Get-PropertyValue -InputObject $scoresDocument -Names @('status'))
$promotionAllowed = [bool](Get-PropertyValue -InputObject $(if ($null -ne $promotionSummaryDocument) { $promotionSummaryDocument } else { $gateDocument }) -Names @('promotionAllowed', 'allowed'))
$promotionStatus = [string](Get-PropertyValue -InputObject $(if ($null -ne $promotionSummaryDocument) { $promotionSummaryDocument } else { $gateDocument }) -Names @('gateStatus', 'status'))
$promotionReady = Get-PropertyValue -InputObject $(if ($null -ne $promotionSummaryDocument) { $promotionSummaryDocument } else { $scoresDocument }) -Names @('promotionReady')

if (-not $promotionAllowed) {
    if ($null -ne $gateDocument -or $null -ne $promotionSummaryDocument) {
        Add-Message -Messages $blockers -Message 'Promotion gate exists but promotionAllowed is false.'
    }
    elseif (-not (Test-Path -LiteralPath $paths.liveCoords)) {
        Add-Message -Messages $blockers -Message 'No live-coords.ndjson truth stream is present.'
    }
    elseif ($null -eq $scoresDocument) {
        Add-Message -Messages $blockers -Message 'No candidate-trajectory-scores.json is present.'
    }
    else {
        Add-Message -Messages $blockers -Message 'Promotion gate has not been written.'
    }
}

if ($captureStatus -in @('preflight-failed', 'stale', 'missing') -or ($captureStatus -eq 'fail')) {
    Add-Message -Messages $blockers -Message "Capture status is $captureStatus."
}
elseif ($captureStatus -eq 'live-coords-present-no-capture-summary') {
    Add-Message -Messages $warnings -Message 'live-coords.ndjson exists without a capture summary; verify freshness provenance before using it.'
}

if ((Test-Path -LiteralPath $paths.liveCoords) -and $liveCoordLineCount -le 0) {
    Add-Message -Messages $blockers -Message 'live-coords.ndjson exists but has no samples.'
}

if ($null -ne $scoresDocument -and $scoreStatus -ne 'complete') {
    Add-Message -Messages $blockers -Message "Candidate scores status is $scoreStatus."
}

foreach ($failure in @((Get-PropertyValue -InputObject $gateDocument -Names @('failures')))) {
    Add-Message -Messages $blockers -Message ([string]$failure)
}

foreach ($failure in @((Get-PropertyValue -InputObject $captureDocument -Names @('failures')))) {
    Add-Message -Messages $blockers -Message ([string]$failure)
}

foreach ($warning in @((Get-PropertyValue -InputObject $gateDocument -Names @('warnings')))) {
    Add-Message -Messages $warnings -Message ([string]$warning)
}

$status = if ($promotionAllowed) {
    'promotion-ready'
}
elseif ($null -ne $gateDocument -or $null -ne $promotionSummaryDocument) {
    'promotion-blocked'
}
elseif (-not (Test-Path -LiteralPath $paths.liveCoords)) {
    'awaiting-live-truth'
}
elseif ($null -eq $scoresDocument) {
    'awaiting-memory-candidates'
}
else {
    'awaiting-promotion-gate'
}

$artifacts = [System.Collections.Generic.List[object]]::new()
foreach ($entry in $paths.GetEnumerator()) {
    $path = [string]$entry.Value
    $exists = Test-Path -LiteralPath $path
    $artifacts.Add([ordered]@{
            name = [string]$entry.Key
            path = $path
            exists = $exists
            length = $(if ($exists) { (Get-Item -LiteralPath $path).Length } else { $null })
        }) | Out-Null
}

$result = [ordered]@{
    schemaVersion = $schemaVersion
    mode = 'coordinate-bundle-status'
    generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    status = $status
    bundleDirectory = $resolvedBundleDirectory
    capture = [ordered]@{
        status = $captureStatus
        fresh = $captureFresh
        exported = $captureExported
        liveCoordLineCount = $liveCoordLineCount
    }
    scoring = [ordered]@{
        status = $scoreStatus
        promotionReady = $promotionReady
        truthSampleCount = ConvertTo-IntOrNull (Get-PropertyValue -InputObject $scoresDocument -Names @('truthSampleCount'))
        memoryRecordCount = ConvertTo-IntOrNull (Get-PropertyValue -InputObject $scoresDocument -Names @('memoryRecordCount'))
        candidateCount = ConvertTo-IntOrNull (Get-PropertyValue -InputObject $scoresDocument -Names @('candidateCount'))
    }
    promotion = [ordered]@{
        status = $promotionStatus
        allowed = $promotionAllowed
        selectedCandidateId = [string](Get-PropertyValue -InputObject $(if ($null -ne $promotionSummaryDocument) { $promotionSummaryDocument } else { $gateDocument }) -Names @('selectedCandidateId'))
        classification = [string](Get-PropertyValue -InputObject $(if ($null -ne $promotionSummaryDocument) { $promotionSummaryDocument } else { $selectedCandidate }) -Names @('classification'))
        score = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $(if ($null -ne $promotionSummaryDocument) { $promotionSummaryDocument } else { $selectedCandidate }) -Names @('score'))
        summaryFile = $paths.promotionGateSummary
        gateFile = $paths.promotionGate
    }
    truthSurface = [ordered]@{
        authoritativeTruthSurface = [string](Get-PropertyValue -InputObject $truthSurfaceDocument -Names @('authoritativeTruthSurface', 'truthSurface'))
        savedVariablesUse = [string](Get-PropertyValue -InputObject $truthSurfaceDocument -Names @('savedVariablesUse'))
        savedVariablesUsableAsLiveTruth = Get-PropertyValue -InputObject $truthSurfaceDocument -Names @('savedVariablesUsableAsLiveTruth')
    }
    savedVariables = [ordered]@{
        freshnessClassification = [string](Get-PropertyValue -InputObject $savedVariablesFreshnessDocument -Names @('freshnessClassification'))
        usableAsLiveTruth = Get-PropertyValue -InputObject $savedVariablesFreshnessDocument -Names @('usableAsLiveTruth')
    }
    blockers = @($blockers.ToArray() | Select-Object -Unique)
    warnings = @($warnings.ToArray() | Select-Object -Unique)
    artifacts = $artifacts.ToArray()
}

Write-Utf8TextAtomic -Path $OutputJsonFile -Content ($result | ConvertTo-Json -Depth 32)
Write-Utf8TextAtomic -Path $OutputMarkdownFile -Content (New-MarkdownStatus -Status ([pscustomobject]$result))

if ($Json) {
    $result | ConvertTo-Json -Depth 32
}
else {
    Write-Host ("Coordinate bundle status: {0}" -f $status)
    Write-Host ("Bundle: {0}" -f $resolvedBundleDirectory)
    if ($blockers.Count -gt 0) {
        Write-Host 'Blockers:' -ForegroundColor Yellow
        foreach ($blocker in @($blockers.ToArray() | Select-Object -Unique)) {
            Write-Host ("- {0}" -f $blocker)
        }
    }
}
