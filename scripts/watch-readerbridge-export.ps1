[CmdletBinding()]
param(
    [string]$FilePath,
    [switch]$Json,
    [switch]$Once,
    [switch]$RunInitial,
    [int]$PollSeconds = 2
)

$ErrorActionPreference = 'Stop'

if ($PollSeconds -lt 1) {
    throw "PollSeconds must be 1 or greater."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'

function Get-SavedRoots {
    $roots = New-Object System.Collections.Generic.List[string]

    if ($env:RIFT_SAVED_ROOT) {
        $roots.Add($env:RIFT_SAVED_ROOT)
    }

    $roots.Add((Join-Path $env:USERPROFILE 'OneDrive\Documents\RIFT\Interface\Saved'))
    $roots.Add((Join-Path $env:USERPROFILE 'Documents\RIFT\Interface\Saved'))

    return $roots |
        Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
        Select-Object -Unique
}

function Find-LatestExportFile {
    $roots = Get-SavedRoots
    $matches = New-Object System.Collections.Generic.List[System.IO.FileInfo]

    foreach ($root in $roots) {
        Get-ChildItem -LiteralPath $root -Recurse -File -Filter 'ReaderBridgeExport.lua' -ErrorAction SilentlyContinue |
            ForEach-Object { [void]$matches.Add($_) }
    }

    if ($matches.Count -eq 0) {
        return $null
    }

    return $matches |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
}

function Resolve-WatchFile {
    if ($FilePath) {
        $resolved = Resolve-Path -LiteralPath $FilePath -ErrorAction SilentlyContinue
        if ($resolved) {
            return Get-Item -LiteralPath $resolved.Path
        }

        return $null
    }

    return Find-LatestExportFile
}

function Invoke-Reader([string]$snapshotPath) {
    $arguments = @('--readerbridge-snapshot', '--readerbridge-snapshot-file', $snapshotPath)
    $arguments += '--json'

    if (-not $Json) {
        Write-Host ""
        Write-Host "[RUN] dotnet run --project $readerProject -- $($arguments -join ' ')" -ForegroundColor Cyan
    }

    $readerOutput = & dotnet run --project $readerProject -- @arguments 2>&1
    $exitCode = $LASTEXITCODE
    $readerText = $readerOutput -join [Environment]::NewLine

    if ($exitCode -ne 0) {
        throw "Reader command failed (`$LASTEXITCODE=$exitCode): $readerText"
    }

    if ($Json) {
        return $readerText | ConvertFrom-Json -Depth 40
    }

    foreach ($line in $readerOutput) {
        Write-Host $line
    }

    return $null
}

$status = ''
$lastPath = ''
$lastWriteTicks = -1L
$lastLength = -1L

if (-not $Json) {
    Write-Host "Watching for ReaderBridgeExport.lua..." -ForegroundColor Yellow
    Write-Host "Repo:   $repoRoot" -ForegroundColor DarkGray

    if ($FilePath) {
        Write-Host "Target: $FilePath" -ForegroundColor DarkGray
    }
    else {
        $roots = Get-SavedRoots
        if ($roots.Count -gt 0) {
            Write-Host "Roots:  $($roots -join '; ')" -ForegroundColor DarkGray
        }
    }
}

while ($true) {
    $file = Resolve-WatchFile

    if (-not $file) {
        if ($status -ne 'waiting') {
            if (-not $Json) {
                Write-Host "[WAIT] ReaderBridgeExport.lua not found yet." -ForegroundColor Yellow
            }
            $status = 'waiting'
        }

        Start-Sleep -Seconds $PollSeconds
        continue
    }

    $writeTicks = $file.LastWriteTimeUtc.Ticks
    $length = $file.Length
    $changed = ($file.FullName -ne $lastPath) -or ($writeTicks -ne $lastWriteTicks) -or ($length -ne $lastLength)

    if (-not $RunInitial -and $lastPath -eq '' -and $changed) {
        $lastPath = $file.FullName
        $lastWriteTicks = $writeTicks
        $lastLength = $length
        if (-not $Json) {
            Write-Host "[READY] Baseline file found; waiting for a new change: $($file.FullName)" -ForegroundColor Green
        }
        $status = 'ready'
        Start-Sleep -Seconds $PollSeconds
        continue
    }

    if ($changed) {
        if (-not $Json) {
            Write-Host ""
            Write-Host "[DETECT] $($file.FullName)" -ForegroundColor Green
            Write-Host "         LastWrite: $($file.LastWriteTime)" -ForegroundColor DarkGray
            Write-Host "         Length:    $($file.Length)" -ForegroundColor DarkGray
        }

        $snapshot = Invoke-Reader -snapshotPath $file.FullName

        if ($Json) {
            $event = [ordered]@{
                Mode = 'watch-readerbridge-export'
                DetectedFile = $file.FullName
                LastWriteTimeUtc = $file.LastWriteTimeUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
                Length = $file.Length
                Snapshot = $snapshot
            }

            Write-Output ($event | ConvertTo-Json -Depth 50)
        }

        $lastPath = $file.FullName
        $lastWriteTicks = $writeTicks
        $lastLength = $length
        $status = 'ready'

        if ($Once) {
            exit 0
        }
    }
    elseif ($status -ne 'ready') {
        if (-not $Json) {
            Write-Host "[READY] Waiting for changes: $($file.FullName)" -ForegroundColor Green
        }
        $status = 'ready'
    }

    Start-Sleep -Seconds $PollSeconds
}
