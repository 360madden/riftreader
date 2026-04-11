# Scan ALL Rift memory for pointers to selected-source
# Then check each candidate for container at +0x78

$rift = Get-Process -Name rift_x64 -ErrorAction SilentlyContinue
if (-not $rift) { Write-Host "RIFT not running"; exit }

Add-Type @"
using System;
using System.Runtime.InteropServices;

public class Mem {
    [DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int dwDesiredAccess, bool bInheritHandle, int dwProcessId);
    [DllImport("kernel32.dll")] public static extern bool ReadProcessMemory(IntPtr hProcess, IntPtr lpBaseAddress, byte[] lpBuffer, int nSize, IntPtr lpNumberOfBytesRead);
    [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr hObject);
    [DllImport("kernel32.dll")] public static extern int VirtualQueryEx(IntPtr hProcess, IntPtr lpAddress, ref MEMORY_BASIC_INFORMATION lpBuffer, int dwLength);
    
    [StructLayout(LayoutKind.Sequential)]
    public struct MEMORY_BASIC_INFORMATION {
        public IntPtr BaseAddress;
        public IntPtr AllocationBase;
        public int AllocationProtect;
        public int RegionSize;
        public int State;
        public int Protect;
        public int Type;
    }
}
"@

$hProcess = [Mem]::OpenProcess(0x1F0, $false, $rift.Id)
$selectedSource = 0x1578D4F9910

Write-Host "Scanning memory for pointers to selected-source (0x$($selectedSource.ToString('X')))..."

$searchBuffer = [BitConverter]::GetBytes([Int64]$selectedSource)
$matches = 0
$owners = @()

# Enumerate all memory regions and scan
$addr = [IntPtr]::Zero
$mbi = New-Object Mem+MEMORY_BASIC_INFORMATION

for ($i = 0; $i -lt 10000; $i++) {
    $result = [Mem]::VirtualQueryEx($hProcess, $addr, [ref]$mbi, [System.Runtime.InteropServices.Marshal]::SizeOf($mbi))
    if ($result -eq 0) { break }
    
    # Only scan committed, readable, non-huge regions
    if ($mbi.State -eq 0x1000 -and $mbi.Protect -gt 0 -and $mbi.RegionSize -lt 0x10000000) {
        $regionBuffer = New-Object byte[] $mbi.RegionSize
        $success = [Mem]::ReadProcessMemory($hProcess, $addr, $regionBuffer, $mbi.RegionSize, [IntPtr]::Zero)
        
        if ($success) {
            # Scan for our pointer
            for ($offset = 0; $offset -lt $mbi.RegionSize - 8; $offset += 4) {
                if ($regionBuffer[$offset] -eq $searchBuffer[0] -and $regionBuffer[$offset+1] -eq $searchBuffer[1] -and 
                    $regionBuffer[$offset+2] -eq $searchBuffer[2] -and $regionBuffer[$offset+3] -eq $searchBuffer[3] -and
                    $regionBuffer[$offset+4] -eq $searchBuffer[4] -and $regionBuffer[$offset+5] -eq $searchBuffer[5] -and
                    $regionBuffer[$offset+6] -eq $searchBuffer[6] -and $regionBuffer[$offset+7] -eq $searchBuffer[7]) {
                    
                    $foundAddr = [Int64]$addr + $offset
                    Write-Host "Found pointer at 0x$($foundAddr.ToString('X'))"
                    $matches++
                    
                    # Check if this is the owner by looking for container at +0x78
                    $containerBuffer = New-Object byte[] 24
                    [Mem]::ReadProcessMemory($hProcess, [IntPtr]($foundAddr + 0x78), $containerBuffer, 24, [IntPtr]::Zero) | Out-Null
                    $containerPtr = [BitConverter]::ToInt64($containerBuffer, 0)
                    $containerCount = [BitConverter]::ToInt32($containerBuffer, 8)
                    
                    if ($containerCount -ge 8 -and $containerCount -le 32 -and $containerPtr -gt 0x150000000000) {
                        Write-Host "  ==> OWNER FOUND at 0x$($foundAddr.ToString('X')) Container=0x$($containerPtr.ToString('X')) count=$containerCount"
                        $owners += $foundAddr
                        if ($owners.Count -ge 1) { break }
                    }
                    
                    if ($matches -ge 50) { break }
                }
            }
        }
    }
    
    if ($owners.Count -ge 1) { break }
    $addr = [IntPtr]([Int64]$mbi.BaseAddress + $mbi.RegionSize)
}

if ($owners.Count -gt 0) {
    Write-Host "`nSUCCESS! Owner: 0x$($owners[0].ToString('X'))"
    
    # Read container
    $containerBuffer = New-Object byte[] 24
    [Mem]::ReadProcessMemory($hProcess, [IntPtr]($owners[0] + 0x78), $containerBuffer, 24, [IntPtr]::Zero) | Out-Null
    $containerPtr = [BitConverter]::ToInt64($containerBuffer, 0)
    $count = [BitConverter]::ToInt32($containerBuffer, 8)
    
    Write-Host "Container entries: 0x$($containerPtr.ToString('X')) count=$count"
    
    $entriesBuffer = New-Object byte[] ($count * 8)
    [Mem]::ReadProcessMemory($hProcess, [IntPtr]$containerPtr, $entriesBuffer, $entriesBuffer.Length, [IntPtr]::Zero) | Out-Null
    
    for ($i = 0; $i -lt $count; $i++) {
        $entryAddr = [BitConverter]::ToInt64($entriesBuffer, $i * 8)
        Write-Host "  Entry[$i] = 0x$($entryAddr.ToString('X'))"
    }
    
    Write-Host "`n==> Entry 15 = 0x$([BitConverter]::ToInt64($entriesBuffer, 15 * 8).ToString('X'))"
} else {
    Write-Host "Found $matches pointers but no owner found"
}

[Mem]::CloseHandle($hProcess)