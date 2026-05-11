# Version: riftreader-sendinput-current-csharp-shortcut-v0.1.0
# Total-Character-Count: 7861
# Purpose: One-line convenience launcher for the repo-owned C# SendInput tool. Auto-discovers the current exact RIFT PID/HWND, uses ScanCode input by default, sends no Esc, and avoids multiline paste issues.

[CmdletBinding()]
param(
    [string]$Key = "w",
    [int]$HoldMilliseconds = 750,
    [ValidateSet("ScanCode", "VirtualKey")]
    [string]$InputMode = "ScanCode",
    [string]$ProcessName = "rift_x64",
    [string]$TitleContains = "RIFT",
    [int]$FocusDelayMilliseconds = 250,
    [switch]$Refocus,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Wrapper = Join-Path $RepoRoot "scripts\send-rift-key-csharp.ps1"

if (-not (Test-Path -LiteralPath $Wrapper -PathType Leaf)) {
    throw "C# SendInput wrapper not found: $Wrapper"
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

$ToolArgs = @(
    "--key", $Key,
    "--hold-ms", ([string]$HoldMilliseconds),
    "--process-name", $ProcessName,
    "--pid", ([string]$RiftProcessId),
    "--hwnd", $RiftHwnd,
    "--title-contains", $TitleContains,
    "--input-mode", $InputMode,
    "--focus-delay-ms", ([string]$FocusDelayMilliseconds)
)

if (-not $Refocus.IsPresent) {
    $ToolArgs += "--no-refocus"
}

if ($Json.IsPresent) {
    $ToolArgs += "--json"
}
else {
    Write-Host "Target PID : $RiftProcessId"
    Write-Host "Target HWND: $RiftHwnd"
    Write-Host "Method     : C# SendInput $InputMode"
    Write-Host "Key/Hold   : $Key / ${HoldMilliseconds}ms"
}

& pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $Wrapper @ToolArgs
exit $LASTEXITCODE

# END_OF_SCRIPT_MARKER
