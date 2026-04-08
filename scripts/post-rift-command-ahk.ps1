[CmdletBinding()]
param(
    [string]$Command = "/reloadui",
    [string]$TargetExe = "rift_x64.exe",
    [string]$VerifyFilePath = "C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\Saved\rift315.1@gmail.com\Deepwood\Atank\SavedVariables\ReaderBridgeExport.lua",
    [string]$BackgroundExe = "cheatengine-x86_64-SSE4-AVX2.exe",
    [int]$AttemptTimeoutSeconds = 12
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

function Wait-ForTimestampAdvance {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [datetime]$BaselineUtc,

        [Parameter(Mandatory = $true)]
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).ToUniversalTime().AddSeconds($TimeoutSeconds)
    do {
        $currentUtc = Get-FileTimestampUtc -Path $Path
        if ($currentUtc -gt $BaselineUtc) {
            return $currentUtc
        }

        Start-Sleep -Milliseconds 250
    }
    while ((Get-Date).ToUniversalTime() -lt $deadline)

    return $null
}

$scriptPath = "C:\RIFT MODDING\RiftReader\scripts\post-rift-command-ahk.ahk"
$autoHotkeyExe = Find-AutoHotkeyExe
$baselineUtc = Get-FileTimestampUtc -Path $VerifyFilePath

Write-Host "[RiftAhkPost] AutoHotkey    : $autoHotkeyExe"
Write-Host "[RiftAhkPost] Script        : $scriptPath"
Write-Host "[RiftAhkPost] Target EXE    : $TargetExe"
Write-Host "[RiftAhkPost] Background EXE: $BackgroundExe"
Write-Host "[RiftAhkPost] Command       : $Command"
Write-Host "[RiftAhkPost] Baseline UTC  : $($baselineUtc.ToString('yyyy-MM-ddTHH:mm:ss.fffffffZ'))"

$argumentList = @(
    Quote-ProcessArgument -Value $scriptPath
    Quote-ProcessArgument -Value $Command
    Quote-ProcessArgument -Value $TargetExe
    Quote-ProcessArgument -Value $BackgroundExe
) -join ' '

$process = Start-Process -FilePath $autoHotkeyExe -ArgumentList $argumentList -PassThru

$updatedUtc = Wait-ForTimestampAdvance -Path $VerifyFilePath -BaselineUtc $baselineUtc -TimeoutSeconds $AttemptTimeoutSeconds

if ($updatedUtc) {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }

    Write-Host "[RiftAhkPost] SUCCESS"
    Write-Host "[RiftAhkPost] Updated UTC   : $($updatedUtc.ToString('yyyy-MM-ddTHH:mm:ss.fffffffZ'))"
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
