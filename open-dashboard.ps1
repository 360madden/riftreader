[CmdletBinding()]
param(
    [switch]$NoOpen,
    [switch]$Live,
    [int]$PollSeconds = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$launcher = Join-Path $PSScriptRoot 'scripts\open-dashboard.ps1'

if (-not (Test-Path -LiteralPath $launcher)) {
    throw "Dashboard launcher was not found: $launcher"
}

& $launcher @PSBoundParameters
exit $LASTEXITCODE
