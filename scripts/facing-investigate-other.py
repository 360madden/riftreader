#!/usr/bin/env python3
"""Investigate the other coord-like object found nearby."""
import ctypes, ctypes.wintypes, struct, math

kernel32 = ctypes.windll.kernel32

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
parser.add_argument("--addr", type=str, required=True)
args = parser.parse_args()
pid = args.pid
addr = int(args.addr, 16)

print(f"=== Investigating coord object at {hex(addr)} ===")

# Read basic fields
x = read_f32(pid, addr + 0x320)
y = read_f32(pid, addr + 0x324)
z = read_f32(pid, addr + 0x328)
counter = read_f32(pid, addr + 0x300)
counter2 = read_f32(pid, addr + 0x304)
print(f"Coordinates: ({x:.2f}, {y:.2f}, {z:.2f})")
print(f"+0x300 counter: {counter:.2f}")
print(f"+0x304 counter2: {counter2:.2f}")

# Check +0x330 (camera state)
cam_ptr = read_ptr(pid, addr + 0x330)
print(f"+0x330 camera pointer: {hex(cam_ptr) if cam_ptr else 'NULL'}")

if cam_ptr and cam_ptr > 0x10000:
    cam_vals = read_f32s(pid, cam_ptr, 64)
    print(f"Camera state:")
    for i, v in enumerate(cam_vals[:32]):
        if v != 0 and v == v:
            print(f"  +{hex(i*4)}: {v:.6f}")

# Check +0x90 (look-ahead target)
obj90 = read_ptr(pid, addr + 0x90)
print(f"\n+0x90 pointer: {hex(obj90) if obj90 else 'NULL'}")
if obj90 and obj90 > 0x10000:
    vals90 = read_f32s(pid, obj90, 64)
    print("+0x90 values:")
    for i, v in enumerate(vals90[:32]):
        if v != 0 and v == v:
            print(f"  +{hex(i*4)}: {v:.6f}")

# Check +0x180
obj180 = read_ptr(pid, addr + 0x180)
print(f"\n+0x180 pointer: {hex(obj180) if obj180 else 'NULL'}")
if obj180 and obj180 > 0x10000:
    vals180 = read_f32s(pid, obj180, 64)
    print("+0x180 values:")
    for i, v in enumerate(vals180[:32]):
        if v != 0 and v == v:
            print(f"  +{hex(i*4)}: {v:.6f}")

# Check +0x1f0 (player ID area)
vals_f0 = read_f32s(pid, addr + 0x1f0, 4)
print(f"\n+0x1f0: {[hex(struct.unpack('<I', struct.pack('<f', v))[0]) for v in vals_f0]}")

# Check +0x190 (counter)
counter_190 = read_f32(pid, addr + 0x190)
print(f"+0x190: {counter_190:.2f}")
