[CmdletBinding()]
param(
    [string]$Command = "/reloadui",
    [string]$TargetExe = "rift_x64.exe",
    [string]$VerifyFilePath,
    [string]$BackgroundExe = "cheatengine-x86_64-SSE4-AVX2.exe",
    [int]$AttemptTimeoutSeconds = 20
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Find-AutoHotkeyExe {
    $candidates = @(
        "C:\Users\mrkoo\AppData\Local\Programs\AutoHotkey\v2\AutoHotkey64.exe",
        "C:\Users\mrkoo\AppData\Local\Programs\AutoHotkey\v2\AutoHotkey32.exe",
        "C:\Program Files\AutoHotkey\AutoHotkey64.exe",
        "C:\Program Files\AutoHotkey\AutoHotkey32.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    $command = Get-Command AutoHotkey64.exe, AutoHotkey32.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) {
        return $command.Source
    }

    throw "AutoHotkey v2 executable was not found."
}

function Quote-ProcessArgument {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Value
    )

    return '"' + ($Value -replace '"', '\"') + '"'
}

function Get-FileTimestampUtc {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Verification file was not found: $Path"
    }

    return (Get-Item -LiteralPath $Path).LastWriteTimeUtc
}

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

function Find-LatestVerificationFile {
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

function Resolve-VerificationFile {
    param(
        [AllowEmptyString()]
        [string]$PreferredPath
    )

    if (-not [string]::IsNullOrWhiteSpace($PreferredPath)) {
        if (-not (Test-Path -LiteralPath $PreferredPath)) {
            throw "Verification file was not found: $PreferredPath"
        }

        return Get-Item -LiteralPath $PreferredPath
    }

    $latest = Find-LatestVerificationFile
    if ($null -eq $latest) {
        throw "Unable to locate ReaderBridgeExport.lua under the known RIFT saved-variable roots."
    }

    return $latest
}

function Wait-ForTimestampAdvance {
    param(
        [Parameter(Mandatory = $true)]
        [datetime]$BaselineUtc,

        [AllowEmptyString()]
        [string]$PreferredPath,

        [Parameter(Mandatory = $true)]
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).ToUniversalTime().AddSeconds($TimeoutSeconds)
    do {
        $candidates = New-Object System.Collections.Generic.List[System.IO.FileInfo]

        if (-not [string]::IsNullOrWhiteSpace($PreferredPath) -and (Test-Path -LiteralPath $PreferredPath)) {
            [void]$candidates.Add((Get-Item -LiteralPath $PreferredPath))
        }

        $latest = Find-LatestVerificationFile
        if ($latest -and @($candidates | Where-Object { $_.FullName -eq $latest.FullName }).Count -eq 0) {
            [void]$candidates.Add($latest)
        }

        foreach ($candidate in ($candidates | Sort-Object LastWriteTimeUtc -Descending)) {
            if ($candidate.LastWriteTimeUtc -gt $BaselineUtc) {
                return $candidate
            }
        }

        Start-Sleep -Milliseconds 250
    }
    while ((Get-Date).ToUniversalTime() -lt $deadline)

    return $null
}

$scriptPath = "C:\RIFT MODDING\RiftReader\scripts\post-rift-command-ahk.ahk"
$autoHotkeyExe = Find-AutoHotkeyExe
$verificationFile = Resolve-VerificationFile -PreferredPath $VerifyFilePath
$resolvedVerifyFilePath = $verificationFile.FullName
$baselineUtc = $verificationFile.LastWriteTimeUtc

Write-Host "[RiftAhkPost] AutoHotkey    : $autoHotkeyExe"
Write-Host "[RiftAhkPost] Script        : $scriptPath"
Write-Host "[RiftAhkPost] Target EXE    : $TargetExe"
Write-Host "[RiftAhkPost] Background EXE: $BackgroundExe"
Write-Host "[RiftAhkPost] Verify file   : $resolvedVerifyFilePath"
Write-Host "[RiftAhkPost] Command       : $Command"
Write-Host "[RiftAhkPost] Baseline UTC  : $($baselineUtc.ToString('yyyy-MM-ddTHH:mm:ss.fffffffZ'))"

$argumentList = @(
    Quote-ProcessArgument -Value $scriptPath
    Quote-ProcessArgument -Value $Command
    Quote-ProcessArgument -Value $TargetExe
    Quote-ProcessArgument -Value $BackgroundExe
) -join ' '

$process = Start-Process -FilePath $autoHotkeyExe -ArgumentList $argumentList -PassThru

$updatedFile = Wait-ForTimestampAdvance -PreferredPath $resolvedVerifyFilePath -BaselineUtc $baselineUtc -TimeoutSeconds $AttemptTimeoutSeconds

if ($updatedFile) {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }

    Write-Host "[RiftAhkPost] SUCCESS"
    Write-Host "[RiftAhkPost] Updated file  : $($updatedFile.FullName)"
    Write-Host "[RiftAhkPost] Updated UTC   : $($updatedFile.LastWriteTimeUtc.ToString('yyyy-MM-ddTHH:mm:ss.fffffffZ'))"
    exit 0
}

if (-not $process.HasExited) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    throw "AutoHotkey helper did not finish and no verification file update was observed."
}

if ($process.ExitCode -ne 0) {
    throw "AutoHotkey helper exited with code $($process.ExitCode)."
}

throw "No verification file update was observed after the AutoHotkey PostMessage command."
