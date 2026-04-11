# Camera Discovery Test - Read memory before/after camera move

$ErrorActionPreference = 'Stop'
$repoRoot = 'C:\RIFT MODDING\RiftReader'
$readerProj = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'

function Get-Json {
    param([string[]]$Args)
    $o = & dotnet run --project $readerProj -- @Args 2>&1
    $j = $o | Where-Object { $_ -match '^\s*\{' } | Select-Object -First 1
    return $j | ConvertFrom-Json
}

Write-Host "=== Get owner from trace ===" -ForegroundColor Cyan
$trace = Get-Content 'C:\RIFT MODDING\RiftReader\scripts\captures\player-selector-owner-trace.json' | ConvertFrom-Json
$ownerAddr = [UInt64]::Parse($trace.Owner.ObjectAddress.Substring(2), [System.Globalization.NumberStyles]::HexNumber)
Write-Host "Owner: $($trace.Owner.ObjectAddress)"

Write-Host "`n=== Read owner+0xD0 (wrapper pointer) ===" -ForegroundColor Cyan
$r1 = Get-Json --process-name, rift_x64, --address, "0x$($ownerAddr.ToString('X'))", --length, 240, --json
$hex1 = $r1.BytesHex -replace ' ', ''
$wrapperPtr = $hex1.Substring(416, 16)
$wrapperAddr = [UInt64]::Parse($wrapperPtr, [System.Globalization.NumberStyles]::HexNumber)
Write-Host "Wrapper: 0x$wrapperPtr"

Write-Host "`n=== Read wrapper+0x100 (candidate pointer) ===" -ForegroundColor Cyan
$r2 = Get-Json --process-name, rift_x64, --address, "0x$($wrapperAddr.ToString('X'))", --length, 400, --json
$hex2 = $r2.BytesHex -replace ' ', ''
$candidatePtr = $hex2.Substring(512, 16)
$candidateAddr = [UInt64]::Parse($candidatePtr, [System.Globalization.NumberStyles]::HexNumber)
Write-Host "Candidate: 0x$candidatePtr"

# === BEFORE ===
Write-Host "`n=== BEFORE camera move: Read candidate+0xA0 ===" -ForegroundColor Green
$rb = Get-Json --process-name, rift_x64, --address, "0x$((($candidateAddr + 0xA0)).ToString('X'))", --length, 64, --json
$beforeHex = $rb.BytesHex -replace ' ', ''
Write-Host "Before: $beforeHex"

Write-Host "`n=== Tell me when ready to move camera ===" -ForegroundColor Yellow