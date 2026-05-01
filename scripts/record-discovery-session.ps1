[CmdletBinding()]
param(
    [string]$Label = 'baseline',
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [int]$SampleCount = 20,
    [int]$IntervalMilliseconds = 500,
    [int]$TopSharedHubs = 4,
    [string]$SessionRoot = (Join-Path $PSScriptRoot 'sessions'),
    [string]$SessionMarkerInputFile,
    [string]$CapturePurpose = 'discovery session package',
    [string]$ExpectedMovement,
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
    [switch]$RefreshDiscoveryChain,
    [switch]$RefreshProjectorTrace,
    [switch]$RefreshReaderBridge,
    [switch]$ProofPolling,
    [string]$ProofCoordAnchorFile,
    [switch]$NoAhkFallback,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$packageSchemaVersion = 1

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$refreshScript = Join-Path $PSScriptRoot 'refresh-readerbridge-export.ps1'
$refreshDiscoveryChainScript = Join-Path $PSScriptRoot 'refresh-discovery-chain.ps1'
$refreshProjectorTraceScript = Join-Path $PSScriptRoot 'trace-player-state-projector.ps1'
$ownerStateNeighborhoodScript = Join-Path $PSScriptRoot 'capture-owner-state-neighborhood.ps1'
$watchsetScript = Join-Path $PSScriptRoot 'export-discovery-watchset.ps1'
$proofWatchsetScript = Join-Path $PSScriptRoot 'export-proof-polling-watchset.ps1'
$consistencyScript = Join-Path $PSScriptRoot 'inspect-capture-consistency.ps1'
$metadataScript = Join-Path $PSScriptRoot 'write-capture-metadata.ps1'
$capturesRoot = Join-Path $PSScriptRoot 'captures'
$ownerStateNeighborhoodFile = Join-Path $capturesRoot 'owner-state-neighborhood.json'

if ($SampleCount -le 0) {
    throw "SampleCount must be greater than zero."
}

if ($IntervalMilliseconds -lt 0) {
    throw "IntervalMilliseconds must be zero or greater."
}

function New-SessionSlug {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $slug = ($Value.Trim().ToLowerInvariant() -replace '[^a-z0-9]+', '-').Trim('-')
    if ([string]::IsNullOrWhiteSpace($slug)) {
        return 'session'
    }

    return $slug
}

function Invoke-ReaderJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & dotnet run --project $readerProject -- @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = ($output -join [Environment]::NewLine)
    }
}

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

function Get-MissingPackagePaths {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string[]]$Paths
    )

    $missing = [System.Collections.Generic.List[string]]::new()
    foreach ($path in $Paths) {
        if ([string]::IsNullOrWhiteSpace($path)) {
            continue
        }

        if (-not (Test-Path -LiteralPath $path)) {
            $missing.Add($path) | Out-Null
        }
    }

    return $missing.ToArray()
}

function Get-DocumentPropertyValue {
    param(
        [Parameter(Mandatory = $true)]
        $Document,

        [Parameter(Mandatory = $true)]
        [string]$Name,

        $Default = $null
    )

    if ($null -eq $Document) {
        return $Default
    }

    $property = $Document.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $Default
    }

    return $property.Value
}

function Get-ReaderBridgeSourceFileFromSnapshot {
    param(
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    try {
        $snapshotDocument = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -Depth 32
        return [string](Get-DocumentPropertyValue -Document $snapshotDocument -Name 'SourceFile')
    }
    catch {
        return $null
    }
}

function Write-CaptureMetadata {
    param(
        [Parameter(Mandatory = $true)]
        [DateTimeOffset]$CaptureStart,

        [Parameter(Mandatory = $true)]
        [DateTimeOffset]$CaptureEnd,

        [int]$CapturedProcessId,

        [string]$SnapshotFile
    )

    $effectiveSavedVariablesFilePath = $SavedVariablesFilePath
    if ([string]::IsNullOrWhiteSpace($effectiveSavedVariablesFilePath)) {
        $effectiveSavedVariablesFilePath = Get-ReaderBridgeSourceFileFromSnapshot -Path $SnapshotFile
    }

    $effectiveSavedVariablesUse = $SavedVariablesUse
    if ($effectiveSavedVariablesUse -eq 'none' -and -not [string]::IsNullOrWhiteSpace($effectiveSavedVariablesFilePath)) {
        $effectiveSavedVariablesUse = 'backup-only'
    }

    $metadataArguments = @(
        '-NoLogo',
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        $metadataScript,
        '-BundleDirectory',
        $sessionDirectory,
        '-Label',
        $Label,
        '-Purpose',
        $CapturePurpose,
        '-TruthSurface',
        $TruthSurface,
        '-SavedVariablesUse',
        $effectiveSavedVariablesUse,
        '-CaptureStartUtc',
        $CaptureStart.ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture),
        '-CaptureEndUtc',
        $CaptureEnd.ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture),
        '-ProcessName',
        $ProcessName,
        '-StopCondition',
        'manual stop; sample count reached; quality gate failure',
        '-Json'
    )

    if (-not [string]::IsNullOrWhiteSpace($effectiveSavedVariablesFilePath)) {
        $metadataArguments += @('-SavedVariablesFilePath', $effectiveSavedVariablesFilePath)
    }
    if (-not [string]::IsNullOrWhiteSpace($ExpectedMovement)) {
        $metadataArguments += @('-ExpectedMovement', $ExpectedMovement)
    }
    if ($CapturedProcessId -gt 0) {
        $metadataArguments += @('-ProcessId', $CapturedProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    }

    $previousErrorActionPreference = $ErrorActionPreference
    $nativePreferenceVariable = Get-Variable -Name PSNativeCommandUseErrorActionPreference -Scope 1 -ErrorAction SilentlyContinue
    $previousNativeCommandPreference = if ($null -ne $nativePreferenceVariable) { $nativePreferenceVariable.Value } else { $null }
    try {
        $ErrorActionPreference = 'Continue'
        if ($null -ne $nativePreferenceVariable) {
            Set-Variable -Name PSNativeCommandUseErrorActionPreference -Scope 1 -Value $false
        }

        $metadataOutput = & pwsh @metadataArguments 2>&1
        $metadataExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        if ($null -ne $nativePreferenceVariable) {
            Set-Variable -Name PSNativeCommandUseErrorActionPreference -Scope 1 -Value $previousNativeCommandPreference
        }
    }
    $metadataText = ($metadataOutput -join [Environment]::NewLine)
    $metadataResult = $null
    if (-not [string]::IsNullOrWhiteSpace($metadataText)) {
        try {
            $metadataResult = $metadataText | ConvertFrom-Json -Depth 32
        }
        catch {
            $metadataResult = $null
        }
    }

    return [pscustomobject]@{
        ExitCode = $metadataExitCode
        Output = $metadataText
        Result = $metadataResult
        CapturePlanFile = Join-Path $sessionDirectory 'capture-plan.json'
        TruthSurfaceFile = Join-Path $sessionDirectory 'truth-surface.json'
        SavedVariablesFreshnessFile = Join-Path $sessionDirectory 'savedvariables-freshness.json'
        QualityGateFile = Join-Path $sessionDirectory 'quality-gate.json'
        CaptureLifecycleFile = Join-Path $sessionDirectory 'capture-lifecycle.ndjson'
        ArtifactIndexFile = Join-Path $sessionDirectory 'artifact-index.json'
    }
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$labelSlug = New-SessionSlug -Value $Label
$sessionId = '{0}-{1}' -f $timestamp, $labelSlug
$resolvedSessionRoot = [System.IO.Path]::GetFullPath($SessionRoot)
$sessionDirectory = Join-Path $resolvedSessionRoot $sessionId
$artifactDirectory = Join-Path $sessionDirectory 'artifacts'
$watchsetFile = Join-Path $sessionDirectory 'watchset.json'
$consistencyFile = Join-Path $sessionDirectory 'capture-consistency.json'
$readerBridgeSnapshotFile = Join-Path $sessionDirectory 'readerbridge-snapshot.json'
$packageManifestFile = Join-Path $sessionDirectory 'package-manifest.json'
$resolvedSessionMarkerInputFile = $null
if (-not [string]::IsNullOrWhiteSpace($SessionMarkerInputFile)) {
    $resolvedSessionMarkerInputFile = [System.IO.Path]::GetFullPath($SessionMarkerInputFile)
}

$warnings = [System.Collections.Generic.List[string]]::new()
$copiedArtifacts = [System.Collections.Generic.List[object]]::new()
$ownerLineageFresh = $false
$recordDocument = $null
$packageManifest = $null
$metadataResult = $null
$captureStartUtc = [DateTimeOffset]::UtcNow

try {
    New-Item -ItemType Directory -Path $artifactDirectory -Force | Out-Null

    if ($TruthSurface -eq 'savedvariables-live' -or $SavedVariablesUse -eq 'invalid-for-live') {
        throw 'Capture preflight rejected SavedVariables-as-live. SavedVariables may be backup/post-flush snapshots or seed-only candidates, but not live truth.'
    }

    if ($RefreshDiscoveryChain) {
        try {
            $chainArguments = @{}
            if (-not $RefreshReaderBridge) {
                $chainArguments['NoReaderBridgeRefresh'] = $true
            }

            & $refreshDiscoveryChainScript @chainArguments
            $ownerLineageFresh = $true
        }
        catch {
            $warnings.Add("Discovery-chain refresh failed before session capture: $($_.Exception.Message)") | Out-Null
        }
    }
    elseif ($RefreshReaderBridge) {
        try {
            $refreshArguments = @{
                NoReader = $true
            }

            if ($NoAhkFallback) {
                $refreshArguments['NoAhkFallback'] = $true
            }

            & $refreshScript @refreshArguments
        }
        catch {
            $warnings.Add("ReaderBridge refresh failed before session capture: $($_.Exception.Message)") | Out-Null
        }
    }

    if ($RefreshProjectorTrace) {
        try {
            $projectorArguments = @{}
            if (-not $ownerLineageFresh) {
                $projectorArguments['RefreshOwnerGraph'] = $true
            }

            & $refreshProjectorTraceScript @projectorArguments | Out-Null
        }
        catch {
            $warnings.Add("State-projector trace refresh failed before session capture: $($_.Exception.Message)") | Out-Null
        }
    }

    if ($RefreshProjectorTrace -or -not (Test-Path -LiteralPath $ownerStateNeighborhoodFile)) {
        try {
            & $ownerStateNeighborhoodScript -Json | Out-Null
        }
        catch {
            $warnings.Add("Owner-state neighborhood capture failed before session capture: $($_.Exception.Message)") | Out-Null
        }
    }

    try {
        Write-Utf8TextAtomic -Path $consistencyFile -Content (& $consistencyScript -Json)
    }
    catch {
        $warnings.Add("Capture consistency report failed: $($_.Exception.Message)") | Out-Null
    }

    try {
        $snapshotResult = Invoke-ReaderJson -Arguments @('--readerbridge-snapshot', '--json')
        if ($snapshotResult.ExitCode -eq 0) {
            Write-Utf8TextAtomic -Path $readerBridgeSnapshotFile -Content $snapshotResult.Output
        }
        else {
            $warnings.Add("ReaderBridge snapshot capture failed: $($snapshotResult.Output)") | Out-Null
        }
    }
    catch {
        $warnings.Add("ReaderBridge snapshot capture threw: $($_.Exception.Message)") | Out-Null
    }

    $artifactNames = @(
        'ce-family-neighborhood.json',
        'ce-smart-player-family.json',
        'owner-state-neighborhood.json',
        'player-current-anchor.json',
        'player-coord-trace-cluster.json',
        'player-selector-owner-trace.json',
        'player-owner-components.json',
        'player-owner-graph.json',
        'player-source-chain.json',
        'player-source-accessor-family.json',
        'player-coord-write-trace.json',
        'player-stat-hub-graph.json',
        'player-state-projector-trace.json'
    )

    foreach ($artifactName in $artifactNames) {
        $sourcePath = Join-Path $capturesRoot $artifactName
        if (-not (Test-Path -LiteralPath $sourcePath)) {
            continue
        }

        $destinationPath = Join-Path $artifactDirectory $artifactName
        Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Force

        $copiedArtifacts.Add([ordered]@{
                Name = $artifactName
                File = $destinationPath
            }) | Out-Null
    }

    if ($ProofPolling) {
        $proofWatchsetArguments = @{
            ProcessName = $ProcessName
            OutputFile = $watchsetFile
            Json = $true
        }
        if ($PSBoundParameters.ContainsKey('ProcessId') -and $ProcessId -gt 0) {
            $proofWatchsetArguments['ProcessId'] = $ProcessId
        }
        if (-not [string]::IsNullOrWhiteSpace($ProofCoordAnchorFile)) {
            $proofWatchsetArguments['ProofCoordAnchorFile'] = $ProofCoordAnchorFile
            if (Test-Path -LiteralPath $ProofCoordAnchorFile) {
                $proofCoordAnchorArtifactFile = Join-Path $artifactDirectory 'proof-coord-anchor.json'
                Copy-Item -LiteralPath $ProofCoordAnchorFile -Destination $proofCoordAnchorArtifactFile -Force
                $copiedArtifacts.Add([ordered]@{
                        Name = 'proof-coord-anchor.json'
                        File = $proofCoordAnchorArtifactFile
                    }) | Out-Null
            }
        }

        & $proofWatchsetScript @proofWatchsetArguments | Out-Null
    }
    else {
        & $watchsetScript -ProcessName $ProcessName -TopSharedHubs $TopSharedHubs -OutputFile $watchsetFile -Json | Out-Null
    }

    if (-not (Test-Path -LiteralPath $watchsetFile)) {
        throw "Watchset export did not create '$watchsetFile'."
    }

    $readerArguments = @('--record-session', '--session-watchset-file', $watchsetFile, '--session-output-directory', $sessionDirectory, '--session-sample-count', $SampleCount.ToString([System.Globalization.CultureInfo]::InvariantCulture), '--session-interval-ms', $IntervalMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture), '--session-label', $Label, '--json')

    if (-not [string]::IsNullOrWhiteSpace($resolvedSessionMarkerInputFile)) {
        $markerInputDirectory = Split-Path -Path $resolvedSessionMarkerInputFile -Parent
        if (-not [string]::IsNullOrWhiteSpace($markerInputDirectory)) {
            New-Item -ItemType Directory -Path $markerInputDirectory -Force | Out-Null
        }

        if (-not (Test-Path -LiteralPath $resolvedSessionMarkerInputFile)) {
            Write-Utf8TextAtomic -Path $resolvedSessionMarkerInputFile -Content ''
        }

        $readerArguments += @('--session-marker-input-file', $resolvedSessionMarkerInputFile)
    }

    if ($PSBoundParameters.ContainsKey('ProcessId') -and $ProcessId -gt 0) {
        $readerArguments = @('--pid', $ProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture)) + $readerArguments
    }
    else {
        $readerArguments = @('--process-name', $ProcessName) + $readerArguments
    }

    $recordResult = Invoke-ReaderJson -Arguments $readerArguments
    if ($recordResult.ExitCode -ne 0) {
        throw "Session recording failed: $($recordResult.Output)"
    }

    $recordDocument = $recordResult.Output | ConvertFrom-Json -Depth 32

    $metadataResult = Write-CaptureMetadata -CaptureStart $captureStartUtc -CaptureEnd ([DateTimeOffset]::UtcNow) -CapturedProcessId ([int]$recordDocument.ProcessId) -SnapshotFile $readerBridgeSnapshotFile

    $packageWarnings = @($warnings)
    foreach ($warning in @($recordDocument.Warnings)) {
        if (-not [string]::IsNullOrWhiteSpace([string]$warning)) {
            $packageWarnings += [string]$warning
        }
    }
    if ($metadataResult.ExitCode -ne 0) {
        $packageWarnings += "Capture metadata quality gate failed: $($metadataResult.Output)"
    }

    $requiredPackagePaths = @(
        $watchsetFile,
        [string]$recordDocument.ManifestFile,
        [string]$recordDocument.SamplesFile,
        [string]$recordDocument.MarkersFile,
        [string]$recordDocument.ModulesFile,
        $metadataResult.CapturePlanFile,
        $metadataResult.TruthSurfaceFile,
        $metadataResult.SavedVariablesFreshnessFile,
        $metadataResult.QualityGateFile,
        $metadataResult.CaptureLifecycleFile,
        $metadataResult.ArtifactIndexFile,
        $artifactDirectory
    )
    $missingFiles = @(Get-MissingPackagePaths -Paths $requiredPackagePaths)
    if ($missingFiles.Count -gt 0) {
        $packageWarnings += "Package is missing required outputs: $($missingFiles -join ', ')"
    }

    $status = 'complete'
    $integrityStatus = 'ok'
    $failureMessage = $null
    if ($missingFiles.Count -gt 0 -or [string]$recordDocument.IntegrityStatus -eq 'failed' -or $metadataResult.ExitCode -ne 0) {
        $status = 'failed'
        $integrityStatus = 'failed'
        $failureMessage = if ($metadataResult.ExitCode -ne 0) { 'Capture metadata quality gate failed.' } else { 'Package is missing one or more required outputs.' }
    }
    elseif ([string]$recordDocument.IntegrityStatus -eq 'warning') {
        $integrityStatus = 'warning'
    }

    $packageManifest = [ordered]@{
        SchemaVersion = $packageSchemaVersion
        Mode = 'discovery-session-package'
        Status = $status
        IntegrityStatus = $integrityStatus
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
        SessionId = $sessionId
        Label = $Label
        SessionDirectory = $sessionDirectory
        WatchsetFile = $watchsetFile
        CaptureConsistencyFile = $(if (Test-Path -LiteralPath $consistencyFile) { $consistencyFile } else { $null })
        ReaderBridgeSnapshotFile = $(if (Test-Path -LiteralPath $readerBridgeSnapshotFile) { $readerBridgeSnapshotFile } else { $null })
        CapturePlanFile = $metadataResult.CapturePlanFile
        TruthSurfaceFile = $metadataResult.TruthSurfaceFile
        SavedVariablesFreshnessFile = $metadataResult.SavedVariablesFreshnessFile
        QualityGateFile = $metadataResult.QualityGateFile
        CaptureLifecycleFile = $metadataResult.CaptureLifecycleFile
        ArtifactIndexFile = $metadataResult.ArtifactIndexFile
        ArtifactDirectory = $artifactDirectory
        RecordingManifestFile = [string]$recordDocument.ManifestFile
        SamplesFile = [string]$recordDocument.SamplesFile
        MarkersFile = [string]$recordDocument.MarkersFile
        ModulesFile = [string]$recordDocument.ModulesFile
        Interrupted = $recordDocument.Interrupted
        SessionMarkerInputFile = [string](Get-DocumentPropertyValue -Document $recordDocument -Name 'SessionMarkerInputFile' -Default $resolvedSessionMarkerInputFile)
        MarkerCount = Get-DocumentPropertyValue -Document $recordDocument -Name 'MarkerCount'
        MarkerKinds = @((Get-DocumentPropertyValue -Document $recordDocument -Name 'MarkerKinds' -Default @()))
        RequestedRegionByteCount = $recordDocument.RequestedRegionByteCount
        TotalBytesRead = $recordDocument.TotalBytesRead
        TotalRegionReadFailures = $recordDocument.TotalRegionReadFailures
        ProcessId = $recordDocument.ProcessId
        ProcessName = $recordDocument.ProcessName
        WatchsetRegionCount = $recordDocument.WatchsetRegionCount
        SampleCount = $recordDocument.RecordedSampleCount
        IntervalMilliseconds = $recordDocument.IntervalMilliseconds
        MissingFiles = $missingFiles
        FailureMessage = $failureMessage
        CopiedArtifacts = $copiedArtifacts.ToArray()
        Warnings = @($packageWarnings | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)
    }

    Write-Utf8TextAtomic -Path $packageManifestFile -Content ($packageManifest | ConvertTo-Json -Depth 16)
    $packageWarningsList = @($packageManifest['Warnings'])

    if ($Json) {
        $packageManifest | ConvertTo-Json -Depth 16
        if ($status -eq 'failed') {
            exit 1
        }

        exit 0
    }

    Write-Host "Discovery session recorded." -ForegroundColor Green
    Write-Host ("Session id:           {0}" -f $sessionId)
    Write-Host ("Session directory:    {0}" -f $sessionDirectory)
    Write-Host ("Watchset:             {0}" -f $watchsetFile)
    Write-Host ("Samples file:         {0}" -f $recordDocument.SamplesFile)
    Write-Host ("Markers file:         {0}" -f $recordDocument.MarkersFile)
    Write-Host ("Quality gate:         {0}" -f $metadataResult.QualityGateFile)
    $sessionMarkerInputFileValue = [string](Get-DocumentPropertyValue -Document $recordDocument -Name 'SessionMarkerInputFile' -Default $resolvedSessionMarkerInputFile)
    if (-not [string]::IsNullOrWhiteSpace($sessionMarkerInputFileValue)) {
        Write-Host ("Marker input file:    {0}" -f $sessionMarkerInputFileValue)
    }
    Write-Host ("Copied artifacts:     {0}" -f $copiedArtifacts.Count)
    Write-Host ("Integrity:            {0}" -f $packageManifest['IntegrityStatus'])
    Write-Host ("Warnings:             {0}" -f $packageWarningsList.Count)

    if ($packageWarningsList.Count -gt 0) {
        Write-Host ""
        Write-Host "Warnings:" -ForegroundColor Yellow
        foreach ($warning in $packageWarningsList) {
            Write-Host ("- {0}" -f $warning)
        }
    }

    if ($status -eq 'failed') {
        Write-Error "Package integrity check failed: $failureMessage"
        exit 1
    }
}
catch {
    $failureMessage = $_.Exception.Message
    $failureWarnings = @($warnings)
    if (-not [string]::IsNullOrWhiteSpace($failureMessage)) {
        $failureWarnings += "Package capture failed: $failureMessage"
    }

    if (Test-Path -LiteralPath $sessionDirectory) {
        if ($null -eq $metadataResult) {
            try {
                $metadataResult = Write-CaptureMetadata -CaptureStart $captureStartUtc -CaptureEnd ([DateTimeOffset]::UtcNow) -CapturedProcessId $(if ($null -ne $recordDocument) { [int]$recordDocument.ProcessId } else { $ProcessId }) -SnapshotFile $readerBridgeSnapshotFile
                if ($metadataResult.ExitCode -ne 0) {
                    $failureWarnings += "Capture metadata quality gate failed: $($metadataResult.Output)"
                }
            }
            catch {
                $failureWarnings += "Capture metadata writing failed during error handling: $($_.Exception.Message)"
            }
        }

        $missingFiles = @(Get-MissingPackagePaths -Paths @(
                $watchsetFile,
                $consistencyFile,
                $readerBridgeSnapshotFile,
                $(if ($null -ne $metadataResult) { $metadataResult.CapturePlanFile } else { $null }),
                $(if ($null -ne $metadataResult) { $metadataResult.TruthSurfaceFile } else { $null }),
                $(if ($null -ne $metadataResult) { $metadataResult.SavedVariablesFreshnessFile } else { $null }),
                $(if ($null -ne $metadataResult) { $metadataResult.QualityGateFile } else { $null }),
                $(if ($null -ne $metadataResult) { $metadataResult.CaptureLifecycleFile } else { $null }),
                $(if ($null -ne $metadataResult) { $metadataResult.ArtifactIndexFile } else { $null }),
                $packageManifestFile,
                $(if ($null -ne $recordDocument) { [string]$recordDocument.ManifestFile } else { $null }),
                $(if ($null -ne $recordDocument) { [string]$recordDocument.SamplesFile } else { $null }),
                $(if ($null -ne $recordDocument) { [string]$recordDocument.MarkersFile } else { $null }),
                $(if ($null -ne $recordDocument) { [string]$recordDocument.ModulesFile } else { $null }),
                $artifactDirectory
            ))

        $packageManifest = [ordered]@{
            SchemaVersion = $packageSchemaVersion
            Mode = 'discovery-session-package'
            Status = 'failed'
            IntegrityStatus = 'failed'
            GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
            SessionId = $sessionId
            Label = $Label
            SessionDirectory = $sessionDirectory
            WatchsetFile = $watchsetFile
            CaptureConsistencyFile = $(if (Test-Path -LiteralPath $consistencyFile) { $consistencyFile } else { $null })
            ReaderBridgeSnapshotFile = $(if (Test-Path -LiteralPath $readerBridgeSnapshotFile) { $readerBridgeSnapshotFile } else { $null })
            CapturePlanFile = $(if ($null -ne $metadataResult) { $metadataResult.CapturePlanFile } else { $null })
            TruthSurfaceFile = $(if ($null -ne $metadataResult) { $metadataResult.TruthSurfaceFile } else { $null })
            SavedVariablesFreshnessFile = $(if ($null -ne $metadataResult) { $metadataResult.SavedVariablesFreshnessFile } else { $null })
            QualityGateFile = $(if ($null -ne $metadataResult) { $metadataResult.QualityGateFile } else { $null })
            CaptureLifecycleFile = $(if ($null -ne $metadataResult) { $metadataResult.CaptureLifecycleFile } else { $null })
            ArtifactIndexFile = $(if ($null -ne $metadataResult) { $metadataResult.ArtifactIndexFile } else { $null })
            ArtifactDirectory = $artifactDirectory
            RecordingManifestFile = $(if ($null -ne $recordDocument) { [string]$recordDocument.ManifestFile } else { $null })
            SamplesFile = $(if ($null -ne $recordDocument) { [string]$recordDocument.SamplesFile } else { $null })
            MarkersFile = $(if ($null -ne $recordDocument) { [string]$recordDocument.MarkersFile } else { $null })
            ModulesFile = $(if ($null -ne $recordDocument) { [string]$recordDocument.ModulesFile } else { $null })
            Interrupted = $(if ($null -ne $recordDocument) { $recordDocument.Interrupted } else { $null })
            SessionMarkerInputFile = $(if ($null -ne $recordDocument) { [string](Get-DocumentPropertyValue -Document $recordDocument -Name 'SessionMarkerInputFile' -Default $resolvedSessionMarkerInputFile) } else { $resolvedSessionMarkerInputFile })
            MarkerCount = $(if ($null -ne $recordDocument) { Get-DocumentPropertyValue -Document $recordDocument -Name 'MarkerCount' } else { $null })
            MarkerKinds = $(if ($null -ne $recordDocument) { @((Get-DocumentPropertyValue -Document $recordDocument -Name 'MarkerKinds' -Default @())) } else { @() })
            RequestedRegionByteCount = $(if ($null -ne $recordDocument) { $recordDocument.RequestedRegionByteCount } else { $null })
            TotalBytesRead = $(if ($null -ne $recordDocument) { $recordDocument.TotalBytesRead } else { $null })
            TotalRegionReadFailures = $(if ($null -ne $recordDocument) { $recordDocument.TotalRegionReadFailures } else { $null })
            ProcessId = $(if ($null -ne $recordDocument) { $recordDocument.ProcessId } else { $ProcessId })
            ProcessName = $(if ($null -ne $recordDocument) { $recordDocument.ProcessName } else { $ProcessName })
            WatchsetRegionCount = $(if ($null -ne $recordDocument) { $recordDocument.WatchsetRegionCount } else { $null })
            SampleCount = $(if ($null -ne $recordDocument) { $recordDocument.RecordedSampleCount } else { 0 })
            IntervalMilliseconds = $IntervalMilliseconds
            MissingFiles = $missingFiles
            FailureMessage = $failureMessage
            CopiedArtifacts = $copiedArtifacts.ToArray()
            Warnings = @($failureWarnings | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)
        }

        try {
            Write-Utf8TextAtomic -Path $packageManifestFile -Content ($packageManifest | ConvertTo-Json -Depth 16)
        }
        catch {
        }
    }

    if ($Json -and $null -ne $packageManifest) {
        $packageManifest | ConvertTo-Json -Depth 16
        exit 1
    }

    throw
}
