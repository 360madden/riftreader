[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ScriptName,

    [Parameter(Mandatory = $true)]
    [string]$ErrorText,

    [string]$LedgerFile = (Join-Path $PSScriptRoot 'captures\ce-debugger-attach-failures.csv'),
    [string]$StatusFile,
    [string]$DebuggerMode = 'windows debugger',
    [string]$CeProcessName = 'cheatengine*',
    [string]$RiftProcessName = 'rift_x64',
    [string]$Outcome = 'attach-failed',
    [string]$Notes,
    [switch]$CeWasFreshStart,
    [switch]$CeStayedOpen,
    [switch]$CeDetached,
    [switch]$CeCrashed,
    [switch]$CeElevated,
    [switch]$RiftElevated
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$resolvedLedgerFile = [System.IO.Path]::GetFullPath($LedgerFile)
$ledgerDirectory = Split-Path -Parent $resolvedLedgerFile
if (-not [string]::IsNullOrWhiteSpace($ledgerDirectory) -and -not (Test-Path -LiteralPath $ledgerDirectory)) {
    New-Item -ItemType Directory -Path $ledgerDirectory -Force | Out-Null
}

$resolvedStatusFile = $null
$statusFileProduced = $false
if (-not [string]::IsNullOrWhiteSpace($StatusFile)) {
    $resolvedStatusFile = [System.IO.Path]::GetFullPath($StatusFile)
    $statusFileProduced = Test-Path -LiteralPath $resolvedStatusFile
}

$ceProcesses = @(Get-Process | Where-Object { $_.ProcessName -like $CeProcessName })
$riftProcess = Get-Process -Name $RiftProcessName -ErrorAction SilentlyContinue | Select-Object -First 1

$entry = [pscustomobject]@{
    TimestampUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    ScriptName = $ScriptName
    Outcome = $Outcome
    ErrorText = ($ErrorText -replace '[\r\n]+', ' ').Trim()
    DebuggerMode = $DebuggerMode
    CeWasFreshStart = $CeWasFreshStart.IsPresent
    CeStayedOpen = $CeStayedOpen.IsPresent
    CeDetached = $CeDetached.IsPresent
    CeCrashed = $CeCrashed.IsPresent
    CeElevated = $CeElevated.IsPresent
    RiftElevated = $RiftElevated.IsPresent
    CeProcessCount = $ceProcesses.Count
    CeProcessIds = (($ceProcesses | ForEach-Object { $_.Id }) -join ';')
    RiftProcessId = if ($null -ne $riftProcess) { $riftProcess.Id } else { $null }
    StatusFile = $resolvedStatusFile
    StatusFileProduced = $statusFileProduced
    Notes = $Notes
}

$append = Test-Path -LiteralPath $resolvedLedgerFile
$entry | Export-Csv -LiteralPath $resolvedLedgerFile -NoTypeInformation -Append:$append

Write-Host ("[CE Ledger] Appended failure entry to {0}" -f $resolvedLedgerFile) -ForegroundColor Green
if ($statusFileProduced -and -not [string]::IsNullOrWhiteSpace($resolvedStatusFile)) {
    Write-Host ("[CE Ledger] Status file existed: {0}" -f $resolvedStatusFile) -ForegroundColor DarkGray
}
