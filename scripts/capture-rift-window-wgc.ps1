[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TitleContains,
    [string]$OutputPath,
    [int]$TimeoutMs = 2500,
    [ValidateRange(1, 20)]
    [int]$Attempts = 1,
    [switch]$CaptureMonitor,
    [switch]$DesktopDuplication,
    [switch]$RequireUsable,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$projectPath = Join-Path $repoRoot 'tools\rift-window-capture\RiftWindowCapture.csproj'

if (-not (Test-Path -LiteralPath $projectPath)) {
    throw "Rift window capture project not found: $projectPath"
}

if ($CaptureMonitor -and $DesktopDuplication) {
    throw '-CaptureMonitor and -DesktopDuplication are mutually exclusive.'
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $captureRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'RiftReader-window-capture\wgc'
    New-Item -ItemType Directory -Force -Path $captureRoot | Out-Null
    $OutputPath = Join-Path $captureRoot ('capture-{0}.png' -f (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
}
elseif (-not [System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath = Join-Path $repoRoot $OutputPath
}

$toolArgs = @(
    'run',
    '--project', $projectPath,
    '--',
    '--output', $OutputPath,
    '--timeout-ms', $TimeoutMs.ToString([Globalization.CultureInfo]::InvariantCulture),
    '--attempts', $Attempts.ToString([Globalization.CultureInfo]::InvariantCulture)
)

if ($PSBoundParameters.ContainsKey('ProcessId')) {
    $toolArgs += @('--pid', $ProcessId.ToString([Globalization.CultureInfo]::InvariantCulture))
}
elseif (-not [string]::IsNullOrWhiteSpace($ProcessName)) {
    $toolArgs += @('--process-name', $ProcessName)
}

if (-not [string]::IsNullOrWhiteSpace($TitleContains)) {
    $toolArgs += @('--title-contains', $TitleContains)
}

if ($Json) {
    $toolArgs += '--json'
}

if ($CaptureMonitor) {
    $toolArgs += '--capture-monitor'
}

if ($DesktopDuplication) {
    $toolArgs += '--desktop-duplication'
}

if ($RequireUsable) {
    $toolArgs += '--require-usable'
}

& dotnet @toolArgs
exit $LASTEXITCODE
