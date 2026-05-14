[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$Hwnd,
    [string]$TitleContains,
    [string]$OutputPath,
    [string]$OutputRoot,
    [string]$ExpectedProcessStartUtc,
    [int]$TimeoutMs = 2500,
    [ValidateRange(1, 20)]
    [int]$Attempts = 1,
    [switch]$CaptureMonitor,
    [switch]$DesktopDuplication,
    [switch]$RequireUsable,
    [switch]$EmitPng,
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

if ([string]::IsNullOrWhiteSpace($OutputPath) -and [string]::IsNullOrWhiteSpace($OutputRoot)) {
    $captureRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'RiftReader-window-capture\wgc'
    New-Item -ItemType Directory -Force -Path $captureRoot | Out-Null
    $OutputPath = Join-Path $captureRoot ('capture-{0}.png' -f (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
}
elseif (-not [string]::IsNullOrWhiteSpace($OutputPath) -and -not [System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath = Join-Path $repoRoot $OutputPath
}

$appArgs = @(
    '--timeout-ms', $TimeoutMs.ToString([Globalization.CultureInfo]::InvariantCulture),
    '--attempts', $Attempts.ToString([Globalization.CultureInfo]::InvariantCulture)
)

if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
    $appArgs += @('--output', $OutputPath)
}

if ($PSBoundParameters.ContainsKey('ProcessId')) {
    $appArgs += @('--pid', $ProcessId.ToString([Globalization.CultureInfo]::InvariantCulture))
}
elseif (-not [string]::IsNullOrWhiteSpace($ProcessName)) {
    $appArgs += @('--process-name', $ProcessName)
}

if (-not [string]::IsNullOrWhiteSpace($Hwnd)) {
    $appArgs += @('--hwnd', $Hwnd)
}

if (-not [string]::IsNullOrWhiteSpace($TitleContains)) {
    $appArgs += @('--title-contains', $TitleContains)
}

if (-not [string]::IsNullOrWhiteSpace($OutputRoot)) {
    if (-not [System.IO.Path]::IsPathRooted($OutputRoot)) {
        # Keep repo-relative paths relative for the native process. Windows
        # PowerShell 5.x can split native arguments that contain spaces (for
        # example the repo root `C:\RIFT MODDING\...`).
        $OutputRoot = $OutputRoot
    }
    $appArgs += @('--output-root', $OutputRoot)
}

if (-not [string]::IsNullOrWhiteSpace($ExpectedProcessStartUtc)) {
    $appArgs += @('--expected-process-start-utc', $ExpectedProcessStartUtc)
}

if ($Json) {
    $appArgs += '--json'
}

if ($EmitPng) {
    $appArgs += '--emit-png'
}

if ($CaptureMonitor) {
    $appArgs += '--capture-monitor'
}

if ($DesktopDuplication) {
    $appArgs += '--desktop-duplication'
}

if ($RequireUsable) {
    $appArgs += '--require-usable'
}

& dotnet build $projectPath --nologo --verbosity quiet
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$toolExe = Join-Path (Split-Path -Parent $projectPath) 'bin\Debug\net10.0-windows10.0.19041.0\RiftWindowCapture.exe'
if (-not (Test-Path -LiteralPath $toolExe)) {
    throw "Built Rift window capture executable not found: $toolExe"
}

Push-Location -LiteralPath $repoRoot
try {
    & $toolExe @appArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
