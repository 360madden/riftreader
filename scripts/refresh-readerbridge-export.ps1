[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$NoReader
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$postCommandScript = Join-Path $PSScriptRoot 'post-rift-command.ps1'

Write-Host "[RiftRefresh] Forcing a Rift UI reload via the native no-focus PostMessage helper..." -ForegroundColor Cyan
& $postCommandScript -Command '/reloadui'

if ($NoReader) {
    exit 0
}

$arguments = @('--readerbridge-snapshot')
if ($Json) {
    $arguments += '--json'
}

Write-Host ""
Write-Host "[RiftRefresh] Loading the fresh ReaderBridge snapshot..." -ForegroundColor Cyan
Write-Host "[RiftRefresh] dotnet run --project $readerProject -- $($arguments -join ' ')" -ForegroundColor DarkGray

& dotnet run --project $readerProject -- @arguments
exit $LASTEXITCODE
