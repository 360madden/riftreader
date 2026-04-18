[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$exePath = 'C:\RIFT MODDING\RiftReader\tools\reverse-engineering\x64dbg\release\x64\x64dbg.exe'
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "x64dbg was not found at '$exePath'. Run C:\RIFT MODDING\RiftReader\tools\reverse-engineering\install-tools.ps1 first."
}

$inspectScript = Join-Path $PSScriptRoot 'inspect-rift-debug-state.ps1'
if (Test-Path -LiteralPath $inspectScript) {
    try {
        & $inspectScript -SummaryOnly
        Write-Host "[x64dbg] If live attach is blocked, use C:\RIFT MODDING\RiftReader\scripts\open-rift-in-x64dbg.cmd to launch a fresh Rift process under x64dbg ownership." -ForegroundColor Yellow
    }
    catch {
        Write-Warning ("Unable to inspect live Rift debug state before launching x64dbg: {0}" -f $_.Exception.Message)
    }
}

Start-Process -FilePath $exePath | Out-Null
Write-Host "[x64dbg] Launched: $exePath"
