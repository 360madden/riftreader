[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [int]$PollIntervalMilliseconds = 100,
    [string]$OutputFile,
    [string]$EventLogFile,
    [string]$DiagnosticsLogFile,
    [string]$ProofCoordAnchorFile,
    [switch]$Diagnostics,
    [switch]$Preflight,
    [switch]$SkipProofCoordPrime,
    [switch]$ReadLatest,
    [switch]$TailLatest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function ConvertFrom-JsonCompat {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Json,
        [int]$Depth = 80
    )

    $convertFromJsonCommand = Get-Command -Name ConvertFrom-Json -CommandType Cmdlet
    if ($convertFromJsonCommand.Parameters.ContainsKey('Depth')) {
        return $Json | Microsoft.PowerShell.Utility\ConvertFrom-Json -Depth $Depth
    }

    return $Json | Microsoft.PowerShell.Utility\ConvertFrom-Json
}

function Get-TelemetryTargetProcess {
    param(
        [string]$ResolvedProcessName,
        [int]$ResolvedProcessId
    )

    if ($ResolvedProcessId -gt 0) {
        return Get-Process -Id $ResolvedProcessId -ErrorAction Stop
    }

    return Get-Process -Name $ResolvedProcessName -ErrorAction Stop |
        Sort-Object StartTime -Descending |
        Select-Object -First 1
}

function Get-CheatEngineDebuggerModuleName {
    param(
        [string]$ResolvedProcessName,
        [int]$ResolvedProcessId
    )

    try {
        $targetProcess = Get-TelemetryTargetProcess -ResolvedProcessName $ResolvedProcessName -ResolvedProcessId $ResolvedProcessId
        foreach ($module in $targetProcess.Modules) {
            if ($module.ModuleName -in @('vehdebug-x86_64.dll', 'vehdebug-i386.dll')) {
                return [string]$module.ModuleName
            }
        }
    }
    catch {
        Write-Verbose ("Unable to inspect telemetry target modules before proof prime: {0}" -f $_.Exception.Message)
    }

    return $null
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$defaultOutputFile = Join-Path $repoRoot 'scripts\captures\readerbridge-telemetry.latest.json'
$defaultEventLogFile = Join-Path $repoRoot 'scripts\captures\readerbridge-telemetry.events.ndjson'
$defaultDiagnosticsLogFile = Join-Path $repoRoot 'scripts\captures\readerbridge-telemetry.discovery.ndjson'
$defaultProofCoordAnchorFile = Join-Path $repoRoot 'scripts\captures\telemetry-proof-coord-anchor.json'

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = $defaultOutputFile
}

if ([string]::IsNullOrWhiteSpace($EventLogFile)) {
    $EventLogFile = $defaultEventLogFile
}

if ([string]::IsNullOrWhiteSpace($DiagnosticsLogFile)) {
    $DiagnosticsLogFile = $defaultDiagnosticsLogFile
}

if ([string]::IsNullOrWhiteSpace($ProofCoordAnchorFile)) {
    $ProofCoordAnchorFile = $defaultProofCoordAnchorFile
}

if (($ReadLatest -and $TailLatest) -or (($ReadLatest -or $TailLatest) -and $Preflight)) {
    throw 'Use only one of -ReadLatest, -TailLatest, or -Preflight.'
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

if (-not $SkipProofCoordPrime) {
    $proofCoordAnchorScript = Join-Path $repoRoot 'scripts\resolve-proof-coord-anchor.ps1'
    if (Test-Path -LiteralPath $proofCoordAnchorScript) {
        try {
            $attachedDebuggerModule = Get-CheatEngineDebuggerModuleName -ResolvedProcessName $ProcessName -ResolvedProcessId $ProcessId
            $primeArguments = @(
                '-NoProfile',
                '-ExecutionPolicy', 'Bypass',
                '-File', $proofCoordAnchorScript
            )

            if ($ProcessId -gt 0) {
                $primeArguments += @('-ProcessId', $ProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
            }
            else {
                $primeArguments += @('-ProcessName', $ProcessName)
            }

            if (-not [string]::IsNullOrWhiteSpace($attachedDebuggerModule)) {
                Write-Warning ("Manual Cheat Engine debugger session detected on the target process ({0}); telemetry startup will use validation-only proof priming and will refuse full proof refresh until that debugger session is stopped." -f $attachedDebuggerModule)
                $primeArguments += '-SkipRefresh'
            }

            $primeArguments += '-Json'
            $primeOutput = & pwsh @primeArguments 2>&1
            if ($LASTEXITCODE -eq 0) {
                $primeJson = $primeOutput -join [Environment]::NewLine
                $primeDocument = ConvertFrom-JsonCompat -Json $primeJson -Depth 80
                $matchIsValid = $false
                if ($null -ne $primeDocument -and $primeDocument.PSObject.Properties['Match'] -and $null -ne $primeDocument.Match) {
                    $matchIsValid = [bool]$primeDocument.Match.CoordMatchesWithinTolerance
                }

                if ($matchIsValid) {
                    $anchorDirectory = Split-Path -Parent $ProofCoordAnchorFile
                    if (-not [string]::IsNullOrWhiteSpace($anchorDirectory)) {
                        New-Item -ItemType Directory -Path $anchorDirectory -Force | Out-Null
                    }

                    Set-Content -LiteralPath $ProofCoordAnchorFile -Value $primeJson -Encoding UTF8
                }
                else {
                    Write-Warning 'Proof coord anchor prime did not return a validated coord source; continuing without a primed cache.'
                }
            }
            else {
                Write-Warning ("Proof coord anchor prime failed; continuing without a primed cache. {0}" -f ($primeOutput -join [Environment]::NewLine))
            }
        }
        catch {
            Write-Warning ("Proof coord anchor prime failed; continuing without a primed cache. {0}" -f $_.Exception.Message)
        }
    }
}

$arguments = @()

if ($Preflight) {
    $arguments += '--telemetry-preflight'
}
else {
    $arguments += '--run-telemetry-host'
}

if ($ProcessId -gt 0) {
    $arguments += @('--pid', $ProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
}
else {
    $arguments += @('--process-name', $ProcessName)
}

$arguments += @('--telemetry-poll-interval-ms', $PollIntervalMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture))
$arguments += @('--telemetry-output-file', $OutputFile)
$arguments += @('--telemetry-event-log-file', $EventLogFile)
$arguments += @('--telemetry-proof-anchor-file', $ProofCoordAnchorFile)

if ($Diagnostics) {
    $arguments += '--telemetry-diagnostics'
    $arguments += @('--telemetry-diagnostics-log-file', $DiagnosticsLogFile)
}

& dotnet run --project $readerProject -- @arguments
exit $LASTEXITCODE
