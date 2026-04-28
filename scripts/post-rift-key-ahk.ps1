[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Key,
    [int]$HoldMilliseconds = 250,
    [string]$TargetExe = 'rift_x64.exe',
    [int]$TargetProcessId,
    [string]$TargetWindowHandle
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Find-AutoHotkeyExe {
    $candidates = @(
        'C:\Users\mrkoo\AppData\Local\Programs\AutoHotkey\v2\AutoHotkey64.exe',
        'C:\Users\mrkoo\AppData\Local\Programs\AutoHotkey\v2\AutoHotkey32.exe',
        'C:\Program Files\AutoHotkey\AutoHotkey64.exe',
        'C:\Program Files\AutoHotkey\AutoHotkey32.exe'
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    throw 'AutoHotkey v2 executable was not found.'
}

function Quote-ProcessArgument {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Value
    )

    return '"' + ($Value -replace '"', '\"') + '"'
}

$autoHotkeyExe = Find-AutoHotkeyExe
$scriptPath = Join-Path $PSScriptRoot 'post-rift-key-ahk.ahk'
if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "AutoHotkey key script was not found: $scriptPath"
}

$argumentList = @(
    Quote-ProcessArgument -Value $scriptPath
    Quote-ProcessArgument -Value $Key
    Quote-ProcessArgument -Value $HoldMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture)
    Quote-ProcessArgument -Value $TargetExe
    Quote-ProcessArgument -Value $TargetWindowHandle
    Quote-ProcessArgument -Value ([string]$TargetProcessId)
) -join ' '

$process = Start-Process -FilePath $autoHotkeyExe -ArgumentList $argumentList -PassThru -Wait
exit $process.ExitCode
