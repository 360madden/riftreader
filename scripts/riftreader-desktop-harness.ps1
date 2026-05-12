# Version: riftreader-desktop-harness-runner-v0.1.0
# Total-Character-Count: 1351
# Purpose: Launch the repo-owned RiftReader Desktop ChatGPT Drive harness for status, prompt, and package artifact generation.
[CmdletBinding()]
param(
  [ValidateSet("status", "prompt", "package")]
  [string]$Action = "status",

  [string]$RepoRoot = "C:\RIFT MODDING\RiftReader",
  [string]$DriveRoot = "G:\My Drive\RiftReader",
  [string]$Task = "",

  [switch]$Json,
  [switch]$WriteStatus
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoPath = Resolve-Path -LiteralPath $RepoRoot -ErrorAction Stop
$HelperPath = Join-Path -Path $RepoPath.Path -ChildPath "tools\riftreader_desktop_harness.py"
if (-not (Test-Path -LiteralPath $HelperPath -PathType Leaf)) {
  throw "Missing helper: $HelperPath"
}

$PythonCommand = Get-Command -Name "python" -ErrorAction Stop
$ArgsList = @($HelperPath, $Action, "--repo-root", $RepoPath.Path, "--drive-root", $DriveRoot)

if ($Action -eq "prompt" -and -not [string]::IsNullOrWhiteSpace($Task)) {
  $ArgsList += @("--task", $Task)
}

if ($Json) {
  $ArgsList += "--json"
}

if ($WriteStatus) {
  $ArgsList += "--write-status"
}

& $PythonCommand.Source @ArgsList
$ExitCode = $LASTEXITCODE
if ($ExitCode -ne 0) {
  throw "RiftReader Desktop harness failed with exit code $ExitCode."
}

# END_OF_SCRIPT_MARKER
