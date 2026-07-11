#!/usr/bin/env python3
"""Enumerate memory regions of the RIFT process to find heap."""

import ctypes
import ctypes.wintypes
import sys

kernel32 = ctypes.windll.kernel32

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
MEM_IMAGE = 0x1000000


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.wintypes.DWORD),
        ("Protect", ctypes.wintypes.DWORD),
        ("Type", ctypes.wintypes.DWORD),
    ]


def main():
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else 16008
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        print("Cannot open process")
        sys.exit(1)

    addr = 0
    regions = []
    mbi = MEMORY_BASIC_INFORMATION()
    mbi_size = ctypes.sizeof(mbi)

    while True:
        result = kernel32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), mbi_size)
        if result == 0:
            break

        if mbi.State == MEM_COMMIT:
            base = mbi.BaseAddress if mbi.BaseAddress else 0
            size = mbi.RegionSize
            protect = mbi.Protect
            mtype = mbi.Type

            type_str = "image" if mtype == MEM_IMAGE else ("private" if mtype == MEM_PRIVATE else "mapped")
            protect_str = ""
            if protect & 0x02: protect_str = "rw"
            elif protect & 0x20: protect_str = "rx"
            elif protect & 0x40: protect_str = "rw"
            elif protect & 0x80: protect_str = "wc"

            # Focus on private (heap) regions that are readable
            if mtype == MEM_PRIVATE and size > 0x10000:
                regions.append((base, size, protect_str))

        addr = (mbi.BaseAddress or 0) + mbi.RegionSize
        if addr >= 0x7FFFFFFFFFFFFFFF:
            break

    print(f"Found {len(regions)} large private (heap) regions:\n")
    for base, size, prot in sorted(regions, key=lambda r: r[0]):
        size_kb = size / 1024
        size_mb = size / (1024 * 1024)
        if size_mb >= 1:
            print(f"  {hex(base):>20s}  {size_mb:8.1f} MB  {prot}")
        elif size_kb >= 64:
            print(f"  {hex(base):>20s}  {size_kb:8.0f} KB  {prot}")

    kernel32.CloseHandle(h)


if __name__ == "__main__":
    main()
