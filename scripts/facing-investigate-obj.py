#!/usr/bin/env python3
"""Investigate coord object structure: vtable, type info, reverse pointers."""
import ctypes, ctypes.wintypes, struct, json, sys

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
if not base:
    print("ERROR: cannot find base")
    sys.exit(1)

obj = read_ptr(pid, base + 0x32EBDC0)
if not obj:
    print("ERROR: cannot read obj")
    sys.exit(1)

print(f"Base: {hex(base)}")
print(f"Object: {hex(obj)}")

# Vtable analysis
vtable = read_ptr(pid, obj)
print(f"\n=== Vtable ===")
print(f"Vtable ptr: {hex(vtable)}")

if vtable and vtable > 0x10000:
    # Read vtable entries
    vtable_entries = read_u64s(pid, vtable, 20)
    print(f"First 20 vtable entries:")
    for i, entry in enumerate(vtable_entries):
        if entry and entry > 0x10000:
            # Check if it's in the binary
            if base < entry < base + 0x10000000:
                rva = entry - base
                print(f"  [{i}] {hex(entry)} (RVA {hex(rva)})")
            else:
                print(f"  [{i}] {hex(entry)} (heap)")

# Object header analysis - read first 0x100 bytes
print(f"\n=== Object header (first 0x100 bytes) ===")
header = read_u64s(pid, obj, 32)
for i, val in enumerate(header):
    off = i * 8
    if val == obj:
        print(f"  +{hex(off)}: {hex(val)} (self-reference)")
    elif val and val > 0x10000:
        if base < val < base + 0x10000000:
            print(f"  +{hex(off)}: {hex(val)} (static RVA {hex(val - base)})")
        elif 0x25700000000 < val < 0x25800000000:
            print(f"  +{hex(off)}: {hex(val)} (heap nearby)")
        else:
            print(f"  +{hex(off)}: {hex(val)} (heap)")
    elif val == 0:
        pass  # skip zeros
    else:
        print(f"  +{hex(off)}: {hex(val)}")

# Check the second vtable pointer at +0x08
vt2 = read_ptr(pid, obj + 8)
print(f"\n=== Second vtable at +0x08 ===")
print(f"Vtable2 ptr: {hex(vt2) if vt2 else 'null'}")
if vt2 and vt2 > 0x10000 and vt2 != vtable:
    vtable2_entries = read_u64s(pid, vt2, 10)
    for i, entry in enumerate(vtable2_entries):
        if entry and entry > 0x10000:
            if base < entry < base + 0x10000000:
                print(f"  [{i}] {hex(entry)} (RVA {hex(entry - base)})")
            else:
                print(f"  [{i}] {hex(entry)}")

# Search static globals for pointer to obj (reverse lookup in .data section)
print(f"\n=== Searching static globals for pointer to object ===")
found = []
for rva in range(0x32E0000, 0x3300000, 8):
    v = read_ptr(pid, base + rva)
    if v == obj:
        found.append(hex(base + rva))
        print(f"  FOUND: base+{hex(rva)} -> {hex(obj)}")
        if len(found) >= 5:
            break

if not found:
    print("  Not found in .data range, trying broader scan...")
    for rva in range(0x3000000, 0x3600000, 0x1000):
        v = read_ptr(pid, base + rva)
        if v == obj:
            found.append(hex(base + rva))
            print(f"  FOUND: base+{hex(rva)} -> {hex(obj)}")
            if len(found) >= 5:
                break

# Scan nearby heap for objects pointing to coord object
print(f"\n=== Nearby heap objects pointing to coord object ===")
# Read a range around the coord object
scan_start = obj - 0x10000
scan_end = obj + 0x100000
# This is too large to scan byte by byte, check aligned pointers
nearby_ptrs = []
for check_addr in range(scan_start, scan_end, 8):
    v = read_ptr(pid, check_addr)
    if v == obj:
        nearby_ptrs.append(hex(check_addr))
        if len(nearby_ptrs) >= 10:
            break

for p in nearby_ptrs:
    print(f"  {p} -> {hex(obj)}")
