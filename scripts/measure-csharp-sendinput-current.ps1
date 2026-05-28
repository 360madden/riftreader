# Version: riftreader-measure-csharp-sendinput-current-v0.6.1
# Total-Character-Count: 19611
# Purpose: Measure repo-owned C# SendInput movement with fresh API coordinates before/after. Uses stable colorized stage lines by default; -Json emits clean JSON only.

[CmdletBinding()]
param(
    [string]$Key = "w",
    [int]$HoldMilliseconds = 750,
    [ValidateSet("ScanCode", "VirtualKey")]
    [string]$InputMode = "ScanCode",
    [string]$ProcessName = "rift_x64",
    [string]$TitleContains = "RIFT",
    [int]$FocusDelayMilliseconds = 250,
    [double]$MinimumPlanarDistance = 0.05,
    [int]$BeforeScanContextBytes = 16384,
    [int]$AfterScanContextBytes = 32768,
    [int]$BeforeMaxHits = 512,
    [int]$AfterMaxHits = 1024,
    [int]$BeforeScanAttempts = 5,
    [int]$AfterScanAttempts = 8,
    [int]$ScanRetryDelayMilliseconds = 1000,
    [int]$HeartbeatSeconds = 5,
    [int]$CommandTimeoutSeconds = 180,
    [ValidateRange(10, 60)]
    [int]$ProgressBarWidth = 26,
    [ValidateSet("Auto", "Steps", "Log", "Off")]
    [string]$ProgressMode = "Auto",
    [string]$OutputRoot,
    [switch]$NoProgress,
    [switch]$NoColor,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw "measure-csharp-sendinput-current.ps1 requires PowerShell 7+ (pwsh). Use scripts\measure-csharp-sendinput-current.cmd or run pwsh -File scripts\measure-csharp-sendinput-current.ps1."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$CaptureScript = Join-Path $RepoRoot "scripts\capture-rift-api-reference-coordinate.ps1"
$SenderScript = Join-Path $RepoRoot "scripts\send-rift-key-csharp.ps1"
$StageCount = 6

$EffectiveProgressMode = $ProgressMode
if ([string]::Equals($ProgressMode, "Auto", [System.StringComparison]::OrdinalIgnoreCase)) {
    if ($Json.IsPresent) {
        $EffectiveProgressMode = "Off"
    }
    else {
        $EffectiveProgressMode = "Steps"
    }
}

if (-not (Test-Path -LiteralPath $CaptureScript -PathType Leaf)) {
    throw "API coordinate capture script not found: $CaptureScript"
}

if (-not (Test-Path -LiteralPath $SenderScript -PathType Leaf)) {
    throw "C# SendInput wrapper not found: $SenderScript"
}

function Get-ProgressBar {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Stage,

        [Parameter(Mandatory = $true)]
        [double]$StageFraction
    )

    $fraction = (($Stage - 1) + [Math]::Min([Math]::Max($StageFraction, 0.0), 1.0)) / [double]$StageCount
    $percent = [int][Math]::Round($fraction * 100.0)
    $filled = [int][Math]::Round(($percent / 100.0) * $ProgressBarWidth)
    if ($filled -lt 0) { $filled = 0 }
    if ($filled -gt $ProgressBarWidth) { $filled = $ProgressBarWidth }

    $bar = "[" + ("#" * $filled) + ("-" * ($ProgressBarWidth - $filled)) + "]"
    return [pscustomobject]@{
        Percent = $percent
        Bar = $bar
    }
}

function Write-StableProgress {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Kind,

        [Parameter(Mandatory = $true)]
        [int]$Stage,

        [Parameter(Mandatory = $true)]
        [string]$Name,

        [double]$ElapsedSeconds = 0.0,
        [string]$Detail = "",
        [string]$Color = "Cyan",
        [double]$StageFraction = 0.0,
        [switch]$IncludeBar
    )

    if ($NoProgress.IsPresent -or [string]::Equals($EffectiveProgressMode, "Off", [System.StringComparison]::OrdinalIgnoreCase)) {
        return
    }

    $elapsedText = ("{0:0.0}s" -f $ElapsedSeconds)
    $label = ("[{0}]" -f $Kind).PadRight(8)
    $line = "$label stage=$Stage/$StageCount $($Name.PadRight(31)) elapsed=$elapsedText"

    if ($IncludeBar.IsPresent) {
        $bar = Get-ProgressBar -Stage $Stage -StageFraction $StageFraction
        $line = "$line $($bar.Bar) $($bar.Percent)%"
    }

    if (-not [string]::IsNullOrWhiteSpace($Detail)) {
        $line = "$line $Detail"
    }

    if ($NoColor.IsPresent) {
        [Console]::Error.WriteLine($line)
        return
    }

    $previousColor = [Console]::ForegroundColor
    try {
        [Console]::ForegroundColor = [System.ConsoleColor]::$Color
        [Console]::Error.WriteLine($line)
    }
    finally {
        [Console]::ForegroundColor = $previousColor
    }
}

function Write-ProgressEvent {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Stage,

        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$State,

        [double]$ElapsedSeconds = 0.0,
        [string]$Detail = "",
        [string]$Color = "Cyan"
    )

    if ($State -eq "running") {
        Write-StableProgress -Kind "wait" -Stage $Stage -Name $Name -ElapsedSeconds $ElapsedSeconds -Detail $Detail -Color "Yellow" -StageFraction 0.50
        return
    }

    $kind = switch ($State) {
        "start" { "start" }
        "done" { "done" }
        "failed" { "fail" }
        "timeout" { "time" }
        default { "info" }
    }

    $fraction = if ($State -eq "done") { 1.0 } elseif ($State -eq "start") { 0.0 } else { 0.95 }
    $includeBar = $State -in @("start", "done", "failed", "timeout")

    Write-StableProgress -Kind $kind -Stage $Stage -Name $Name -ElapsedSeconds $ElapsedSeconds -Detail $Detail -Color $Color -StageFraction $fraction -IncludeBar:($includeBar)
}

function Invoke-JsonCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,

        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter(Mandatory = $true)]
        [string]$ChildOutputRoot,

        [Parameter(Mandatory = $true)]
        [int]$Stage,

        [Parameter(Mandatory = $true)]
        [string]$StageName
    )

    $StdoutPath = Join-Path $ChildOutputRoot "$Label.stdout.json"
    $StderrPath = Join-Path $ChildOutputRoot "$Label.stderr.txt"
    $CommandPath = Join-Path $ChildOutputRoot "$Label.command.json"

    $StartedAt = Get-Date
    Write-ProgressEvent -Stage $Stage -Name $StageName -State "start" -ElapsedSeconds 0.0 -Color "Cyan"

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $FilePath
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    foreach ($argument in $Arguments) {
        [void]$psi.ArgumentList.Add($argument)
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $psi

    if (-not $process.Start()) {
        throw "Failed to start $StageName command: $FilePath"
    }

    $nextHeartbeatAt = if ($HeartbeatSeconds -gt 0) { $HeartbeatSeconds } else { [int]::MaxValue }
    while (-not $process.HasExited) {
        Start-Sleep -Milliseconds 200
        $elapsed = ((Get-Date) - $StartedAt).TotalSeconds

        if ($CommandTimeoutSeconds -gt 0 -and $elapsed -gt $CommandTimeoutSeconds) {
            try {
                $process.Kill($true)
            }
            catch {
                try { $process.Kill() } catch { }
            }

            Write-ProgressEvent -Stage $Stage -Name $StageName -State "timeout" -ElapsedSeconds $elapsed -Detail "limit=${CommandTimeoutSeconds}s" -Color "Red"
            throw "$StageName timed out after ${CommandTimeoutSeconds}s."
        }

        if ($elapsed -ge $nextHeartbeatAt) {
            Write-ProgressEvent -Stage $Stage -Name $StageName -State "running" -ElapsedSeconds $elapsed -Detail "heartbeat"
            $nextHeartbeatAt += [Math]::Max(1, $HeartbeatSeconds)
        }
    }

    $stdoutText = $process.StandardOutput.ReadToEnd()
    $stderrText = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    Set-Content -LiteralPath $StdoutPath -Value $stdoutText -Encoding UTF8
    Set-Content -LiteralPath $StderrPath -Value $stderrText -Encoding UTF8

    [ordered]@{
        label = $Label
        filePath = $FilePath
        arguments = @($Arguments)
        startedAtUtc = $StartedAt.ToUniversalTime().ToString("o")
        completedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
        exitCode = $process.ExitCode
        stdoutPath = $StdoutPath
        stderrPath = $StderrPath
    } | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $CommandPath -Encoding UTF8

    $duration = ((Get-Date) - $StartedAt).TotalSeconds

    if ($process.ExitCode -ne 0) {
        Write-ProgressEvent -Stage $Stage -Name $StageName -State "failed" -ElapsedSeconds $duration -Detail "exit=$($process.ExitCode)" -Color "Red"
        throw "$Label failed with exit code $($process.ExitCode). Stdout=$StdoutPath Stderr=$StderrPath $stderrText"
    }

    Write-ProgressEvent -Stage $Stage -Name $StageName -State "done" -ElapsedSeconds $duration -Detail "exit=0" -Color "Green"

    try {
        $Parsed = $stdoutText | ConvertFrom-Json -Depth 100
    }
    catch {
        throw "$Label exited cleanly but did not return valid JSON. Stdout=$StdoutPath"
    }

    return [pscustomobject]@{
        Json = $Parsed
        StdoutPath = $StdoutPath
        StderrPath = $StderrPath
        CommandPath = $CommandPath
        DurationSeconds = $duration
    }
}

function Get-CoordinateDelta {
    param(
        [Parameter(Mandatory = $true)]
        $Before,

        [Parameter(Mandatory = $true)]
        $After
    )

    $Dx = [double]$After.X - [double]$Before.X
    $Dy = [double]$After.Y - [double]$Before.Y
    $Dz = [double]$After.Z - [double]$Before.Z

    return [ordered]@{
        DeltaX = $Dx
        DeltaY = $Dy
        DeltaZ = $Dz
        PlanarDistance = [Math]::Sqrt(($Dx * $Dx) + ($Dz * $Dz))
        SpatialDistance = [Math]::Sqrt(($Dx * $Dx) + ($Dy * $Dy) + ($Dz * $Dz))
    }
}

function Write-HumanSummary {
    param(
        [Parameter(Mandatory = $true)]
        $Summary
    )

    $statusColor = if ([bool]$Summary.ok) { "Green" } else { "Yellow" }
    Write-Host ""
    Write-Host "=== C# SendInput measured proof summary ===" -ForegroundColor Cyan
    Write-Host ("Status        : {0}" -f $Summary.status) -ForegroundColor $statusColor
    Write-Host ("Target        : {0} PID {1} HWND {2}" -f $Summary.target.processName, $Summary.target.processId, $Summary.target.hwnd)
    Write-Host ("Method        : {0}" -f $Summary.method)
    Write-Host ("Before        : X={0} Y={1} Z={2}" -f $Summary.before.X, $Summary.before.Y, $Summary.before.Z)
    Write-Host ("After         : X={0} Y={1} Z={2}" -f $Summary.after.X, $Summary.after.Y, $Summary.after.Z)
    Write-Host ("Planar        : {0}" -f $Summary.delta.PlanarDistance) -ForegroundColor $statusColor
    Write-Host ("Before scan   : {0:0.0}s" -f $Summary.stageTimings.beforeApiCoordinateSeconds)
    Write-Host ("Input send    : {0:0.0}s" -f $Summary.stageTimings.csharpSendInputStimulusSeconds)
    Write-Host ("After scan    : {0:0.0}s" -f $Summary.stageTimings.afterApiCoordinateSeconds)
    Write-Host ("Summary JSON  : {0}" -f $Summary.artifacts.summaryJson)
    Write-Host ("Summary MD    : {0}" -f $Summary.artifacts.summaryMarkdown)
}

$OverallStartedAt = Get-Date

Write-ProgressEvent -Stage 1 -Name "target-discovery" -State "start" -ElapsedSeconds 0.0 -Color "Cyan"
$Targets = @(
    Get-Process -Name $ProcessName -ErrorAction Stop |
        Where-Object {
            $_.MainWindowHandle -ne 0 -and
            $_.MainWindowTitle -like "*$TitleContains*"
        } |
        Sort-Object StartTime -Descending
)

if ($Targets.Count -ne 1) {
    $Detail = $Targets |
        Select-Object Id, ProcessName, MainWindowTitle, MainWindowHandle, StartTime |
        Format-Table |
        Out-String

    Write-ProgressEvent -Stage 1 -Name "target-discovery" -State "failed" -ElapsedSeconds ((Get-Date) - $OverallStartedAt).TotalSeconds -Detail "targets=$($Targets.Count)" -Color "Red"
    throw "Expected exactly one windowed RIFT target; found $($Targets.Count).`n$Detail"
}

$Target = $Targets[0]
$RiftProcessId = [int]$Target.Id
$RiftHwnd = "0x{0:X}" -f ([int64]$Target.MainWindowHandle)
Write-ProgressEvent -Stage 1 -Name "target-discovery" -State "done" -ElapsedSeconds ((Get-Date) - $OverallStartedAt).TotalSeconds -Detail "pid=$RiftProcessId hwnd=$RiftHwnd" -Color "Green"

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputRoot = Join-Path $RepoRoot "scripts\captures\csharp-sendinput-current-measured-proof-$Stamp"
}

$RunRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$ChildOutputRoot = Join-Path $RunRoot "child-outputs"
$BeforeDir = Join-Path $RunRoot "before"
$AfterDir = Join-Path $RunRoot "after"

New-Item -ItemType Directory -Path $RunRoot, $ChildOutputRoot, $BeforeDir, $AfterDir -Force | Out-Null

$BeforeFile = Join-Path $BeforeDir "before-reference.json"
$AfterFile = Join-Path $AfterDir "after-reference.json"
$StimulusFile = Join-Path $RunRoot "csharp-sendinput-stimulus.json"
$SummaryJson = Join-Path $RunRoot "measured-result.json"
$SummaryMarkdown = Join-Path $RunRoot "measured-result.md"

Write-ProgressEvent -Stage 2 -Name "run-context" -State "done" -ElapsedSeconds ((Get-Date) - $OverallStartedAt).TotalSeconds -Detail "runRoot=$RunRoot" -Color "DarkCyan"

$Before = Invoke-JsonCommand `
    -Label "before-api-coordinate" `
    -FilePath "pwsh" `
    -Arguments @(
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $CaptureScript,
        "-ProcessName",
        $ProcessName,
        "-ProcessId",
        ([string]$RiftProcessId),
        "-TargetWindowHandle",
        $RiftHwnd,
        "-OutputRoot",
        $BeforeDir,
        "-OutputFile",
        $BeforeFile,
        "-ScanContextBytes",
        ([string]$BeforeScanContextBytes),
        "-MaxHits",
        ([string]$BeforeMaxHits),
        "-ScanAttempts",
        ([string]$BeforeScanAttempts),
        "-ScanRetryDelayMilliseconds",
        ([string]$ScanRetryDelayMilliseconds),
        "-Json"
    ) `
    -ChildOutputRoot $ChildOutputRoot `
    -Stage 3 `
    -StageName "before-api-coordinate"

if ($Before.Json.Status -ne "captured") {
    throw "Before API coordinate capture did not return Status=captured."
}

$Stimulus = Invoke-JsonCommand `
    -Label "csharp-sendinput-stimulus" `
    -FilePath "pwsh" `
    -Arguments @(
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $SenderScript,
        "--key",
        $Key,
        "--hold-ms",
        ([string]$HoldMilliseconds),
        "--process-name",
        $ProcessName,
        "--pid",
        ([string]$RiftProcessId),
        "--hwnd",
        $RiftHwnd,
        "--title-contains",
        $TitleContains,
        "--input-mode",
        $InputMode,
        "--focus-delay-ms",
        ([string]$FocusDelayMilliseconds),
        "--no-refocus",
        "--json"
    ) `
    -ChildOutputRoot $ChildOutputRoot `
    -Stage 4 `
    -StageName "csharp-sendinput-stimulus"

$Stimulus.Json | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $StimulusFile -Encoding UTF8

if (-not [bool]$Stimulus.Json.ok) {
    throw "C# SendInput stimulus returned ok=false."
}

Write-ProgressEvent -Stage 5 -Name "post-stimulus-settle" -State "start" -ElapsedSeconds ((Get-Date) - $OverallStartedAt).TotalSeconds -Detail "sleep=2s" -Color "Cyan"
Start-Sleep -Seconds 2
Write-ProgressEvent -Stage 5 -Name "post-stimulus-settle" -State "done" -ElapsedSeconds ((Get-Date) - $OverallStartedAt).TotalSeconds -Color "Green"

$After = Invoke-JsonCommand `
    -Label "after-api-coordinate" `
    -FilePath "pwsh" `
    -Arguments @(
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $CaptureScript,
        "-ProcessName",
        $ProcessName,
        "-ProcessId",
        ([string]$RiftProcessId),
        "-TargetWindowHandle",
        $RiftHwnd,
        "-OutputRoot",
        $AfterDir,
        "-OutputFile",
        $AfterFile,
        "-ScanContextBytes",
        ([string]$AfterScanContextBytes),
        "-MaxHits",
        ([string]$AfterMaxHits),
        "-ScanAttempts",
        ([string]$AfterScanAttempts),
        "-ScanRetryDelayMilliseconds",
        ([string]$ScanRetryDelayMilliseconds),
        "-Json"
    ) `
    -ChildOutputRoot $ChildOutputRoot `
    -Stage 6 `
    -StageName "after-api-coordinate"

if ($After.Json.Status -ne "captured") {
    throw "After API coordinate capture did not return Status=captured."
}

$BeforeCoordinate = $Before.Json.Coordinate
$AfterCoordinate = $After.Json.Coordinate
$Delta = Get-CoordinateDelta -Before $BeforeCoordinate -After $AfterCoordinate
$Moved = [double]$Delta.PlanarDistance -ge $MinimumPlanarDistance

$Summary = [ordered]@{
    schemaVersion = 1
    status = if ($Moved) { "passed-csharp-sendinput-current-displacement" } else { "blocked-csharp-sendinput-current-no-displacement" }
    ok = $Moved
    target = [ordered]@{
        processName = $ProcessName
        processId = $RiftProcessId
        hwnd = $RiftHwnd
        title = $Target.MainWindowTitle
    }
    method = "scripts/send-rift-key-csharp.ps1 --input-mode $InputMode --key $Key --hold-ms $HoldMilliseconds"
    minimumPlanarDistance = $MinimumPlanarDistance
    stimulus = $Stimulus.Json
    before = $BeforeCoordinate
    after = $AfterCoordinate
    delta = $Delta
    stageTimings = [ordered]@{
        beforeApiCoordinateSeconds = $Before.DurationSeconds
        csharpSendInputStimulusSeconds = $Stimulus.DurationSeconds
        afterApiCoordinateSeconds = $After.DurationSeconds
        overallSeconds = ((Get-Date) - $OverallStartedAt).TotalSeconds
    }
    artifacts = [ordered]@{
        runRoot = $RunRoot
        beforeReference = $BeforeFile
        beforeStdout = $Before.StdoutPath
        stimulusJson = $StimulusFile
        stimulusStdout = $Stimulus.StdoutPath
        afterReference = $AfterFile
        afterStdout = $After.StdoutPath
        summaryJson = $SummaryJson
        summaryMarkdown = $SummaryMarkdown
    }
    safety = [ordered]@{
        automaticEscUsed = $false
        proofAnchorRequiredForBackendCalibration = $false
        cheatEngineUsed = $false
        savedVariablesLiveTruthUsed = $false
        reloadUiUsed = $false
    }
    completedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
}

$Summary | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $SummaryJson -Encoding UTF8

@"
# C# SendInput current-target measured proof

| Field | Value |
|---|---|
| Status | `$($Summary.status)` |
| Target | `$ProcessName PID $RiftProcessId HWND $RiftHwnd` |
| Method | `C# SendInput $InputMode` |
| Key / hold | `$Key / ${HoldMilliseconds}ms` |
| Before | `X=$($BeforeCoordinate.X) Y=$($BeforeCoordinate.Y) Z=$($BeforeCoordinate.Z)` |
| After | `X=$($AfterCoordinate.X) Y=$($AfterCoordinate.Y) Z=$($AfterCoordinate.Z)` |
| Planar distance | `$($Delta.PlanarDistance)` |
| Spatial distance | `$($Delta.SpatialDistance)` |
| Automatic Esc | `false` |
| Cheat Engine | `false` |
| SavedVariables live truth | `false` |
| Before API seconds | `$($Before.DurationSeconds)` |
| C# SendInput seconds | `$($Stimulus.DurationSeconds)` |
| After API seconds | `$($After.DurationSeconds)` |
| Summary JSON | `$SummaryJson` |
"@ | Set-Content -LiteralPath $SummaryMarkdown -Encoding UTF8

if ($Moved) {
    Write-ProgressEvent -Stage 6 -Name "summary" -State "done" -ElapsedSeconds ((Get-Date) - $OverallStartedAt).TotalSeconds -Detail ("planar={0:0.######}" -f $Delta.PlanarDistance) -Color "Green"
}
else {
    Write-ProgressEvent -Stage 6 -Name "summary" -State "done" -ElapsedSeconds ((Get-Date) - $OverallStartedAt).TotalSeconds -Detail ("planar={0:0.######}; below-threshold" -f $Delta.PlanarDistance) -Color "Yellow"
}

if ($Json.IsPresent) {
    Get-Content -LiteralPath $SummaryJson -Raw
}
else {
    Write-HumanSummary -Summary $Summary
}

# END_OF_SCRIPT_MARKER
