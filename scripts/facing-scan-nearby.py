#!/usr/bin/env python3
"""Scan nearby heap objects for player entity with facing data."""
import ctypes, ctypes.wintypes, struct, math, sys

kernel32 = ctypes.windll.kernel32

def find_base(pid):
    TH32CS_SNAPMODULE = 0x00000010
    TH32CS_SNAPMODULE32 = 0x00000008
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snapshot == ctypes.wintypes.HANDLE(-1).value:
        return None
    class ME(ctypes.Structure):
        _fields_ = [("dwSize", ctypes.wintypes.DWORD), ("th32ModuleID", ctypes.wintypes.DWORD),
                     ("th32ProcessID", ctypes.wintypes.DWORD), ("GlblcntUsage", ctypes.wintypes.DWORD),
                     ("ProccntUsage", ctypes.wintypes.DWORD), ("modBaseAddr", ctypes.c_void_p),
                     ("modBaseSize", ctypes.wintypes.DWORD), ("hModule", ctypes.wintypes.HMODULE),
                     ("szModule", ctypes.c_char * 256), ("szExePath", ctypes.c_char * 260)]
    me = ME()
    me.dwSize = ctypes.sizeof(me)
    base = None
    try:
        if kernel32.Module32First(snapshot, ctypes.byref(me)):
            while True:
                if b"rift_x64" in me.szModule.lower():
                    base = me.modBaseAddr
                    break
                if not kernel32.Module32Next(snapshot, ctypes.byref(me)):
                    break
    finally:
        kernel32.CloseHandle(snapshot)
    return base

def read_bytes(pid, addr, length):
    h = kernel32.OpenProcess(0x0010, False, pid)
    buf = ctypes.create_string_buffer(length)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, length, ctypes.byref(br))
    kernel32.CloseHandle(h)
    return buf.raw[:br.value] if ok else None

def read_ptr(pid, addr):
    d = read_bytes(pid, addr, 8)
    return struct.unpack('<Q', d)[0] if d and len(d) == 8 else None

def read_f32(pid, addr):
    d = read_bytes(pid, addr, 4)
    return struct.unpack('<f', d)[0] if d and len(d) == 4 else None

def read_f32s(pid, addr, count):
    d = read_bytes(pid, addr, count * 4)
    if not d:
        return []
    return [struct.unpack('<f', d[i*4:i*4+4])[0] for i in range(count)]

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--pid", type=int, required=True)
args = parser.parse_args()
pid = args.pid

base = find_base(pid)
obj = read_ptr(pid, base + 0x32EBDC0)
print(f"Base: {hex(base)}  Object: {hex(obj)}")

# The coord object at +0x80, +0x88, +0x90 point to nearby heap objects
# These might be part of the same entity structure
nearby_offsets = [0x80, 0x88, 0x90, 0xC8, 0xD0, 0xD8]
for off in nearby_offsets:
    ptr = read_ptr(pid, obj + off)
    if not ptr or ptr < 0x10000:
        print(f"\n+{hex(off)}: null/invalid")
        continue
    
    print(f"\n=== Object at +{hex(off)} -> {hex(ptr)} ===")
    # Scan first 256 bytes
    vals = read_f32s(pid, ptr, 64)
    interesting = []
    for i, v in enumerate(vals):
        a = i * 4
        if v == 0.0 or v != v:
            continue
        # Check if looks like game coordinate
        if 5000 < abs(v) < 10000:
            interesting.append((a, "coord", v))
        # Check if looks like angle (0-360)
        elif 0 < v < 360 and v != int(v):
            interesting.append((a, "angle", v))
        # Check if unit vector magnitude
        elif 0.85 < abs(v) < 1.15 and i + 2 < len(vals):
            v2 = vals[i+1]
            v3 = vals[i+2]
            if v2 != 0 and v3 != 0:
                mag = (v**2 + v2**2 + v3**2) ** 0.5
                if 0.95 < mag < 1.05:
                    yaw = math.degrees(math.atan2(v, v3))
                    interesting.append((a, f"unit_vec yaw={yaw:.1f}", v))
        # Check if looks like speed (small float)
        elif -5 < v < 5 and abs(v) > 0.01:
            pass  # skip small values
    
    for a, desc, v in interesting[:10]:
        print(f"  +{hex(a)}: {v:.4f} ({desc})")

# Also scan the coord object itself more carefully for any pointer chain
# that might lead to a larger entity
print("\n=== Scanning coord object for heap pointers ===")
for off in range(0, 0x400, 8):
    ptr = read_ptr(pid, obj + off)
    if ptr and 0x25700000000 < ptr < 0x25800000000 and ptr != obj:
        # This is a heap pointer (not self, not static)
        # Check if target has coords
        x = read_f32(pid, ptr + 0x320)
        z = read_f32(pid, ptr + 0x328)
        if x and z and 5000 < abs(x) < 10000 and 2000 < abs(z) < 5000:
            print(f"  +{hex(off)} -> {hex(ptr)}: HAS COORDS ({x:.1f}, {z:.1f})")
        else:
            # Check if it has any non-zero data
            test_vals = read_f32s(pid, ptr, 8)
            non_zero = sum(1 for v in test_vals if v != 0 and v == v)
            if non_zero > 3:
                print(f"  +{hex(off)} -> {hex(ptr)}: {non_zero}/8 non-zero floats")
