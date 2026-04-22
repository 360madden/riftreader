[CmdletBinding()]
param(
    [string]$Label = 'continuous-polling',
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [int]$SampleCount = 30,
    [int]$IntervalMilliseconds = 100,
    [int]$TopSharedHubs = 4,
    [string]$SessionRoot = (Join-Path $PSScriptRoot 'sessions'),
    [string]$SessionMarkerInputFile,
    [switch]$RefreshDiscoveryChain,
    [switch]$RefreshProjectorTrace,
    [switch]$RefreshReaderBridge,
    [switch]$NoAhkFallback,
    [switch]$AutoStart,
    [switch]$PrepareOnly,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$recordScript = Join-Path $PSScriptRoot 'record-discovery-session.ps1'
$appendMarkerScript = Join-Path $PSScriptRoot 'append-session-marker.ps1'
$resolveProofCoordAnchorScript = Join-Path $PSScriptRoot 'resolve-proof-coord-anchor.ps1'

if ($SampleCount -le 0) {
    throw 'SampleCount must be greater than zero.'
}

if ($IntervalMilliseconds -lt 0) {
    throw 'IntervalMilliseconds must be zero or greater.'
}

function Write-BigPrompt {
    param(
        [Parameter(Mandatory = $true)][string]$Color,
        [Parameter(Mandatory = $true)][string[]]$Lines
    )

    Write-Host ''
    Write-Host ('# ====================================================================') -ForegroundColor $Color
    foreach ($line in $Lines) {
        Write-Host ("# {0}" -f $line) -ForegroundColor $Color
    }
    Write-Host ('# ====================================================================') -ForegroundColor $Color
    Write-Host ''
}

function Start-Countdown {
    param(
        [Parameter(Mandatory = $true)][string]$Color,
        [Parameter(Mandatory = $true)][string]$Heading,
        [Parameter(Mandatory = $true)][string]$Detail,
        [int]$Seconds = 5
    )

    for ($remaining = $Seconds; $remaining -ge 1; $remaining--) {
        Write-BigPrompt -Color $Color -Lines @(
            $Heading,
            $Detail,
            ("⏳ {0}..." -f $remaining)
        )

        Start-Sleep -Seconds 1
    }
}

function Get-ProofCoordAnchorSnapshot {
    param(
        [switch]$Quiet
    )

    $resolveArguments = @{
        ProcessName = $ProcessName
        Json = $true
    }
    if ($PSBoundParameters.ContainsKey('ProcessId') -and $ProcessId -gt 0) {
        $resolveArguments['ProcessId'] = $ProcessId
    }

    if (-not $Quiet) {
        Write-Host '[ContinuousPolling] Resolving proof-grade coord-trace anchor before watchset export...' -ForegroundColor Cyan
    }

    $snapshotOutput = if ($Quiet) {
        & $resolveProofCoordAnchorScript @resolveArguments 3>$null 4>$null 5>$null 6>$null
    }
    else {
        & $resolveProofCoordAnchorScript @resolveArguments
    }

    $snapshotJson = ($snapshotOutput -join [Environment]::NewLine).Trim()
    if ([string]::IsNullOrWhiteSpace($snapshotJson)) {
        throw 'Proof coord-anchor resolution returned no JSON output.'
    }

    $snapshot = $snapshotJson | ConvertFrom-Json -Depth 32
    if ($snapshot.PSObject.Properties['Status'] -and $snapshot.Status -eq 'failed') {
        throw [string]$snapshot.Error
    }

    if ([string]::IsNullOrWhiteSpace([string]$snapshot.ObjectBaseAddress) -or [string]::IsNullOrWhiteSpace([string]$snapshot.CoordRegionAddress)) {
        throw 'Proof coord-anchor resolution did not produce a usable ObjectBaseAddress / CoordRegionAddress.'
    }

    return $snapshot
}

$resolvedSessionRoot = [System.IO.Path]::GetFullPath($SessionRoot)
New-Item -ItemType Directory -Path $resolvedSessionRoot -Force | Out-Null

$proofCoordAnchorSnapshot = $null
if (-not $Json -and -not $PrepareOnly) {
    Write-BigPrompt -Color Cyan -Lines @(
        '🧭 START PRECHECK',
        '🔎 Proof-anchor validation will run before recording is allowed.',
        '📣 You will now see a visible countdown before validation begins.'
    )

    Start-Countdown -Color Cyan -Heading '🧭 VALIDATING PROOF SOURCE' -Detail 'Proof-anchor validation will begin automatically before recording.' -Seconds 5
}

try {
    $proofCoordAnchorSnapshot = Get-ProofCoordAnchorSnapshot -Quiet:$Json
}
catch {
    if (-not $Json) {
        Write-BigPrompt -Color Red -Lines @(
            '🔴 START BLOCKED',
            '⚠️ Proof-anchor validation failed before recording could begin.',
            ("🧾 Error: {0}" -f $_.Exception.Message),
            '🚫 Recording countdown was not reached because proof mode failed closed.'
        )
    }

    throw
}

$proofCoordObjectAddress = [string]$proofCoordAnchorSnapshot.ObjectBaseAddress
$proofCoordRegionAddress = [string]$proofCoordAnchorSnapshot.CoordRegionAddress
$proofCoordTraceFile = [string]$proofCoordAnchorSnapshot.TraceSourceFile

$resolvedMarkerInputFile = if (-not [string]::IsNullOrWhiteSpace($SessionMarkerInputFile)) {
    [System.IO.Path]::GetFullPath($SessionMarkerInputFile)
}
else {
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    Join-Path $resolvedSessionRoot ("{0}-{1}-marker-input.ndjson" -f $timestamp, ($Label -replace '[^a-zA-Z0-9_-]+', '-'))
}

$markerDirectory = Split-Path -Path $resolvedMarkerInputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($markerDirectory)) {
    New-Item -ItemType Directory -Path $markerDirectory -Force | Out-Null
}

if (-not (Test-Path -LiteralPath $resolvedMarkerInputFile)) {
    [System.IO.File]::WriteAllText($resolvedMarkerInputFile, '', [System.Text.UTF8Encoding]::new($false))
}

$preflight = [ordered]@{
    Mode = 'continuous-polling-session-preflight'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    Label = $Label
    ProcessName = $ProcessName
    ProcessId = if ($PSBoundParameters.ContainsKey('ProcessId') -and $ProcessId -gt 0) { $ProcessId } else { $null }
    SampleCount = $SampleCount
    IntervalMilliseconds = $IntervalMilliseconds
    SessionRoot = $resolvedSessionRoot
    SessionMarkerInputFile = $resolvedMarkerInputFile
    ProofCoordObjectAddress = $proofCoordObjectAddress
    ProofCoordRegionAddress = $proofCoordRegionAddress
    ProofCoordTraceFile = $proofCoordTraceFile
    AutoStart = [bool]$AutoStart
    Notes = @(
        'This coordinator resolves a validated coord-trace anchor before exporting the watchset.',
        'Movement polling proof must use coord-trace-anchor truth only; heuristic or cached current-player anchors are not accepted here.',
        'This coordinator prepares a bounded continuous-polling capture and uses visible countdowns before starting and before final stop/reporting.',
        'Use the marker input file to append manual labels during the run if needed.'
    )
}

if ($Json) {
    $preflight | ConvertTo-Json -Depth 10 | Write-Output
}
else {
    Write-BigPrompt -Color Yellow -Lines @(
        '🟡 READY TO RECORD',
        '🎯 Continuous polling is prepared.',
        ("📦 Label: {0}" -f $Label),
        ("⏱️ Interval: {0} ms | Samples: {1}" -f $IntervalMilliseconds, $SampleCount),
        ("📍 Proof coord region: {0}" -f $proofCoordRegionAddress),
        ("🧱 Proof coord object: {0}" -f $proofCoordObjectAddress),
        ("📝 Marker file: {0}" -f $resolvedMarkerInputFile),
        '👀 Put Rift in the exact test state before the automatic countdown starts.'
    )
}

if ($PrepareOnly) {
    return
}

if (-not $Json) {
    Start-Countdown -Color Yellow -Heading '🚀 RECORDING STARTING' -Detail 'No confirmation required. Recording will begin automatically.' -Seconds 5
}

& $appendMarkerScript -File $resolvedMarkerInputFile -Kind 'phase' -Label 'recording-start' -Message 'Automatic countdown finished; recording started.' -Source 'continuous-polling-session' -Json *> $null

$recordArguments = @{
    Label = $Label
    ProcessName = $ProcessName
    SampleCount = $SampleCount
    IntervalMilliseconds = $IntervalMilliseconds
    TopSharedHubs = $TopSharedHubs
    SessionRoot = $resolvedSessionRoot
    SessionMarkerInputFile = $resolvedMarkerInputFile
    ProofPolling = $true
    Json = $true
}

if ($PSBoundParameters.ContainsKey('ProcessId') -and $ProcessId -gt 0) {
    $recordArguments['ProcessId'] = $ProcessId
}
if ($RefreshDiscoveryChain) {
    $recordArguments['RefreshDiscoveryChain'] = $true
}
if ($RefreshProjectorTrace) {
    $recordArguments['RefreshProjectorTrace'] = $true
}
if ($RefreshReaderBridge) {
    $recordArguments['RefreshReaderBridge'] = $true
}
if ($NoAhkFallback) {
    $recordArguments['NoAhkFallback'] = $true
}

$recordJson = & $recordScript @recordArguments
$recordDocument = $recordJson | ConvertFrom-Json -Depth 40
$recordFailed = (
    ($recordDocument.PSObject.Properties['Status'] -and [string]$recordDocument.Status -ne 'complete') -or
    ($recordDocument.PSObject.Properties['IntegrityStatus'] -and [string]$recordDocument.IntegrityStatus -eq 'failed')
)

if (-not $Json) {
    Start-Countdown -Color Magenta -Heading '🛑 RECORDING STOPPING' -Detail 'Target sample count reached. Final stop/reporting will complete automatically.' -Seconds 5
}

& $appendMarkerScript -File $resolvedMarkerInputFile -Kind 'phase' -Label 'recording-complete' -Message 'Sample target reached; recording finished.' -Source 'continuous-polling-session' -Json *> $null

if (-not $Json) {
    if ($recordFailed) {
        Write-BigPrompt -Color Red -Lines @(
            '🔴 RECORDING FAILED',
            '⚠️ Sample target countdown flow ran, but the recorder returned a failed package status.',
            ("📁 Session directory: {0}" -f [string]$recordDocument.SessionDirectory),
            ("🧾 Failure: {0}" -f [string]$recordDocument.FailureMessage)
        )
    }
    else {
        Write-BigPrompt -Color Green -Lines @(
            '🟢 RECORDING COMPLETE',
            '✅ Target sample count reached.',
            ("📁 Session directory: {0}" -f [string]$recordDocument.SessionDirectory),
            ("🧾 Manifest: {0}" -f [string]$recordDocument.RecordingManifestFile),
            ("📊 Samples: {0}" -f [string]$recordDocument.SamplesFile),
            '📣 Ready for review, summary, or analysis.'
        )
    }
}

$recordJson | Write-Output


