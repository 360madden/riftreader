[CmdletBinding()]
param(
    [string]$SnapshotFile,
    [switch]$Json,
    [switch]$NoBuild
)

$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptRoot
$projectPath = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'

$dotnetArgs = @(
    'run',
    '--project', $projectPath
)

if ($NoBuild) {
    $dotnetArgs += '--no-build'
}

$dotnetArgs += '--'
$dotnetArgs += '--readerbridge-snapshot'

if ($SnapshotFile) {
    $resolvedSnapshotFile = (Resolve-Path -LiteralPath $SnapshotFile).Path
    $dotnetArgs += '--readerbridge-snapshot-file'
    $dotnetArgs += $resolvedSnapshotFile
}

if ($Json) {
    $dotnetArgs += '--json'
}

& dotnet @dotnetArgs
exit $LASTEXITCODE
