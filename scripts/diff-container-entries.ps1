[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$readerProject = Join-Path $scriptDir '..' 'reader' 'RiftReader.Reader' 'RiftReader.Reader.csproj'
$keyScript = Join-Path $scriptDir 'post-rift-key.ps1'

Write-Host "=== Differential Container Entry Test ===" -ForegroundColor Cyan
Write-Host "Turn player and see which container entries change" -ForegroundColor Yellow
Write-Host ""

# Load component list
$componentsFile = Join-Path $scriptDir 'captures' 'player-owner-components.json'
$components = Get-Content $componentsFile -Raw | ConvertFrom-Json -Depth 30

# Interesting entries to test (those with camera-like data)
$testEntries = @(1, 2, 3, 4, 6, 12, 13, 14, 15)

function Dump-Entry($addr) {
    $output = & dotnet run --project $readerProject --configuration Release -- `
        --process-name rift_x64 --address $addr --length 512 --json 2>&1

    $jLines = @()
    $jStart = $false
    foreach ($line in $output) {
        if ($line -match '^\{') { $jStart = $true }
        if ($jStart) { $jLines += $line }
    }

    $dump = ($jLines -join "`n") | ConvertFrom-Json -Depth 30
    $hex = $dump.BytesHex -replace ' ', ''
    $bytes = [byte[]]::new($hex.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [Convert]::ToByte($hex.Substring($i * 2, 2), 16)
    }
    return $bytes
}

# BEFORE snapshot
Write-Host "Capturing BEFORE snapshots..." -ForegroundColor Yellow
$beforeMap = @{}
foreach ($idx in $testEntries) {
    $addr = $components.Entries[$idx].Address
    Write-Host "  Entry $idx [$addr]..." -NoNewline -ForegroundColor Gray
    $beforeMap[$idx] = Dump-Entry $addr
    Write-Host " done" -ForegroundColor DarkGray
}

# Turn player right
Write-Host ""
Write-Host "Turning player RIGHT (6x D key for ~270 degree turn)..." -ForegroundColor Yellow
for ($i = 0; $i -lt 6; $i++) {
    & $keyScript -Key D
    Start-Sleep -Milliseconds 250
}
Start-Sleep -Milliseconds 1500

# AFTER snapshot
Write-Host ""
Write-Host "Capturing AFTER snapshots..." -ForegroundColor Yellow
$afterMap = @{}
foreach ($idx in $testEntries) {
    $addr = $components.Entries[$idx].Address
    Write-Host "  Entry $idx [$addr]..." -NoNewline -ForegroundColor Gray
    $afterMap[$idx] = Dump-Entry $addr
    Write-Host " done" -ForegroundColor DarkGray
}

# Compare
Write-Host ""
Write-Host "=== Results ===" -ForegroundColor Cyan
Write-Host ""

foreach ($idx in $testEntries) {
    $before = $beforeMap[$idx]
    $after = $afterMap[$idx]
    $addr = $components.Entries[$idx].Address
    $roles = $components.Entries[$idx].RoleHints -join ', '

    $changedOffsets = @()
    $minLen = [Math]::Min($before.Length, $after.Length)

    for ($off = 0; $off -lt ($minLen - 3); $off += 4) {
        $bVal = [BitConverter]::ToSingle($before, $off)
        $aVal = [BitConverter]::ToSingle($after, $off)

        if ([float]::IsNaN($bVal) -or [float]::IsNaN($aVal)) { continue }
        if ([float]::IsInfinity($bVal) -or [float]::IsInfinity($aVal)) { continue }

        $delta = $aVal - $bVal
        if ([Math]::Abs($delta) -gt 0.001) {
            $changedOffsets += [ordered]@{
                Offset = '+0x{0:X3}' -f $off
                Before = [Math]::Round($bVal, 4)
                After = [Math]::Round($aVal, 4)
                Delta = [Math]::Round($delta, 4)
            }
        }
    }

    if ($changedOffsets.Count -gt 0) {
        Write-Host "Entry $idx [$addr] roles=[$roles] — $($changedOffsets.Count) CHANGED offsets" -ForegroundColor Green
        foreach ($c in $changedOffsets) {
            Write-Host "  $($c.Offset): $($c.Before) -> $($c.After) (delta=$($c.Delta))" -ForegroundColor White
        }
    } else {
        Write-Host "Entry $idx [$addr] roles=[$roles] — NO CHANGES" -ForegroundColor DarkGray
    }
    Write-Host ""
}
