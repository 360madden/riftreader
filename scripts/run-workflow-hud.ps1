[CmdletBinding()]
param(
    [string]$StatusFile = (Join-Path (Join-Path $PSScriptRoot '..') 'debug\workflow-hud-status.json'),
    [string]$ConfigFile = (Join-Path (Join-Path $PSScriptRoot '..') 'debug\workflow-hud-config.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$projectPath = Join-Path $repoRoot 'tools\RiftReader.WorkflowHud\RiftReader.WorkflowHud.csproj'
$resolvedStatusFile = [System.IO.Path]::GetFullPath($StatusFile)
$resolvedConfigFile = [System.IO.Path]::GetFullPath($ConfigFile)

if (-not (Test-Path -LiteralPath $projectPath)) {
    throw "Workflow HUD project not found: $projectPath"
}

& dotnet run --project $projectPath -- --status-file $resolvedStatusFile --config-file $resolvedConfigFile
