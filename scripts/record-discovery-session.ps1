[CmdletBinding()]
param(
    [string]$Label = 'baseline',
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [int]$SampleCount = 20,
    [int]$IntervalMilliseconds = 500,
    [int]$TopSharedHubs = 4,
    [string]$SessionRoot = (Join-Path $PSScriptRoot 'sessions'),
    [switch]$RefreshDiscoveryChain,
    [switch]$RefreshReaderBridge,
    [switch]$NoAhkFallback,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$refreshScript = Join-Path $PSScriptRoot 'refresh-readerbridge-export.ps1'
$refreshDiscoveryChainScript = Join-Path $PSScriptRoot 'refresh-discovery-chain.ps1'
$watchsetScript = Join-Path $PSScriptRoot 'export-discovery-watchset.ps1'
$consistencyScript = Join-Path $PSScriptRoot 'inspect-capture-consistency.ps1'
$capturesRoot = Join-Path $PSScriptRoot 'captures'

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

New-Item -ItemType Directory -Path $artifactDirectory -Force | Out-Null

$warnings = [System.Collections.Generic.List[string]]::new()
$copiedArtifacts = [System.Collections.Generic.List[object]]::new()

if ($RefreshDiscoveryChain) {
    try {
        $chainArguments = @{}
        if (-not $RefreshReaderBridge) {
            $chainArguments['NoReaderBridgeRefresh'] = $true
        }

        & $refreshDiscoveryChainScript @chainArguments
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

try {
    & $consistencyScript -Json | Set-Content -LiteralPath $consistencyFile -Encoding UTF8
}
catch {
    $warnings.Add("Capture consistency report failed: $($_.Exception.Message)") | Out-Null
}

try {
    $snapshotResult = Invoke-ReaderJson -Arguments @('--readerbridge-snapshot', '--json')
    if ($snapshotResult.ExitCode -eq 0) {
        $snapshotResult.Output | Set-Content -LiteralPath $readerBridgeSnapshotFile -Encoding UTF8
    }
    else {
        $warnings.Add("ReaderBridge snapshot capture failed: $($snapshotResult.Output)") | Out-Null
    }
}
catch {
    $warnings.Add("ReaderBridge snapshot capture threw: $($_.Exception.Message)") | Out-Null
}

$artifactNames = @(
    'player-current-anchor.json',
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

& $watchsetScript -ProcessName $ProcessName -TopSharedHubs $TopSharedHubs -OutputFile $watchsetFile -Json | Out-Null

$readerArguments = @('--record-session', '--session-watchset-file', $watchsetFile, '--session-output-directory', $sessionDirectory, '--session-sample-count', $SampleCount.ToString([System.Globalization.CultureInfo]::InvariantCulture), '--session-interval-ms', $IntervalMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture), '--session-label', $Label, '--json')

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

$packageWarnings = @($warnings)
foreach ($warning in @($recordDocument.Warnings)) {
    if (-not [string]::IsNullOrWhiteSpace([string]$warning)) {
        $packageWarnings += [string]$warning
    }
}

$packageManifest = [ordered]@{
    Mode = 'discovery-session-package'
    SessionId = $sessionId
    Label = $Label
    SessionDirectory = $sessionDirectory
    WatchsetFile = $watchsetFile
    CaptureConsistencyFile = $(if (Test-Path -LiteralPath $consistencyFile) { $consistencyFile } else { $null })
    ReaderBridgeSnapshotFile = $(if (Test-Path -LiteralPath $readerBridgeSnapshotFile) { $readerBridgeSnapshotFile } else { $null })
    ArtifactDirectory = $artifactDirectory
    RecordingManifestFile = [string]$recordDocument.ManifestFile
    SamplesFile = [string]$recordDocument.SamplesFile
    MarkersFile = [string]$recordDocument.MarkersFile
    ModulesFile = [string]$recordDocument.ModulesFile
    ProcessId = $recordDocument.ProcessId
    ProcessName = $recordDocument.ProcessName
    WatchsetRegionCount = $recordDocument.WatchsetRegionCount
    SampleCount = $recordDocument.RecordedSampleCount
    IntervalMilliseconds = $recordDocument.IntervalMilliseconds
    CopiedArtifacts = $copiedArtifacts.ToArray()
    Warnings = @($packageWarnings | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)
}

$packageManifest | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $packageManifestFile -Encoding UTF8
$packageWarningsList = @($packageManifest['Warnings'])

if ($Json) {
    $packageManifest | ConvertTo-Json -Depth 16
    exit 0
}

Write-Host "Discovery session recorded." -ForegroundColor Green
Write-Host ("Session id:           {0}" -f $sessionId)
Write-Host ("Session directory:    {0}" -f $sessionDirectory)
Write-Host ("Watchset:             {0}" -f $watchsetFile)
Write-Host ("Samples file:         {0}" -f $recordDocument.SamplesFile)
Write-Host ("Markers file:         {0}" -f $recordDocument.MarkersFile)
Write-Host ("Copied artifacts:     {0}" -f $copiedArtifacts.Count)
Write-Host ("Warnings:             {0}" -f $packageWarningsList.Count)

if ($packageWarningsList.Count -gt 0) {
    Write-Host ""
    Write-Host "Warnings:" -ForegroundColor Yellow
    foreach ($warning in $packageWarningsList) {
        Write-Host ("- {0}" -f $warning)
    }
}
