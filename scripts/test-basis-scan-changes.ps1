[CmdletBinding()]
param(
    [string]$OwnerAddress = '0x1576A38AA10',
    [int]$KeyPresses = 4,
    [int]$KeyHoldMs = 400,
    [int]$PostKeyWaitMs = 1500,
    [string]$Key = 'LEFT'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class ScanMemory {
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool ReadProcessMemory(
        IntPtr hProcess, IntPtr lpBaseAddress, byte[] lpBuffer,
        int nSize, out IntPtr lpNumberOfBytesRead);

    public static long ReadPointer(IntPtr processHandle, long address) {
        byte[] buf = new byte[8];
        IntPtr read;
        if (!ReadProcessMemory(processHandle, (IntPtr)address, buf, 8, out read))
            return 0;
        return BitConverter.ToInt64(buf, 0);
    }

    public static byte[] ReadBytes(IntPtr processHandle, long address, int size) {
        byte[] buf = new byte[size];
        IntPtr read;
        if (!ReadProcessMemory(processHandle, (IntPtr)address, buf, buf.Length, out read))
            return null;
        return buf;
    }
}
"@

function Parse-HexAddress([string]$s) {
    if ($s -match '^0x([0-9A-Fa-f]+)$') {
        return [long]::Parse($Matches[1], [System.Globalization.NumberStyles]::HexNumber)
    }
    return [long]::Parse($s, [System.Globalization.NumberStyles]::HexNumber)
}

$ownerAddr = Parse-HexAddress $OwnerAddress
$riftProcess = Get-Process -Name "rift_x64" -ErrorAction Stop | Select-Object -First 1
$handle = $riftProcess.Handle

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Scan Objects For Any Changed Floats" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# Walk the chain
$step1Ptr = [ScanMemory]::ReadPointer($handle, $ownerAddr + 0xD0)
$step2Ptr = [ScanMemory]::ReadPointer($handle, $step1Ptr + 0x100)

Write-Host ("Owner:  0x{0:X}" -f $ownerAddr)
Write-Host ("Step1:  0x{0:X} (owner+0xD0)" -f $step1Ptr)
Write-Host ("Step2:  0x{0:X} (step1+0x100)" -f $step2Ptr)

# Define objects to scan: read 512 bytes from each
$objects = @(
    @{ Name = "Step1"; Addr = $step1Ptr; Size = 512 }
    @{ Name = "Step2"; Addr = $step2Ptr; Size = 512 }
    @{ Name = "SelectedSource"; Addr = (Parse-HexAddress '0x1577AC2FB60'); Size = 512 }
)

# Also scan any pointers at step1+0x80..0x180 that look like heap objects
Write-Host ""
Write-Host "Finding additional pointer targets from Step1..." -ForegroundColor Yellow
$step1Bytes = [ScanMemory]::ReadBytes($handle, $step1Ptr, 0x200)
$extraTargets = @{}
if ($null -ne $step1Bytes) {
    for ($off = 0; $off -le 0x1F8; $off += 8) {
        $ptr = [BitConverter]::ToInt64($step1Bytes, $off)
        if ($ptr -gt 0x100000000 -and $ptr -lt 0x7FFFFFFFFFFF -and $ptr -ne $step1Ptr -and $ptr -ne $step2Ptr -and $ptr -ne $ownerAddr) {
            $ptrKey = "0x{0:X}" -f $ptr
            if (-not $extraTargets.ContainsKey($ptrKey)) {
                $extraTargets[$ptrKey] = $off
                $objects += @{ Name = "Step1+0x$($off.ToString('X'))=>0x$($ptr.ToString('X'))"; Addr = $ptr; Size = 512 }
            }
        }
    }
}
Write-Host ("  Found {0} additional pointer targets" -f $extraTargets.Count)

# BEFORE snapshot
Write-Host ""
Write-Host ("--- BEFORE: Capturing {0} objects ---" -f $objects.Count) -ForegroundColor Yellow
$beforeSnapshots = @()
foreach ($obj in $objects) {
    $bytes = [ScanMemory]::ReadBytes($handle, $obj.Addr, $obj.Size)
    $beforeSnapshots += @{ Name = $obj.Name; Addr = $obj.Addr; Size = $obj.Size; Bytes = $bytes }
}

# SEND KEYS
Write-Host ""
Write-Host "--- SENDING $KeyPresses x '$Key' ---" -ForegroundColor Yellow
$scriptRoot = $PSScriptRoot
for ($i = 1; $i -le $KeyPresses; $i++) {
    & "$scriptRoot\post-rift-key.ps1" -Key $Key -HoldMilliseconds $KeyHoldMs -SkipBackgroundFocus
    if ($i -lt $KeyPresses) { Start-Sleep -Milliseconds 250 }
}
Start-Sleep -Milliseconds $PostKeyWaitMs

# AFTER snapshot
Write-Host ""
Write-Host "--- AFTER: Capturing objects ---" -ForegroundColor Yellow
$afterSnapshots = @()
foreach ($obj in $objects) {
    $bytes = [ScanMemory]::ReadBytes($handle, $obj.Addr, $obj.Size)
    $afterSnapshots += @{ Name = $obj.Name; Addr = $obj.Addr; Size = $obj.Size; Bytes = $bytes }
}

# COMPARE
Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  CHANGES DETECTED" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

for ($idx = 0; $idx -lt $objects.Count; $idx++) {
    $before = $beforeSnapshots[$idx]
    $after = $afterSnapshots[$idx]

    if ($null -eq $before.Bytes -or $null -eq $after.Bytes) {
        Write-Host ""
        Write-Host ("{0} (0x{1:X}): UNREADABLE" -f $before.Name, $before.Addr) -ForegroundColor Red
        continue
    }

    $changedOffsets = @()
    for ($b = 0; $b -lt $before.Size; $b++) {
        if ($before.Bytes[$b] -ne $after.Bytes[$b]) {
            $changedOffsets += $b
        }
    }

    if ($changedOffsets.Count -eq 0) {
        # skip silent objects
        continue
    }

    Write-Host ""
    Write-Host ("{0} (0x{1:X}): {2} bytes changed" -f $before.Name, $before.Addr, $changedOffsets.Count) -ForegroundColor Green

    # Group into float-aligned changes and show float values
    $floatOffsets = $changedOffsets | ForEach-Object { [Math]::Floor($_ / 4) * 4 } | Sort-Object -Unique
    foreach ($foff in $floatOffsets) {
        if ($foff + 4 -le $before.Size) {
            $bVal = [BitConverter]::ToSingle($before.Bytes, $foff)
            $aVal = [BitConverter]::ToSingle($after.Bytes, $foff)
            $delta = $aVal - $bVal
            $color = if ([Math]::Abs($delta) -gt 0.001) { 'Cyan' } else { 'Gray' }
            Write-Host ("  +0x{0:X3}: {1,12:F6} -> {2,12:F6}  (delta {3:F6})" -f [int]$foff, $bVal, $aVal, $delta) -ForegroundColor $color
        }
    }
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "Done." -ForegroundColor Green

exit 0
