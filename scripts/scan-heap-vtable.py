#!/usr/bin/env python3
"""Scan heap for objects with the same vtable as the player object."""

import ctypes
import struct
import sys

kernel32 = ctypes.windll.kernel32

PLAYER_PTR = 0x201b68d06a0
VTABLE = 0x7FF72B1C8FD8
PLAYER_X, PLAYER_Z = 6974.5, 3324.5
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

    scan_regions = [
        (0x201B6800000, 0x100000),  # 1MB near player
        (0x201B6700000, 0x100000),  # 1MB before
        (0x201B6900000, 0x100000),  # 1MB after
        (0x201B5000000, 0x200000),  # 2MB further before
        (0x201B6A00000, 0x200000),  # 2MB further after
    ]

    found = []

    for start, size in scan_regions:
        data = read_bytes(h, start, size)
        if not data:
            continue

        for off in range(0, len(data) - 8, 8):
            val = struct.unpack_from('<Q', data, off)[0]
            if val != VTABLE:
                continue

            obj_base = start + off

            # Read coordinates
            x_data = read_bytes(h, obj_base + 0x320, 4)
            y_data = read_bytes(h, obj_base + 0x324, 4)
            z_data = read_bytes(h, obj_base + 0x328, 4)
            if not (x_data and y_data and z_data):
                continue

            x = struct.unpack('<f', x_data)[0]
            y = struct.unpack('<f', y_data)[0]
            z = struct.unpack('<f', z_data)[0]

            if x != x or y != y or z != z:  # NaN
                continue
            if abs(x) > 100000 or abs(y) > 2000 or abs(z) > 100000:
                continue
            if x == 0 and y == 0 and z == 0:
                continue

            h_data = read_bytes(h, obj_base + 0x300, 4)
            heading = (struct.unpack('<f', h_data)[0] % 360) if h_data else None

            dist = ((x - PLAYER_X)**2 + (z - PLAYER_Z)**2)**0.5
            is_player = (obj_base == PLAYER_PTR)

            found.append({
                'addr': hex(obj_base),
                'x': round(x, 1), 'y': round(y, 1), 'z': round(z, 1),
                'heading': round(heading, 1) if heading else None,
                'dist': round(dist, 1),
                'isPlayer': is_player,
            })

    found.sort(key=lambda c: c['dist'])
    for c in found:
        marker = ' <<<< PLAYER' if c['isPlayer'] else ''
        print(f"  {c['addr']}: ({c['x']}, {c['y']}, {c['z']}) H={c['heading']} dist={c['dist']}m{marker}")

    print(f'\nTotal: {len(found)} objects with player vtable')
    kernel32.CloseHandle(h)


if __name__ == "__main__":
    main()
