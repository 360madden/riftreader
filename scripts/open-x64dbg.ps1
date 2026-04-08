[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$exePath = 'C:\RIFT MODDING\RiftReader\tools\reverse-engineering\x64dbg\release\x64\x64dbg.exe'
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "x64dbg was not found at '$exePath'. Run C:\RIFT MODDING\RiftReader\tools\reverse-engineering\install-tools.ps1 first."
}

Start-Process -FilePath $exePath | Out-Null
Write-Host "[x64dbg] Launched: $exePath"
