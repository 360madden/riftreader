#!/usr/bin/env python3
"""Search a memory dump for float patterns — find angle-like values, basis vectors, etc."""

import json
import struct
import sys
from pathlib import Path


def load_manifest(dump_dir):
    dump_dir = Path(dump_dir)
    with open(dump_dir / "manifest.json") as f:
        return json.load(f)


def read_region(dump_dir, region, offset, length):
    """Read bytes from a region at a given offset."""
    bin_path = Path(dump_dir) / "regions.bin"
    file_offset = region['file_offset'] + offset
    with open(bin_path, 'rb') as f:
        f.seek(file_offset)
        return f.read(length)


def search_dump(dump_dir, manifest):
    """Search the entire dump for interesting float patterns."""
    dump_dir = Path(dump_dir)
    bin_path = dump_dir / "regions.bin"

    # Known values from live session
    known = {
        'player_x': 7052.71,
        'player_y': 843.90,
        'player_z': 3236.37,
        'rotation_counter': 30501.09,
        'heading_mod360': 261.1,
    }

    print(f"Searching {manifest['total_bytes'] / 1024 / 1024:.0f} MB dump...")

    results = {
        'near_player_coords': [],
        'angle_like': [],
        'unit_vectors': [],
        'large_counters': [],
    }

    with open(bin_path, 'rb') as f:
        for region in manifest['regions']:
            base = region['base_int']
            size = region['read_size']
            if size < 4:
                continue

            f.seek(region['file_offset'])

            # Read in 1MB chunks
            chunk_size = 1024 * 1024
            for chunk_offset in range(0, size, chunk_size):
                f.seek(region['file_offset'] + chunk_offset)
                data = f.read(min(chunk_size + 3, size - chunk_offset))
                if not data:
                    break

                for i in range(0, len(data) - 3, 4):
                    abs_addr = base + chunk_offset + i
                    val = struct.unpack('<f', data[i:i+4])[0]

                    # Skip zeros, NaN, denormals
                    if val == 0.0 or val != val or abs(val) < 0.0001:
                        continue

                    # Check if near player coordinates
                    for name, target in [('x', known['player_x']), ('y', known['player_y']), ('z', known['player_z'])]:
                        if abs(val - target) < 1.0:
                            results['near_player_coords'].append({
                                'address': hex(abs_addr),
                                'value': val,
                                'field': name,
                                'delta': val - target,
                            })

                    # Check for angle-like values (0-360 range, non-integer)
                    if 0 < val < 360 and val != int(val) and abs(val - int(val)) > 0.01:
                        results['angle_like'].append({
                            'address': hex(abs_addr),
                            'value': val,
                        })

                    # Check for unit vectors (magnitude near 1.0)
                    if 0.85 < val < 1.15:
                        # Check if next 2 floats also exist and form a unit vector
                        if i + 12 <= len(data):
                            v2 = struct.unpack('<f', data[i+4:i+8])[0]
                            v3 = struct.unpack('<f', data[i+8:i+12])[0]
                            mag = (val**2 + v2**2 + v3**2) ** 0.5
                            if 0.95 < mag < 1.05 and abs(v2) > 0.05 and abs(v3) > 0.05:
                                results['unit_vectors'].append({
                                    'address': hex(abs_addr),
                                    'vector': [val, v2, v3],
                                    'magnitude': mag,
                                })

                    # Check for large counters (like the rotation counter)
                    if 10000 < val < 100000 and val == int(val):
                        results['large_counters'].append({
                            'address': hex(abs_addr),
                            'value': val,
                        })

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump-dir", default="artifacts/memory-dumps/2026-07-12")
    args = parser.parse_args()

    manifest = load_manifest(args.dump_dir)
    results = search_dump(args.dump_dir, manifest)

    print(f"\n=== Results ===")
    print(f"Near player coords: {len(results['near_player_coords'])}")
    print(f"Angle-like values: {len(results['angle_like'])}")
    print(f"Unit vectors: {len(results['unit_vectors'])}")
    print(f"Large counters: {len(results['large_counters'])}")

    if results['near_player_coords']:
        print(f"\n--- Near player coordinates ---")
        for r in results['near_player_coords'][:20]:
            print(f"  {r['address']}: {r['value']:.4f} ({r['field']}, delta={r['delta']:+.4f})")

    if results['angle_like']:
        print(f"\n--- Angle-like values (0-360) ---")
        for r in results['angle_like'][:20]:
            print(f"  {r['address']}: {r['value']:.4f}")

    if results['unit_vectors']:
        print(f"\n--- Unit vectors (basis/orientation) ---")
        for r in results['unit_vectors'][:20]:
            v = r['vector']
            print(f"  {r['address']}: ({v[0]:.4f}, {v[1]:.4f}, {v[2]:.4f}) mag={r['magnitude']:.4f}")

    if results['large_counters']:
        print(f"\n--- Large counters ---")
        for r in results['large_counters'][:20]:
            print(f"  {r['address']}: {r['value']:.0f}")

    # Save results
    out_path = Path(args.dump_dir) / "search-results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
