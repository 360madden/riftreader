#!/usr/bin/env python3
"""Scan large heap arenas for coordinate-bearing objects."""

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

    # The 6 large 32MB heap arenas
    arenas = [
        0x201f2980000,
        0x201f4980000,
        0x201f6980000,
        0x201f8980000,
        0x201fa980000,
        0x201fc980000,
    ]

    ARENA_SIZE = 32 * 1024 * 1024  # 32MB

    found = []
    t0 = time.time()

    for arena_start in arenas:
        data = read_bytes(h, arena_start, ARENA_SIZE)
        if not data:
            continue

        print(f"Scanning arena {hex(arena_start)} ({ARENA_SIZE // 1024 // 1024}MB)...", flush=True)

        for off in range(0, len(data) - 0x400, 8):
            # Quick filter: first 8 bytes should look like a code pointer (vtable)
            vt = struct.unpack_from('<Q', data, off)[0]
            if not (0x7FF728000000 <= vt <= 0x7FF72C000000):
                continue

            # Check if +0x320 has reasonable coordinates
            if off + 0x32C > len(data):
                continue

            x = struct.unpack_from('<f', data, off + 0x320)[0]
            y = struct.unpack_from('<f', data, off + 0x324)[0]
            z = struct.unpack_from('<f', data, off + 0x328)[0]

            if x != x or y != y or z != z:  # NaN
                continue
            if not (1000 < x < 15000 and 0 < y < 2000 and 1000 < z < 15000):
                continue
            if x == 0 and y == 0 and z == 0:
                continue

            # Check heading
            heading = struct.unpack_from('<f', data, off + 0x300)[0] % 360

            # Check it has a valid vtable (code pointer)
            obj_addr = arena_start + off
            dist = ((x - PLAYER_X)**2 + (z - PLAYER_Z)**2)**0.5

            found.append({
                'addr': hex(obj_addr),
                'arena': hex(arena_start),
                'x': round(x, 1), 'y': round(y, 1), 'z': round(z, 1),
                'heading': round(heading, 1),
                'dist': round(dist, 1),
                'vtable': hex(vt),
            })

    found.sort(key=lambda c: c['dist'])
    for c in found:
        print(f"  {c['addr']}: ({c['x']}, {c['y']}, {c['z']}) H={c['heading']} dist={c['dist']}m vt={c['vtable']}")

    print(f'\nTotal: {len(found)} coordinate-bearing objects with vtable in 6 arenas')
    print(f'Time: {time.time() - t0:.1f}s')
    kernel32.CloseHandle(h)


if __name__ == "__main__":
    main()
