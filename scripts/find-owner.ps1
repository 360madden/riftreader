# Find owner: narrow scan around selected-source
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
$objectAtB0 = $selectedSource + 0xB0

Write-Host "Scanning for owner of object at 0x$($objectAtB0.ToString('X'))..."

# Scan a larger range from objectAtB0 - but only check pointers for container
$searchBytes = [BitConverter]::GetBytes([Int64]$objectAtB0)

for ($offset = -0x10000; $offset -le 0x1000; $offset += 8) {
    $scanAddr = [Int64]$objectAtB0 + $offset
    if ($scanAddr -lt 0x150000000000) { continue }
    
    $buffer = New-Object byte[] 8
    [Mem]::ReadProcessMemory($hProcess, [IntPtr]$scanAddr, $buffer, 8, [IntPtr]::Zero) | Out-Null
    $ptr = [BitConverter]::ToInt64($buffer, 0)
    
    # Check if ptr points to container (pointer to pointer array, count)
    if ($ptr -gt 0x150000000000) {
        $containerCheck = New-Object byte[] 32
        [Mem]::ReadProcessMemory($hProcess, [IntPtr]$ptr, $containerCheck, 32, [IntPtr]::Zero) | Out-Null
        
        $entriesPtr = [BitConverter]::ToInt64($containerCheck, 0)
        $count = [BitConverter]::ToInt32($containerCheck, 8)
        
        if ($count -ge 8 -and $count -le 32 -and $entriesPtr -gt 0x150000000000) {
            Write-Host "FOUND OWNER at offset $offset (0x$([Int64]$scanAddr.ToString('X')))"
            Write-Host "  Container: 0x$($entriesPtr.ToString('X')) count=$count"
            
            $entriesBuffer = New-Object byte[] ($count * 8)
            [Mem]::ReadProcessMemory($hProcess, [IntPtr]$entriesPtr, $entriesBuffer, $entriesBuffer.Length, [IntPtr]::Zero) | Out-Null
            
            for ($i = 0; $i -lt $count; $i++) {
                $entryAddr = [BitConverter]::ToInt64($entriesBuffer, $i * 8)
                Write-Host "  Entry[$i] = 0x$($entryAddr.ToString('X'))"
            }
            
            Write-Host "`n==> ENTRY 15 = 0x$([BitConverter]::ToInt64($entriesBuffer, 15 * 8).ToString('X'))"
            
            [Mem]::CloseHandle($hProcess)
            exit
        }
    }
}

Write-Host "Not found"
[Mem]::CloseHandle($hProcess)