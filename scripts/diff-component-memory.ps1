[CmdletBinding()]
param(
    [string]$Label = '',
    [int]$DumpSize = 2048,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$readerProject = Join-Path $PSScriptRoot '..' 'reader' 'RiftReader.Reader' 'RiftReader.Reader.csproj'

function Get-ComponentDump {
    param([string]$DumpLabel)

    $orientJson = & dotnet run --project $readerProject --configuration Release -- --read-player-orientation --json 2>&1
    $orient = $orientJson | ConvertFrom-Json -Depth 30
    $addr = $orient.SelectedSourceAddress

    $dumpJson = & dotnet run --project $readerProject --configuration Release -- --process-name rift_x64 --address $addr --length $DumpSize --json 2>&1
    $dump = $dumpJson | ConvertFrom-Json -Depth 30

    $hex = $dump.BytesHex -replace ' ', ''
    $bytes = [byte[]]::new($hex.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [Convert]::ToByte($hex.Substring($i * 2, 2), 16)
    }

    return @{
        Address = $addr
        Bytes = $bytes
        Label = $DumpLabel
    }
}

Write-Host '=== Component Memory Diff ===' -ForegroundColor Cyan
Write-Host ''

# BEFORE
Write-Host 'Snapshot BEFORE...' -ForegroundColor Yellow
$before = Get-ComponentDump 'before'
Write-Host "  Component: $($before.Address), $($before.Bytes.Length) bytes" -ForegroundColor Green

# Move character
Write-Host 'Moving character (3x W key)...' -ForegroundColor Yellow
$keyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'
& $keyScript -Key W
Start-Sleep -Milliseconds 300
& $keyScript -Key W
Start-Sleep -Milliseconds 300
& $keyScript -Key W
Start-Sleep -Milliseconds 800

# AFTER
Write-Host 'Snapshot AFTER...' -ForegroundColor Yellow
$after = Get-ComponentDump 'after'
Write-Host "  Component: $($after.Address), $($after.Bytes.Length) bytes" -ForegroundColor Green
Write-Host ''

# Diff
Write-Host 'Changed offsets (float comparison, delta > 0.001):' -ForegroundColor Cyan
$changes = @()

$minLen = [Math]::Min($before.Bytes.Length, $after.Bytes.Length)
for ($i = 0; $i -lt $minLen - 3; $i += 4) {
    $bVal = [BitConverter]::ToSingle($before.Bytes, $i)
    $aVal = [BitConverter]::ToSingle($after.Bytes, $i)

    if ([float]::IsNaN($bVal) -or [float]::IsNaN($aVal)) { continue }
    if ([float]::IsInfinity($bVal) -or [float]::IsInfinity($aVal)) { continue }

    $delta = $aVal - $bVal
    if ([Math]::Abs($delta) -gt 0.001) {
        $changes += [ordered]@{
            Offset = '+0x{0:X3}' -f $i
            Before = [Math]::Round($bVal, 4)
            After = [Math]::Round($aVal, 4)
            Delta = [Math]::Round($delta, 4)
        }
        $offsetStr = '+0x' + $i.ToString('X3')
        Write-Host "  $offsetStr  $($bVal.ToString('F4').PadLeft(14)) -> $($aVal.ToString('F4').PadLeft(14))  (delta: $($delta.ToString('F4').PadLeft(10)))" -ForegroundColor White
    }
}

Write-Host ''
Write-Host "Total offsets changed: $($changes.Count)" -ForegroundColor Green

if ($Json) {
    [ordered]@{
        Mode = 'component-memory-diff'
        GeneratedAtUtc = [DateTime]::UtcNow.ToString('o')
        Label = $Label
        ComponentAddress = $before.Address
        DumpSize = $DumpSize
        ChangedOffsets = $changes
    } | ConvertTo-Json -Depth 20
}
