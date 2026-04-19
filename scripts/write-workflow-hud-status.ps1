[CmdletBinding()]
param(
    [ValidateSet('active', 'waiting', 'blocked', 'idle')]
    [string]$State = 'idle',
    [string]$Action = 'waiting for status',
    [ValidateRange(3, 300)]
    [int]$StaleAfterSeconds = 8,
    [string]$StatusFile = (Join-Path (Join-Path $PSScriptRoot '..') 'debug\workflow-hud-status.json'),
    [switch]$Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$resolvedStatusFile = [System.IO.Path]::GetFullPath($StatusFile)
$directory = Split-Path -Parent $resolvedStatusFile
if (-not [string]::IsNullOrWhiteSpace($directory)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

$utcNow = [DateTimeOffset]::UtcNow
$normalizedAction = if ([string]::IsNullOrWhiteSpace($Action)) {
    if ($State -eq 'idle') { 'idle' } else { 'working' }
}
else {
    $Action.Trim()
}

$existingDocument = $null
if (Test-Path -LiteralPath $resolvedStatusFile) {
    try {
        $existingDocument = Get-Content -LiteralPath $resolvedStatusFile -Raw -Encoding UTF8 | Microsoft.PowerShell.Utility\ConvertFrom-Json -Depth 10
    }
    catch {
        $existingDocument = $null
    }
}

$previousLastMessage = if ($null -ne $existingDocument -and $existingDocument.PSObject.Properties['lastMessage']) {
    [string]$existingDocument.lastMessage
}
else {
    $null
}

$previousLastMessageAtUtc = if ($null -ne $existingDocument -and $existingDocument.PSObject.Properties['lastMessageAtUtc']) {
    [string]$existingDocument.lastMessageAtUtc
}
else {
    $null
}

$shouldUpdateLastMessage = -not [string]::IsNullOrWhiteSpace($normalizedAction) -and $normalizedAction -notin @('idle', 'waiting for status')
$lastMessage = if ($shouldUpdateLastMessage) { $normalizedAction } else { $previousLastMessage }
$lastMessageAtUtc = if ($shouldUpdateLastMessage) {
    $utcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
}
else {
    $previousLastMessageAtUtc
}

$document = [ordered]@{
    state        = $State
    action       = $normalizedAction
    updatedAtUtc = $utcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    staleAfterSeconds = $StaleAfterSeconds
    lastMessage = $lastMessage
    lastMessageAtUtc = $lastMessageAtUtc
}

$json = $document | Microsoft.PowerShell.Utility\ConvertTo-Json -Depth 5
$tempFile = '{0}.tmp' -f $resolvedStatusFile
Set-Content -LiteralPath $tempFile -Value $json -Encoding UTF8
Move-Item -LiteralPath $tempFile -Destination $resolvedStatusFile -Force

if (-not $Quiet) {
    Write-Host ("Workflow HUD status updated: {0} | {1}" -f $State, $normalizedAction)
    Write-Host ("Status file: {0}" -f $resolvedStatusFile)
}
