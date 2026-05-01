[CmdletBinding()]
param(
    [string]$SnapshotPath = (Join-Path $env:LOCALAPPDATA 'ChromaLink\DesktopDotNet\out\chromalink-live-telemetry.json'),

    [string]$WorldStateUrl = '',

    [string]$WorldStatePath = '',

    [string]$OutputFile = (Join-Path (Join-Path $PSScriptRoot 'captures') ('chromalink-live-coords-{0}\live-coords.ndjson' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))),

    [switch]$Watch,

    [int]$IntervalMilliseconds = 250,

    [int]$DurationSeconds = 0,

    [int]$MaxSamples = 0,

    [int]$MaxFreshAgeMilliseconds = 2000,

    [switch]$Append,

    [switch]$AllowStale,

    [switch]$IncludeDuplicates,

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$schemaVersion = 1

if ($IntervalMilliseconds -lt 50) {
    throw 'IntervalMilliseconds must be at least 50.'
}

if ($DurationSeconds -lt 0) {
    throw 'DurationSeconds must be zero or greater.'
}

if ($MaxSamples -lt 0) {
    throw 'MaxSamples must be zero or greater.'
}

if ($MaxFreshAgeMilliseconds -lt 0) {
    throw 'MaxFreshAgeMilliseconds must be zero or greater.'
}

$useWorldStateUrl = -not [string]::IsNullOrWhiteSpace($WorldStateUrl)
$useWorldStatePath = -not [string]::IsNullOrWhiteSpace($WorldStatePath)
if ($useWorldStateUrl -and $useWorldStatePath) {
    throw 'Specify only one of WorldStateUrl or WorldStatePath.'
}

function ConvertTo-DateTimeOffsetOrNull {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    if ($Value -is [DateTimeOffset]) {
        return $Value.ToUniversalTime()
    }

    if ($Value -is [DateTime]) {
        return ([DateTimeOffset]$Value).ToUniversalTime()
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    try {
        return ([DateTimeOffset]::Parse(
                $text,
                [System.Globalization.CultureInfo]::InvariantCulture,
                [System.Globalization.DateTimeStyles]::RoundtripKind)).ToUniversalTime()
    }
    catch {
        return $null
    }
}

function Format-UtcOrNull {
    param([object]$Value)

    $date = ConvertTo-DateTimeOffsetOrNull -Value $Value
    if ($null -eq $date) {
        return $null
    }

    return $date.ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
}

function Get-PropertyValue {
    param(
        [object]$InputObject,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $InputObject) {
        return $null
    }

    if ($InputObject -is [System.Collections.IDictionary]) {
        if ($InputObject.Contains($Name)) {
            return $InputObject[$Name]
        }

        return $null
    }

    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Get-NestedValue {
    param(
        [object]$InputObject,
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $current = $InputObject
    foreach ($segment in $Path.Split('.')) {
        $current = Get-PropertyValue -InputObject $current -Name $segment
        if ($null -eq $current) {
            return $null
        }
    }

    return $current
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

    return [double]::Parse($text, [System.Globalization.CultureInfo]::InvariantCulture)
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

    return [int]::Parse($text, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Read-ChromaLinkSnapshot {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $resolvedPath)) {
        throw "ChromaLink telemetry snapshot not found: $resolvedPath"
    }

    $file = Get-Item -LiteralPath $resolvedPath
    $document = Get-Content -LiteralPath $resolvedPath -Raw | ConvertFrom-Json -Depth 64
    return [pscustomobject]@{
        InputMode = 'snapshot-file'
        Path = $resolvedPath
        LastWriteTimeUtc = [DateTimeOffset]::new($file.LastWriteTimeUtc).ToUniversalTime()
        Document = $document
    }
}

function Read-ChromaLinkWorldState {
    param(
        [string]$Url,
        [string]$Path
    )

    if (-not [string]::IsNullOrWhiteSpace($Path)) {
        $resolvedPath = [System.IO.Path]::GetFullPath($Path)
        if (-not (Test-Path -LiteralPath $resolvedPath)) {
            throw "ChromaLink RiftReader world-state file not found: $resolvedPath"
        }

        $file = Get-Item -LiteralPath $resolvedPath
        $document = Get-Content -LiteralPath $resolvedPath -Raw | ConvertFrom-Json -Depth 64
        return [pscustomobject]@{
            InputMode = 'world-state-file'
            Path = $resolvedPath
            WorldStateUrl = $null
            LastWriteTimeUtc = [DateTimeOffset]::new($file.LastWriteTimeUtc).ToUniversalTime()
            Document = $document
        }
    }

    $response = Invoke-WebRequest -Method Get -Uri $Url -UseBasicParsing -SkipHttpErrorCheck -TimeoutSec 5
    if ([int]$response.StatusCode -lt 200 -or [int]$response.StatusCode -gt 299) {
        throw "ChromaLink RiftReader world-state endpoint returned a non-success HTTP status: $Url status=$([int]$response.StatusCode)"
    }

    if ([string]::IsNullOrWhiteSpace($response.Content)) {
        throw "ChromaLink RiftReader world-state endpoint returned an empty response: $Url"
    }

    return [pscustomobject]@{
        InputMode = 'world-state-url'
        Path = $null
        WorldStateUrl = [string]$Url
        LastWriteTimeUtc = $null
        StatusCode = [int]$response.StatusCode
        Document = $response.Content | ConvertFrom-Json -Depth 64
    }
}

function New-LiveCoordSample {
    param(
        [Parameter(Mandatory = $true)]
        $Snapshot
    )

    $document = $Snapshot.Document
    $inputMode = [string]$Snapshot.InputMode
    $isWorldState = $inputMode -like 'world-state-*'
    $position = if ($isWorldState) {
        Get-NestedValue -InputObject $document -Path 'player.position'
    }
    else {
        Get-NestedValue -InputObject $document -Path 'aggregate.playerPosition'
    }
    if ($null -eq $position) {
        if ($isWorldState) {
            throw 'ChromaLink RiftReader world-state does not contain player.position.'
        }

        throw 'ChromaLink snapshot does not contain aggregate.playerPosition.'
    }

    $x = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $position -Name 'x')
    $y = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $position -Name 'y')
    $z = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $position -Name 'z')
    if ($null -eq $x -or $null -eq $y -or $null -eq $z) {
        throw 'ChromaLink aggregate.playerPosition is missing x/y/z.'
    }

    $nowUtc = [DateTimeOffset]::UtcNow
    $observedAtUtc = ConvertTo-DateTimeOffsetOrNull (Get-PropertyValue -InputObject $position -Name 'observedAtUtc')
    $snapshotGeneratedAtUtc = if ($isWorldState) { $null } else { ConvertTo-DateTimeOffsetOrNull (Get-PropertyValue -InputObject $document -Name 'generatedAtUtc') }
    $ageMs = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $position -Name 'ageMs')
    if ($null -eq $ageMs -and $null -ne $observedAtUtc) {
        $ageMs = [Math]::Round(($nowUtc - $observedAtUtc).TotalMilliseconds, 3)
    }

    $sourceFrameFresh = Get-PropertyValue -InputObject $position -Name 'fresh'
    $sourceFrameStale = Get-PropertyValue -InputObject $position -Name 'stale'
    $frameWithinFreshWindow = if ($null -ne $ageMs) { $ageMs -le $MaxFreshAgeMilliseconds } else { $null }
    $worldStateSnapshotAgeSeconds = if ($isWorldState) { ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $document -Name 'snapshotAgeSeconds') } else { $null }
    $snapshotAgeMs = if ($null -ne $worldStateSnapshotAgeSeconds) {
        [Math]::Round($worldStateSnapshotAgeSeconds * 1000.0, 3)
    }
    else {
        $snapshotAgeBasisUtc = if ($null -ne $snapshotGeneratedAtUtc) {
            $snapshotGeneratedAtUtc
        }
        elseif ($null -ne $Snapshot.LastWriteTimeUtc) {
            $Snapshot.LastWriteTimeUtc
        }
        else {
            $null
        }

        if ($null -ne $snapshotAgeBasisUtc) {
            [Math]::Round(($nowUtc - $snapshotAgeBasisUtc).TotalMilliseconds, 3)
        }
        else {
            $null
        }
    }
    $snapshotWithinFreshWindow = if ($null -ne $snapshotAgeMs) { $snapshotAgeMs -le $MaxFreshAgeMilliseconds } else { $false }
    $worldStateOk = if ($isWorldState) { Get-PropertyValue -InputObject $document -Name 'ok' } else { $true }
    $worldStateReady = if ($isWorldState) { Get-PropertyValue -InputObject $document -Name 'ready' } else { $true }
    $worldStateFresh = if ($isWorldState) { Get-PropertyValue -InputObject $document -Name 'fresh' } else { $true }
    $worldStateStale = if ($isWorldState) { Get-PropertyValue -InputObject $document -Name 'stale' } else { $false }
    $playerPositionAvailable = if ($isWorldState) { Get-NestedValue -InputObject $document -Path 'navigation.playerPositionAvailable' } else { $true }
    $fresh = $snapshotWithinFreshWindow -and
        ($frameWithinFreshWindow -ne $false) -and
        ($sourceFrameFresh -ne $false) -and
        ($worldStateOk -eq $true) -and
        ($worldStateReady -eq $true) -and
        ($worldStateFresh -eq $true) -and
        ($worldStateStale -ne $true) -and
        ($playerPositionAvailable -eq $true)
    $stale = -not $fresh

    if ($isWorldState) {
        $sourceContractNameValue = Get-NestedValue -InputObject $document -Path 'sourceContract.name'
        $sourceContractSchemaVersionValue = Get-NestedValue -InputObject $document -Path 'sourceContract.schemaVersion'
        $sourceViewContractNameValue = Get-NestedValue -InputObject $document -Path 'contract.name'
        $sourceViewContractSchemaVersionValue = Get-NestedValue -InputObject $document -Path 'contract.schemaVersion'
    }
    else {
        $sourceContractNameValue = Get-NestedValue -InputObject $document -Path 'contract.name'
        $sourceContractSchemaVersionValue = Get-NestedValue -InputObject $document -Path 'contract.schemaVersion'
        $sourceViewContractNameValue = $null
        $sourceViewContractSchemaVersionValue = $null
    }

    return [ordered]@{
        schemaVersion = $schemaVersion
        mode = 'live-coord-sample'
        source = 'chromalink-live-telemetry'
        sourceView = $(if ($isWorldState) { 'chromalink-riftreader-world-state' } else { 'chromalink-rolling-snapshot' })
        inputMode = $inputMode
        sourceContractName = [string]$sourceContractNameValue
        sourceContractSchemaVersion = ConvertTo-IntOrNull $sourceContractSchemaVersionValue
        sourceViewContractName = [string]$sourceViewContractNameValue
        sourceViewContractSchemaVersion = ConvertTo-IntOrNull $sourceViewContractSchemaVersionValue
        sourceSnapshotPath = $(if ($isWorldState) { [string](Get-PropertyValue -InputObject $document -Name 'snapshotPath') } else { $Snapshot.Path })
        sourceSnapshotLastWriteUtc = $(if ($null -ne $Snapshot.LastWriteTimeUtc) { $Snapshot.LastWriteTimeUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture) } else { $null })
        sourceWorldStateUrl = $(if ($isWorldState) { $Snapshot.WorldStateUrl } else { $null })
        sourceWorldStatePath = $(if ($isWorldState) { $Snapshot.Path } else { $null })
        exportedAtUtc = $nowUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        snapshotGeneratedAtUtc = $(if ($null -ne $snapshotGeneratedAtUtc) { $snapshotGeneratedAtUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture) } else { $null })
        snapshotAgeMs = $snapshotAgeMs
        snapshotWithinFreshWindow = $snapshotWithinFreshWindow
        observedAtUtc = $(if ($null -ne $observedAtUtc) { $observedAtUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture) } else { $null })
        ageMs = $ageMs
        maxFreshAgeMs = $MaxFreshAgeMilliseconds
        sourceFrameFresh = $sourceFrameFresh
        sourceFrameStale = $sourceFrameStale
        frameWithinFreshWindow = $frameWithinFreshWindow
        fresh = $fresh
        stale = $stale
        withinFreshWindow = $fresh
        aggregateReady = $(if ($isWorldState) { $worldStateReady } else { Get-NestedValue -InputObject $document -Path 'aggregate.ready' })
        aggregateHealthy = $(if ($isWorldState) { Get-PropertyValue -InputObject $document -Name 'healthy' } else { Get-NestedValue -InputObject $document -Path 'aggregate.healthy' })
        aggregateStale = $(if ($isWorldState) { $worldStateStale } else { Get-NestedValue -InputObject $document -Path 'aggregate.stale' })
        aggregateAcceptedFrames = $(if ($isWorldState) { $null } else { ConvertTo-IntOrNull (Get-NestedValue -InputObject $document -Path 'aggregate.acceptedFrames') })
        frameType = $(if ($isWorldState) { $null } else { [string](Get-PropertyValue -InputObject $position -Name 'frameType') })
        schemaId = $(if ($isWorldState) { $null } else { ConvertTo-IntOrNull (Get-PropertyValue -InputObject $position -Name 'schemaId') })
        sequence = $(if ($isWorldState) { $null } else { ConvertTo-IntOrNull (Get-PropertyValue -InputObject $position -Name 'sequence') })
        reservedFlags = $(if ($isWorldState) { $null } else { ConvertTo-IntOrNull (Get-PropertyValue -InputObject $position -Name 'reservedFlags') })
        x = $x
        y = $y
        z = $z
    }
}

function Get-SampleKey {
    param([Parameter(Mandatory = $true)]$Sample)

    return '{0}|{1}|{2}|{3}|{4}' -f $Sample.sequence, $Sample.observedAtUtc, $Sample.x, $Sample.y, $Sample.z
}

function Add-NdjsonSample {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        $Sample
    )

    $directory = Split-Path -Path $Path -Parent
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $line = ($Sample | ConvertTo-Json -Depth 16 -Compress)
    [System.IO.File]::AppendAllText($Path, $line + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
}

$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
if (-not $Append -and (Test-Path -LiteralPath $resolvedOutputFile)) {
    Remove-Item -LiteralPath $resolvedOutputFile -Force
}

$seenKeys = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
$startedAtUtc = [DateTimeOffset]::UtcNow
$samplesWritten = 0
$freshSamplesWritten = 0
$duplicateSamplesSkipped = 0
$lastSample = $null
$lastError = $null

do {
    try {
        $snapshot = if ($useWorldStateUrl -or $useWorldStatePath) {
            Read-ChromaLinkWorldState -Url $WorldStateUrl -Path $WorldStatePath
        }
        else {
            Read-ChromaLinkSnapshot -Path $SnapshotPath
        }
        $sample = New-LiveCoordSample -Snapshot $snapshot
        $key = Get-SampleKey -Sample $sample
        if ($IncludeDuplicates -or $seenKeys.Add($key)) {
            Add-NdjsonSample -Path $resolvedOutputFile -Sample $sample
            $samplesWritten++
            if ($sample.fresh -eq $true) {
                $freshSamplesWritten++
            }
            $lastSample = $sample
        }
        else {
            $duplicateSamplesSkipped++
        }
    }
    catch {
        $lastError = $_.Exception.Message
        if (-not $Watch) {
            throw
        }
    }

    if (-not $Watch) {
        break
    }

    if ($MaxSamples -gt 0 -and $samplesWritten -ge $MaxSamples) {
        break
    }

    if ($DurationSeconds -gt 0 -and ([DateTimeOffset]::UtcNow - $startedAtUtc).TotalSeconds -ge $DurationSeconds) {
        break
    }

    Start-Sleep -Milliseconds $IntervalMilliseconds
} while ($true)

$status = if ($samplesWritten -le 0) { 'fail' } elseif ($freshSamplesWritten -le 0) { 'stale' } else { 'pass' }
$result = [ordered]@{
    schemaVersion = $schemaVersion
    mode = 'chromalink-live-coords-export'
    status = $status
    inputMode = $(if ($useWorldStateUrl) { 'world-state-url' } elseif ($useWorldStatePath) { 'world-state-file' } else { 'snapshot-file' })
    snapshotPath = $(if ($useWorldStateUrl -or $useWorldStatePath) { if ($lastSample) { $lastSample.sourceSnapshotPath } else { $null } } else { [System.IO.Path]::GetFullPath($SnapshotPath) })
    worldStateUrl = $(if ($useWorldStateUrl) { $WorldStateUrl } else { $null })
    worldStatePath = $(if ($useWorldStatePath) { [System.IO.Path]::GetFullPath($WorldStatePath) } else { $null })
    outputFile = $resolvedOutputFile
    watch = [bool]$Watch
    samplesWritten = $samplesWritten
    freshSamplesWritten = $freshSamplesWritten
    duplicateSamplesSkipped = $duplicateSamplesSkipped
    allowStale = [bool]$AllowStale
    lastError = $lastError
    lastSample = $lastSample
}

if ($Json) {
    $result | ConvertTo-Json -Depth 16
}
else {
    $color = if ($status -eq 'pass') { 'Green' } else { 'Red' }
    Write-Host ("ChromaLink live coords export: {0}" -f $status) -ForegroundColor $color
    Write-Host ("Snapshot: {0}" -f ([System.IO.Path]::GetFullPath($SnapshotPath)))
    if ($useWorldStateUrl) {
        Write-Host ("WorldStateUrl: {0}" -f $WorldStateUrl)
    }
    if ($useWorldStatePath) {
        Write-Host ("WorldStatePath: {0}" -f ([System.IO.Path]::GetFullPath($WorldStatePath)))
    }
    Write-Host ("Output:   {0}" -f $resolvedOutputFile)
    Write-Host ("Samples:  {0}" -f $samplesWritten)
    if (-not [string]::IsNullOrWhiteSpace($lastError)) {
        Write-Host ("Last error: {0}" -f $lastError) -ForegroundColor Red
    }
}

if ($status -eq 'fail' -or ($status -eq 'stale' -and -not $AllowStale)) {
    exit 1
}
