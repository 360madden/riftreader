#!/usr/bin/env python3
"""Targeted search near the coord object for facing-related floats."""
import json, struct, math
from pathlib import Path

dump_dir = Path("artifacts/memory-dumps/2026-07-12")
with open(dump_dir / "manifest.json") as f:
    m = json.load(f)

target = 0x257b99b0b70
bin_path = dump_dir / "regions.bin"

# Find the region containing the coord object
for r in m["regions"]:
    base = r["base_int"]
    end = base + r["read_size"]
    if base <= target < end:
        print("Coord object in region:", hex(base), "size=", r["read_size"] // 1024 // 1024, "MB")
        
        # Read the entire region
        with open(bin_path, "rb") as f:
            f.seek(r["file_offset"])
            data = f.read(r["read_size"])
        
        print("Read", len(data) // 1024 // 1024, "MB")
        
        # Search for floats that look like angles (0-360, non-integer)
        # and unit vectors
        angle_like = []
        unit_vecs = []
        
        for i in range(0, len(data) - 11, 4):
            val = struct.unpack("<f", data[i:i+4])[0]
            
            # Skip zeros, NaN, denormals
            if val == 0.0 or val != val or abs(val) < 0.0001:
                continue
            
            # Angle-like (0-360)
            if 0 < val < 360 and val != int(val):
                addr = base + i
                angle_like.append((hex(addr), val))
            
            # Unit vector check
            if 0.85 < val < 1.15:
                v2 = struct.unpack("<f", data[i+4:i+8])[0]
                v3 = struct.unpack("<f", data[i+8:i+12])[0]
                mag = (val**2 + v2**2 + v3**2) ** 0.5
                if 0.95 < mag < 1.05 and abs(v2) > 0.05 and abs(v3) > 0.05:
                    addr = base + i
                    unit_vecs.append((hex(addr), val, v2, v3, mag))
        
        print("\nAngle-like values:", len(angle_like))
        for addr, val in angle_like[:30]:
            print("  ", addr, ":", round(val, 4))
        
        print("\nUnit vectors:", len(unit_vecs))
        for addr, v1, v2, v3, mag in unit_vecs[:30]:
            yaw = math.degrees(math.atan2(v1, v3))
            print("  ", addr, ":", round(v1, 4), round(v2, 4), round(v3, 4), "yaw=", round(yaw, 1))
        
        break
