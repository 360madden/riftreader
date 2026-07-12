#!/usr/bin/env python3
"""Explore the coord object's neighborhood — find pointers, scan children for facing."""
import ctypes, struct, time, sys

kernel32 = ctypes.windll.kernel32
COORD_RVA = 0x32EBDC0
base = 0x7FF728B80000
PID = 36332

def read_bytes(addr, length):
    h = kernel32.OpenProcess(0x0010, False, PID)
    buf = ctypes.create_string_buffer(length)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, length, ctypes.byref(br))
    kernel32.CloseHandle(h)
    if not ok:
        return None
    return buf.raw[:br.value]

def read_ptr(addr):
    d = read_bytes(addr, 8)
    return struct.unpack('<Q', d)[0] if d and len(d) == 8 else None

def read_float(addr):
    d = read_bytes(addr, 4)
    return struct.unpack('<f', d)[0] if d and len(d) == 4 else None

def is_ptr(v):
    return v is not None and 0x10000 < v < 0x7FFFFFFFFFFFFFFF

def is_float(v):
    return v is not None and abs(v) < 100000 and v != 0.0

obj = read_ptr(base + COORD_RVA)
print(f"Coord object: {hex(obj)}")

# Scan for outbound pointers
print("\n--- Outbound pointers from coord object ---")
for off in range(0, 0x360, 8):
    v = read_ptr(obj + off)
    if is_ptr(v):
        print(f"  +{hex(off)}: {hex(v)}")

# Check +0x318 child
p318 = read_ptr(obj + 0x318)
if is_ptr(p318):
    print(f"\n+0x318 -> {hex(p318)}")
    for off in range(0, 256, 4):
        f = read_float(p318 + off)
        if is_float(f):
            print(f"  +{hex(off)}: {f:.6f}")

# Check +0x330 and +0x338
for off in [0x330, 0x338]:
    v = read_ptr(obj + off)
    if is_ptr(v):
        print(f"\n+{hex(off)} -> {hex(v)}")
        for off2 in range(0, 128, 4):
            f = read_float(v + off2)
            if is_float(f):
                print(f"  +{hex(off2)}: {f:.6f}")

# Now: search for what POINTS TO the coord object (reverse scan)
# The parent object should have a pointer to obj somewhere
# We can't do a full heap scan, but we know the object is near the top of a heap block
# Let's look at static globals that might point to it
print("\n--- Searching static globals near COORD_RVA for pointer to object ---")
for rva in range(COORD_RVA - 0x1000, COORD_RVA + 0x1000, 8):
    v = read_ptr(base + rva)
    if v == obj:
        print(f"  FOUND: base+{hex(rva)} -> {hex(obj)}")
