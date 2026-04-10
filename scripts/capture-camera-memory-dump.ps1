[CmdletBinding()]
param(
    [string]$SelectedSourceAddress = '0x1577AC2FB60',
    [string]$Label = '',
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Parse address
$address = if ($SelectedSourceAddress -match '^0x([0-9A-Fa-f]+)$') {
    [UInt64]::Parse($Matches[1], [System.Globalization.NumberStyles]::HexNumber)
}
else {
    [UInt64]::Parse($SelectedSourceAddress, [System.Globalization.NumberStyles]::HexNumber)
}

$cameraStart = $address + 0xB8

# C# code for memory reading
Add-Type @"
using System;
using System.Collections.Generic;

public class MemoryDump {
    [System.Runtime.InteropServices.DllImport("kernel32.dll")]
    private static extern bool ReadProcessMemory(
        IntPtr hProcess,
        IntPtr lpBaseAddress,
        byte[] lpBuffer,
        int nSize,
        out IntPtr lpNumberOfBytesRead);

    public static byte[] ReadMemory(IntPtr processHandle, IntPtr address, int size) {
        byte[] buffer = new byte[size];
        if (ReadProcessMemory(processHandle, address, buffer, size, out _)) {
            return buffer;
        }
        return null;
    }

    public static float ReadFloat32(IntPtr processHandle, IntPtr address) {
        byte[] buffer = ReadMemory(processHandle, address, 4);
        if (buffer != null && buffer.Length >= 4) {
            return BitConverter.ToSingle(buffer, 0);
        }
        return float.NaN;
    }

    public static List<float> ReadFloatArray(IntPtr processHandle, IntPtr address, int count) {
        var result = new List<float>();
        byte[] buffer = ReadMemory(processHandle, address, count * 4);
        if (buffer != null) {
            for (int i = 0; i < count; i++) {
                result.Add(BitConverter.ToSingle(buffer, i * 4));
            }
        }
        return result;
    }
}
"@

try {
    $riftProcess = Get-Process -Name "rift_x64" -ErrorAction Stop | Select-Object -First 1

    Write-Host "=== Camera Memory Dump ===" -ForegroundColor Cyan
    Write-Host "Component: $SelectedSourceAddress" -ForegroundColor Green
    Write-Host "Camera range: $('{0:X}' -f $cameraStart) (22 float32s = 88 bytes)" -ForegroundColor Green
    Write-Host ""

    # Read 22 float32s from camera range
    $floats = [MemoryDump]::ReadFloatArray($riftProcess.Handle, [IntPtr]$cameraStart, 22)

    if ($floats.Count -eq 0) {
        Write-Error "Failed to read memory"
        exit 1
    }

    Write-Host "Raw float values (offsets from +0xB8):" -ForegroundColor Yellow
    for ($i = 0; $i -lt $floats.Count; $i++) {
        $offset = $i * 4
        $offsetHex = [string]::Format('0x{0:X}', $offset)
        $value = $floats[$i]
        $hex = [System.BitConverter]::DoubleToInt64Bits($value)

        # Highlight interesting values
        $highlight = ""
        if ($value -gt 0.9 -and $value -lt 1.1) {
            $highlight = " ← normalized (likely vector component)"
        }
        elseif ($value -gt 5 -and $value -lt 100) {
            $highlight = " ← distance scalar"
        }
        elseif ($value -gt -360 -and $value -lt 360 -and [Math]::Abs($value) -gt 0.1) {
            $highlight = " ← angle"
        }

        Write-Host "[+$offsetHex] $([string]::Format('{0,12:F6}', $value))$highlight" -ForegroundColor White
    }

    # Check for triplet patterns
    Write-Host ""
    Write-Host "Potential vector triplets (normalized):" -ForegroundColor Yellow

    for ($i = 0; $i -le 19; $i += 3) {
        $x = $floats[$i]
        $y = $floats[$i + 1]
        $z = $floats[$i + 2]
        $mag = [Math]::Sqrt($x * $x + $y * $y + $z * $z)

        if ($mag -gt 0.8 -and $mag -lt 1.2) {
            $offset = $i * 4
            $offsetHex = [string]::Format('0x{0:X}', $offset)
            Write-Host "  [$offsetHex] Vector: ($([string]::Format('{0:F3}', $x)), $([string]::Format('{0:F3}', $y)), $([string]::Format('{0:F3}', $z))) Magnitude: $([string]::Format('{0:F3}', $mag))" -ForegroundColor Cyan
        }
    }

    # JSON output
    if ($Json) {
        $vectors = @()
        for ($i = 0; $i -le 19; $i += 3) {
            $x = $floats[$i]
            $y = $floats[$i + 1]
            $z = $floats[$i + 2]
            $mag = [Math]::Sqrt($x * $x + $y * $y + $z * $z)

            $vectors += [PSCustomObject]@{
                Offset = [string]::Format('0x{0:X}', $i * 4)
                X = $x
                Y = $y
                Z = $z
                Magnitude = $mag
            }
        }

        $output = [ordered]@{
            Mode = 'camera-memory-dump'
            GeneratedAtUtc = [System.DateTime]::UtcNow.ToString('o')
            Label = $Label
            SelectedSourceAddress = $SelectedSourceAddress
            CameraRangeStart = [string]::Format('0x{0:X}', $cameraStart)
            FloatValues = $floats
            VectorTriplets = $vectors
        }
        $output | ConvertTo-Json -Depth 20
    }
}
catch {
    Write-Error "Failed to dump camera memory: $_"
    exit 1
}
