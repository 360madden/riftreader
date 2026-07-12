#!/usr/bin/env python3
"""Investigate +0x180 object and look for rotation matrices/quaternions."""
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
obj90 = read_ptr(pid, obj + 0x90)
obj180 = read_ptr(pid, obj + 0x180)
print(f"Object: {hex(obj)}")
print(f"+0x90: {hex(obj90)}")
print(f"+0x180: {hex(obj180)}")

# The +0x180 object has coordinates at +0x19c and +0x1b0
# And shares camera state pointers at +0x1c0 and +0x1c8
# Let's look for rotation/quaternion data in it

print("\n=== +0x180 object — checking for rotation matrix ===")
# Read 128 bytes from +0x180
vals = read_f32s(pid, obj180, 64)
# Look for 4x4 matrix patterns (16 floats that form an identity or rotation)
for start in range(0, len(vals) - 15, 4):
    # Check if this could be a 4x4 matrix
    m = vals[start:start+16]
    if all(v != 0 and v == v for v in m):
        # Check if it's an identity-like matrix
        diag_sum = abs(m[0] - 1.0) + abs(m[5] - 1.0) + abs(m[10] - 1.0) + abs(m[15] - 1.0)
        off_diag = sum(abs(m[i]) for i in [1,2,3,4,6,7,8,9,11,12,13,14])
        if diag_sum < 0.1 and off_diag < 0.1:
            print(f"  +{hex(start*4)}: IDENTITY MATRIX")
        else:
            # Check if rows are unit vectors
            for row in range(4):
                r = m[row*4:row*4+3]
                mag = math.sqrt(sum(x*x for x in r))
                if 0.95 < mag < 1.05:
                    yaw = math.degrees(math.atan2(r[0], r[2]))
                    print(f"  +{hex(start*4)}: matrix row {row}: ({r[0]:.4f}, {r[1]:.4f}, {r[2]:.4f}) yaw={yaw:.1f}")

# Check for quaternion (4 consecutive floats where sqrt(w²+x²+y²+z²) ≈ 1)
print("\n=== Looking for quaternions ===")
for i in range(0, len(vals) - 3):
    w, x, y, z = vals[i], vals[i+1], vals[i+2], vals[i+3]
    if w == 0 and x == 0 and y == 0 and z == 0:
        continue
    mag = math.sqrt(w*w + x*x + y*y + z*z)
    if 0.95 < mag < 1.05:
        # Convert to euler angles (simplified)
        # Yaw = atan2(2(wy + xz), 1 - 2(y² + x²))
        yaw = math.degrees(math.atan2(2*(w*y + x*z), 1 - 2*(y*y + x*x)))
        pitch = math.degrees(math.asin(max(-1, min(1, 2*(w*x - z*y)))))
        roll = math.degrees(math.atan2(2*(w*z + x*y), 1 - 2*(x*x + z*z)))
        print(f"  +{hex(i*4)}: quat=({w:.4f}, {x:.4f}, {y:.4f}, {z:.4f}) yaw={yaw:.1f} pitch={pitch:.1f} roll={roll:.1f}")

# Also check the +0x90 object for rotation data
print("\n=== +0x90 object — checking for rotation ===")
vals90 = read_f32s(pid, obj90, 128)
# Look for quaternions
for i in range(0, len(vals90) - 3):
    w, x, y, z = vals90[i], vals90[i+1], vals90[i+2], vals90[i+3]
    if w == 0 and x == 0 and y == 0 and z == 0:
        continue
    mag = math.sqrt(w*w + x*x + y*y + z*z)
    if 0.95 < mag < 1.05:
        yaw = math.degrees(math.atan2(2*(w*y + x*z), 1 - 2*(y*y + x*x)))
        pitch = math.degrees(math.asin(max(-1, min(1, 2*(w*x - z*y)))))
        roll = math.degrees(math.atan2(2*(w*z + x*y), 1 - 2*(x*x + z*z)))
        print(f"  +{hex(i*4)}: quat=({w:.4f}, {x:.4f}, {y:.4f}, {z:.4f}) yaw={yaw:.1f} pitch={pitch:.1f} roll={roll:.1f}")

# Check for basis vectors (unit vectors that could be forward/right/up)
print("\n=== Looking for basis vectors in +0x90 ===")
for i in range(0, len(vals90) - 2):
    x, y, z = vals90[i], vals90[i+1], vals90[i+2]
    if x == 0 and y == 0 and z == 0:
        continue
    mag = math.sqrt(x*x + y*y + z*z)
    if 0.95 < mag < 1.05 and abs(y) < 0.5:  # mostly horizontal
        yaw = math.degrees(math.atan2(x, z))
        print(f"  +{hex(i*4)}: ({x:.4f}, {y:.4f}, {z:.4f}) yaw={yaw:.1f}")
