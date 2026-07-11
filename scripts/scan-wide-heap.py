#!/usr/bin/env python3
"""
Wide heap scan: find ALL objects with coordinate-like floats at +0x320.
Scans a large region of the heap.
"""

import ctypes
import struct
import sys
import time

kernel32 = ctypes.windll.kernel32
PROCESS_VM_READ = 0x0010
PLAYER_X, PLAYER_Z = 6974.5, 3324.5


def read_bytes(h, addr, size):
    buf = ctypes.create_string_buffer(size)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(br))
    return buf.raw if ok and br.value == size else None


def main():
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else 16008
    h = kernel32.OpenProcess(PROCESS_VM_READ, False, pid)
    if not h:
        print("Cannot open process")
        sys.exit(1)

    # Scan a wide range of the heap
    # Heap for this process likely lives in 0x201B0000000 range
    # Let's scan 16MB in various directions
    regions = [
        (0x201B0000000, 0x1000000),  # 16MB starting at known heap
        (0x2018000000, 0x1000000),   # 16MB before (if address is 10-digit)
        (0x201C000000, 0x1000000),   # 16MB after
        (0x201D000000, 0x1000000),   # further after
        (0x2017000000, 0x1000000),   # further before
    ]

    # But actually, let's try to find the heap bounds from the process
    # For now, just scan what we can

    found = []
    total_ptrs_checked = 0

    t0 = time.time()
    for start, size in regions:
        data = read_bytes(h, start, size)
        if not data:
            continue

        for off in range(0, len(data) - 8, 8):
            ptr = struct.unpack_from('<Q', data, off)[0]

            # Must be a plausible heap pointer (user-mode address)
            if ptr < 0x10000 or ptr > 0x7FFFFFFFFFFFFFFF:
                continue
            # Skip if it points into .text or .data (not heap)
            if 0x7FF728000000 <= ptr <= 0x7FF72C000000:
                continue

            total_ptrs_checked += 1

            # Read 12 bytes at +0x320
            coord_data = read_bytes(h, ptr + 0x320, 12)
            if not coord_data:
                continue

            x, y, z = struct.unpack('<fff', coord_data)

            if x != x or y != y or z != z:  # NaN
                continue
            if not (1000 < x < 15000 and 0 < y < 2000 and 1000 < z < 15000):
                continue
            if x == 0 and y == 0 and z == 0:
                continue

            # Read heading
            h_data = read_bytes(h, ptr + 0x300, 4)
            heading = (struct.unpack('<f', h_data)[0] % 360) if h_data else None

            dist = ((x - PLAYER_X)**2 + (z - PLAYER_Z)**2)**0.5

            found.append({
                'addr': hex(ptr),
                'from': hex(start + off),
                'x': round(x, 1), 'y': round(y, 1), 'z': round(z, 1),
                'heading': round(heading, 1) if heading else None,
                'dist': round(dist, 1),
            })

    elapsed = time.time() - t0

    # Deduplicate
    seen = set()
    unique = []
    for c in found:
        if c['addr'] not in seen:
            seen.add(c['addr'])
            unique.append(c)

    unique.sort(key=lambda c: c['dist'])
    for c in unique:
        print(f"  {c['addr']}: ({c['x']}, {c['y']}, {c['z']}) H={c['heading']} dist={c['dist']}m")

    print(f'\nTotal: {len(unique)} coordinate-bearing objects')
    print(f'Pointers checked: {total_ptrs_checked:,}')
    print(f'Time: {elapsed:.1f}s')
    kernel32.CloseHandle(h)


if __name__ == "__main__":
    main()
