[CmdletBinding()]
param(
    [string]$PrimaryAddress   = '0x1579115D0A0',
    [string]$SecondaryAddress = '0x1578AA40570',
    [int]$BasisOffset         = 0xA0,
    [int]$KeyPresses          = 4,
    [int]$KeyHoldMs           = 250,
    [int]$InterKeyDelayMs     = 250,
    [int]$PostKeyWaitMs       = 1500,
    [string]$Key              = 'A'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# --- inline C# for direct ReadProcessMemory ---
Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class BasisMemory {
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool ReadProcessMemory(
        IntPtr hProcess, IntPtr lpBaseAddress, byte[] lpBuffer,
        int nSize, out IntPtr lpNumberOfBytesRead);

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
        return [UInt64]::Parse($Matches[1], [System.Globalization.NumberStyles]::HexNumber)
    }
    return [UInt64]::Parse($s, [System.Globalization.NumberStyles]::HexNumber)
}

function Read-BasisMatrix([IntPtr]$handle, [long]$baseAddr, [int]$offset) {
    $floats = [BasisMemory]::ReadFloats($handle, $baseAddr + $offset, 9)
    if ($null -eq $floats) { return $null }
    return [PSCustomObject]@{
        ForwardX = $floats[0]; ForwardY = $floats[1]; ForwardZ = $floats[2]
        RightX   = $floats[3]; RightY   = $floats[4]; RightZ   = $floats[5]
        UpX      = $floats[6]; UpY      = $floats[7]; UpZ      = $floats[8]
    }
}

function Compute-YawPitch($m) {
    $yawRad  = [Math]::Atan2($m.ForwardZ, $m.ForwardX)
    $horizLen = [Math]::Sqrt($m.ForwardX * $m.ForwardX + $m.ForwardZ * $m.ForwardZ)
    $pitchRad = [Math]::Atan2($m.ForwardY, $horizLen)
    $yawDeg   = $yawRad  * 180.0 / [Math]::PI
    $pitchDeg = $pitchRad * 180.0 / [Math]::PI
    return [PSCustomObject]@{ YawDeg = $yawDeg; PitchDeg = $pitchDeg }
}

function Format-Matrix($m) {
    "  Forward: ({0,10:F6}, {1,10:F6}, {2,10:F6})" -f $m.ForwardX, $m.ForwardY, $m.ForwardZ
    "  Right  : ({0,10:F6}, {1,10:F6}, {2,10:F6})" -f $m.RightX, $m.RightY, $m.RightZ
    "  Up     : ({0,10:F6}, {1,10:F6}, {2,10:F6})" -f $m.UpX, $m.UpY, $m.UpZ
}

# --- main ---
$primaryAddr   = Parse-HexAddress $PrimaryAddress
$secondaryAddr = Parse-HexAddress $SecondaryAddress

$riftProcess = Get-Process -Name "rift_x64" -ErrorAction Stop | Select-Object -First 1
$handle = $riftProcess.Handle

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Basis Matrix Camera Rotation Test" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Primary   : $PrimaryAddress + 0x$($BasisOffset.ToString('X'))" -ForegroundColor Green
Write-Host "Secondary : $SecondaryAddress + 0x$($BasisOffset.ToString('X'))" -ForegroundColor Green
Write-Host "Stimulus  : $KeyPresses x '$Key' key ($KeyHoldMs ms hold, $InterKeyDelayMs ms gap)" -ForegroundColor Green
Write-Host ""

# ---- BEFORE ----
Write-Host "--- BEFORE (reading basis matrices) ---" -ForegroundColor Yellow

$beforePrimary = Read-BasisMatrix $handle $primaryAddr $BasisOffset
if ($null -eq $beforePrimary) {
    Write-Error "Failed to read primary basis at $PrimaryAddress + 0x$($BasisOffset.ToString('X'))"
    exit 1
}
$beforeSecondary = Read-BasisMatrix $handle $secondaryAddr $BasisOffset
if ($null -eq $beforeSecondary) {
    Write-Warning "Failed to read secondary basis (may be stale pointer)"
}

$beforePrimaryYP = Compute-YawPitch $beforePrimary

Write-Host ""
Write-Host "Primary basis:" -ForegroundColor White
Format-Matrix $beforePrimary | ForEach-Object { Write-Host $_ }
Write-Host ("  => Yaw: {0:F2} deg  Pitch: {1:F2} deg" -f $beforePrimaryYP.YawDeg, $beforePrimaryYP.PitchDeg) -ForegroundColor Cyan

if ($null -ne $beforeSecondary) {
    $beforeSecondaryYP = Compute-YawPitch $beforeSecondary
    Write-Host ""
    Write-Host "Secondary basis:" -ForegroundColor White
    Format-Matrix $beforeSecondary | ForEach-Object { Write-Host $_ }
    Write-Host ("  => Yaw: {0:F2} deg  Pitch: {1:F2} deg" -f $beforeSecondaryYP.YawDeg, $beforeSecondaryYP.PitchDeg) -ForegroundColor Cyan
}

# Also read a wider dump (256 bytes) for context
$beforeDump = [BasisMemory]::ReadBytes($handle, $primaryAddr, 256)

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
Write-Host "--- AFTER (reading basis matrices) ---" -ForegroundColor Yellow

$afterPrimary = Read-BasisMatrix $handle $primaryAddr $BasisOffset
if ($null -eq $afterPrimary) {
    Write-Error "Failed to read primary basis AFTER stimulus"
    exit 1
}
$afterSecondary = Read-BasisMatrix $handle $secondaryAddr $BasisOffset

$afterPrimaryYP = Compute-YawPitch $afterPrimary

Write-Host ""
Write-Host "Primary basis:" -ForegroundColor White
Format-Matrix $afterPrimary | ForEach-Object { Write-Host $_ }
Write-Host ("  => Yaw: {0:F2} deg  Pitch: {1:F2} deg" -f $afterPrimaryYP.YawDeg, $afterPrimaryYP.PitchDeg) -ForegroundColor Cyan

if ($null -ne $afterSecondary) {
    $afterSecondaryYP = Compute-YawPitch $afterSecondary
    Write-Host ""
    Write-Host "Secondary basis:" -ForegroundColor White
    Format-Matrix $afterSecondary | ForEach-Object { Write-Host $_ }
    Write-Host ("  => Yaw: {0:F2} deg  Pitch: {1:F2} deg" -f $afterSecondaryYP.YawDeg, $afterSecondaryYP.PitchDeg) -ForegroundColor Cyan
}

# ---- DELTA ANALYSIS ----
Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  DELTA ANALYSIS" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

$yawDelta   = $afterPrimaryYP.YawDeg   - $beforePrimaryYP.YawDeg
$pitchDelta = $afterPrimaryYP.PitchDeg - $beforePrimaryYP.PitchDeg

Write-Host ""
Write-Host "PRIMARY:" -ForegroundColor White
$yawDeltaStr = if ($yawDelta -ge 0) { "+{0:F2}" -f $yawDelta } else { "{0:F2}" -f $yawDelta }
$pitchDeltaStr = if ($pitchDelta -ge 0) { "+{0:F2}" -f $pitchDelta } else { "{0:F2}" -f $pitchDelta }
Write-Host ("  Yaw   BEFORE: {0,8:F2} deg  AFTER: {1,8:F2} deg  DELTA: {2} deg" -f $beforePrimaryYP.YawDeg, $afterPrimaryYP.YawDeg, $yawDeltaStr) -ForegroundColor $(if ([Math]::Abs($yawDelta) -gt 0.1) { 'Green' } else { 'Gray' })
Write-Host ("  Pitch BEFORE: {0,8:F2} deg  AFTER: {1,8:F2} deg  DELTA: {2} deg" -f $beforePrimaryYP.PitchDeg, $afterPrimaryYP.PitchDeg, $pitchDeltaStr) -ForegroundColor $(if ([Math]::Abs($pitchDelta) -gt 0.1) { 'Green' } else { 'Gray' })

# Forward vector deltas
$fwdDeltaX = $afterPrimary.ForwardX - $beforePrimary.ForwardX
$fwdDeltaY = $afterPrimary.ForwardY - $beforePrimary.ForwardY
$fwdDeltaZ = $afterPrimary.ForwardZ - $beforePrimary.ForwardZ
Write-Host ("  Forward delta: ({0,10:F6}, {1,10:F6}, {2,10:F6})" -f $fwdDeltaX, $fwdDeltaY, $fwdDeltaZ)

if ($null -ne $afterSecondary -and $null -ne $beforeSecondary) {
    $secYawDelta   = $afterSecondaryYP.YawDeg   - $beforeSecondaryYP.YawDeg
    $secPitchDelta = $afterSecondaryYP.PitchDeg - $beforeSecondaryYP.PitchDeg
    Write-Host ""
    Write-Host "SECONDARY:" -ForegroundColor White
    $secYawDeltaStr = if ($secYawDelta -ge 0) { "+{0:F2}" -f $secYawDelta } else { "{0:F2}" -f $secYawDelta }
    $secPitchDeltaStr = if ($secPitchDelta -ge 0) { "+{0:F2}" -f $secPitchDelta } else { "{0:F2}" -f $secPitchDelta }
    Write-Host ("  Yaw   BEFORE: {0,8:F2} deg  AFTER: {1,8:F2} deg  DELTA: {2} deg" -f $beforeSecondaryYP.YawDeg, $afterSecondaryYP.YawDeg, $secYawDeltaStr) -ForegroundColor $(if ([Math]::Abs($secYawDelta) -gt 0.1) { 'Green' } else { 'Gray' })
    Write-Host ("  Pitch BEFORE: {0,8:F2} deg  AFTER: {1,8:F2} deg  DELTA: {2} deg" -f $beforeSecondaryYP.PitchDeg, $afterSecondaryYP.PitchDeg, $secPitchDeltaStr) -ForegroundColor $(if ([Math]::Abs($secPitchDelta) -gt 0.1) { 'Green' } else { 'Gray' })
}

# ---- VERDICT ----
Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
$yawChanged   = [Math]::Abs($yawDelta) -gt 0.5
$pitchChanged = [Math]::Abs($pitchDelta) -gt 0.5

if ($yawChanged) {
    Write-Host "  ** YAW CHANGED by $([Math]::Round($yawDelta, 2)) deg -- THIS BASIS TRACKS CAMERA ROTATION **" -ForegroundColor Green
} else {
    Write-Host "  Yaw did NOT change significantly (delta $([Math]::Round($yawDelta, 4)) deg)" -ForegroundColor Red
}
if ($pitchChanged) {
    Write-Host "  ** PITCH also changed by $([Math]::Round($pitchDelta, 2)) deg **" -ForegroundColor Green
} else {
    Write-Host "  Pitch did not change significantly (delta $([Math]::Round($pitchDelta, 4)) deg) -- expected for keyboard yaw-only" -ForegroundColor Gray
}

if ($yawChanged) {
    Write-Host ""
    Write-Host "  VERDICT: This basis matrix at $PrimaryAddress + 0x$($BasisOffset.ToString('X'))" -ForegroundColor Green
    Write-Host "           TRACKS CAMERA/PLAYER ROTATION (yaw confirmed)" -ForegroundColor Green
    Write-Host "           Pointer chain: owner +0xD0 -> +0x100 -> basis at +0xA0" -ForegroundColor Green
} elseif (-not $yawChanged -and -not $pitchChanged) {
    Write-Host ""
    Write-Host "  VERDICT: Basis matrix did NOT change. Possible causes:" -ForegroundColor Red
    Write-Host "    - Pointer is stale (address shifted since last session)" -ForegroundColor Red
    Write-Host "    - Key input did not reach the game" -ForegroundColor Red
    Write-Host "    - This is not the camera basis" -ForegroundColor Red
}
Write-Host "=============================================" -ForegroundColor Cyan

# Dump byte-level diff of the 256-byte region
$afterDump = [BasisMemory]::ReadBytes($handle, $primaryAddr, 256)
if ($null -ne $beforeDump -and $null -ne $afterDump) {
    $changedOffsets = @()
    for ($i = 0; $i -lt 256; $i++) {
        if ($beforeDump[$i] -ne $afterDump[$i]) {
            $changedOffsets += $i
        }
    }
    if ($changedOffsets.Count -gt 0) {
        Write-Host ""
        Write-Host "Byte-level changes in 256-byte dump from $PrimaryAddress :" -ForegroundColor Yellow
        Write-Host ("  {0} bytes changed at offsets: {1}" -f $changedOffsets.Count, (($changedOffsets | ForEach-Object { "0x{0:X2}" -f $_ }) -join ", "))
    } else {
        Write-Host ""
        Write-Host "No byte-level changes in 256-byte dump -- entire object is static" -ForegroundColor Red
    }
}

exit 0
