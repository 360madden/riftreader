[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$exePath = 'C:\RIFT MODDING\RiftReader\tools\reverse-engineering\ReClass.NET\x64\ReClass.NET.exe'
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "ReClass.NET was not found at '$exePath'. Run C:\RIFT MODDING\RiftReader\tools\reverse-engineering\install-tools.ps1 first."
}

Start-Process -FilePath $exePath | Out-Null
Write-Host "[ReClass] Launched: $exePath"
