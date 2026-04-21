[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Key,
    [int]$HoldMilliseconds = 250,
    [string]$TargetExe = "rift_x64.exe",
    [switch]$NoRefocus
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

$scriptPath = Join-Path $PSScriptRoot 'send-rift-key-ahk.ahk'
$autoHotkeyExe = Find-AutoHotkeyExe

Write-Host "[RiftAhkKey] AutoHotkey : $autoHotkeyExe"
Write-Host "[RiftAhkKey] Script     : $scriptPath"
Write-Host "[RiftAhkKey] Target EXE : $TargetExe"
Write-Host "[RiftAhkKey] Key        : $Key"
Write-Host "[RiftAhkKey] Hold ms    : $HoldMilliseconds"
Write-Host "[RiftAhkKey] NoRefocus  : $NoRefocus"

$argumentList = @(
    Quote-ProcessArgument -Value $scriptPath
    Quote-ProcessArgument -Value $Key
    Quote-ProcessArgument -Value ([string]$HoldMilliseconds)
    Quote-ProcessArgument -Value $TargetExe
    Quote-ProcessArgument -Value $(if ($NoRefocus) { "1" } else { "0" })
) -join ' '

$process = Start-Process -FilePath $autoHotkeyExe -ArgumentList $argumentList -PassThru -Wait
if ($process.ExitCode -ne 0) {
    throw "AutoHotkey key helper exited with code $($process.ExitCode)."
}

Write-Host "[RiftAhkKey] SUCCESS"
exit 0
