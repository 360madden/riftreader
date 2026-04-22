[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [int]$PollIntervalMilliseconds = 100,
    [string]$OutputFile,
    [string]$EventLogFile,
    [string]$DiagnosticsLogFile,
    [switch]$Diagnostics,
    [switch]$ReadLatest,
    [switch]$TailLatest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$defaultOutputFile = Join-Path $repoRoot 'scripts\captures\readerbridge-telemetry.latest.json'
$defaultEventLogFile = Join-Path $repoRoot 'scripts\captures\readerbridge-telemetry.events.ndjson'
$defaultDiagnosticsLogFile = Join-Path $repoRoot 'scripts\captures\readerbridge-telemetry.discovery.ndjson'

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = $defaultOutputFile
}

if ([string]::IsNullOrWhiteSpace($EventLogFile)) {
    $EventLogFile = $defaultEventLogFile
}

if ([string]::IsNullOrWhiteSpace($DiagnosticsLogFile)) {
    $DiagnosticsLogFile = $defaultDiagnosticsLogFile
}

if ($ReadLatest -and $TailLatest) {
    throw 'Use either -ReadLatest or -TailLatest, not both.'
}

if ($ReadLatest) {
    if (-not (Test-Path -LiteralPath $OutputFile)) {
        throw "Telemetry snapshot file not found: $OutputFile"
    }

    Get-Content -LiteralPath $OutputFile -Raw
    return
}

if ($TailLatest) {
    $lastWrite = [DateTime]::MinValue
    while ($true) {
        if (Test-Path -LiteralPath $OutputFile) {
            $item = Get-Item -LiteralPath $OutputFile
            if ($item.LastWriteTimeUtc -gt $lastWrite) {
                $lastWrite = $item.LastWriteTimeUtc
                Clear-Host
                Get-Content -LiteralPath $OutputFile -Raw
            }
        }

        Start-Sleep -Milliseconds 500
    }
}

$arguments = @('--run-telemetry-host')

if ($ProcessId -gt 0) {
    $arguments += @('--pid', $ProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
}
else {
    $arguments += @('--process-name', $ProcessName)
}

$arguments += @('--telemetry-poll-interval-ms', $PollIntervalMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture))
$arguments += @('--telemetry-output-file', $OutputFile)
$arguments += @('--telemetry-event-log-file', $EventLogFile)

if ($Diagnostics) {
    $arguments += '--telemetry-diagnostics'
    $arguments += @('--telemetry-diagnostics-log-file', $DiagnosticsLogFile)
}

& dotnet run --project $readerProject -- @arguments
exit $LASTEXITCODE
