[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$candidatePaths = @(
    $env:RIFTREADER_X64DBG_EXE,
    'C:\RIFT MODDING\Tools\x64dbg\release\x64\x64dbg.exe',
    'C:\RIFT MODDING\RiftReader\tools\reverse-engineering\x64dbg\release\x64\x64dbg.exe'
) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

$exePath = $candidatePaths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $exePath) {
    $candidateText = ($candidatePaths | ForEach-Object { "  - $_" }) -join [Environment]::NewLine
    throw "x64dbg was not found. Checked:$([Environment]::NewLine)$candidateText"
}

Start-Process -FilePath $exePath | Out-Null
Write-Host "[x64dbg] Launched: $exePath"
