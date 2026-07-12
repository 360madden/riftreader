#!/usr/bin/env python3
"""Deep scan +0x330 child for player facing, plus test +0x338 child."""
import ctypes, struct, time, math

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32
COORD_RVA = 0x32EBDC0
base = 0x7FF728B80000
PID = 36332
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101

def read_bytes(addr, length):
    h = kernel32.OpenProcess(0x0010, False, PID)
    buf = ctypes.create_string_buffer(length)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, length, ctypes.byref(br))
    kernel32.CloseHandle(h)
    return buf.raw[:br.value] if ok else None

def read_ptr(addr):
    d = read_bytes(addr, 8)
    return struct.unpack('<Q', d)[0] if d and len(d) == 8 else None

def read_floats(addr, count):
    d = read_bytes(addr, count * 4)
    if not d:
        return []
    return [struct.unpack('<f', d[i*4:i*4+4])[0] for i in range(count)]

obj = read_ptr(base + COORD_RVA)
child330 = read_ptr(obj + 0x330)
child338 = read_ptr(obj + 0x338)

print(f"Coord object: {hex(obj)}")
print(f"+0x330 child: {hex(child330)}")
print(f"+0x338 child: {hex(child338)}")

# Deep scan +0x330 child (512 bytes)
print("\n=== +0x330 child full scan (512 bytes) ===")
vals330 = read_floats(child330, 128)
for i, v in enumerate(vals330):
    off = i * 4
    if abs(v) > 0.001 and abs(v) < 100000:
        print(f"  +{hex(off):>4}: {v:>14.6f}")

# Deep scan +0x338 child
print(f"\n=== +0x338 child full scan (512 bytes) ===")
vals338 = read_floats(child338, 128)
for i, v in enumerate(vals338):
    off = i * 4
    if abs(v) > 0.001 and abs(v) < 100000:
        print(f"  +{hex(off):>4}: {v:>14.6f}")

# Also scan the coord object for any basis vectors we might have missed
# The old system used orthonormal basis at +0xD4 on the old heap object
# Let's check if there's a basis matrix somewhere in the coord object
print("\n=== Looking for orthonormal basis vectors in coord object ===")
for start_off in range(0, 0x360, 4):
    # Check for 3 consecutive floats that form a unit vector
    vals = read_floats(obj + start_off, 3)
    if vals and len(vals) == 3:
        x, y, z = vals
        mag = math.sqrt(x*x + y*y + z*z)
        if 0.85 < mag < 1.15 and abs(x) > 0.05 and abs(z) > 0.05:
            yaw = math.degrees(math.atan2(x, z))
            pitch = math.degrees(math.atan2(y, math.sqrt(x*x + z*z)))
            print(f"  +{hex(start_off)}: ({x:.4f}, {y:.4f}, {z:.4f}) mag={mag:.4f} yaw={yaw:.1f} pitch={pitch:.1f}")
