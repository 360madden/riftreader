#!/usr/bin/env python3
"""Deep scan +0x90 (has coords) and +0x180 (7/8 non-zero) objects."""
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

def read_u64s(pid, addr, count):
    d = read_bytes(pid, addr, count * 8)
    if not d:
        return []
    return [struct.unpack('<Q', d[i*8:i*8+8])[0] for i in range(count)]

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--pid", type=int, required=True)
args = parser.parse_args()
pid = args.pid

base = find_base(pid)
obj = read_ptr(pid, base + 0x32EBDC0)
print(f"Object: {hex(obj)}")

# Deep scan +0x90 object (has coordinates)
ptr90 = read_ptr(pid, obj + 0x90)
print(f"\n=== Object at +0x90 -> {hex(ptr90)} ===")

# Read 512 bytes
print("Full scan (512 bytes):")
vals = read_f32s(pid, ptr90, 128)
for i, v in enumerate(vals):
    off = i * 4
    if v == 0.0 or v != v:
        continue
    # Check for coordinates, angles, unit vectors
    tags = []
    if 5000 < abs(v) < 10000:
        tags.append("COORD")
    if 0 < v < 360 and v != int(v):
        tags.append("ANGLE")
    if 0.85 < abs(v) < 1.15 and i + 2 < len(vals):
        v2 = vals[i+1]
        v3 = vals[i+2]
        if v2 != 0 and v3 != 0:
            mag = (v**2 + v2**2 + v3**2) ** 0.5
            if 0.95 < mag < 1.05:
                tags.append(f"UNIT_VEC yaw={math.degrees(math.atan2(v, v3)):.1f}")
    tag = " ".join(tags) if tags else ""
    print(f"  +{hex(off):>4}: {v:>14.6f}  {tag}")

# Deep scan +0x180 object (7/8 non-zero)
ptr180 = read_ptr(pid, obj + 0x180)
print(f"\n=== Object at +0x180 -> {hex(ptr180)} ===")

vals2 = read_f32s(pid, ptr180, 128)
for i, v in enumerate(vals2):
    off = i * 4
    if v == 0.0 or v != v:
        continue
    tags = []
    if 5000 < abs(v) < 10000:
        tags.append("COORD")
    if 0 < v < 360 and v != int(v):
        tags.append("ANGLE")
    if 0.85 < abs(v) < 1.15 and i + 2 < len(vals2):
        v2 = vals2[i+1]
        v3 = vals2[i+2]
        if v2 != 0 and v3 != 0:
            mag = (v**2 + v2**2 + v3**2) ** 0.5
            if 0.95 < mag < 1.05:
                tags.append(f"UNIT_VEC yaw={math.degrees(math.atan2(v, v3)):.1f}")
    tag = " ".join(tags) if tags else ""
    print(f"  +{hex(off):>4}: {v:>14.6f}  {tag}")

# Check if +0x90 object has its own camera child
ptr90_child = read_ptr(pid, ptr90 + 0x330)
print(f"\n+0x90 -> +0x330 child: {hex(ptr90_child) if ptr90_child and ptr90_child > 0x10000 else 'null'}")

# Check if +0x180 object has pointers to coord object or its children
print(f"\n=== +0x180 object pointers ===")
ptrs = read_u64s(pid, ptr180, 64)
for i, v in enumerate(ptrs):
    off = i * 8
    if v == obj:
        print(f"  +{hex(off)}: -> COORD OBJECT (self)")
    elif v and 0x25700000000 < v < 0x25800000000:
        print(f"  +{hex(off)}: {hex(v)} (heap)")
