#!/usr/bin/env python3
"""Search memory dump for coord-like objects near player coordinates."""
import struct, math, json, os

dump_dir = r"C:\RIFT MODDING\RiftReader\artifacts\memory-dumps\2026-07-12"
manifest_path = os.path.join(dump_dir, "manifest.json")
regions_path = os.path.join(dump_dir, "regions.bin")

with open(manifest_path, 'r') as f:
    manifest = json.load(f)

regions = manifest["regions"]
print(f"Searching {len(regions)} regions for coord objects")

# Player coord object address
player_obj = 0x257b99b0b70
player_x, player_y, player_z = 7162.0, 818.0, 3417.0

candidates = []

with open(regions_path, 'rb') as f:
    for region in regions:
        base = region["base_int"]
        size = region["read_size"]
        offset = region["file_offset"]
        
        # Skip large regions
        if size > 1024 * 1024:
            continue
        
        f.seek(offset)
        data = f.read(size)
        
        # Look for float values that could be coordinates
        for off in range(0, len(data) - 0x400, 4):
            try:
                x = struct.unpack('<f', data[off:off+4])[0]
                y = struct.unpack('<f', data[off+4:off+8])[0]
                z = struct.unpack('<f', data[off+8:off+12])[0]
            except:
                continue
            
            # Check if this could be a coordinate triplet
            if not (5000 < x < 10000 and 500 < y < 2000 and 2000 < z < 5000):
                continue
            
            # Skip if this is our player's coord object
            obj_addr = base + off
            if abs(obj_addr - player_obj) < 0x1000:
                continue
            
            # Check if +0x320/+0x324/+0x328 are also coordinates
            if off + 0x400 > len(data):
                continue
            
            try:
                coord_x = struct.unpack('<f', data[off+0x320:off+0x324])[0]
                coord_y = struct.unpack('<f', data[off+0x324:off+0x328])[0]
                coord_z = struct.unpack('<f', data[off+0x328:off+0x32c])[0]
            except:
                continue
            
            if 5000 < coord_x < 10000 and 500 < coord_y < 2000 and 2000 < coord_z < 5000:
                # Found a coord-like object
                dist = math.sqrt((coord_x - player_x)**2 + (coord_z - player_z)**2)
                if dist > 5:  # Not our player
                    candidates.append((obj_addr, coord_x, coord_y, coord_z, dist))
                elif dist < 2:
                    # This might be our player — check +0x300 counter
                    print(f"Potential player match: {hex(obj_addr)}: ({coord_x:.2f}, {coord_y:.2f}, {coord_z:.2f})")

# Sort by distance from player
candidates.sort(key=lambda c: c[4])

print(f"\nFound {len(candidates)} coord-like objects near player:")
for addr, x, y, z, dist in candidates[:30]:
    print(f"  {hex(addr)}: ({x:.2f}, {y:.2f}, {z:.2f}) dist={dist:.1f}")
