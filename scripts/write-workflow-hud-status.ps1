[CmdletBinding()]
param(
    [ValidateSet('active', 'waiting', 'blocked', 'idle')]
    [string]$State = 'idle',
    [string]$Action = 'waiting for status',
    [string]$StatusFile = (Join-Path (Join-Path $PSScriptRoot '..') 'debug\workflow-hud-status.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$resolvedStatusFile = [System.IO.Path]::GetFullPath($StatusFile)
$directory = Split-Path -Parent $resolvedStatusFile
if (-not [string]::IsNullOrWhiteSpace($directory)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

$document = [ordered]@{
    state        = $State
    action       = $Action
    updatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
}

$json = $document | Microsoft.PowerShell.Utility\ConvertTo-Json -Depth 5
$tempFile = '{0}.tmp' -f $resolvedStatusFile
Set-Content -LiteralPath $tempFile -Value $json -Encoding UTF8
Move-Item -LiteralPath $tempFile -Destination $resolvedStatusFile -Force

Write-Host ("Workflow HUD status updated: {0} | {1}" -f $State, $Action)
Write-Host ("Status file: {0}" -f $resolvedStatusFile)
