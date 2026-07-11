#!/usr/bin/env python3
"""Inspect the engine subsystem container at 0x32DD7E8."""

import ctypes
import struct
import sys

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

    base = 0x7FF728B80000
    container_rva = 0x32DD7E8

    # Read container pointer
    data = read_bytes(h, base + container_rva, 8)
    if not data:
        print("Cannot read container")
        sys.exit(1)

    container_ptr = struct.unpack('<Q', data)[0]
    print(f"Container RVA: {hex(container_rva)}")
    print(f"Container ptr: {hex(container_ptr)}")

    # Read the container's contents (array of pointers)
    # It's likely a fixed-size array of engine subsystem pointers
    print("\n=== Container entries (first 32) ===")
    for i in range(32):
        entry_data = read_bytes(h, container_ptr + i * 8, 8)
        if not entry_data:
            break
        val = struct.unpack('<Q', entry_data)[0]

        # Try to read what this pointer points to
        desc = ""
        if 0x10000 < val < 0x7FFFFFFFFFFFFFFF:
            target_data = read_bytes(h, val, 16)
            if target_data:
                vtable = struct.unpack('<Q', target_data[:8])[0]
                second = struct.unpack('<Q', target_data[8:16])[0]
                is_text = 0x7FF728000000 <= vtable <= 0x7FF72C000000
                desc = f" -> vtable={hex(vtable)} {'[text]' if is_text else ''}"

                # Check if it has coordinates nearby
                coord_data = read_bytes(h, val + 0x320, 12)
                if coord_data:
                    x, y, z = struct.unpack('<fff', coord_data)
                    if 1000 < x < 15000 and 0 < y < 2000 and 1000 < z < 15000:
                        desc += f" COORDS=({x:.1f}, {y:.1f}, {z:.1f})"

        print(f"  [{i:2d}] {hex(val)}{desc}")

    kernel32.CloseHandle(h)


if __name__ == "__main__":
    main()
