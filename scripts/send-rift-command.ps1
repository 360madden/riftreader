[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$ChatCommand,

    [string]$ProcessName = "rift_x64",
    [int]$HoldMilliseconds = 80,
    [int]$FocusDelayMilliseconds = 200,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$postCommandScript = Join-Path $PSScriptRoot 'post-rift-command.ps1'

if ($Help) {
    Write-Host "Usage: send-rift-command.ps1 -ChatCommand <command> [-ProcessName <name>] [-HoldMilliseconds <ms>] [-FocusDelayMilliseconds <ms>] [-Help]"
    Write-Host ""
    Write-Host "Parameters:"
    Write-Host "  -ChatCommand                The chat command to send to Rift (e.g., '/reloadui', '/help')"
    Write-Host "  -ProcessName                Target process name (default: 'rift_x64')"
    Write-Host "  -HoldMilliseconds           Compatibility knob; mapped to the native helper inter-key delay"
    Write-Host "  -FocusDelayMilliseconds     Delay after focusing the window (default: 200)"
    Write-Host "  -Help                       Display this help message"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\send-rift-command.ps1 -ChatCommand '/reloadui'"
    Write-Host "  .\send-rift-command.ps1 -ChatCommand '/test' -ProcessName 'rift_x64' -HoldMilliseconds 100"
    exit 0
}

if ([string]::IsNullOrWhiteSpace($ChatCommand)) {
    Write-Error "ChatCommand parameter is required. Use -Help for usage information."
    exit 1
}

try {
    $arguments = @{
        Command = $ChatCommand
        TargetProcessName = $ProcessName
        FocusSettleMilliseconds = $FocusDelayMilliseconds
        InterKeyDelayMilliseconds = [Math]::Max(10, [int]$HoldMilliseconds)
        RequireTargetFocus = $true
        SkipVerify = $true
    }

    & $postCommandScript @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Focused PostMessage command helper failed (`$LASTEXITCODE=$LASTEXITCODE)."
    }
}
catch {
    Write-Error "Failed to send command '$ChatCommand': $_"
    exit 1
}
