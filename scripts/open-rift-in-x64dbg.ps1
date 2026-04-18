[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [string]$StateFilePath = 'C:\RIFT MODDING\RiftReader\scripts\captures\rift-restart-state.json',
    [switch]$PreferSavedState,
    [switch]$RequireRunningProcess,
    [switch]$PreviewOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$x64dbgPath = 'C:\RIFT MODDING\RiftReader\tools\reverse-engineering\x64dbg\release\x64\x64dbg.exe'
if (-not (Test-Path -LiteralPath $x64dbgPath)) {
    throw "x64dbg was not found at '$x64dbgPath'. Run C:\RIFT MODDING\RiftReader\tools\reverse-engineering\install-tools.ps1 first."
}

function Split-ExecutableFromCommandLine {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandLine
    )

    if ($CommandLine -match '^\s*"(?<exe>[^"]+)"\s*(?<args>.*)$') {
        return [pscustomobject]@{
            ExecutablePath = $matches.exe
            ArgumentString = $matches.args
        }
    }

    if ($CommandLine -match '^\s*(?<exe>\S+)\s*(?<args>.*)$') {
        return [pscustomobject]@{
            ExecutablePath = $matches.exe
            ArgumentString = $matches.args
        }
    }

    throw "Unable to parse command line '$CommandLine'."
}

function Get-RiftLaunchStateFromRunningProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetProcessName
    )

    $process = Get-Process -Name $TargetProcessName -ErrorAction SilentlyContinue |
        Sort-Object StartTime -Descending |
        Select-Object -First 1

    if (-not $process) {
        return $null
    }

    $wmiProcess = Get-CimInstance Win32_Process -Filter ("ProcessId = {0}" -f $process.Id) |
        Select-Object -First 1

    if (-not $wmiProcess) {
        throw "Unable to query Win32_Process details for '$TargetProcessName' [$($process.Id)]."
    }

    $split = Split-ExecutableFromCommandLine -CommandLine $wmiProcess.CommandLine
    $currentDirectory = Split-Path -Parent $split.ExecutablePath

    return [pscustomobject]@{
        OldProcessId = $process.Id
        ExecutablePath = $split.ExecutablePath
        ArgumentString = $split.ArgumentString
        CurrentDirectory = $currentDirectory
        CapturedAt = [DateTimeOffset]::Now.ToString('o')
        Source = 'running-process'
    }
}

function Get-RiftLaunchStateFromFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    $raw = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    if (-not $raw.ExecutablePath) {
        throw "State file '$Path' does not contain an ExecutablePath."
    }

    $currentDirectory = $raw.CurrentDirectory
    if ([string]::IsNullOrWhiteSpace($currentDirectory)) {
        $currentDirectory = Split-Path -Parent $raw.ExecutablePath
    }

    return [pscustomobject]@{
        OldProcessId = $raw.OldProcessId
        ExecutablePath = $raw.ExecutablePath
        ArgumentString = $raw.ArgumentString
        CurrentDirectory = $currentDirectory
        CapturedAt = $raw.CapturedAt
        Source = 'saved-state'
    }
}

function Save-RiftLaunchState {
    param(
        [Parameter(Mandatory = $true)]
        [object]$State,
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $directory = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $persisted = [pscustomobject]@{
        OldProcessId = $State.OldProcessId
        ExecutablePath = $State.ExecutablePath
        ArgumentString = $State.ArgumentString
        CurrentDirectory = $State.CurrentDirectory
        CapturedAt = $State.CapturedAt
    }

    $persisted | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $Path -Encoding UTF8
}

$runningState = if (-not $PreferSavedState) {
    Get-RiftLaunchStateFromRunningProcess -TargetProcessName $ProcessName
}
else {
    $null
}

if ($RequireRunningProcess -and -not $runningState) {
    throw "No running '$ProcessName' process was found. Start Rift through Glyph once, then rerun this script."
}

$launchState = if ($runningState) {
    Save-RiftLaunchState -State $runningState -Path $StateFilePath
    $runningState
}
else {
    Get-RiftLaunchStateFromFile -Path $StateFilePath
}

if (-not $launchState) {
    throw "No launch state is available. Start Rift through Glyph once so the script can capture its executable path and arguments, or provide a saved state at '$StateFilePath'."
}

$argumentList = @($launchState.ExecutablePath)
if (-not [string]::IsNullOrWhiteSpace($launchState.ArgumentString)) {
    $argumentList += $launchState.ArgumentString
}
if (-not [string]::IsNullOrWhiteSpace($launchState.CurrentDirectory) -and -not [string]::IsNullOrWhiteSpace($launchState.ArgumentString)) {
    $argumentList += $launchState.CurrentDirectory
}

if ($PreviewOnly) {
    Write-Host ''
    Write-Host '# **✅ RESULT**' -ForegroundColor Green
    Write-Host ''
    [pscustomobject]@{
        X64DbgPath = $x64dbgPath
        LaunchSource = $launchState.Source
        CapturedAt = $launchState.CapturedAt
        TargetExecutable = $launchState.ExecutablePath
        CurrentDirectory = $launchState.CurrentDirectory
        ArgumentString = $launchState.ArgumentString
    } | Format-List

    Write-Host "[x64dbg] Preview invocation:" -ForegroundColor Cyan
    $argumentList | ForEach-Object { Write-Host ("  {0}" -f $_) }

    if ($runningState) {
        Write-Warning ("This launches a new Rift process under x64dbg. It does not attach to the already-running '{0}' instance [{1}]." -f $ProcessName, $runningState.OldProcessId)
    }

    return
}

Start-Process -FilePath $x64dbgPath -ArgumentList $argumentList | Out-Null

Write-Host "[x64dbg] Launched with Rift target:" -ForegroundColor Green
Write-Host ("[x64dbg]   Debugger: {0}" -f $x64dbgPath)
Write-Host ("[x64dbg]   Target  : {0}" -f $launchState.ExecutablePath)
Write-Host ("[x64dbg]   Source  : {0}" -f $launchState.Source)

if ($runningState) {
    Write-Warning ("A running '{0}' instance [{1}] is still active and already debugged elsewhere. The new x64dbg session starts a fresh process instead of attaching to that live instance." -f $ProcessName, $runningState.OldProcessId)
}
