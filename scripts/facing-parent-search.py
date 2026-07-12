#!/usr/bin/env python3
"""Search for the parent object that contains the coord object."""
import ctypes, struct, time, math

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32
COORD_RVA = 0x32EBDC0
base = 0x7FF728B80000
PID = 36332

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
print(f"Coord object: {hex(obj)}")

# The coord object is at +0x32EBDC0 as a static global.
# The object itself has many outbound pointers.
# Let's check if any of these point back to the object (circular reference = parent)
# and scan those potential parents for facing data.

# First, let's look at the objects pointed to by the coord object's early pointers
# +0x00 -> 0x7ff72b1c8fd8 (static data, likely vtable or type info)
# +0x10 -> self (0x257b99b0b70) - self-reference
# +0x30 -> self - another self-reference
# +0x50 -> self - another self-reference
# +0x70 -> self - another self-reference

# The self-references at +0x10, +0x30, +0x50, +0x70 suggest this IS the object
# and the coord values are embedded directly.

# Let's look at the static data pointers to understand the class hierarchy
for off in [0, 8, 0x18, 0x20, 0x38, 0x58]:
    v = read_ptr(obj + off)
    if v and v > 0x10000:
        # Check if it points to static data (in .rdata/.data sections)
        if base < v < base + 0x10000000:
            rva = v - base
            print(f"  +{hex(off)}: {hex(v)} (RVA {hex(rva)}) - static data")
        else:
            print(f"  +{hex(off)}: {hex(v)} - heap")

# The old system had the coord object as a CHILD of a larger player object.
# Let's search for any pointer in the coord object that points to a larger object
# that contains both coords AND facing.
# We know coords are at +0x320, and facing target was at +0x30C in old system.
# Let's check if +0x30C is still pointing to something useful on the NEW root.

# Actually, +0x30C is a float (6967.3), not a pointer. But let's check nearby
# for any pointer that could be a parent container.
print("\n--- Checking all pointers in coord object for potential parents ---")
for off in range(0, 0x360, 8):
    v = read_ptr(obj + off)
    if not v or v < 0x10000:
        continue
    # Check if this pointer is in the heap (not static)
    if v > base + 0x10000000:
        # This is a heap pointer. Scan it for coords to see if it's a parent.
        floats = read_floats(v, 4)
        if floats and len(floats) >= 3:
            x, y, z = floats[0], floats[1], floats[2]
            # Check if these look like game coordinates
            if 5000 < abs(x) < 10000 and 500 < abs(y) < 2000 and 2000 < abs(z) < 5000:
                print(f"  +{hex(off)}: {hex(v)} -> coords ({x:.1f}, {y:.1f}, {z:.1f})")

# Let's also scan for any float that looks like an angle (0-360 or -180 to 180)
# in the coord object's immediate neighborhood
print("\n--- Scanning coord object for angle-like values ---")
for off in range(0, 0x360, 4):
    d = read_bytes(obj + off, 4)
    if d:
        f = struct.unpack('<f', d)[0]
        i = struct.unpack('<I', d)[0]
        # Check if float is in angle range
        if 0 < f < 360 and f != int(f):  # non-integer angle
            print(f"  +{hex(off)}: float={f:.4f} (possible angle)")
        # Check if uint looks like packed angles
        if 0 < i < 0xFFFFFFFF:
            # Try as half-floats or packed data
            pass
