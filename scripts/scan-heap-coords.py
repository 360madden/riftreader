#!/usr/bin/env python3
"""Scan heap for any objects with coordinate-like floats at +0x320."""

import ctypes
import struct
import sys

kernel32 = ctypes.windll.kernel32

PLAYER_PTR = 0x201B68D06A0
PLAYER_X, PLAYER_Y, PLAYER_Z = 6974.5, 840.3, 3324.5
PROCESS_VM_READ = 0x0010


def read_bytes(handle, addr, size):
    buf = ctypes.create_string_buffer(size)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(br))
    return buf.raw if ok and br.value == size else None


def main():
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else 16008
    h = kernel32.OpenProcess(PROCESS_VM_READ, False, pid)
    if not h:
        print("Cannot open process")
        sys.exit(1)

    # Scan a wide range of the heap
    # The player is at 0x201B68D06A0, heap likely starts around 0x201B0000000
    scan_regions = [
        (0x201B0000000, 0x400000),  # 4MB around player
        (0x201A000000, 0x400000),   # 4MB before (note: 9-digit)
        (0x201C000000, 0x400000),   # 4MB after
    ]

    found = []

    for start, size in scan_regions:
        data = read_bytes(h, start, size)
        if not data:
            continue

        # Scan every 8 bytes for pointers, then check if pointer+0x320 has coords
        for off in range(0, len(data) - 8, 8):
            ptr = struct.unpack_from('<Q', data, off)[0]

            # Filter: must look like a heap pointer
            if ptr < 0x20100000000 or ptr > 0x20200000000:
                continue

            # Read 12 bytes at +0x320 (X, Y, Z)
            coord_data = read_bytes(h, ptr + 0x320, 12)
            if not coord_data:
                continue

            x, y, z = struct.unpack('<fff', coord_data)

            # Must be reasonable coordinates
            if x != x or y != y or z != z:  # NaN
                continue
            if not (1000 < x < 15000 and 0 < y < 2000 and 1000 < z < 15000):
                continue

            # Must not be all zero
            if x == 0 and y == 0 and z == 0:
                continue

            # Check heading
            h_data = read_bytes(h, ptr + 0x300, 4)
            heading = (struct.unpack('<f', h_data)[0] % 360) if h_data else None

            # Check if it has a vtable in .text
            vt_data = read_bytes(h, ptr, 8)
            has_vtable = False
            if vt_data:
                vt = struct.unpack('<Q', vt_data)[0]
                has_vtable = 0x7FF728000000 <= vt <= 0x7FF72C000000

            dist = ((x - PLAYER_X)**2 + (z - PLAYER_Z)**2)**0.5
            is_player = (ptr == PLAYER_PTR)

            found.append({
                'addr': hex(ptr),
                'heapFrom': hex(start + off),
                'x': round(x, 1), 'y': round(y, 1), 'z': round(z, 1),
                'heading': round(heading, 1) if heading else None,
                'dist': round(dist, 1),
                'isPlayer': is_player,
                'hasVtable': has_vtable,
            })

    # Deduplicate by address
    seen = set()
    unique = []
    for c in found:
        if c['addr'] not in seen:
            seen.add(c['addr'])
            unique.append(c)

    unique.sort(key=lambda c: c['dist'])
    for c in unique:
        marker = ' <<<< PLAYER' if c['isPlayer'] else ''
        vt = ' [vtable]' if c['hasVtable'] else ''
        print(f"  {c['addr']}: ({c['x']}, {c['y']}, {c['z']}) H={c['heading']} dist={c['dist']}m{vt}{marker}")

    print(f'\nTotal: {len(unique)} coordinate-bearing heap objects')
    kernel32.CloseHandle(h)


if __name__ == "__main__":
    main()
