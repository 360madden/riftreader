[CmdletBinding()]
param(
    [string]$SelectedSourceAddress = '0x1577AC2FB60',
    [switch]$Json,
    [switch]$RefreshReaderBridge
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
$cameraEnd = $address + 0x150

Write-Host "=== Camera Candidate Scanner ===" -ForegroundColor Cyan
Write-Host "Component address: $('{0:X}' -f $address)" -ForegroundColor Green
Write-Host "Camera search: $('{0:X}' -f $cameraStart) to $('{0:X}' -f $cameraEnd) (88 bytes)" -ForegroundColor Green
Write-Host ""

# Add the C# code to read process memory
Add-Type @"
using System;
using System.Diagnostics;

public class ProcessMemoryReader {
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
        if (buffer != null) {
            return BitConverter.ToSingle(buffer, 0);
        }
        return float.NaN;
    }

    public static double ReadFloat64(IntPtr processHandle, IntPtr address) {
        byte[] buffer = ReadMemory(processHandle, address, 8);
        if (buffer != null) {
            return BitConverter.ToDouble(buffer, 0);
        }
        return double.NaN;
    }
}
"@

try {
    $riftProcess = Get-Process -Name "rift_x64" -ErrorAction Stop | Select-Object -First 1
    $processHandle = [System.Diagnostics.Process]::GetProcessById($riftProcess.Id).Handle

    Write-Host "Scanning component memory for candidates..." -ForegroundColor Yellow
    Write-Host ""

    # Scan for candidates
    $candidates = @()

    for ($offset = 0; $offset -lt 88; $offset += 4) {
        $currentAddr = [IntPtr]($cameraStart + $offset)
        $value = [ProcessMemoryReader]::ReadFloat32($processHandle, $currentAddr)

        if (-not [float]::IsNaN($value) -and -not [float]::IsInfinity($value)) {
            # Check for normalized vector-like values (~1.0 magnitude)
            $magnitude = [Math]::Abs($value)

            # Could be part of normalized vector (component between -1 and 1)
            if ($magnitude -le 1.0) {
                $candidates += [PSCustomObject]@{
                    Offset = "+0x$([string]::Format('{0:X}', $offset))"
                    Address = [string]::Format('0x{0:X}', $currentAddr)
                    Value = $value
                    Type = 'normalized-vector-component'
                    AbsValue = $magnitude
                }
            }

            # Could be distance scalar (5-100 units)
            if ($value -gt 5 -and $value -lt 100) {
                $candidates += [PSCustomObject]@{
                    Offset = "+0x$([string]::Format('{0:X}', $offset))"
                    Address = [string]::Format('0x{0:X}', $currentAddr)
                    Value = $value
                    Type = 'distance-scalar'
                    AbsValue = $value
                }
            }

            # Could be angle in degrees (0-360)
            if ($value -ge -360 -and $value -le 360) {
                $candidates += [PSCustomObject]@{
                    Offset = "+0x$([string]::Format('{0:X}', $offset))"
                    Address = [string]::Format('0x{0:X}', $currentAddr)
                    Value = $value
                    Type = 'angle-degrees'
                    AbsValue = [Math]::Abs($value)
                }
            }
        }
    }

    if ($candidates.Count -eq 0) {
        Write-Host "No obvious candidates found in initial scan." -ForegroundColor Yellow
        Write-Host "Camera may use double precision (float64) or be stored differently." -ForegroundColor Yellow
    }
    else {
        Write-Host "Found $($candidates.Count) candidate locations:" -ForegroundColor Green
        Write-Host ""

        # Group by type
        $byType = $candidates | Group-Object -Property Type

        foreach ($typeGroup in $byType) {
            Write-Host "$($typeGroup.Name):" -ForegroundColor Cyan
            foreach ($candidate in $typeGroup.Group | Sort-Object AbsValue -Descending) {
                Write-Host "  Offset: $($candidate.Offset)  Value: $($candidate.Value)  Type: $($candidate.Type)" -ForegroundColor White
            }
            Write-Host ""
        }

        Write-Host "Next steps:" -ForegroundColor Yellow
        Write-Host "1. Test each candidate with stimulus: scripts\test-camera-stimulus.ps1 -Stimulus mouse-yaw -Json" -ForegroundColor Gray
        Write-Host "2. Compare offset values before/after mouse movement" -ForegroundColor Gray
        Write-Host "3. Document offsets that correlate with input" -ForegroundColor Gray
    }

    # Output JSON if requested
    if ($Json) {
        $output = [ordered]@{
            Mode = 'scan-camera-candidates'
            GeneratedAtUtc = [System.DateTime]::UtcNow.ToString('o')
            SelectedSourceAddress = $SelectedSourceAddress
            CameraSearchRange = @{
                Start = [string]::Format('0x{0:X}', $cameraStart)
                End = [string]::Format('0x{0:X}', $cameraEnd)
                SizeBytes = 88
            }
            CandidatesFound = $candidates.Count
            Candidates = $candidates
        }
        $output | ConvertTo-Json -Depth 10
    }
}
catch {
    Write-Error "Failed to scan camera candidates: $_"
    exit 1
}
