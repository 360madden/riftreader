[CmdletBinding()]
param(
    [string]$SnapshotPath = (Join-Path $env:LOCALAPPDATA 'ChromaLink\DesktopDotNet\out\chromalink-live-telemetry.json'),

    [string]$BundleDirectory,

    [string]$OutputFile,

    [string]$PreflightFile,

    [string]$ExportResultFile,

    [string]$SummaryFile,

    [int]$PreflightDurationSeconds = 0,

    [int]$PreflightIntervalMilliseconds = 250,

    [int]$ExportDurationSeconds = 0,

    [int]$ExportIntervalMilliseconds = 250,

    [int]$MaxSamples = 0,

    [int]$MaxFreshAgeMilliseconds = 2000,

    [switch]$IncludeDuplicates,

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$schemaVersion = 1

$freshnessScript = Join-Path $PSScriptRoot 'test-chromalink-live-telemetry.ps1'
$exportScript = Join-Path $PSScriptRoot 'export-chromalink-live-coords.ps1'

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

if ([string]::IsNullOrWhiteSpace($BundleDirectory)) {
    $BundleDirectory = Join-Path (Join-Path $PSScriptRoot 'captures') ('chromalink-live-coords-{0}' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
}

$resolvedBundleDirectory = [System.IO.Path]::GetFullPath($BundleDirectory)
New-Item -ItemType Directory -Path $resolvedBundleDirectory -Force | Out-Null

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = Join-Path $resolvedBundleDirectory 'live-coords.ndjson'
}

if ([string]::IsNullOrWhiteSpace($PreflightFile)) {
    $PreflightFile = Join-Path $resolvedBundleDirectory 'chromalink-freshness-preflight.json'
}

if ([string]::IsNullOrWhiteSpace($ExportResultFile)) {
    $ExportResultFile = Join-Path $resolvedBundleDirectory 'chromalink-live-coords-export-result.json'
}

if ([string]::IsNullOrWhiteSpace($SummaryFile)) {
    $SummaryFile = Join-Path $resolvedBundleDirectory 'chromalink-live-coords-capture-summary.json'
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

function New-Summary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Status,

        [Parameter(Mandatory = $true)]
        [bool]$Fresh,

        [Parameter(Mandatory = $true)]
        [bool]$Exported,

        [object]$PreflightDocument,

        [object]$ExportDocument,

        [bool]$RemovedOutputFile = $false,

        [string[]]$Failures = @()
    )

    return [ordered]@{
        schemaVersion = $schemaVersion
        mode = 'chromalink-live-coords-capture'
        generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        status = $Status
        fresh = $Fresh
        exported = $Exported
        snapshotPath = [System.IO.Path]::GetFullPath($SnapshotPath)
        bundleDirectory = $resolvedBundleDirectory
        outputFile = [System.IO.Path]::GetFullPath($OutputFile)
        removedOutputFile = $RemovedOutputFile
        preflightFile = [System.IO.Path]::GetFullPath($PreflightFile)
        exportResultFile = [System.IO.Path]::GetFullPath($ExportResultFile)
        summaryFile = [System.IO.Path]::GetFullPath($SummaryFile)
        maxFreshAgeMs = $MaxFreshAgeMilliseconds
        preflightDurationSeconds = $PreflightDurationSeconds
        exportDurationSeconds = $ExportDurationSeconds
        preflight = $PreflightDocument
        export = $ExportDocument
        failures = @($Failures)
    }
}

$preflightArguments = @(
    '-NoLogo',
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $freshnessScript,
    '-SnapshotPath',
    $SnapshotPath,
    '-MaxFreshAgeMilliseconds',
    $MaxFreshAgeMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-IntervalMilliseconds',
    $PreflightIntervalMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-Json'
)

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

    $summary = New-Summary -Status 'preflight-failed' -Fresh $false -Exported $false -PreflightDocument $preflightDocument -ExportDocument $null -Failures $failures.ToArray()
    Write-Utf8TextAtomic -Path $SummaryFile -Content ($summary | ConvertTo-Json -Depth 64)

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

$exportArguments = @(
    '-NoLogo',
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $exportScript,
    '-SnapshotPath',
    $SnapshotPath,
    '-OutputFile',
    $OutputFile,
    '-IntervalMilliseconds',
    $ExportIntervalMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-MaxFreshAgeMilliseconds',
    $MaxFreshAgeMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-Json'
)

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

$summary = New-Summary -Status $summaryStatus -Fresh $true -Exported $exported -PreflightDocument $preflightDocument -ExportDocument $exportDocument -RemovedOutputFile $removedOutputFile -Failures $summaryFailures.ToArray()
Write-Utf8TextAtomic -Path $SummaryFile -Content ($summary | ConvertTo-Json -Depth 64)

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
