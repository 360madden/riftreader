#!/usr/bin/env python3
"""Search for character name in heap to find player entity object."""

import ctypes
import struct
import sys
import time

kernel32 = ctypes.windll.kernel32
PROCESS_VM_READ = 0x0010


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

    # Search for "Atank" as UTF-16LE (RIFT stores strings in Lua heap as UTF-16)
    target = "Atank".encode("utf-16-le")
    print(f"Searching for '{'Atank'.encode()}' ({len(target)} bytes) in heap...")

    # Scan the large arenas
    arenas = [
        0x201f2980000, 0x201f4980000, 0x201f6980000,
        0x201f8980000, 0x201fa980000, 0x201fc980000,
    ]
    ARENA_SIZE = 32 * 1024 * 1024

    # Also scan the Lua heap regions (where addon strings live)
    lua_heaps = [
        0x201b2800000, 0x1000000,  # 16MB
        0x201b3810000, 0xA00000,   # 10MB
        0x201b7cb6000, 0x1B00000,  # 27MB
    ]

    t0 = time.time()
    matches = []

    for i in range(0, len(arenas), 1):
        start = arenas[i]
        data = read_bytes(h, start, ARENA_SIZE)
        if not data:
            continue

        # Find all occurrences of target
        idx = 0
        while True:
            pos = data.find(target, idx)
            if pos == -1:
                break
            addr = start + pos
            matches.append(hex(addr))
            idx = pos + 1

    # Also scan some additional regions
    for i in range(0, len(lua_heaps), 2):
        start = lua_heaps[i]
        size = lua_heaps[i + 1]
        data = read_bytes(h, start, size)
        if not data:
            continue
        idx = 0
        while True:
            pos = data.find(target, idx)
            if pos == -1:
                break
            addr = start + pos
            matches.append(hex(addr))
            idx = pos + 1

    elapsed = time.time() - t0

    if matches:
        print(f"\nFound {len(matches)} matches for 'Atank':")
        for m in matches:
            print(f"  {m}")
    else:
        print("No matches found. Trying 'ank' substring...")
        target2 = "ank".encode("utf-16-le")
        for i in range(0, len(arenas), 1):
            start = arenas[i]
            data = read_bytes(h, start, ARENA_SIZE)
            if not data:
                continue
            idx = 0
            count = 0
            while True:
                pos = data.find(target2, idx)
                if pos == -1:
                    break
                if count < 5:
                    # Check context (6 bytes before and after)
                    ctx_start = max(0, pos - 6)
                    ctx_end = min(len(data), pos + len(target2) + 6)
                    ctx = data[ctx_start:ctx_end]
                    try:
                        ctx_str = ctx.decode('utf-16-le', errors='replace')
                    except:
                        ctx_str = str(ctx)
                    print(f"  {hex(start + pos)}: ...{ctx_str}...")
                count += 1
                idx = pos + 1
            if count > 5:
                print(f"  ... and {count - 5} more in arena {hex(start)}")

    print(f'\nTime: {elapsed:.1f}s')
    kernel32.CloseHandle(h)


if __name__ == "__main__":
    main()
