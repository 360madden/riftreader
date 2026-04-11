# Find container by scanning wider area around selected-source
# Look for: any pointer to a valid array + count of 16 + capacity >= 16

$rift = Get-Process -Name rift_x64 -ErrorAction SilentlyContinue
if (-not $rift) { Write-Host "RIFT not running"; exit }

Add-Type @"
using System;
using System.Runtime.InteropServices;

public class Mem {
    [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int dwDesiredAccess, bool bInheritHandle, int dwProcessId);
    [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr hProcess, IntPtr lpBaseAddress, byte[] lpBuffer, int nSize, IntPtr lpNumberOfBytesRead);
    [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr hObject);
}
"@

$hProcess = [Mem]::OpenProcess(0x1F0, $false, $rift.Id)

$selectedSource = 0x1578D4F9910
$buffer = New-Object byte[] 24

Write-Host "Scanning for ANY container structure around selected-source..."

# Scan backward more aggressively
$found = $false

for ($offset = -0x5000; $offset -le 0x2000; $offset += 8) {
    $scanAddr = [Int64]$selectedSource + $offset
    if ($scanAddr -lt 0x150000000000) { continue }
    
    $addr = [IntPtr]$scanAddr
    
    $success = [Mem]::ReadProcessMemory($hProcess, $addr, $buffer, 24, [IntPtr]::Zero)
    if ($success) {
        $ptr1 = [BitConverter]::ToInt64($buffer, 0)
        $count = [BitConverter]::ToInt32($buffer, 8)
        $cap = [BitConverter]::ToInt32($buffer, 16)
        
        # Relaxed: count is reasonable (8-32), capacity >= count
        if ($count -ge 8 -and $count -le 32 -and $cap -ge $count -and $ptr1 -gt 0x150000000000 -and $ptr1 -lt 0x160000000000) {
            Write-Host "FOUND at offset $offset (0x$([Int64]$scanAddr.ToString('X')))"
            Write-Host "  Entries: 0x$($ptr1.ToString('X'))"
            Write-Host "  Count: $count, Cap: $cap"
            
            # Read entries
            $entriesBuffer = New-Object byte[] ($count * 8)
            [Mem]::ReadProcessMemory($hProcess, [IntPtr]$ptr1, $entriesBuffer, $entriesBuffer.Length, [IntPtr]::Zero) | Out-Null
            
            for ($i = 0; $i -lt $count; $i++) {
                $entryAddr = [BitConverter]::ToInt64($entriesBuffer, $i * 8)
                if ($entryAddr -gt 0x150000000000) {
                    Write-Host "  Entry[$i] = 0x$($entryAddr.ToString('X'))"
                }
            }
            $found = $true
            break
        }
    }
}

if (-not $found) {
    Write-Host "No container found in that range"
}

[Mem]::CloseHandle($hProcess)