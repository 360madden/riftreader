[CmdletBinding()]
param(
    [string]$SnapshotPath = (Join-Path $env:LOCALAPPDATA 'ChromaLink\DesktopDotNet\out\chromalink-live-telemetry.json'),

    [string]$WorldStateUrl = '',

    [string]$WorldStatePath = '',

    [string]$ChromaLinkRoot = 'C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink',

    [string]$BridgeProject = '',

    [string]$BundleDirectory,

    [string]$OutputFile,

    [string]$BridgeReadinessFile,

    [string]$ContractFile,

    [string]$ContractManifestPath = '',

    [string]$ContractSchemaPath = '',

    [string]$PreflightFile,

    [string]$TruthSurfaceFile,

    [string]$SavedVariablesFreshnessFile,

    [string]$CapturePlanFile,

    [string]$QualityGateFile,

    [string]$ArtifactIndexFile,

    [string]$ExportResultFile,

    [string]$SummaryFile,

    [int]$PreflightDurationSeconds = 0,

    [int]$PreflightIntervalMilliseconds = 250,

    [int]$ExportDurationSeconds = 0,

    [int]$ExportIntervalMilliseconds = 250,

    [int]$MaxSamples = 0,

    [int]$MaxFreshAgeMilliseconds = 2000,

    [int]$BridgeWaitSeconds = 10,

    [int]$BridgeRequestTimeoutSeconds = 2,

    [switch]$SkipBridgeReadiness,

    [switch]$StartBridge,

    [switch]$KeepBridgeRunning,

    [switch]$SkipContractPreflight,

    [switch]$IncludeDuplicates,

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$schemaVersion = 1

$bridgeScript = Join-Path $PSScriptRoot 'test-chromalink-http-bridge.ps1'
$contractScript = Join-Path $PSScriptRoot 'test-chromalink-world-state-contract.ps1'
$freshnessScript = Join-Path $PSScriptRoot 'test-chromalink-live-telemetry.ps1'
$exportScript = Join-Path $PSScriptRoot 'export-chromalink-live-coords.ps1'

if (-not (Test-Path -LiteralPath $bridgeScript)) {
    throw "ChromaLink bridge readiness script not found: $bridgeScript"
}

if (-not (Test-Path -LiteralPath $contractScript)) {
    throw "ChromaLink contract script not found: $contractScript"
}

if (-not (Test-Path -LiteralPath $freshnessScript)) {
    throw "ChromaLink freshness script not found: $freshnessScript"
}

if (-not (Test-Path -LiteralPath $exportScript)) {
    throw "ChromaLink export script not found: $exportScript"
}

if ($PreflightDurationSeconds -lt 0) {
    throw 'PreflightDurationSeconds must be zero or greater.'
}

if ($PreflightIntervalMilliseconds -lt 50) {
    throw 'PreflightIntervalMilliseconds must be at least 50.'
}

if ($ExportDurationSeconds -lt 0) {
    throw 'ExportDurationSeconds must be zero or greater.'
}

if ($ExportIntervalMilliseconds -lt 50) {
    throw 'ExportIntervalMilliseconds must be at least 50.'
}

if ($MaxSamples -lt 0) {
    throw 'MaxSamples must be zero or greater.'
}

if ($MaxFreshAgeMilliseconds -lt 0) {
    throw 'MaxFreshAgeMilliseconds must be zero or greater.'
}

if ($BridgeWaitSeconds -lt 0) {
    throw 'BridgeWaitSeconds must be zero or greater.'
}

if ($BridgeRequestTimeoutSeconds -lt 1) {
    throw 'BridgeRequestTimeoutSeconds must be at least 1.'
}

$useWorldStateUrl = -not [string]::IsNullOrWhiteSpace($WorldStateUrl)
$useWorldStatePath = -not [string]::IsNullOrWhiteSpace($WorldStatePath)
$useWorldStateInput = $useWorldStateUrl -or $useWorldStatePath

if ($useWorldStateUrl -and $useWorldStatePath) {
    throw 'Specify only one of WorldStateUrl or WorldStatePath.'
}

if ([string]::IsNullOrWhiteSpace($BundleDirectory)) {
    $BundleDirectory = Join-Path (Join-Path $PSScriptRoot 'captures') ('chromalink-live-coords-{0}' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
}

$resolvedBundleDirectory = [System.IO.Path]::GetFullPath($BundleDirectory)
New-Item -ItemType Directory -Path $resolvedBundleDirectory -Force | Out-Null

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = Join-Path $resolvedBundleDirectory 'live-coords.ndjson'
}

if ([string]::IsNullOrWhiteSpace($BridgeReadinessFile)) {
    $BridgeReadinessFile = Join-Path $resolvedBundleDirectory 'chromalink-http-bridge-readiness.json'
}

if ([string]::IsNullOrWhiteSpace($ContractFile)) {
    $ContractFile = Join-Path $resolvedBundleDirectory 'chromalink-world-state-contract.json'
}

if ([string]::IsNullOrWhiteSpace($PreflightFile)) {
    $PreflightFile = Join-Path $resolvedBundleDirectory 'chromalink-freshness-preflight.json'
}

if ([string]::IsNullOrWhiteSpace($TruthSurfaceFile)) {
    $TruthSurfaceFile = Join-Path $resolvedBundleDirectory 'truth-surface.json'
}

if ([string]::IsNullOrWhiteSpace($SavedVariablesFreshnessFile)) {
    $SavedVariablesFreshnessFile = Join-Path $resolvedBundleDirectory 'savedvariables-freshness.json'
}

if ([string]::IsNullOrWhiteSpace($CapturePlanFile)) {
    $CapturePlanFile = Join-Path $resolvedBundleDirectory 'capture-plan.json'
}

if ([string]::IsNullOrWhiteSpace($QualityGateFile)) {
    $QualityGateFile = Join-Path $resolvedBundleDirectory 'quality-gate.json'
}

if ([string]::IsNullOrWhiteSpace($ArtifactIndexFile)) {
    $ArtifactIndexFile = Join-Path $resolvedBundleDirectory 'artifact-index.json'
}

if ([string]::IsNullOrWhiteSpace($ExportResultFile)) {
    $ExportResultFile = Join-Path $resolvedBundleDirectory 'chromalink-live-coords-export-result.json'
}

if ([string]::IsNullOrWhiteSpace($SummaryFile)) {
    $SummaryFile = Join-Path $resolvedBundleDirectory 'chromalink-live-coords-capture-summary.json'
}

if (Test-Path -LiteralPath $TruthSurfaceFile) {
    Remove-Item -LiteralPath $TruthSurfaceFile -Force
}

if (Test-Path -LiteralPath $SavedVariablesFreshnessFile) {
    Remove-Item -LiteralPath $SavedVariablesFreshnessFile -Force
}

foreach ($metadataFile in @($CapturePlanFile, $QualityGateFile, $ArtifactIndexFile)) {
    if (Test-Path -LiteralPath $metadataFile) {
        Remove-Item -LiteralPath $metadataFile -Force
    }
}

$captureStartedAtUtc = [DateTimeOffset]::UtcNow

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

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $nativePreferenceVariable = Get-Variable -Name PSNativeCommandUseErrorActionPreference -Scope 1 -ErrorAction SilentlyContinue
    $previousNativeCommandPreference = if ($null -ne $nativePreferenceVariable) { $nativePreferenceVariable.Value } else { $null }
    try {
        $ErrorActionPreference = 'Continue'
        if ($null -ne $nativePreferenceVariable) {
            Set-Variable -Name PSNativeCommandUseErrorActionPreference -Scope 1 -Value $false
        }

        $output = & pwsh @Arguments 2>&1
        return [pscustomobject]@{
            ExitCode = $LASTEXITCODE
            Output = ($output -join [Environment]::NewLine)
        }
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        if ($null -ne $nativePreferenceVariable) {
            Set-Variable -Name PSNativeCommandUseErrorActionPreference -Scope 1 -Value $previousNativeCommandPreference
        }
    }
}

function ConvertFrom-JsonOrNull {
    param([string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $null
    }

    try {
        return $Text | ConvertFrom-Json -Depth 64
    }
    catch {
        return $null
    }
}

function Get-BaseUrlFromWorldStateUrl {
    param([Parameter(Mandatory = $true)][string]$Url)

    try {
        $uri = [Uri]$Url
        return $uri.GetLeftPart([UriPartial]::Authority)
    }
    catch {
        throw "WorldStateUrl is not a valid absolute URI: $Url"
    }
}

function Get-CaptureInputMode {
    if ($useWorldStateUrl) {
        return 'world-state-url'
    }
    elseif ($useWorldStatePath) {
        return 'world-state-file'
    }

    return 'snapshot-file'
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

function Stop-StartedBridgeIfNeeded {
    param([int]$ProcessId)

    if ($ProcessId -le 0 -or $KeepBridgeRunning) {
        return $false
    }

    try {
        $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($null -eq $process) {
            return $false
        }

        Stop-Process -Id $ProcessId -Force
        return $true
    }
    catch {
        return $false
    }
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
        '^artifact-index\.json$' { return 'artifact-index' }
        '^live-coords\.ndjson$' { return 'live-coordinate-truth' }
        '^chromalink-http-bridge-readiness\.json$' { return 'chromalink-http-bridge-readiness' }
        '^chromalink-world-state-contract\.json$' { return 'chromalink-world-state-contract' }
        '^chromalink-freshness-preflight\.json$' { return 'chromalink-freshness-preflight' }
        '^chromalink-live-coords-export-result\.json$' { return 'chromalink-live-coords-export-result' }
        '^chromalink-live-coords-capture-summary\.json$' { return 'chromalink-live-coords-capture-summary' }
        default { return 'artifact' }
    }
}

function New-CapturePlanDocument {
    return [ordered]@{
        schemaVersion = $schemaVersion
        mode = 'capture-plan'
        generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        label = 'chromalink-live-coords'
        purpose = 'Capture ChromaLink coordinate telemetry as an external truth stream for candidate scoring.'
        bundleDirectory = $resolvedBundleDirectory
        inputMode = Get-CaptureInputMode
        truthSurface = 'chromalink-live-telemetry'
        savedVariablesUse = 'none'
        failClosedIfStaleSavedVariables = $true
        input = [ordered]@{
            worldStateUrl = $(if ($useWorldStateUrl) { $WorldStateUrl } else { $null })
            worldStatePath = $(if ($useWorldStatePath) { [System.IO.Path]::GetFullPath($WorldStatePath) } else { $null })
            snapshotPath = $(if (-not $useWorldStateInput) { [System.IO.Path]::GetFullPath($SnapshotPath) } else { $null })
        }
        outputFile = [System.IO.Path]::GetFullPath($OutputFile)
        preflight = [ordered]@{
            maxFreshAgeMs = $MaxFreshAgeMilliseconds
            durationSeconds = $PreflightDurationSeconds
            intervalMilliseconds = $PreflightIntervalMilliseconds
        }
        export = [ordered]@{
            durationSeconds = $ExportDurationSeconds
            intervalMilliseconds = $ExportIntervalMilliseconds
            maxSamples = $MaxSamples
            includeDuplicates = [bool]$IncludeDuplicates
        }
        bridge = [ordered]@{
            required = [bool]($useWorldStateUrl -and -not $SkipBridgeReadiness)
            startBridge = [bool]$StartBridge
            keepBridgeRunning = [bool]$KeepBridgeRunning
            waitSeconds = $BridgeWaitSeconds
            requestTimeoutSeconds = $BridgeRequestTimeoutSeconds
        }
        contract = [ordered]@{
            required = [bool]($useWorldStateInput -and -not $SkipContractPreflight)
            skipContractPreflight = [bool]$SkipContractPreflight
        }
        stopConditions = @(
            'Fail if bridge readiness, freshness preflight, contract preflight, or export does not pass.',
            'Do not write truth-surface.json or savedvariables-freshness.json unless export passes.'
        )
    }
}

function New-TruthSurfaceDocument {
    param(
        [object]$PreflightDocument,

        [object]$BridgeDocument,

        [object]$ContractDocument,

        [object]$ExportDocument
    )

    $inputMode = Get-CaptureInputMode
    $sourceView = if ($useWorldStateInput) { 'chromalink-riftreader-world-state' } else { 'chromalink-rolling-snapshot' }
    $liveTruth = -not $useWorldStatePath

    return [ordered]@{
        schemaVersion = $schemaVersion
        mode = 'truth-surface'
        generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        authoritativeTruthSurface = 'chromalink-live-telemetry'
        sourceView = $sourceView
        inputMode = $inputMode
        liveTruth = [bool]$liveTruth
        freshnessRequired = $true
        savedVariablesUse = 'none'
        savedVariablesUsableAsLiveTruth = $false
        candidateSurfaces = @()
        backupSurfaces = @()
        input = [ordered]@{
            worldStateUrl = $(if ($useWorldStateUrl) { $WorldStateUrl } else { $null })
            worldStatePath = $(if ($useWorldStatePath) { [System.IO.Path]::GetFullPath($WorldStatePath) } else { $null })
            snapshotPath = $(if (-not $useWorldStateInput) { [System.IO.Path]::GetFullPath($SnapshotPath) } else { $null })
        }
        freshness = [ordered]@{
            status = [string](Get-PropertyValue -InputObject $PreflightDocument -Names @('status'))
            fresh = Get-PropertyValue -InputObject $PreflightDocument -Names @('fresh')
            maxFreshAgeMs = $MaxFreshAgeMilliseconds
            file = [System.IO.Path]::GetFullPath($PreflightFile)
        }
        bridge = [ordered]@{
            required = [bool]($useWorldStateUrl -and -not $SkipBridgeReadiness)
            status = [string](Get-PropertyValue -InputObject $BridgeDocument -Names @('status'))
            file = $(if ($useWorldStateUrl -and -not $SkipBridgeReadiness) { [System.IO.Path]::GetFullPath($BridgeReadinessFile) } else { $null })
        }
        contract = [ordered]@{
            required = [bool]($useWorldStateInput -and -not $SkipContractPreflight)
            status = [string](Get-PropertyValue -InputObject $ContractDocument -Names @('status'))
            file = $(if ($useWorldStateInput -and -not $SkipContractPreflight) { [System.IO.Path]::GetFullPath($ContractFile) } else { $null })
        }
        export = [ordered]@{
            status = [string](Get-PropertyValue -InputObject $ExportDocument -Names @('status'))
            sampleCount = Get-PropertyValue -InputObject $ExportDocument -Names @('sampleCount', 'writtenSampleCount', 'writtenCount')
            file = [System.IO.Path]::GetFullPath($ExportResultFile)
            liveCoordsFile = [System.IO.Path]::GetFullPath($OutputFile)
        }
        artifacts = [ordered]@{
            truthSurfaceFile = [System.IO.Path]::GetFullPath($TruthSurfaceFile)
            liveCoordsFile = [System.IO.Path]::GetFullPath($OutputFile)
            preflightFile = [System.IO.Path]::GetFullPath($PreflightFile)
            bridgeReadinessFile = $(if ($useWorldStateUrl -and -not $SkipBridgeReadiness) { [System.IO.Path]::GetFullPath($BridgeReadinessFile) } else { $null })
            contractFile = $(if ($useWorldStateInput -and -not $SkipContractPreflight) { [System.IO.Path]::GetFullPath($ContractFile) } else { $null })
            exportResultFile = [System.IO.Path]::GetFullPath($ExportResultFile)
            summaryFile = [System.IO.Path]::GetFullPath($SummaryFile)
        }
        notes = @(
            'ChromaLink telemetry is an external live/API truth surface for coordinate capture and candidate scoring.',
            'This artifact does not prove native ReaderBridge pointer/source-chain provenance.',
            'RIFT SavedVariables are not used as live truth by this capture path.'
        )
    }
}

function New-SavedVariablesFreshnessDocument {
    param([DateTimeOffset]$CaptureEndUtc)

    return [ordered]@{
        schemaVersion = $schemaVersion
        mode = 'savedvariables-freshness'
        generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        filePath = $null
        exists = $false
        lastWriteTimeUtc = $null
        captureStartUtc = $captureStartedAtUtc.ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        captureEndUtc = $CaptureEndUtc.ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        savedVariablesUse = 'none'
        freshnessClassification = 'not-used'
        usableAsLiveTruth = $false
        source = 'chromalink-live-telemetry'
        notes = @(
            'This ChromaLink capture path does not read RIFT SavedVariables.',
            'SavedVariables are post-save snapshots and are not usable as live movement truth.'
        )
    }
}

function New-QualityGateDocument {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CaptureStatus,

        [Parameter(Mandatory = $true)]
        [bool]$Fresh,

        [Parameter(Mandatory = $true)]
        [bool]$Exported,

        [object]$PreflightDocument,

        [object]$BridgeDocument,

        [object]$ContractDocument,

        [object]$ExportDocument,

        [string[]]$Failures = @()
    )

    $checks = [System.Collections.Generic.List[object]]::new()
    $checks.Add([ordered]@{
            name = 'savedvariables-not-live-truth'
            status = 'pass'
            message = 'ChromaLink capture path does not read SavedVariables as live truth.'
        }) | Out-Null

    $checks.Add([ordered]@{
            name = 'bridge-readiness'
            status = $(if ($useWorldStateUrl -and -not $SkipBridgeReadiness) { if ($null -ne $BridgeDocument -and [string]$BridgeDocument.status -eq 'pass') { 'pass' } else { 'fail' } } else { 'skipped' })
            message = $(if ($useWorldStateUrl -and -not $SkipBridgeReadiness) { "Bridge status=$([string](Get-PropertyValue -InputObject $BridgeDocument -Names @('status')))." } else { 'Bridge readiness is not required for this input mode or was skipped.' })
        }) | Out-Null

    $checks.Add([ordered]@{
            name = 'freshness-preflight'
            status = $(if ($null -ne $PreflightDocument -and [string]$PreflightDocument.status -eq 'pass' -and [bool]$PreflightDocument.fresh -eq $true) { 'pass' } else { 'fail' })
            message = "Preflight status=$([string](Get-PropertyValue -InputObject $PreflightDocument -Names @('status'))) fresh=$([string](Get-PropertyValue -InputObject $PreflightDocument -Names @('fresh')))."
        }) | Out-Null

    $checks.Add([ordered]@{
            name = 'contract-preflight'
            status = $(if ($useWorldStateInput -and -not $SkipContractPreflight) { if ($null -ne $ContractDocument -and [string]$ContractDocument.status -eq 'pass') { 'pass' } else { 'fail' } } else { 'skipped' })
            message = $(if ($useWorldStateInput -and -not $SkipContractPreflight) { "Contract status=$([string](Get-PropertyValue -InputObject $ContractDocument -Names @('status')))." } else { 'Contract preflight is not required for this input mode or was skipped.' })
        }) | Out-Null

    $checks.Add([ordered]@{
            name = 'live-coord-export'
            status = $(if ($Exported -and $null -ne $ExportDocument -and [string]$ExportDocument.status -eq 'pass') { 'pass' } else { 'fail' })
            message = "Export status=$([string](Get-PropertyValue -InputObject $ExportDocument -Names @('status'))) samplesWritten=$([string](Get-PropertyValue -InputObject $ExportDocument -Names @('samplesWritten')))."
        }) | Out-Null

    return [ordered]@{
        schemaVersion = $schemaVersion
        mode = 'capture-quality-gate'
        generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        status = $(if ($CaptureStatus -eq 'pass' -and $Fresh -and $Exported) { 'pass' } else { 'fail' })
        captureStatus = $CaptureStatus
        truthSurface = 'chromalink-live-telemetry'
        savedVariablesUse = 'none'
        savedVariablesFreshness = $(if ($Exported) { 'not-used' } else { $null })
        fresh = $Fresh
        exported = $Exported
        inputMode = Get-CaptureInputMode
        failures = @($Failures)
        warnings = @()
        checks = $checks.ToArray()
    }
}

function Write-ArtifactIndex {
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
                fullPath = [System.IO.Path]::GetFullPath($ArtifactIndexFile)
                role = 'artifact-index'
                length = $null
                lastWriteTimeUtc = $null
            }) | Out-Null
    }

    $artifactIndex = [ordered]@{
        schemaVersion = $schemaVersion
        mode = 'artifact-index'
        generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        bundleDirectory = $resolvedBundleDirectory
        capturePlanFile = [System.IO.Path]::GetFullPath($CapturePlanFile)
        qualityGateFile = [System.IO.Path]::GetFullPath($QualityGateFile)
        truthSurfaceFile = [System.IO.Path]::GetFullPath($TruthSurfaceFile)
        savedVariablesFreshnessFile = [System.IO.Path]::GetFullPath($SavedVariablesFreshnessFile)
        artifacts = $artifactRecords.ToArray()
    }

    Write-Utf8TextAtomic -Path $ArtifactIndexFile -Content ($artifactIndex | ConvertTo-Json -Depth 64)
}

function New-Summary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Status,

        [Parameter(Mandatory = $true)]
        [bool]$Fresh,

        [Parameter(Mandatory = $true)]
        [bool]$Exported,

        [object]$PreflightDocument,

        [object]$BridgeDocument,

        [object]$ContractDocument,

        [object]$ExportDocument,

        [object]$TruthSurfaceDocument,

        [object]$SavedVariablesFreshnessDocument,

        [bool]$RemovedOutputFile = $false,

        [bool]$BridgeStoppedAfterCapture = $false,

        [string[]]$Failures = @()
    )

    return [ordered]@{
        schemaVersion = $schemaVersion
        mode = 'chromalink-live-coords-capture'
        generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        status = $Status
        fresh = $Fresh
        exported = $Exported
        inputMode = $(if ($useWorldStateUrl) { 'world-state-url' } elseif ($useWorldStatePath) { 'world-state-file' } else { 'snapshot-file' })
        worldStateUrl = $(if ($useWorldStateUrl) { $WorldStateUrl } else { $null })
        worldStatePath = $(if ($useWorldStatePath) { [System.IO.Path]::GetFullPath($WorldStatePath) } else { $null })
        snapshotPath = [System.IO.Path]::GetFullPath($SnapshotPath)
        bundleDirectory = $resolvedBundleDirectory
        outputFile = [System.IO.Path]::GetFullPath($OutputFile)
        removedOutputFile = $RemovedOutputFile
        bridgeReadinessFile = [System.IO.Path]::GetFullPath($BridgeReadinessFile)
        skipBridgeReadiness = [bool]$SkipBridgeReadiness
        startBridge = [bool]$StartBridge
        keepBridgeRunning = [bool]$KeepBridgeRunning
        bridgeStoppedAfterCapture = $BridgeStoppedAfterCapture
        contractFile = [System.IO.Path]::GetFullPath($ContractFile)
        skipContractPreflight = [bool]$SkipContractPreflight
        preflightFile = [System.IO.Path]::GetFullPath($PreflightFile)
        truthSurfaceFile = [System.IO.Path]::GetFullPath($TruthSurfaceFile)
        savedVariablesFreshnessFile = [System.IO.Path]::GetFullPath($SavedVariablesFreshnessFile)
        capturePlanFile = [System.IO.Path]::GetFullPath($CapturePlanFile)
        qualityGateFile = [System.IO.Path]::GetFullPath($QualityGateFile)
        artifactIndexFile = [System.IO.Path]::GetFullPath($ArtifactIndexFile)
        exportResultFile = [System.IO.Path]::GetFullPath($ExportResultFile)
        summaryFile = [System.IO.Path]::GetFullPath($SummaryFile)
        maxFreshAgeMs = $MaxFreshAgeMilliseconds
        preflightDurationSeconds = $PreflightDurationSeconds
        exportDurationSeconds = $ExportDurationSeconds
        preflight = $PreflightDocument
        bridge = $BridgeDocument
        contract = $ContractDocument
        export = $ExportDocument
        truthSurface = $TruthSurfaceDocument
        savedVariablesFreshness = $SavedVariablesFreshnessDocument
        failures = @($Failures)
    }
}

Write-Utf8TextAtomic -Path $CapturePlanFile -Content ((New-CapturePlanDocument) | ConvertTo-Json -Depth 64)

$bridgeDocument = $null
$startedBridgeProcessId = $null
$bridgeStoppedAfterCapture = $false
if ($useWorldStateUrl -and -not $SkipBridgeReadiness) {
    $bridgeArguments = @(
        '-NoLogo',
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        $bridgeScript,
        '-BaseUrl',
        (Get-BaseUrlFromWorldStateUrl -Url $WorldStateUrl),
        '-ChromaLinkRoot',
        $ChromaLinkRoot,
        '-WaitSeconds',
        $BridgeWaitSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-RequestTimeoutSeconds',
        $BridgeRequestTimeoutSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-Json'
    )

    if (-not [string]::IsNullOrWhiteSpace($BridgeProject)) {
        $bridgeArguments += @('-BridgeProject', $BridgeProject)
    }

    if ($StartBridge) {
        $bridgeArguments += @('-StartBridge', '-KeepRunning')
    }

    $bridgeRun = Invoke-NativeCommand -Arguments $bridgeArguments
    $bridgeDocument = ConvertFrom-JsonOrNull -Text $bridgeRun.Output
    Write-Utf8TextAtomic -Path $BridgeReadinessFile -Content $bridgeRun.Output

    if ($null -ne $bridgeDocument -and $bridgeDocument.startedByScript -eq $true -and $null -ne $bridgeDocument.bridgeProcessId) {
        $startedBridgeProcessId = [int]$bridgeDocument.bridgeProcessId
    }

    if ($bridgeRun.ExitCode -ne 0 -or $null -eq $bridgeDocument -or [string]$bridgeDocument.status -ne 'pass') {
        if ($null -ne $startedBridgeProcessId) {
            if (Stop-StartedBridgeIfNeeded -ProcessId $startedBridgeProcessId) {
                $bridgeStoppedAfterCapture = $true
            }
        }

        $failures = [System.Collections.Generic.List[string]]::new()
        if ($bridgeRun.ExitCode -ne 0) {
            $failures.Add("ChromaLink HTTP bridge readiness exited $($bridgeRun.ExitCode).") | Out-Null
        }
        if ($null -eq $bridgeDocument) {
            $failures.Add('ChromaLink HTTP bridge readiness output could not be parsed.') | Out-Null
        }
        else {
            foreach ($failure in @($bridgeDocument.failures)) {
                if (-not [string]::IsNullOrWhiteSpace([string]$failure)) {
                    $failures.Add([string]$failure) | Out-Null
                }
            }
        }

        $qualityGate = New-QualityGateDocument -CaptureStatus 'bridge-failed' -Fresh $false -Exported $false -PreflightDocument $null -BridgeDocument $bridgeDocument -ContractDocument $null -ExportDocument $null -Failures $failures.ToArray()
        Write-Utf8TextAtomic -Path $QualityGateFile -Content ($qualityGate | ConvertTo-Json -Depth 64)
        $summary = New-Summary -Status 'bridge-failed' -Fresh $false -Exported $false -PreflightDocument $null -BridgeDocument $bridgeDocument -ContractDocument $null -ExportDocument $null -BridgeStoppedAfterCapture $bridgeStoppedAfterCapture -Failures $failures.ToArray()
        Write-Utf8TextAtomic -Path $SummaryFile -Content ($summary | ConvertTo-Json -Depth 64)
        Write-ArtifactIndex

        if ($Json) {
            $summary | ConvertTo-Json -Depth 64
        }
        else {
            Write-Host 'ChromaLink live coord capture: bridge-failed' -ForegroundColor Red
            foreach ($failure in @($summary.failures)) {
                Write-Host ("- {0}" -f $failure) -ForegroundColor Red
            }
        }

        exit 1
    }
}

$preflightArguments = @(
    '-NoLogo',
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $freshnessScript,
    '-MaxFreshAgeMilliseconds',
    $MaxFreshAgeMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-IntervalMilliseconds',
    $PreflightIntervalMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-Json'
)

if ($useWorldStateUrl) {
    $preflightArguments += @('-WorldStateUrl', $WorldStateUrl)
}
elseif ($useWorldStatePath) {
    $preflightArguments += @('-WorldStatePath', $WorldStatePath)
}
else {
    $preflightArguments += @('-SnapshotPath', $SnapshotPath)
}

if ($PreflightDurationSeconds -gt 0) {
    $preflightArguments += @(
        '-Watch',
        '-DurationSeconds',
        $PreflightDurationSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture)
    )
}

$preflightRun = Invoke-NativeCommand -Arguments $preflightArguments
$preflightDocument = ConvertFrom-JsonOrNull -Text $preflightRun.Output
Write-Utf8TextAtomic -Path $PreflightFile -Content $preflightRun.Output

if ($preflightRun.ExitCode -ne 0 -or $null -eq $preflightDocument -or [string]$preflightDocument.status -ne 'pass' -or [bool]$preflightDocument.fresh -ne $true) {
    $failures = [System.Collections.Generic.List[string]]::new()
    if ($preflightRun.ExitCode -ne 0) {
        $failures.Add("ChromaLink freshness preflight exited $($preflightRun.ExitCode).") | Out-Null
    }
    if ($null -eq $preflightDocument) {
        $failures.Add('ChromaLink freshness preflight output could not be parsed.') | Out-Null
    }
    else {
        foreach ($failure in @($preflightDocument.failures)) {
            if (-not [string]::IsNullOrWhiteSpace([string]$failure)) {
                $failures.Add([string]$failure) | Out-Null
            }
        }
    }

    if ($null -ne $startedBridgeProcessId) {
        if (Stop-StartedBridgeIfNeeded -ProcessId $startedBridgeProcessId) {
            $bridgeStoppedAfterCapture = $true
        }
    }

    $qualityGate = New-QualityGateDocument -CaptureStatus 'preflight-failed' -Fresh $false -Exported $false -PreflightDocument $preflightDocument -BridgeDocument $bridgeDocument -ContractDocument $null -ExportDocument $null -Failures $failures.ToArray()
    Write-Utf8TextAtomic -Path $QualityGateFile -Content ($qualityGate | ConvertTo-Json -Depth 64)
    $summary = New-Summary -Status 'preflight-failed' -Fresh $false -Exported $false -PreflightDocument $preflightDocument -BridgeDocument $bridgeDocument -ContractDocument $null -ExportDocument $null -BridgeStoppedAfterCapture $bridgeStoppedAfterCapture -Failures $failures.ToArray()
    Write-Utf8TextAtomic -Path $SummaryFile -Content ($summary | ConvertTo-Json -Depth 64)
    Write-ArtifactIndex

    if ($Json) {
        $summary | ConvertTo-Json -Depth 64
    }
    else {
        Write-Host 'ChromaLink live coord capture: preflight-failed' -ForegroundColor Red
        foreach ($failure in @($summary.failures)) {
            Write-Host ("- {0}" -f $failure) -ForegroundColor Red
        }
    }

    exit 1
}

$contractDocument = $null
if ($useWorldStateInput -and -not $SkipContractPreflight) {
    $contractArguments = @(
        '-NoLogo',
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        $contractScript,
        '-Json'
    )

    if ($useWorldStateUrl) {
        $contractArguments += @('-BaseUrl', (Get-BaseUrlFromWorldStateUrl -Url $WorldStateUrl))
    }
    else {
        $contractArguments += @(
            '-ManifestPath',
            $ContractManifestPath,
            '-SchemaPath',
            $ContractSchemaPath,
            '-WorldStatePath',
            $WorldStatePath
        )
    }

    $contractRun = Invoke-NativeCommand -Arguments $contractArguments
    $contractDocument = ConvertFrom-JsonOrNull -Text $contractRun.Output
    Write-Utf8TextAtomic -Path $ContractFile -Content $contractRun.Output

    if ($contractRun.ExitCode -ne 0 -or $null -eq $contractDocument -or [string]$contractDocument.status -ne 'pass') {
        $failures = [System.Collections.Generic.List[string]]::new()
        if ($contractRun.ExitCode -ne 0) {
            $failures.Add("ChromaLink world-state contract preflight exited $($contractRun.ExitCode).") | Out-Null
        }
        if ($null -eq $contractDocument) {
            $failures.Add('ChromaLink world-state contract preflight output could not be parsed.') | Out-Null
        }
        else {
            foreach ($failure in @($contractDocument.failures)) {
                if (-not [string]::IsNullOrWhiteSpace([string]$failure)) {
                    $failures.Add([string]$failure) | Out-Null
                }
            }
        }

        if ($null -ne $startedBridgeProcessId) {
            if (Stop-StartedBridgeIfNeeded -ProcessId $startedBridgeProcessId) {
                $bridgeStoppedAfterCapture = $true
            }
        }

        $qualityGate = New-QualityGateDocument -CaptureStatus 'contract-failed' -Fresh $true -Exported $false -PreflightDocument $preflightDocument -BridgeDocument $bridgeDocument -ContractDocument $contractDocument -ExportDocument $null -Failures $failures.ToArray()
        Write-Utf8TextAtomic -Path $QualityGateFile -Content ($qualityGate | ConvertTo-Json -Depth 64)
        $summary = New-Summary -Status 'contract-failed' -Fresh $true -Exported $false -PreflightDocument $preflightDocument -BridgeDocument $bridgeDocument -ContractDocument $contractDocument -ExportDocument $null -BridgeStoppedAfterCapture $bridgeStoppedAfterCapture -Failures $failures.ToArray()
        Write-Utf8TextAtomic -Path $SummaryFile -Content ($summary | ConvertTo-Json -Depth 64)
        Write-ArtifactIndex

        if ($Json) {
            $summary | ConvertTo-Json -Depth 64
        }
        else {
            Write-Host 'ChromaLink live coord capture: contract-failed' -ForegroundColor Red
            foreach ($failure in @($summary.failures)) {
                Write-Host ("- {0}" -f $failure) -ForegroundColor Red
            }
        }

        exit 1
    }
}

$exportArguments = @(
    '-NoLogo',
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $exportScript,
    '-OutputFile',
    $OutputFile,
    '-IntervalMilliseconds',
    $ExportIntervalMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-MaxFreshAgeMilliseconds',
    $MaxFreshAgeMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-Json'
)

if ($useWorldStateUrl) {
    $exportArguments += @('-WorldStateUrl', $WorldStateUrl)
}
elseif ($useWorldStatePath) {
    $exportArguments += @('-WorldStatePath', $WorldStatePath)
}
else {
    $exportArguments += @('-SnapshotPath', $SnapshotPath)
}

if ($ExportDurationSeconds -gt 0) {
    $exportArguments += @(
        '-Watch',
        '-DurationSeconds',
        $ExportDurationSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture)
    )
}

if ($MaxSamples -gt 0) {
    $exportArguments += @('-MaxSamples', $MaxSamples.ToString([System.Globalization.CultureInfo]::InvariantCulture))
}

if ($IncludeDuplicates) {
    $exportArguments += '-IncludeDuplicates'
}

$exportRun = Invoke-NativeCommand -Arguments $exportArguments
$exportDocument = ConvertFrom-JsonOrNull -Text $exportRun.Output
Write-Utf8TextAtomic -Path $ExportResultFile -Content $exportRun.Output

$exported = $exportRun.ExitCode -eq 0 -and $null -ne $exportDocument -and [string]$exportDocument.status -eq 'pass'
$summaryStatus = if ($exported) { 'pass' } else { 'export-failed' }
$summaryFailures = [System.Collections.Generic.List[string]]::new()
if (-not $exported) {
    $summaryFailures.Add("ChromaLink live coord export did not pass; exitCode=$($exportRun.ExitCode).") | Out-Null
    if ($null -eq $exportDocument) {
        $summaryFailures.Add('ChromaLink live coord export output could not be parsed.') | Out-Null
    }
    elseif (-not [string]::IsNullOrWhiteSpace([string]$exportDocument.lastError)) {
        $summaryFailures.Add([string]$exportDocument.lastError) | Out-Null
    }
}

$removedOutputFile = $false
if (-not $exported -and (Test-Path -LiteralPath $OutputFile)) {
    Remove-Item -LiteralPath $OutputFile -Force
    $removedOutputFile = $true
    $summaryFailures.Add('Rejected live-coords.ndjson was removed because export did not pass freshness checks.') | Out-Null
}

if ($null -ne $startedBridgeProcessId) {
    if (Stop-StartedBridgeIfNeeded -ProcessId $startedBridgeProcessId) {
        $bridgeStoppedAfterCapture = $true
    }
}

$truthSurfaceDocument = $null
$savedVariablesFreshnessDocument = $null
if ($exported) {
    $captureEndedAtUtc = [DateTimeOffset]::UtcNow
    $truthSurfaceDocument = New-TruthSurfaceDocument -PreflightDocument $preflightDocument -BridgeDocument $bridgeDocument -ContractDocument $contractDocument -ExportDocument $exportDocument
    $savedVariablesFreshnessDocument = New-SavedVariablesFreshnessDocument -CaptureEndUtc $captureEndedAtUtc
    Write-Utf8TextAtomic -Path $TruthSurfaceFile -Content ($truthSurfaceDocument | ConvertTo-Json -Depth 64)
    Write-Utf8TextAtomic -Path $SavedVariablesFreshnessFile -Content ($savedVariablesFreshnessDocument | ConvertTo-Json -Depth 64)
}

$qualityGate = New-QualityGateDocument -CaptureStatus $summaryStatus -Fresh $true -Exported $exported -PreflightDocument $preflightDocument -BridgeDocument $bridgeDocument -ContractDocument $contractDocument -ExportDocument $exportDocument -Failures $summaryFailures.ToArray()
Write-Utf8TextAtomic -Path $QualityGateFile -Content ($qualityGate | ConvertTo-Json -Depth 64)

$summary = New-Summary -Status $summaryStatus -Fresh $true -Exported $exported -PreflightDocument $preflightDocument -BridgeDocument $bridgeDocument -ContractDocument $contractDocument -ExportDocument $exportDocument -TruthSurfaceDocument $truthSurfaceDocument -SavedVariablesFreshnessDocument $savedVariablesFreshnessDocument -RemovedOutputFile $removedOutputFile -BridgeStoppedAfterCapture $bridgeStoppedAfterCapture -Failures $summaryFailures.ToArray()
Write-Utf8TextAtomic -Path $SummaryFile -Content ($summary | ConvertTo-Json -Depth 64)
Write-ArtifactIndex

if ($Json) {
    $summary | ConvertTo-Json -Depth 64
}
else {
    $color = if ($exported) { 'Green' } else { 'Red' }
    Write-Host ("ChromaLink live coord capture: {0}" -f $summaryStatus) -ForegroundColor $color
    Write-Host ("Output: {0}" -f ([System.IO.Path]::GetFullPath($OutputFile)))
    foreach ($failure in @($summary.failures)) {
        Write-Host ("- {0}" -f $failure) -ForegroundColor Red
    }
}

if (-not $exported) {
    exit 1
}
