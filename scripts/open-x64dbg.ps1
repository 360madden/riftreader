[CmdletBinding()]
param(
    [switch]$PrintSafetyOnly,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$LauncherArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$pythonArgs = @()
if ($PrintSafetyOnly) {
    $pythonArgs += '--print-safety-only'
}
if ($LauncherArgs) {
    $pythonArgs += $LauncherArgs
}

& python (Join-Path $PSScriptRoot 'x64dbg_launcher.py') @pythonArgs
exit $LASTEXITCODE
