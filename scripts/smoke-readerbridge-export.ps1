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
    try {
        $resolvedSnapshotFile = (Resolve-Path -LiteralPath $SnapshotFile -ErrorAction Stop).Path
    }
    catch {
        [Console]::Error.WriteLine(("Snapshot file was not found: {0}" -f [System.IO.Path]::GetFullPath($SnapshotFile)))
        exit 1
    }
    $dotnetArgs += '--readerbridge-snapshot-file'
    $dotnetArgs += $resolvedSnapshotFile
}

if ($Json) {
    $dotnetArgs += '--json'
}

& dotnet @dotnetArgs
exit $LASTEXITCODE
