#!/usr/bin/env python3
"""Scan heap for other coordinate objects (NPCs, targets, other players)."""
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

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--pid", type=int, required=True)
parser.add_argument("--player-x", type=float, default=7162.0)
parser.add_argument("--player-z", type=float, default=3417.0)
args = parser.parse_args()
pid = args.pid
player_x = args.player_x
player_z = args.player_z

base = find_base(pid)
obj = read_ptr(pid, base + 0x32EBDC0)

# Strategy: scan for pointers to objects that have coordinates similar to our player
# but at different positions (other entities)
# First, find all memory regions that could contain game objects

# Get the coord object's address range
print(f"Player coord object: {hex(obj)}")

# Scan for other objects that look like coord objects
# Key pattern: coordinates that change, camera state pointer, heading float
# We'll scan for objects that have:
# 1. Float values in the coordinate range (5000-10000)
# 2. A pointer at +0x330 that points to a camera-like object

# Get memory regions
class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                 ("AllocationProtect", ctypes.wintypes.DWORD), ("RegionSize", ctypes.c_size_t),
                 ("State", ctypes.wintypes.DWORD), ("Protect", ctypes.wintypes.DWORD),
                 ("Type", ctypes.wintypes.DWORD)]

h = kernel32.OpenProcess(0x0010, False, pid)

regions = []
addr = 0
while addr < 0x7FFFFFFFFFFF:
    mbi = MEMORY_BASIC_INFORMATION()
    if kernel32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)) == 0:
        break
    if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x40):  # MEM_COMMIT, PAGE_READWRITE
        regions.append((mbi.BaseAddress, mbi.RegionSize))
    addr = mbi.BaseAddress + mbi.RegionSize
    if addr <= mbi.BaseAddress:
        break

kernel32.CloseHandle(h)

print(f"Found {len(regions)} committed RW regions")

# Scan regions for coord-like objects
candidates = []
for reg_addr, reg_size in regions:
    if reg_size > 1024 * 1024:  # Skip large regions (>1MB)
        continue
    data = read_bytes(pid, reg_addr, min(reg_size, 4096))
    if not data:
        continue
    
    # Look for float values that could be coordinates
    for off in range(0, len(data) - 20, 4):
        try:
            x = struct.unpack('<f', data[off:off+4])[0]
            y = struct.unpack('<f', data[off+4:off+8])[0]
            z = struct.unpack('<f', data[off+8:off+12])[0]
        except:
            continue
        
        # Check if this could be a coordinate triplet
        if not (5000 < x < 10000 and 500 < y < 2000 and 2000 < z < 5000):
            continue
        
        # Skip if this is our player's coord object
        obj_addr = reg_addr + off
        if abs(obj_addr - obj) < 100:
            continue
        
        # Check if nearby values look like a coord object
        # +0x320/+0x324/+0x328 should be coordinates
        # +0x330 should be a pointer
        try:
            coord_x = struct.unpack('<f', data[off+0x320:off+0x324])[0] if off+0x324 <= len(data) else 0
            coord_y = struct.unpack('<f', data[off+0x324:off+0x328])[0] if off+0x328 <= len(data) else 0
            coord_z = struct.unpack('<f', data[off+0x328:off+0x32c])[0] if off+0x32c <= len(data) else 0
        except:
            continue
        
        if 5000 < coord_x < 10000 and 500 < coord_y < 2000 and 2000 < coord_z < 5000:
            # Found a coord-like object
            dist = math.sqrt((coord_x - player_x)**2 + (coord_z - player_z)**2)
            if dist > 5:  # Not our player
                candidates.append((obj_addr, coord_x, coord_y, coord_z, dist))

# Sort by distance from player
candidates.sort(key=lambda c: c[4])

print(f"\nFound {len(candidates)} coord-like objects near player:")
for addr, x, y, z, dist in candidates[:20]:
    print(f"  {hex(addr)}: ({x:.2f}, {y:.2f}, {z:.2f}) dist={dist:.1f}")
