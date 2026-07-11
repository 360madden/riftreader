#!/usr/bin/env python3
"""
Scan memory near the player object to find other player/NPC objects.

Usage:
    python scan-nearby-objects.py --pid <pid>
"""

import argparse
import ctypes
import json
import struct
import sys

kernel32 = ctypes.windll.kernel32

COORD_GLOBAL_RVA = 0x32EBDC0
OFFSET_X = 0x320
OFFSET_Y = 0x324
OFFSET_Z = 0x328
PROCESS_VM_READ = 0x0010


def read_bytes(handle, address, size):
    buf = ctypes.create_string_buffer(size)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(handle, ctypes.c_void_p(address), buf, size, ctypes.byref(br))
    if not ok or br.value != size:
        return None
    return buf.raw


def read_u64(handle, address):
    data = read_bytes(handle, address, 8)
    return struct.unpack('<Q', data)[0] if data else None


def read_f32(handle, address):
    data = read_bytes(handle, address, 4)
    return struct.unpack('<f', data)[0] if data else None


def main():
    parser = argparse.ArgumentParser(description="Scan for nearby player/NPC objects")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    handle = kernel32.OpenProcess(PROCESS_VM_READ, False, args.pid)
    if not handle:
        print("Cannot open process", file=sys.stderr)
        sys.exit(1)

    # Find module base (fast path)
    base = None
    for addr in [0x7FF728B80000, 0x7FF728A00000, 0x7FF728C00000]:
        data = read_bytes(handle, addr, 2)
        if data == b"MZ":
            base = addr
            break
    if not base:
        print("Cannot find module base", file=sys.stderr)
        sys.exit(1)

    # Read player object pointer
    player_ptr = read_u64(handle, base + COORD_GLOBAL_RVA)
    if not player_ptr or player_ptr < 0x10000:
        print("Player pointer invalid", file=sys.stderr)
        sys.exit(1)

    # Read player coords for reference
    px = read_f32(handle, player_ptr + OFFSET_X)
    py = read_f32(handle, player_ptr + OFFSET_Y)
    pz = read_f32(handle, player_ptr + OFFSET_Z)

    # Scan .data section for pointers that resolve to coordinate-bearing objects
    # Scan a wider range around the player global
    scan_ranges = [
        (base + 0x32EB000, 0x2000),   # Near player global
        (base + 0x32DD000, 0x2000),   # Near container
        (base + 0x32E0000, 0x2000),   # Between
    ]

    candidates = []
    seen_ptrs = set()

    for scan_start, scan_size in scan_ranges:
        scan_data = read_bytes(handle, scan_start, scan_size)
        if not scan_data:
            continue

        for offset in range(0, len(scan_data), 8):
            ptr = struct.unpack('<Q', scan_data[offset:offset+8])[0]
            if ptr < 0x10000 or ptr > 0x7FFFFFFFFFFFFFFF:
                continue
            if ptr in seen_ptrs:
                continue
            seen_ptrs.add(ptr)

            # Try reading coordinates at +0x320
            x = read_f32(handle, ptr + OFFSET_X)
            y = read_f32(handle, ptr + OFFSET_Y)
            z = read_f32(handle, ptr + OFFSET_Z)

            if x is None or y is None or z is None:
                continue
            if x != x or y != y or z != z:  # NaN check
                continue
            if abs(x) > 100000 or abs(y) > 100000 or abs(z) > 100000:
                continue
            if x == 0.0 and y == 0.0 and z == 0.0:
                continue

            # Reasonable RIFT coordinate range
            if not (1000 < x < 15000 and 0 < y < 2000 and 1000 < z < 15000):
                continue

            # Check heading at +0x300
            heading = read_f32(handle, ptr + 0x300)
            heading_deg = (heading % 360) if heading is not None else None

            # Check speed at +0x304
            speed = read_f32(handle, ptr + 0x304)

            is_player = (ptr == player_ptr)
            abs_rva = (scan_start + offset) - base

            candidates.append({
                "rva": hex(abs_rva),
                "heapPtr": hex(ptr),
                "x": round(x, 2),
                "y": round(y, 2),
                "z": round(z, 2),
                "headingDeg": round(heading_deg, 2) if heading_deg is not None else None,
                "speed": round(speed, 4) if speed is not None else None,
                "isPlayer": is_player,
                "distToPlayer": round(((x - px)**2 + (z - pz)**2)**0.5, 2) if not is_player else 0,
            })

    # Sort by distance to player
    candidates.sort(key=lambda c: c["distToPlayer"])

    if args.json:
        print(json.dumps({
            "pid": args.pid,
            "moduleBase": hex(base),
            "playerPtr": hex(player_ptr),
            "playerCoords": {"x": round(px, 2), "y": round(py, 2), "z": round(pz, 2)},
            "candidates": candidates,
            "totalFound": len(candidates),
        }, indent=2))
    else:
        print(f"Player: {hex(player_ptr)} ({px:.1f}, {py:.1f}, {pz:.1f})")
        print(f"Found {len(candidates)} coordinate-bearing objects:\n")
        for c in candidates:
            marker = " <<< PLAYER" if c["isPlayer"] else ""
            print(f"  {c['rva']}: ptr={c['heapPtr']} ({c['x']:.1f}, {c['y']:.1f}, {c['z']:.1f}) "
                  f"dist={c['distToPlayer']:.1f}m{marker}")

    kernel32.CloseHandle(handle)


if __name__ == "__main__":
    main()
