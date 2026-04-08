[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$downloads = Join-Path $root 'downloads'
$reclassDir = Join-Path $root 'ReClass.NET'
$x64dbgDir = Join-Path $root 'x64dbg'

New-Item -ItemType Directory -Force -Path $downloads | Out-Null

$sevenZip = 'C:\Program Files\7-Zip\7z.exe'
if (-not (Test-Path -LiteralPath $sevenZip)) {
    throw "7-Zip was not found at '$sevenZip'. Install 7-Zip first so the official ReClass.NET .rar release can be extracted."
}

function Stop-RepoToolProcesses {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$ProcessNames
    )

    $rootPrefix = $root.TrimEnd('\') + '\'

    foreach ($process in Get-Process -Name $ProcessNames -ErrorAction SilentlyContinue) {
        try {
            if (-not [string]::IsNullOrWhiteSpace($process.Path) -and $process.Path.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                Write-Host "[ReTools] Stopping running repo-local tool process: $($process.ProcessName) [$($process.Id)]" -ForegroundColor Yellow
                Stop-Process -Id $process.Id -Force -ErrorAction Stop
            }
        }
        catch {
            Write-Warning ("Unable to stop process {0} [{1}]: {2}" -f $process.ProcessName, $process.Id, $_.Exception.Message)
        }
    }
}

Stop-RepoToolProcesses -ProcessNames @('ReClass.NET', 'x64dbg', 'x96dbg')

Write-Host "[ReTools] Fetching latest official ReClass.NET release metadata..." -ForegroundColor Cyan
$reclassRelease = Invoke-RestMethod 'https://api.github.com/repos/KN4CK3R/ReClass.NET/releases/latest'
$reclassAsset = $reclassRelease.assets | Select-Object -First 1
if (-not $reclassAsset) {
    throw 'The latest ReClass.NET release did not expose a downloadable asset.'
}

Write-Host "[ReTools] Fetching latest official x64dbg release metadata..." -ForegroundColor Cyan
$x64dbgRelease = Invoke-RestMethod 'https://api.github.com/repos/x64dbg/x64dbg/releases/latest'
$x64dbgAsset = $x64dbgRelease.assets | Where-Object { $_.name -like 'snapshot_*.zip' } | Select-Object -First 1
if (-not $x64dbgAsset) {
    throw 'The latest x64dbg release did not expose a snapshot zip asset.'
}

$reclassArchive = Join-Path $downloads $reclassAsset.name
$x64dbgArchive = Join-Path $downloads $x64dbgAsset.name

Write-Host "[ReTools] Downloading ReClass.NET $($reclassRelease.tag_name)..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $reclassAsset.browser_download_url -OutFile $reclassArchive

Write-Host "[ReTools] Downloading x64dbg $($x64dbgRelease.tag_name)..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $x64dbgAsset.browser_download_url -OutFile $x64dbgArchive

Remove-Item -Recurse -Force $reclassDir, $x64dbgDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $reclassDir, $x64dbgDir | Out-Null

Write-Host "[ReTools] Extracting ReClass.NET..." -ForegroundColor Cyan
& $sevenZip x $reclassArchive ('-o' + $reclassDir) -y | Out-Null

Write-Host "[ReTools] Extracting x64dbg..." -ForegroundColor Cyan
Expand-Archive -Path $x64dbgArchive -DestinationPath $x64dbgDir -Force

$summary = [pscustomobject]@{
    ReClassTag = $reclassRelease.tag_name
    ReClassExe = Join-Path $reclassDir 'x64\ReClass.NET.exe'
    X64DbgTag = $x64dbgRelease.tag_name
    X64DbgExe = Join-Path $x64dbgDir 'release\x64\x64dbg.exe'
}

Write-Host "[ReTools] Ready." -ForegroundColor Green
$summary | ConvertTo-Json
