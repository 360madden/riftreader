#!/usr/bin/env python3
"""Scan heap near player coord object for similar objects."""
import ctypes, ctypes.wintypes, struct, math

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

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--pid", type=int, required=True)
args = parser.parse_args()
pid = args.pid

base = find_base(pid)
obj = read_ptr(pid, base + 0x32EBDC0)

# Get player position
player_x = read_f32(pid, obj + 0x320)
player_y = read_f32(pid, obj + 0x324)
player_z = read_f32(pid, obj + 0x328)
print(f"Player coord object: {hex(obj)}")
print(f"Player position: ({player_x:.2f}, {player_y:.2f}, {player_z:.2f})")

# Scan the heap page that contains the coord object
# The heap allocator typically allocates nearby objects in nearby pages
page_size = 0x1000  # 4KB pages
scan_range = 0x100000  # 1MB range

candidates = []
for offset in range(-scan_range, scan_range, 4):
    addr = obj + offset
    if addr < 0x10000:
        continue
    
    # Read +0x320/+0x324/+0x328 (coord offsets)
    x = read_f32(pid, addr + 0x320)
    y = read_f32(pid, addr + 0x324)
    z = read_f32(pid, addr + 0x328)
    
    if x is None or y is None or z is None:
        continue
    
    # Check if coordinates are in valid range
    if not (5000 < x < 10000 and 500 < y < 2000 and 2000 < z < 5000):
        continue
    
    # Skip if this is our player's coord object
    if offset == 0:
        continue
    
    # Check if +0x330 is a valid pointer
    ptr = read_ptr(pid, addr + 0x330)
    if ptr is None or ptr < 0x10000:
        continue
    
    # Check if +0x158 (heading) is a valid float
    heading = read_f32(pid, ptr + 0x158)
    if heading is None or heading != heading:  # NaN check
        continue
    
    # Check if +0x300 (counter) is a valid float
    counter = read_f32(pid, addr + 0x300)
    if counter is None or counter != counter:
        continue
    
    dist = math.sqrt((x - player_x)**2 + (z - player_z)**2)
    candidates.append((addr, x, y, z, heading, counter, dist))

# Sort by distance
candidates.sort(key=lambda c: c[6])

print(f"\nFound {len(candidates)} coord-like objects:")
for addr, x, y, z, heading, counter, dist in candidates[:20]:
    heading_deg = math.degrees(heading) if abs(heading) < 10 else 0
    print(f"  {hex(addr)}: ({x:.2f}, {y:.2f}, {z:.2f}) heading={heading_deg:.1f}° counter={counter:.0f} dist={dist:.1f}")
