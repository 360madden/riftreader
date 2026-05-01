[CmdletBinding()]
param(
    [string]$SnapshotPath = (Join-Path $env:LOCALAPPDATA 'ChromaLink\DesktopDotNet\out\chromalink-live-telemetry.json'),

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
        Path = $resolvedPath
        LastWriteTimeUtc = [DateTimeOffset]::new($file.LastWriteTimeUtc).ToUniversalTime()
        Document = $document
    }
}

function New-LiveCoordSample {
    param(
        [Parameter(Mandatory = $true)]
        $Snapshot
    )

    $document = $Snapshot.Document
    $position = Get-NestedValue -InputObject $document -Path 'aggregate.playerPosition'
    if ($null -eq $position) {
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
    $snapshotGeneratedAtUtc = ConvertTo-DateTimeOffsetOrNull (Get-PropertyValue -InputObject $document -Name 'generatedAtUtc')
    $ageMs = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $position -Name 'ageMs')
    if ($null -eq $ageMs -and $null -ne $observedAtUtc) {
        $ageMs = [Math]::Round(($nowUtc - $observedAtUtc).TotalMilliseconds, 3)
    }

    $sourceFrameFresh = Get-PropertyValue -InputObject $position -Name 'fresh'
    $sourceFrameStale = Get-PropertyValue -InputObject $position -Name 'stale'
    $frameWithinFreshWindow = if ($null -ne $ageMs) { $ageMs -le $MaxFreshAgeMilliseconds } else { $null }
    $snapshotAgeBasisUtc = if ($null -ne $snapshotGeneratedAtUtc) { $snapshotGeneratedAtUtc } else { $Snapshot.LastWriteTimeUtc }
    $snapshotAgeMs = [Math]::Round(($nowUtc - $snapshotAgeBasisUtc).TotalMilliseconds, 3)
    $snapshotWithinFreshWindow = $snapshotAgeMs -le $MaxFreshAgeMilliseconds
    $fresh = $snapshotWithinFreshWindow -and ($frameWithinFreshWindow -ne $false) -and ($sourceFrameFresh -ne $false)
    $stale = -not $fresh

    return [ordered]@{
        schemaVersion = $schemaVersion
        mode = 'live-coord-sample'
        source = 'chromalink-live-telemetry'
        sourceContractName = [string](Get-NestedValue -InputObject $document -Path 'contract.name')
        sourceContractSchemaVersion = ConvertTo-IntOrNull (Get-NestedValue -InputObject $document -Path 'contract.schemaVersion')
        sourceSnapshotPath = $Snapshot.Path
        sourceSnapshotLastWriteUtc = $Snapshot.LastWriteTimeUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
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
        aggregateReady = Get-NestedValue -InputObject $document -Path 'aggregate.ready'
        aggregateHealthy = Get-NestedValue -InputObject $document -Path 'aggregate.healthy'
        aggregateStale = Get-NestedValue -InputObject $document -Path 'aggregate.stale'
        aggregateAcceptedFrames = ConvertTo-IntOrNull (Get-NestedValue -InputObject $document -Path 'aggregate.acceptedFrames')
        frameType = [string](Get-PropertyValue -InputObject $position -Name 'frameType')
        schemaId = ConvertTo-IntOrNull (Get-PropertyValue -InputObject $position -Name 'schemaId')
        sequence = ConvertTo-IntOrNull (Get-PropertyValue -InputObject $position -Name 'sequence')
        reservedFlags = ConvertTo-IntOrNull (Get-PropertyValue -InputObject $position -Name 'reservedFlags')
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
        $snapshot = Read-ChromaLinkSnapshot -Path $SnapshotPath
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
    snapshotPath = [System.IO.Path]::GetFullPath($SnapshotPath)
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
    Write-Host ("Output:   {0}" -f $resolvedOutputFile)
    Write-Host ("Samples:  {0}" -f $samplesWritten)
    if (-not [string]::IsNullOrWhiteSpace($lastError)) {
        Write-Host ("Last error: {0}" -f $lastError) -ForegroundColor Red
    }
}

if ($status -eq 'fail' -or ($status -eq 'stale' -and -not $AllowStale)) {
    exit 1
}
