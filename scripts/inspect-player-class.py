#!/usr/bin/env python3
"""
Broader scan: look for the player object's class ID or RTTI info,
then find other instances of the same class.
"""

import ctypes
import struct
import sys

kernel32 = ctypes.windll.kernel32
PROCESS_VM_READ = 0x0010
PLAYER_PTR = 0x201B68D06A0


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

    base = 0x7FF728B80000

    # Read the player object's RTTI/class info
    # In Gamebryo/NetImmerse, the vtable points to a class descriptor
    # Let's read the vtable and follow it to find class info
    vt_data = read_bytes(h, PLAYER_PTR, 8)
    if vt_data:
        vtable = struct.unpack('<Q', vt_data)[0]
        print(f"Player vtable: {hex(vtable)}")

        # Read the vtable entries (function pointers)
        print("\n=== Player vtable entries ===")
        for i in range(20):
            entry = read_bytes(h, vtable + i * 8, 8)
            if not entry:
                break
            val = struct.unpack('<Q', entry)[0]
            is_text = 0x7FF728000000 <= val <= 0x7FF72C000000
            print(f"  [{i:2d}] {hex(val)} {'[text]' if is_text else ''}")

    # Read the player object's name/strings
    print("\n=== Player object strings (UTF-16) ===")
    for offset in [0xE0, 0x160, 0x190, 0x280, 0x2C0]:
        str_data = read_bytes(h, PLAYER_PTR + offset, 32)
        if str_data:
            try:
                s = str_data.decode('utf-16-le', errors='ignore').rstrip('\x00')
                if s and len(s) > 1:
                    print(f"  +{offset:03X}: '{s}'")
            except:
                pass

    # Now try to find the entity manager or scene graph
    # Look for a pointer that references the player object
    # Scan .data section for pointers to the player's heap address
    print("\n=== Scanning .data for references to player object ===")
    data_start = base + 0x320000
    data_size = 0x40000  # 256KB
    data = read_bytes(h, data_start, data_size)
    if data:
        for off in range(0, len(data), 8):
            val = struct.unpack_from('<Q', data, off)[0]
            if val == PLAYER_PTR:
                rva = hex((data_start + off) - base)
                print(f"  Found reference at RVA {rva}")

    # Also check if there's an entity list in the player object
    # Look at +0x80 (sub-object), +0xD0, +0x120, etc.
    print("\n=== Player object sub-objects ===")
    for offset in [0x80, 0x90, 0xD0, 0x120, 0x128, 0x1C0, 0x210, 0x220]:
        ptr_data = read_bytes(h, PLAYER_PTR + offset, 8)
        if ptr_data:
            ptr = struct.unpack('<Q', ptr_data)[0]
            if 0x10000 < ptr < 0x7FFFFFFFFFFFFFFF:
                # Read what's at this pointer
                target = read_bytes(h, ptr, 32)
                if target:
                    first = struct.unpack('<Q', target[:8])[0]
                    is_text = 0x7FF728000000 <= first <= 0x7FF72C000000

                    # Check for coords
                    coord = read_bytes(h, ptr + 0x320, 12)
                    has_coords = False
                    if coord:
                        x, y, z = struct.unpack('<fff', coord)
                        has_coords = 1000 < x < 15000 and 0 < y < 2000 and 1000 < z < 15000

                    print(f"  +{offset:03X}: {hex(ptr)} vtable={hex(first)} {'[text]' if is_text else ''} {'HAS_COORDS' if has_coords else ''}")

    kernel32.CloseHandle(h)


if __name__ == "__main__":
    main()
