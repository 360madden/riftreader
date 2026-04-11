# Debug: Get-Json function
$repoRoot = 'C:\RIFT MODDING\RiftReader'
$readerProj = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'

function Get-Json {
    param([string[]]$Args)
    $o = & dotnet run --project $readerProj -- @Args 2>&1
    $lines = $o | Where-Object { $_ -match '"BytesHex"' }
    if ($lines) {
        $hex = $lines[0] -replace '.*": "', '' -replace '".*', ''
        return $hex
    }
    return $null
}

Write-Host "Testing Get-Json..." -ForegroundColor Cyan

$hex1 = Get-Json --process-name, rift_x64, --address, 0x1576A38AA10, --length, 240, --json

Write-Host "Hex length: $($hex1.Length)"
Write-Host "First 50 chars: $($hex1.Substring(0, 50))"
Write-Host "At offset 416 (416-432): $($hex1.Substring(416, 16))"

$wrapperPtr = $hex1.Substring(416, 16)
Write-Host "Wrapper pointer: 0x$wrapperPtr"