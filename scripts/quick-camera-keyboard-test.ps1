# EXPERIMENTAL PROBE: ultra-simple keyboard/candidate memory test.
# Prefer send-rift-key.ps1 plus Run-CameraDiscoveryStable.ps1 for the supported workflow.
# Ultra Simple Camera Test

$ErrorActionPreference = 'Stop'
$repoRoot = 'C:\RIFT MODDING\RiftReader'
$readerProj = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'

# Helper function to extract JSON
function Get-JsonOutput {
    param([string[]]$Args)
    $out = & dotnet run --project $readerProj -- @Args 2>&1
    # Find line starting with { and extract from there
    $start = $out | Where-Object { $_ -match '^\s*\{' } | Select-Object -First 1
    if ($start) {
        $rest = $out | Where-Object { $_ -match '^\s*[\}\]]' } | Select-Object -First 1
        if ($rest) {
            $idx = [Array]::IndexOf($out, $rest)
            $jsonLines = $out[0..$idx] -join "`n"
            return $jsonLines | ConvertFrom-Json
        }
    }
    return $null
}

Write-Host "Step 1: Get player state" -ForegroundColor Cyan
$player = Get-JsonOutput --process-name rift_x64, --read-player-current, --json
Write-Host "Anchor: $($player.Memory.AddressHex)"

Write-Host "`nStep 2: Get owner address from trace" -ForegroundColor Cyan
$trace = Get-Content 'C:\RIFT MODDING\RiftReader\scripts\captures\player-selector-owner-trace.json' | ConvertFrom-Json
$ownerAddr = [UInt64]::Parse($trace.Owner.ObjectAddress.Substring(2), [System.Globalization.NumberStyles]::HexNumber)
Write-Host "Owner: $($trace.Owner.ObjectAddress)"

Write-Host "`nStep 3: Read owner+0xD0" -ForegroundColor Cyan
$r1 = Get-JsonOutput --process-name rift_x64, --address, "0x$($ownerAddr.ToString('X'))", --length, 240, --json
$hex1 = $r1.BytesHex -replace ' ', ''
$wrapper = [UInt64]::Parse($hex1.Substring(416,16), [System.Globalization.NumberStyles]::HexNumber)
Write-Host "Wrapper: 0x$($hex1.Substring(416,16))"

Write-Host "`nStep 4: Read wrapper+0x100" -ForegroundColor Cyan
$r2 = Get-JsonOutput --process-name rift_x64, --address, "0x$($wrapper.ToString('X'))", --length, 400, --json
$hex2 = $r2.BytesHex -replace ' ', ''
$candidate = [UInt64]::Parse($hex2.Substring(512,16), [System.Globalization.NumberStyles]::HexNumber)
Write-Host "Candidate: 0x$($hex2.Substring(512,16))"

Write-Host "`nStep 5: Read BEFORE candidate+0xA0" -ForegroundColor Cyan
$rb = Get-JsonOutput --process-name rift_x64, --address, "0x$((($candidate + 0xA0)).ToString('X'))", --length, 64, --json
$beforeHex = $rb.BytesHex -replace ' ', ''
Write-Host "Before: $beforeHex"

Write-Host "`nStep 6: Send 'A' key" -ForegroundColor Yellow
Add-Type "using System; using System.Runtime.InteropServices; public class K {[DllImport(`"user32.dll`")] public static extern IntPtr FindWindow(string c, string n); [DllImport(`"user32.dll`")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l); public const uint WM_KEYDOWN = 0x0100; public const uint WM_KEYUP = 0x0101;}"
$h = [K]::FindWindow("TWNClientFramework", "Rift")
[K]::PostMessage($h, [K]::WM_KEYDOWN, [IntPtr]0x41, [IntPtr]::MakeInt32(0,30)) | Out-Null
Start-Sleep -Milliseconds 300
[K]::PostMessage($h, [K]::WM_KEYUP, [IntPtr]0x41, [IntPtr]::MakeInt32(0,30)) | Out-Null
Write-Host "Sent"

Start-Sleep -Milliseconds 800

Write-Host "`nStep 7: Read AFTER candidate+0xA0" -ForegroundColor Cyan
$ra = Get-JsonOutput --process-name rift_x64, --address, "0x$((($candidate + 0xA0)).ToString('X'))", --length, 64, --json
$afterHex = $ra.BytesHex -replace ' ', ''
Write-Host "After: $afterHex"

Write-Host "`n=== RESULT ===" -ForegroundColor Cyan
if ($beforeHex -eq $afterHex) {
    Write-Host "NO CHANGE at candidate+0xA0" -ForegroundColor Red
} else {
    Write-Host "CHANGED!" -ForegroundColor Green
    0..31 | ForEach-Object {
        $b = $beforeHex.Substring($_*2,2)
        $a = $afterHex.Substring($_*2,2)
        if ($b -ne $a) { Write-Host "  +0x$($_.ToString('X2')): $b -> $a" }
    }
}
