[CmdletBinding()]
param(
    [string]$OwnerAddress = '0x1576A38AA10',
    [int]$FirstOffset = 0xD0,
    [int]$SecondOffset = 0x100,
    [int]$BasisOffset = 0xA0,
    [int]$KeyPresses = 4,
    [int]$KeyHoldMs = 400,
    [int]$InterKeyDelayMs = 250,
    [int]$PostKeyWaitMs = 1500,
    [string]$Key = 'LEFT'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class ChainMemory {
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

    public static float[] ReadFloats(IntPtr processHandle, long address, int count) {
        byte[] buf = new byte[count * 4];
        IntPtr read;
        if (!ReadProcessMemory(processHandle, (IntPtr)address, buf, buf.Length, out read))
            return null;
        float[] result = new float[count];
        for (int i = 0; i < count; i++)
            result[i] = BitConverter.ToSingle(buf, i * 4);
        return result;
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

function Compute-YawPitch($fwd) {
    $yawRad  = [Math]::Atan2($fwd[2], $fwd[0])
    $horizLen = [Math]::Sqrt($fwd[0] * $fwd[0] + $fwd[2] * $fwd[2])
    $pitchRad = [Math]::Atan2($fwd[1], $horizLen)
    return @{
        YawDeg   = $yawRad  * 180.0 / [Math]::PI
        PitchDeg = $pitchRad * 180.0 / [Math]::PI
    }
}

$ownerAddr = Parse-HexAddress $OwnerAddress
$riftProcess = Get-Process -Name "rift_x64" -ErrorAction Stop | Select-Object -First 1
$handle = $riftProcess.Handle

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Live Pointer Chain -> Basis Matrix Test" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# Walk the pointer chain
Write-Host ""
Write-Host "Walking pointer chain from owner..." -ForegroundColor Yellow

$step1Addr = $ownerAddr + $FirstOffset
$step1Value = [ChainMemory]::ReadPointer($handle, $step1Addr)
Write-Host ("  Owner 0x{0:X} + 0x{1:X} = 0x{2:X} -> 0x{3:X}" -f $ownerAddr, $FirstOffset, $step1Addr, $step1Value)

if ($step1Value -eq 0 -or $step1Value -lt 0x10000) {
    Write-Error "Pointer chain broken at step 1 (null or invalid pointer)"
    exit 1
}

$step2Addr = $step1Value + $SecondOffset
$step2Value = [ChainMemory]::ReadPointer($handle, $step2Addr)
Write-Host ("  Step1 0x{0:X} + 0x{1:X} = 0x{2:X} -> 0x{3:X}" -f $step1Value, $SecondOffset, $step2Addr, $step2Value)

if ($step2Value -eq 0 -or $step2Value -lt 0x10000) {
    Write-Error "Pointer chain broken at step 2 (null or invalid pointer)"
    exit 1
}

$basisAddr = $step2Value + $BasisOffset
Write-Host ("  Step2 0x{0:X} + 0x{1:X} = Basis at 0x{2:X}" -f $step2Value, $BasisOffset, $basisAddr)

# Also try some alternative offsets from step1 in case the chain has shifted
# Read a wider range of pointers from step1
Write-Host ""
Write-Host "Scanning step1 object for pointer-like values (offsets 0x80-0x180)..." -ForegroundColor Yellow
$scanFloats = [ChainMemory]::ReadBytes($handle, $step1Value, 0x200)
if ($null -ne $scanFloats) {
    for ($off = 0x80; $off -le 0x180; $off += 8) {
        $ptr = [BitConverter]::ToInt64($scanFloats, $off)
        if ($ptr -gt 0x100000000 -and $ptr -lt 0x7FFFFFFFFFFF) {
            # Try reading basis at +0xA0 from this pointer
            $testBasis = [ChainMemory]::ReadFloats($handle, $ptr + $BasisOffset, 3)
            if ($null -ne $testBasis) {
                $mag = [Math]::Sqrt($testBasis[0]*$testBasis[0] + $testBasis[1]*$testBasis[1] + $testBasis[2]*$testBasis[2])
                if ($mag -gt 0.9 -and $mag -lt 1.1) {
                    Write-Host ("    +0x{0:X}: 0x{1:X} -> basis fwd ({2:F4}, {3:F4}, {4:F4}) mag={5:F4}" -f $off, $ptr, $testBasis[0], $testBasis[1], $testBasis[2], $mag) -ForegroundColor Green
                }
            }
        }
    }
}

# Read basis from the chain-derived address
Write-Host ""
Write-Host ("--- BEFORE: Reading basis at 0x{0:X} ---" -f $basisAddr) -ForegroundColor Yellow
$beforeFloats = [ChainMemory]::ReadFloats($handle, $basisAddr, 9)
if ($null -eq $beforeFloats) {
    Write-Error "Failed to read basis matrix"
    exit 1
}

Write-Host ("  Forward: ({0,10:F6}, {1,10:F6}, {2,10:F6})" -f $beforeFloats[0], $beforeFloats[1], $beforeFloats[2])
Write-Host ("  Right  : ({0,10:F6}, {1,10:F6}, {2,10:F6})" -f $beforeFloats[3], $beforeFloats[4], $beforeFloats[5])
Write-Host ("  Up     : ({0,10:F6}, {1,10:F6}, {2,10:F6})" -f $beforeFloats[6], $beforeFloats[7], $beforeFloats[8])
$beforeYP = Compute-YawPitch @($beforeFloats[0], $beforeFloats[1], $beforeFloats[2])
Write-Host ("  => Yaw: {0:F2} deg  Pitch: {1:F2} deg" -f $beforeYP.YawDeg, $beforeYP.PitchDeg) -ForegroundColor Cyan

# Also check if this looks like a unit-length basis
$fwdMag = [Math]::Sqrt($beforeFloats[0]*$beforeFloats[0] + $beforeFloats[1]*$beforeFloats[1] + $beforeFloats[2]*$beforeFloats[2])
Write-Host ("  Forward magnitude: {0:F6} (should be ~1.0)" -f $fwdMag)

# Also read the known actor basis for comparison (at selected source +0x60)
$selectedSource = [ChainMemory]::ReadPointer($handle, $ownerAddr + 0x78)
# The selected source container
$containerAddr = 0
# Read from the player-owner-graph: container is at offset 0x78 from owner, selected source index 6
# Actually let's read from the known selected source address
$knownSelectedSource = Parse-HexAddress '0x1577AC2FB60'
$actorBasis = [ChainMemory]::ReadFloats($handle, $knownSelectedSource + 0x60, 3)
if ($null -ne $actorBasis) {
    $actorYP = Compute-YawPitch @($actorBasis[0], $actorBasis[1], $actorBasis[2])
    Write-Host ""
    Write-Host "Actor basis (selected source +0x60) for comparison:" -ForegroundColor Yellow
    Write-Host ("  Forward: ({0,10:F6}, {1,10:F6}, {2,10:F6})" -f $actorBasis[0], $actorBasis[1], $actorBasis[2])
    Write-Host ("  => Yaw: {0:F2} deg  Pitch: {1:F2} deg" -f $actorYP.YawDeg, $actorYP.PitchDeg) -ForegroundColor Cyan
}

# ---- SEND KEYS ----
Write-Host ""
Write-Host "--- SENDING $KeyPresses x '$Key' KEY PRESSES ---" -ForegroundColor Yellow

$scriptRoot = $PSScriptRoot
for ($i = 1; $i -le $KeyPresses; $i++) {
    Write-Host "  Press $i / $KeyPresses ..." -ForegroundColor Gray
    & "$scriptRoot\post-rift-key.ps1" -Key $Key -HoldMilliseconds $KeyHoldMs -SkipBackgroundFocus
    if ($i -lt $KeyPresses) {
        Start-Sleep -Milliseconds $InterKeyDelayMs
    }
}

Write-Host "  Waiting ${PostKeyWaitMs}ms for game to settle..." -ForegroundColor Gray
Start-Sleep -Milliseconds $PostKeyWaitMs

# ---- AFTER ----
Write-Host ""
Write-Host "--- AFTER: Reading basis at chain endpoint ---" -ForegroundColor Yellow

# Re-walk the chain (pointers might have changed!)
$step1ValueAfter = [ChainMemory]::ReadPointer($handle, $step1Addr)
$step2ValueAfter = [ChainMemory]::ReadPointer($handle, $step1ValueAfter + $SecondOffset)
$basisAddrAfter = $step2ValueAfter + $BasisOffset

if ($step2ValueAfter -ne $step2Value) {
    Write-Host ("  NOTE: Step2 pointer changed! Was 0x{0:X}, now 0x{1:X}" -f $step2Value, $step2ValueAfter) -ForegroundColor Red
}

$afterFloats = [ChainMemory]::ReadFloats($handle, $basisAddrAfter, 9)
if ($null -eq $afterFloats) {
    Write-Error "Failed to read basis matrix AFTER"
    exit 1
}

Write-Host ("  Forward: ({0,10:F6}, {1,10:F6}, {2,10:F6})" -f $afterFloats[0], $afterFloats[1], $afterFloats[2])
Write-Host ("  Right  : ({0,10:F6}, {1,10:F6}, {2,10:F6})" -f $afterFloats[3], $afterFloats[4], $afterFloats[5])
Write-Host ("  Up     : ({0,10:F6}, {1,10:F6}, {2,10:F6})" -f $afterFloats[6], $afterFloats[7], $afterFloats[8])
$afterYP = Compute-YawPitch @($afterFloats[0], $afterFloats[1], $afterFloats[2])
Write-Host ("  => Yaw: {0:F2} deg  Pitch: {1:F2} deg" -f $afterYP.YawDeg, $afterYP.PitchDeg) -ForegroundColor Cyan

# Also read actor basis after
$actorBasisAfter = [ChainMemory]::ReadFloats($handle, $knownSelectedSource + 0x60, 3)
if ($null -ne $actorBasisAfter) {
    $actorYPAfter = Compute-YawPitch @($actorBasisAfter[0], $actorBasisAfter[1], $actorBasisAfter[2])
    Write-Host ""
    Write-Host "Actor basis AFTER (selected source +0x60):" -ForegroundColor Yellow
    Write-Host ("  Forward: ({0,10:F6}, {1,10:F6}, {2,10:F6})" -f $actorBasisAfter[0], $actorBasisAfter[1], $actorBasisAfter[2])
    Write-Host ("  => Yaw: {0:F2} deg  Pitch: {1:F2} deg" -f $actorYPAfter.YawDeg, $actorYPAfter.PitchDeg) -ForegroundColor Cyan
}

# ---- DELTAS ----
Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  DELTA ANALYSIS" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

$yawDelta = $afterYP.YawDeg - $beforeYP.YawDeg
$pitchDelta = $afterYP.PitchDeg - $beforeYP.PitchDeg

Write-Host ""
Write-Host "CAMERA BASIS (chain-derived):" -ForegroundColor White
Write-Host ("  Yaw   BEFORE: {0,8:F2}   AFTER: {1,8:F2}   DELTA: {2:F2} deg" -f $beforeYP.YawDeg, $afterYP.YawDeg, $yawDelta)
Write-Host ("  Pitch BEFORE: {0,8:F2}   AFTER: {1,8:F2}   DELTA: {2:F2} deg" -f $beforeYP.PitchDeg, $afterYP.PitchDeg, $pitchDelta)

if ($null -ne $actorBasis -and $null -ne $actorBasisAfter) {
    $actorYawDelta = $actorYPAfter.YawDeg - $actorYP.YawDeg
    $actorPitchDelta = $actorYPAfter.PitchDeg - $actorYP.PitchDeg
    Write-Host ""
    Write-Host "ACTOR BASIS (selected source +0x60):" -ForegroundColor White
    Write-Host ("  Yaw   BEFORE: {0,8:F2}   AFTER: {1,8:F2}   DELTA: {2:F2} deg" -f $actorYP.YawDeg, $actorYPAfter.YawDeg, $actorYawDelta)
    Write-Host ("  Pitch BEFORE: {0,8:F2}   AFTER: {1,8:F2}   DELTA: {2:F2} deg" -f $actorYP.PitchDeg, $actorYPAfter.PitchDeg, $actorPitchDelta)
}

$yawChanged = [Math]::Abs($yawDelta) -gt 0.5
$pitchChanged = [Math]::Abs($pitchDelta) -gt 0.5

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
if ($yawChanged) {
    Write-Host "  ** CAMERA YAW CHANGED by $([Math]::Round($yawDelta, 2)) deg -- THIS IS THE CAMERA BASIS **" -ForegroundColor Green
} else {
    Write-Host "  Camera yaw did NOT change (delta $([Math]::Round($yawDelta, 4)) deg)" -ForegroundColor Red
}
if ($pitchChanged) {
    Write-Host "  ** CAMERA PITCH CHANGED by $([Math]::Round($pitchDelta, 2)) deg **" -ForegroundColor Green
} else {
    Write-Host "  Camera pitch did not change (expected for LEFT key)" -ForegroundColor Gray
}
Write-Host "=============================================" -ForegroundColor Cyan

exit 0
