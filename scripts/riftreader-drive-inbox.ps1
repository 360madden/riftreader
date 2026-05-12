# Version: riftreader-drive-inbox-runner-v0.1.0
# Total-Character-Count: 1706
# Purpose: Launch the repo-owned RiftReader Drive inbox Python helper with safe defaults for bootstrap, status, and verified package import.
[CmdletBinding()]
param(
  [ValidateSet("bootstrap", "status", "import")]
  [string]$Action = "status",

  [string]$RepoRoot = "C:\RIFT MODDING\RiftReader",
  [string]$DriveRoot = "G:\My Drive\RiftReader",
  [string]$Source,

  [ValidateSet("packages", "scripts", "prompts", "handoffs")]
  [string]$Lane = "packages",

  [switch]$Json,
  [switch]$WriteStatus,
  [switch]$RemoveSourceAfterVerify
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoPath = Resolve-Path -LiteralPath $RepoRoot -ErrorAction Stop
$HelperPath = Join-Path -Path $RepoPath.Path -ChildPath "tools\riftreader_drive_inbox.py"
if (-not (Test-Path -LiteralPath $HelperPath -PathType Leaf)) {
  throw "Missing helper: $HelperPath"
}

$PythonCommand = Get-Command -Name "python" -ErrorAction Stop
$ArgsList = @($HelperPath, $Action, "--drive-root", $DriveRoot)

if ($Action -eq "import") {
  if ([string]::IsNullOrWhiteSpace($Source)) {
    throw "-Source is required when -Action import is used."
  }
  $SourcePath = Resolve-Path -LiteralPath $Source -ErrorAction Stop
  $ArgsList += @("--source", $SourcePath.Path, "--lane", $Lane)
  if ($RemoveSourceAfterVerify) {
    $ArgsList += "--remove-source-after-verify"
  }
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
  throw "RiftReader Drive inbox helper failed with exit code $ExitCode."
}

# END_OF_SCRIPT_MARKER
