#!/usr/bin/env python3
"""Dump memory around the coordinate object, turn, dump again, diff to find facing."""

import ctypes
import ctypes.wintypes
import json
import struct
import subprocess
import sys
import time
from pathlib import Path

COORD_RVA = 0x32EBDC0
DUMP_RANGE = (-0x60, 0x360)  # from -0x60 to +0x360 relative to object
SAMPLE_DELAY = 1.0  # seconds after turn before sampling


class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.wintypes.DWORD),
        ("th32ModuleID", ctypes.wintypes.DWORD),
        ("th32ProcessID", ctypes.wintypes.DWORD),
        ("GlblcntUsage", ctypes.wintypes.DWORD),
        ("ProccntUsage", ctypes.wintypes.DWORD),
        ("modBaseAddr", ctypes.c_void_p),
        ("modBaseSize", ctypes.wintypes.DWORD),
        ("hModule", ctypes.wintypes.HMODULE),
        ("szModule", ctypes.c_char * 256),
        ("szExePath", ctypes.c_char * 260),
    ]


def find_base(pid):
    """Find base address of rift_x64.exe."""
    kernel32 = ctypes.windll.kernel32
    TH32CS_SNAPMODULE = 0x00000010
    TH32CS_SNAPMODULE32 = 0x00000008
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snapshot == ctypes.wintypes.HANDLE(-1).value:
        return None
    me = MODULEENTRY32()
    me.dwSize = ctypes.sizeof(me)
    base = None
    try:
        if kernel32.Module32First(snapshot, ctypes.byref(me)):
            while True:
                name = me.szModule.decode("utf-8", errors="ignore").lower()
                if "rift_x64" in name or "rift" in name:
                    base = me.modBaseAddr
                    break
                if not kernel32.Module32Next(snapshot, ctypes.byref(me)):
                    break
    finally:
        kernel32.CloseHandle(snapshot)
    return base


def read_bytes(pid, addr, length):
    """Read raw bytes from process memory."""
    kernel32 = ctypes.windll.kernel32
    h = kernel32.OpenProcess(0x0010, False, pid)  # PROCESS_VM_READ
    if not h:
        return None
    try:
        buf = ctypes.create_string_buffer(length)
        br = ctypes.c_size_t(0)
        if not kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, length, ctypes.byref(br)):
            return None
        return buf.raw[:br.value]
    finally:
        kernel32.CloseHandle(h)


def read_pointer(pid, addr):
    """Read a 64-bit pointer."""
    data = read_bytes(pid, addr, 8)
    if not data or len(data) < 8:
        return None
    return struct.unpack("<Q", data)[0]


def read_float(pid, addr):
    """Read a 32-bit float."""
    data = read_bytes(pid, addr, 4)
    if not data or len(data) < 4:
        return None
    return struct.unpack("<f", data)[0]


def dump_region(pid, base_addr, start_off, end_off):
    """Dump memory region relative to base address, returns dict of offset->bytes."""
    obj_ptr = read_pointer(pid, base_addr + COORD_RVA)
    if not obj_ptr or obj_ptr < 0x10000:
        print(f"ERROR: cannot read object pointer at {hex(base_addr + COORD_RVA)}")
        return None
    
    length = end_off - start_off
    data = read_bytes(pid, obj_ptr + start_off, length)
    if not data:
        print(f"ERROR: cannot read {length} bytes at {hex(obj_ptr + start_off)}")
        return None
    
    result = {}
    for i in range(0, len(data) - 3, 4):
        offset = start_off + i
        val = struct.unpack("<f", data[i:i+4])[0]
        result[offset] = val
    return result


def send_key(direction):
    """Send a turn key using C# SendInput."""
    script = f'''
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class SendInput {{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    [DllImport("user32.dll")]
    public static extern IntPtr SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);
    [StructLayout(LayoutKind.Sequential)]
    public struct INPUT {{ public uint type; public INPUTUNION U; }}
    [StructLayout(LayoutKind.Explicit)]
    public struct INPUTUNION {{ [FieldOffset(0)] public KEYBDINPUT ki; }}
    [StructLayout(LayoutKind.Sequential)]
    public struct KEYBDINPUT {{ public ushort wVk; public ushort wScan; public uint dwFlags; public uint time; public IntPtr dwExtraInfo; }}
}}
"@ -Language CSharp

$hwnd = [SendInput]::FindWindow($null, "RIFT")
if ($hwnd -eq [IntPtr]::Zero) {{ Write-Host "RIFT not found"; exit 1 }}
$fg = [SendInput]::GetForegroundWindow()
if ($fg -ne $hwnd) {{
    [SendInput]::SetForegroundWindow($hwnd)
    Start-Sleep -Milliseconds 200
}}

$vk = 0x41  # A = left
if ("{direction}" -eq "right") {{ $vk = 0x44 }}  # D = right

$down = New-Object SendInput.INPUT
$down.type = 1
$down.U.ki.wVk = $vk
$up = New-Object SendInput.INPUT
$up.type = 1
$up.U.ki.wVk = $vk
$up.U.ki.dwFlags = 2  # KEYEVENTF_KEYUP

[SendInput]::SendInput(2, @($down, $up), [System.Runtime.InteropServices.Marshal]::SizeOf([type][SendInput]::INPUT))
'''
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", script],
        capture_output=True, text=True, timeout=10
    )
    return result.returncode == 0


def diff_snapshots(snap1, snap2):
    """Compare two snapshots, return offsets that changed directionally."""
    changes = []
    for offset in sorted(set(snap1.keys()) & set(snap2.keys())):
        v1 = snap1[offset]
        v2 = snap2[offset]
        delta = v2 - v1
        if abs(delta) > 0.001:
            changes.append((offset, v1, v2, delta))
    return changes


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--base", type=str, default=None, help="Override base address (hex)")
    parser.add_argument("--direction", choices=["left", "right"], default="right")
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()

    if args.base:
        base = int(args.base, 16)
    else:
        base = find_base(args.pid)
    if not base:
        print(f"ERROR: cannot find rift_x64.exe base for PID {args.pid}")
        sys.exit(1)
    print(f"Base: {hex(base)}")

    obj_ptr = read_pointer(args.pid, base + COORD_RVA)
    if not obj_ptr:
        print("ERROR: cannot read object pointer")
        sys.exit(1)
    print(f"Object: {hex(obj_ptr)}")

    # Take initial snapshot
    print("\n--- Initial snapshot ---")
    snap1 = dump_region(args.pid, base, DUMP_RANGE[0], DUMP_RANGE[1])
    if not snap1:
        sys.exit(1)
    
    x1 = snap1.get(0x320, 0)
    z1 = snap1.get(0x328, 0)
    print(f"X={x1:.2f}  Z={z1:.2f}")

    # Turn
    print(f"\n--- Turning {args.direction} ---")
    for i in range(args.rounds):
        send_key(args.direction)
        time.sleep(0.3)
    
    time.sleep(SAMPLE_DELAY)

    # Take second snapshot
    print("--- Post-turn snapshot ---")
    snap2 = dump_region(args.pid, base, DUMP_RANGE[0], DUMP_RANGE[1])
    if not snap2:
        sys.exit(1)
    
    x2 = snap2.get(0x320, 0)
    z2 = snap2.get(0x328, 0)
    print(f"X={x2:.2f}  Z={z2:.2f}")

    # Diff
    changes = diff_snapshots(snap1, snap2)
    print(f"\n--- Changed offsets ({len(changes)}) ---")
    print(f"{'Offset':>8}  {'Before':>12}  {'After':>12}  {'Delta':>12}")
    for offset, v1, v2, delta in changes:
        print(f"  {hex(offset):>6}  {v1:>12.4f}  {v2:>12.4f}  {delta:>+12.4f}")

    # Also dump raw bytes for key offsets
    print("\n--- Key offset values (post-turn) ---")
    key_offsets = [0x2F0, 0x2F4, 0x2F8, 0x2FC, 0x300, 0x304, 0x308, 
                   0x30C, 0x310, 0x314, 0x318, 0x320, 0x324, 0x328,
                   0x32C, 0x330, 0x334, 0x338]
    for off in key_offsets:
        v = snap2.get(off, None)
        if v is not None:
            print(f"  +{hex(off)}: {v:.6f}")

    # Save results
    out = {
        "pid": args.pid,
        "direction": args.direction,
        "rounds": args.rounds,
        "base": hex(base),
        "object": hex(obj_ptr),
        "snap1": {hex(k): v for k, v in snap1.items()},
        "snap2": {hex(k): v for k, v in snap2.items()},
        "changes": [(hex(o), v1, v2, d) for o, v1, v2, d in changes],
        "key_offsets": {hex(k): snap2.get(k) for k in key_offsets if k in snap2}
    }
    out_path = Path("scripts/captures/facing-diff.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
