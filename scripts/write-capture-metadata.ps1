[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BundleDirectory,

    [string]$Label = 'capture',

    [string]$Purpose = 'unspecified',

    [ValidateSet(
        'none',
        'overlay',
        'overlay-screenshot-manual-extract',
        'validated-memory-anchor',
        'chromalink-live-telemetry',
        'readerbridge-live-telemetry',
        'candidate-memory',
        'post-flush-savedvariables',
        'savedvariables-live',
        'other')]
    [string]$TruthSurface = 'none',

    [ValidateSet('none', 'backup-only', 'seed-only', 'post-flush-snapshot', 'invalid-for-live')]
    [string]$SavedVariablesUse = 'none',

    [string]$SavedVariablesFilePath,

    [string]$CaptureStartUtc,

    [string]$CaptureEndUtc,

    [string]$ProcessName,

    [int]$ProcessId,

    [string]$TargetWindowHandle,

    [string]$ExpectedMovement,

    [string[]]$StopCondition = @(),

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$metadataSchemaVersion = 1

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

function ConvertTo-UtcDateTimeOffset {
    param(
        [string]$Value,
        [DateTimeOffset]$Default
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $Default.ToUniversalTime()
    }

    return ([DateTimeOffset]::Parse(
            $Value,
            [System.Globalization.CultureInfo]::InvariantCulture,
            [System.Globalization.DateTimeStyles]::RoundtripKind)).ToUniversalTime()
}

function Format-Utc {
    param([DateTimeOffset]$Value)

    return $Value.ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
}

function Get-RelativePathSafe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BasePath,

        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    try {
        return [System.IO.Path]::GetRelativePath($BasePath, $Path)
    }
    catch {
        return $Path
    }
}

function Get-ArtifactRole {
    param([string]$RelativePath)

    $fileName = [System.IO.Path]::GetFileName($RelativePath)
    switch -Regex ($fileName) {
        '^capture-plan\.json$' { return 'capture-plan' }
        '^truth-surface\.json$' { return 'truth-surface' }
        '^savedvariables-freshness\.json$' { return 'savedvariables-freshness' }
        '^quality-gate\.json$' { return 'quality-gate' }
        '^capture-lifecycle\.ndjson$' { return 'capture-lifecycle' }
        '^artifact-index\.json$' { return 'artifact-index' }
        '^live-coords\.ndjson$' { return 'live-coordinate-truth' }
        '^chromalink-live-coords\.ndjson$' { return 'live-coordinate-truth' }
        '^input-events\.ndjson$' { return 'input-events' }
        '^memory-timeseries\.csv$' { return 'candidate-memory-timeseries' }
        '^candidate-trajectory-scores\.json$' { return 'candidate-trajectory-scores' }
        '^promotion-gate\.json$' { return 'promotion-gate' }
        '^readerbridge-snapshot\.json$' { return 'readerbridge-post-save-snapshot' }
        '^package-manifest\.json$' { return 'package-manifest' }
        '^samples.*\.ndjson$' { return 'recorded-memory-samples' }
        default { return 'artifact' }
    }
}

function Add-Check {
    param(
        [System.Collections.Generic.List[object]]$Checks,

        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$Status,

        [string]$Message
    )

    $Checks.Add([ordered]@{
            name = $Name
            status = $Status
            message = $Message
        }) | Out-Null
}

$resolvedBundleDirectory = [System.IO.Path]::GetFullPath($BundleDirectory)
New-Item -ItemType Directory -Path $resolvedBundleDirectory -Force | Out-Null

$nowUtc = [DateTimeOffset]::UtcNow
$captureStart = ConvertTo-UtcDateTimeOffset -Value $CaptureStartUtc -Default $nowUtc
$captureEnd = ConvertTo-UtcDateTimeOffset -Value $CaptureEndUtc -Default $nowUtc
if ($captureEnd -lt $captureStart) {
    throw "CaptureEndUtc must be greater than or equal to CaptureStartUtc."
}

$truthSurfaceFile = Join-Path $resolvedBundleDirectory 'truth-surface.json'
$savedVariablesFreshnessFile = Join-Path $resolvedBundleDirectory 'savedvariables-freshness.json'
$capturePlanFile = Join-Path $resolvedBundleDirectory 'capture-plan.json'
$captureLifecycleFile = Join-Path $resolvedBundleDirectory 'capture-lifecycle.ndjson'
$qualityGateFile = Join-Path $resolvedBundleDirectory 'quality-gate.json'
$artifactIndexFile = Join-Path $resolvedBundleDirectory 'artifact-index.json'

$savedVariablesItem = $null
$resolvedSavedVariablesFilePath = $null
if (-not [string]::IsNullOrWhiteSpace($SavedVariablesFilePath)) {
    $resolvedSavedVariablesFilePath = [System.IO.Path]::GetFullPath($SavedVariablesFilePath)
    if (Test-Path -LiteralPath $resolvedSavedVariablesFilePath) {
        $savedVariablesItem = Get-Item -LiteralPath $resolvedSavedVariablesFilePath
    }
}

$savedVariablesLastWriteUtc = $null
$freshnessClassification = 'not-used'
if (-not [string]::IsNullOrWhiteSpace($resolvedSavedVariablesFilePath)) {
    if ($null -eq $savedVariablesItem) {
        $freshnessClassification = 'missing'
    }
    else {
        $savedVariablesLastWriteUtc = [DateTimeOffset]::new($savedVariablesItem.LastWriteTimeUtc).ToUniversalTime()
        if ($SavedVariablesUse -eq 'none') {
            $freshnessClassification = 'available-but-not-used'
        }
        elseif ($savedVariablesLastWriteUtc -lt $captureStart) {
            $freshnessClassification = 'stale-post-save-snapshot'
        }
        elseif ($savedVariablesLastWriteUtc -ge $captureEnd) {
            $freshnessClassification = 'post-capture-save'
        }
        else {
            $freshnessClassification = 'during-capture-save'
        }
    }
}

$failures = [System.Collections.Generic.List[string]]::new()
$warnings = [System.Collections.Generic.List[string]]::new()
$checks = [System.Collections.Generic.List[object]]::new()

if ($TruthSurface -eq 'savedvariables-live') {
    $failures.Add('SavedVariables cannot be used as a live truth surface. Use overlay, validated memory, or live telemetry instead.') | Out-Null
    Add-Check -Checks $checks -Name 'savedvariables-live-truth' -Status 'fail' -Message 'Rejected SavedVariables-as-live.'
}
else {
    Add-Check -Checks $checks -Name 'savedvariables-live-truth' -Status 'pass' -Message 'SavedVariables are not declared as live truth.'
}

if ($SavedVariablesUse -eq 'invalid-for-live') {
    $failures.Add('SavedVariablesUse=invalid-for-live is a fail-closed marker and cannot pass a capture quality gate.') | Out-Null
    Add-Check -Checks $checks -Name 'savedvariables-use' -Status 'fail' -Message 'Invalid-for-live marker was requested.'
}
else {
    Add-Check -Checks $checks -Name 'savedvariables-use' -Status 'pass' -Message "SavedVariablesUse=$SavedVariablesUse."
}

if ($TruthSurface -eq 'post-flush-savedvariables') {
    if ([string]::IsNullOrWhiteSpace($resolvedSavedVariablesFilePath)) {
        $failures.Add('TruthSurface=post-flush-savedvariables requires SavedVariablesFilePath.') | Out-Null
        Add-Check -Checks $checks -Name 'post-flush-savedvariables-freshness' -Status 'fail' -Message 'No SavedVariables path was provided.'
    }
    elseif ($null -eq $savedVariablesItem) {
        $failures.Add("SavedVariables file was not found: $resolvedSavedVariablesFilePath") | Out-Null
        Add-Check -Checks $checks -Name 'post-flush-savedvariables-freshness' -Status 'fail' -Message 'SavedVariables file missing.'
    }
    elseif ($savedVariablesLastWriteUtc -lt $captureEnd) {
        $failures.Add("Post-flush SavedVariables truth requires a file write at or after capture end; LastWriteUtc=$((Format-Utc $savedVariablesLastWriteUtc)), CaptureEndUtc=$((Format-Utc $captureEnd)).") | Out-Null
        Add-Check -Checks $checks -Name 'post-flush-savedvariables-freshness' -Status 'fail' -Message 'SavedVariables file predates capture end.'
    }
    else {
        Add-Check -Checks $checks -Name 'post-flush-savedvariables-freshness' -Status 'pass' -Message 'SavedVariables file is post-capture.'
    }
}

if ($freshnessClassification -eq 'stale-post-save-snapshot') {
    $warnings.Add("SavedVariables file predates capture start and is stale for live movement truth: $resolvedSavedVariablesFilePath") | Out-Null
    Add-Check -Checks $checks -Name 'savedvariables-staleness' -Status 'warning' -Message 'SavedVariables file predates capture start.'
}
elseif ($freshnessClassification -eq 'missing') {
    $warnings.Add("SavedVariables file path was provided but the file is missing: $resolvedSavedVariablesFilePath") | Out-Null
    Add-Check -Checks $checks -Name 'savedvariables-staleness' -Status 'warning' -Message 'SavedVariables file missing.'
}
else {
    Add-Check -Checks $checks -Name 'savedvariables-staleness' -Status 'pass' -Message "Freshness classification: $freshnessClassification."
}

if (-not [string]::IsNullOrWhiteSpace($resolvedSavedVariablesFilePath) -and $SavedVariablesUse -eq 'none') {
    $warnings.Add('SavedVariablesFilePath was supplied while SavedVariablesUse=none; file is recorded as available-but-not-used.') | Out-Null
}

$usableAsLiveTruth = $false
$status = if ($failures.Count -gt 0) { 'fail' } elseif ($warnings.Count -gt 0) { 'warning' } else { 'pass' }

$capturePlan = [ordered]@{
    schemaVersion = $metadataSchemaVersion
    mode = 'capture-plan'
    generatedAtUtc = Format-Utc $nowUtc
    label = $Label
    purpose = $Purpose
    bundleDirectory = $resolvedBundleDirectory
    captureStartUtc = Format-Utc $captureStart
    captureEndUtc = Format-Utc $captureEnd
    expectedMovement = $ExpectedMovement
    stopConditions = @($StopCondition)
    target = [ordered]@{
        processName = $ProcessName
        processId = $(if ($ProcessId -gt 0) { $ProcessId } else { $null })
        targetWindowHandle = $TargetWindowHandle
    }
    truthSurface = $TruthSurface
    savedVariablesUse = $SavedVariablesUse
    failClosedIfStaleSavedVariables = $true
}

$truthSurfaceDocument = [ordered]@{
    schemaVersion = $metadataSchemaVersion
    mode = 'truth-surface'
    generatedAtUtc = Format-Utc $nowUtc
    authoritativeTruthSurface = $TruthSurface
    savedVariablesUse = $SavedVariablesUse
    savedVariablesUsableAsLiveTruth = $usableAsLiveTruth
    candidateSurfaces = @()
    backupSurfaces = @()
    notes = @(
        'RIFT SavedVariables are post-save snapshots, not live IPC.',
        'Use overlay, validated memory anchors, or live telemetry for live movement truth.'
    )
}

if ($SavedVariablesUse -in @('backup-only', 'post-flush-snapshot')) {
    $truthSurfaceDocument['backupSurfaces'] = @('savedvariables-post-save-snapshot')
}
elseif ($SavedVariablesUse -eq 'seed-only') {
    $truthSurfaceDocument['candidateSurfaces'] = @('savedvariables-seed-only')
}

$savedVariablesFreshness = [ordered]@{
    schemaVersion = $metadataSchemaVersion
    mode = 'savedvariables-freshness'
    generatedAtUtc = Format-Utc $nowUtc
    filePath = $resolvedSavedVariablesFilePath
    exists = ($null -ne $savedVariablesItem)
    lastWriteTimeUtc = $(if ($null -ne $savedVariablesLastWriteUtc) { Format-Utc $savedVariablesLastWriteUtc } else { $null })
    captureStartUtc = Format-Utc $captureStart
    captureEndUtc = Format-Utc $captureEnd
    savedVariablesUse = $SavedVariablesUse
    freshnessClassification = $freshnessClassification
    usableAsLiveTruth = $usableAsLiveTruth
}

$qualityGate = [ordered]@{
    schemaVersion = $metadataSchemaVersion
    mode = 'capture-quality-gate'
    generatedAtUtc = Format-Utc $nowUtc
    status = $status
    truthSurface = $TruthSurface
    savedVariablesUse = $SavedVariablesUse
    savedVariablesFreshness = $freshnessClassification
    failures = $failures.ToArray()
    warnings = $warnings.ToArray()
    checks = $checks.ToArray()
}

$lifecycleEvents = @(
    [ordered]@{
        schemaVersion = $metadataSchemaVersion
        event = 'capture-start'
        timestampUtc = Format-Utc $captureStart
        label = $Label
        purpose = $Purpose
    },
    [ordered]@{
        schemaVersion = $metadataSchemaVersion
        event = 'capture-stop'
        timestampUtc = Format-Utc $captureEnd
        status = $status
    },
    [ordered]@{
        schemaVersion = $metadataSchemaVersion
        event = 'metadata-written'
        timestampUtc = Format-Utc $nowUtc
        qualityGateStatus = $status
    }
)

Write-Utf8TextAtomic -Path $capturePlanFile -Content ($capturePlan | ConvertTo-Json -Depth 16)
Write-Utf8TextAtomic -Path $truthSurfaceFile -Content ($truthSurfaceDocument | ConvertTo-Json -Depth 16)
Write-Utf8TextAtomic -Path $savedVariablesFreshnessFile -Content ($savedVariablesFreshness | ConvertTo-Json -Depth 16)
Write-Utf8TextAtomic -Path $qualityGateFile -Content ($qualityGate | ConvertTo-Json -Depth 16)
Write-Utf8TextAtomic -Path $captureLifecycleFile -Content (($lifecycleEvents | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 16 }) -join [Environment]::NewLine)

$artifactRecords = [System.Collections.Generic.List[object]]::new()
Get-ChildItem -LiteralPath $resolvedBundleDirectory -Recurse -File -ErrorAction SilentlyContinue |
    Sort-Object FullName |
    ForEach-Object {
        $relativePath = Get-RelativePathSafe -BasePath $resolvedBundleDirectory -Path $_.FullName
        $artifactRecords.Add([ordered]@{
                relativePath = $relativePath
                fullPath = $_.FullName
                role = Get-ArtifactRole -RelativePath $relativePath
                length = $_.Length
                lastWriteTimeUtc = ([DateTimeOffset]::new($_.LastWriteTimeUtc).ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture))
            }) | Out-Null
    }

if (-not @($artifactRecords | Where-Object { $_.relativePath -eq 'artifact-index.json' }).Count) {
    $artifactRecords.Add([ordered]@{
            relativePath = 'artifact-index.json'
            fullPath = $artifactIndexFile
            role = 'artifact-index'
            length = $null
            lastWriteTimeUtc = $null
        }) | Out-Null
}

$artifactIndex = [ordered]@{
    schemaVersion = $metadataSchemaVersion
    mode = 'artifact-index'
    generatedAtUtc = Format-Utc $nowUtc
    bundleDirectory = $resolvedBundleDirectory
    qualityGateFile = $qualityGateFile
    truthSurfaceFile = $truthSurfaceFile
    savedVariablesFreshnessFile = $savedVariablesFreshnessFile
    capturePlanFile = $capturePlanFile
    lifecycleFile = $captureLifecycleFile
    artifacts = $artifactRecords.ToArray()
}

Write-Utf8TextAtomic -Path $artifactIndexFile -Content ($artifactIndex | ConvertTo-Json -Depth 16)

$result = [ordered]@{
    schemaVersion = $metadataSchemaVersion
    mode = 'capture-metadata-result'
    status = $status
    bundleDirectory = $resolvedBundleDirectory
    capturePlanFile = $capturePlanFile
    truthSurfaceFile = $truthSurfaceFile
    savedVariablesFreshnessFile = $savedVariablesFreshnessFile
    qualityGateFile = $qualityGateFile
    captureLifecycleFile = $captureLifecycleFile
    artifactIndexFile = $artifactIndexFile
    failures = $failures.ToArray()
    warnings = $warnings.ToArray()
}

if ($Json) {
    $result | ConvertTo-Json -Depth 16
}
else {
    $color = if ($status -eq 'fail') { 'Red' } elseif ($status -eq 'warning') { 'Yellow' } else { 'Green' }
    Write-Host ("Capture metadata written: {0}" -f $resolvedBundleDirectory) -ForegroundColor $color
    Write-Host ("Quality gate: {0}" -f $status)
    if ($failures.Count -gt 0) {
        Write-Host 'Failures:' -ForegroundColor Red
        foreach ($failure in $failures) {
            Write-Host ("- {0}" -f $failure)
        }
    }
    if ($warnings.Count -gt 0) {
        Write-Host 'Warnings:' -ForegroundColor Yellow
        foreach ($warning in $warnings) {
            Write-Host ("- {0}" -f $warning)
        }
    }
}

if ($status -eq 'fail') {
    exit 1
}
