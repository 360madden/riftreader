# Find ASCII strings near selected-source to identify the object
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

# Read 512 bytes around selected-source
$buffer = New-Object byte[] 512
[Mem]::ReadProcessMemory($hProcess, [IntPtr]($selectedSource - 0x100), $buffer, 512, [IntPtr]::Zero) | Out-Null

# Find ASCII strings
$string = ""
$strings = @()

for ($i = 0; $i -lt $buffer.Length; $i++) {
    $b = $buffer[$i]
    if ($b -ge 32 -and $b -le 126) {
        $string += [char]$b
    } elseif ($string.Length -ge 4) {
        $strings += @{offset=$i-$string.Length-1; str=$string}
        $string = ""
    } else {
        $string = ""
    }
}

foreach ($s in $strings) {
    Write-Host "Offset +$($s.offset): $($s.str)"
}

[Mem]::CloseHandle($hProcess)