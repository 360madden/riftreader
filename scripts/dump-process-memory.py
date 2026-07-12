#!/usr/bin/env python3
"""Dump all readable memory from a process for offline Ghidra analysis."""

import ctypes
import ctypes.wintypes
import json
import struct
import sys
import time
from pathlib import Path

kernel32 = ctypes.windll.kernel32

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('BaseAddress', ctypes.c_void_p),
        ('AllocationBase', ctypes.c_void_p),
        ('AllocationProtect', ctypes.wintypes.DWORD),
        ('RegionSize', ctypes.c_size_t),
        ('State', ctypes.wintypes.DWORD),
        ('Protect', ctypes.wintypes.DWORD),
        ('Type', ctypes.wintypes.DWORD),
    ]

READABLE_PROTECTS = {0x02, 0x04, 0x20, 0x40, 0x80}  # RW, WC, XRX, XRW, XWC
PROTECT_NAMES = {
    0x01: "R", 0x02: "RW", 0x04: "WC", 0x08: "Guard",
    0x10: "X", 0x20: "XR", 0x40: "XRW", 0x80: "XWC",
}


def dump_process(pid, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
    h = kernel32.OpenProcess(0x0410, False, pid)
    if not h:
        print(f"ERROR: Cannot open PID {pid}")
        return

    print(f"Enumerating memory regions for PID {pid}...")
    regions = []
    addr = 0
    while addr < 0x7FFFFFFFFFFFFFFF:
        mbi = MEMORY_BASIC_INFORMATION()
        result = kernel32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
        if result == 0:
            break

        base = mbi.BaseAddress if mbi.BaseAddress else addr
        if mbi.State == 0x1000 and mbi.Protect in READABLE_PROTECTS:
            regions.append({
                'base': base,
                'size': mbi.RegionSize,
                'protect': mbi.Protect,
                'protect_name': PROTECT_NAMES.get(mbi.Protect, hex(mbi.Protect)),
            })

        addr = base + mbi.RegionSize
        if addr <= base:
            break

    total_size = sum(r['size'] for r in regions)
    print(f"Found {len(regions)} readable regions, {total_size / 1024 / 1024:.1f} MB total")

    # Dump regions
    manifest = {
        'pid': pid,
        'region_count': len(regions),
        'total_bytes': total_size,
        'regions': [],
    }

    start_time = time.time()
    bytes_read = 0
    region_file = output_dir / "regions.bin"

    with open(region_file, 'wb') as f:
        for i, region in enumerate(regions):
            base = region['base']
            size = region['size']
            buf = ctypes.create_string_buffer(size)
            br = ctypes.c_size_t(0)

            ok = kernel32.ReadProcessMemory(h, ctypes.c_void_p(base), buf, size, ctypes.byref(br))
            data = buf.raw[:br.value] if ok else b''

            region_offset = f.tell()
            f.write(data)

            manifest['regions'].append({
                'index': i,
                'base': hex(base),
                'base_int': base,
                'requested_size': size,
                'read_size': len(data),
                'protect': region['protect_name'],
                'file_offset': region_offset,
            })

            bytes_read += len(data)
            pct = bytes_read / total_size * 100 if total_size else 0
            elapsed = time.time() - start_time
            rate = bytes_read / 1024 / 1024 / elapsed if elapsed > 0 else 0
            print(f"\r  [{i+1}/{len(regions)}] {pct:5.1f}% {bytes_read/1024/1024:.1f} MB / {total_size/1024/1024:.1f} MB ({rate:.0f} MB/s)", end="", flush=True)

    kernel32.CloseHandle(h)
    elapsed = time.time() - start_time

    # Save manifest
    manifest['elapsed_seconds'] = round(elapsed, 1)
    manifest['bytes_per_second'] = round(bytes_read / elapsed) if elapsed > 0 else 0
    manifest['output_files'] = {
        'regions_bin': str(region_file),
        'manifest_json': str(output_dir / "manifest.json"),
    }

    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n\nDone in {elapsed:.1f}s ({bytes_read / 1024 / 1024 / elapsed:.0f} MB/s)")
    print(f"Output: {output_dir}")
    print(f"  regions.bin: {region_file.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"  manifest.json: {len(regions)} regions indexed")

    # Also save key addresses for quick lookup
    key_addrs = {
        'coord_rva': 0x32EBDC0,
        'coord_obj': None,
        'base': None,
    }
    for r in manifest['regions']:
        base_int = r['base_int']
        if 0x7FF728000000 <= base_int <= 0x7FF730000000:
            key_addrs['base'] = hex(base_int)

    with open(output_dir / "key_addresses.json", "w") as f:
        json.dump(key_addrs, f, indent=2)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Dump process memory for Ghidra analysis")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--output", type=str, default="artifacts/memory-dumps")
    args = parser.parse_args()

    dump_process(args.pid, args.output)


if __name__ == "__main__":
    main()
