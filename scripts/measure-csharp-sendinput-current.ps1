# Version: riftreader-measure-csharp-sendinput-current-v0.1.0
# Total-Character-Count: 10359
# Purpose: Measure repo-owned C# SendInput movement with fresh API coordinates before/after. Auto-discovers the current exact RIFT PID/HWND, sends no Esc, uses no Cheat Engine, and writes JSON/Markdown proof artifacts.

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
    [string]$OutputRoot,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$CaptureScript = Join-Path $RepoRoot "scripts\capture-rift-api-reference-coordinate.ps1"
$SenderScript = Join-Path $RepoRoot "scripts\send-rift-key-csharp.ps1"

if (-not (Test-Path -LiteralPath $CaptureScript -PathType Leaf)) {
    throw "API coordinate capture script not found: $CaptureScript"
}

if (-not (Test-Path -LiteralPath $SenderScript -PathType Leaf)) {
    throw "C# SendInput wrapper not found: $SenderScript"
}

function Write-ProgressLine {
    param([string]$Message)
    if (-not $Json.IsPresent) {
        Write-Host $Message
    }
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
        [string]$ChildOutputRoot
    )

    $StdoutPath = Join-Path $ChildOutputRoot "$Label.stdout.json"
    $StderrPath = Join-Path $ChildOutputRoot "$Label.stderr.txt"

    $Output = & $FilePath @Arguments 2> $StderrPath
    $ExitCode = $LASTEXITCODE
    $Text = ($Output -join "`n")
    Set-Content -LiteralPath $StdoutPath -Value $Text -Encoding UTF8

    if ($ExitCode -ne 0) {
        $ErrText = if (Test-Path -LiteralPath $StderrPath) { Get-Content -LiteralPath $StderrPath -Raw } else { "" }
        throw "$Label failed with exit code $ExitCode. Stdout=$StdoutPath Stderr=$StderrPath $ErrText"
    }

    try {
        $Parsed = $Text | ConvertFrom-Json -Depth 100
    }
    catch {
        throw "$Label exited cleanly but did not return valid JSON. Stdout=$StdoutPath"
    }

    return [pscustomobject]@{
        Json = $Parsed
        StdoutPath = $StdoutPath
        StderrPath = $StderrPath
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

    throw "Expected exactly one windowed RIFT target; found $($Targets.Count).`n$Detail"
}

$Target = $Targets[0]
$RiftProcessId = [int]$Target.Id
$RiftHwnd = "0x{0:X}" -f ([int64]$Target.MainWindowHandle)

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

Write-ProgressLine "Target PID : $RiftProcessId"
Write-ProgressLine "Target HWND: $RiftHwnd"
Write-ProgressLine "RunRoot    : $RunRoot"
Write-ProgressLine "Method     : C# SendInput $InputMode; key=$Key; hold=${HoldMilliseconds}ms"
Write-ProgressLine "Safety     : no automatic Esc; no Cheat Engine; no SavedVariables live truth"

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
    -ChildOutputRoot $ChildOutputRoot

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
    -ChildOutputRoot $ChildOutputRoot

$Stimulus.Json | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $StimulusFile -Encoding UTF8

if (-not [bool]$Stimulus.Json.ok) {
    throw "C# SendInput stimulus returned ok=false."
}

Start-Sleep -Seconds 2

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
    -ChildOutputRoot $ChildOutputRoot

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
| Summary JSON | `$SummaryJson` |
"@ | Set-Content -LiteralPath $SummaryMarkdown -Encoding UTF8

Get-Content -LiteralPath $SummaryJson -Raw

# END_OF_SCRIPT_MARKER
