#!/usr/bin/env python3
"""Record player positions as they move. Build navmesh from recorded path."""

import argparse
import ctypes
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

kernel32 = ctypes.windll.kernel32
COORD_RVA = 0x32EBDC0


def read_coords(pid, base):
    h = kernel32.OpenProcess(0x0010, False, pid)
    if not h:
        return None
    try:
        buf = ctypes.create_string_buffer(8)
        br = ctypes.c_size_t(0)
        if not kernel32.ReadProcessMemory(h, ctypes.c_void_p(base + COORD_RVA), buf, 8, ctypes.byref(br)):
            return None
        obj = int.from_bytes(buf.raw[:8], "little")
        if not (0x10000 < obj < 0x7FFFFFFFFFFFFFFF):
            return None
        c = {}
        for n, o in [("x", 0x320), ("y", 0x324), ("z", 0x328)]:
            if not kernel32.ReadProcessMemory(h, ctypes.c_void_p(obj + o), buf, 4, ctypes.byref(br)):
                return None
            c[n] = ctypes.c_float.from_buffer(buf).value
        return c
    finally:
        kernel32.CloseHandle(h)


def find_base(pid):
    h = kernel32.OpenProcess(0x0010, False, pid)
    if not h:
        return None
    try:
        for b in [0x7FF728B80000, 0x7FF700000000, 0x7FF600000000]:
            buf = ctypes.create_string_buffer(8)
            br = ctypes.c_size_t(0)
            if kernel32.ReadProcessMemory(h, ctypes.c_void_p(b + COORD_RVA), buf, 8, ctypes.byref(br)):
                v = int.from_bytes(buf.raw[:8], "little")
                if 0x10000 < v < 0x7FFFFFFFFFFFFFFF:
                    return b
        return None
    finally:
        kernel32.CloseHandle(h)


def pos_key(pos, grid_size):
    gx = round(pos["x"] / grid_size) * grid_size
    gz = round(pos["z"] / grid_size) * grid_size
    return (round(gx, 1), round(gz, 1))


def build_navmesh(positions, grid_size=2.0):
    """Build navmesh from recorded positions. Connect nearby positions."""
    grid = {}

    for p in positions:
        key = pos_key(p, grid_size)
        if key not in grid:
            grid[key] = {"x": p["x"], "z": p["z"], "y": p.get("y", 0), "neighbors": []}

    # Connect positions that are within 3 grid cells of each other
    keys = list(grid.keys())
    for i, k1 in enumerate(keys):
        for k2 in keys[i+1:]:
            dx = k1[0] - k2[0]
            dz = k1[1] - k2[1]
            dist = math.sqrt(dx*dx + dz*dz)
            if dist <= grid_size * 3:  # within 3 cells
                if k2 not in grid[k1]["neighbors"]:
                    grid[k1]["neighbors"].append(k2)
                if k1 not in grid[k2]["neighbors"]:
                    grid[k2]["neighbors"].append(k1)

    return grid


def find_path(grid, start_key, end_key):
    """BFS shortest path."""
    from collections import deque
    if start_key not in grid or end_key not in grid:
        return None
    queue = deque([(start_key, [start_key])])
    visited = {start_key}
    while queue:
        current, path = queue.popleft()
        if current == end_key:
            return path
        for neighbor in grid.get(current, {}).get("neighbors", []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--interval", type=float, default=0.5, help="Seconds between samples")
    p.add_argument("--duration", type=float, default=60, help="Total seconds to record")
    p.add_argument("--grid-size", type=float, default=2.0)
    p.add_argument("--output", type=str, default="scripts/captures/recorded-navmesh.json")
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--target-x", type=float)
    p.add_argument("--target-z", type=float)
    args = p.parse_args()

    base = find_base(args.pid)
    if not base:
        print("ERROR: cannot find base"); sys.exit(1)

    positions = []
    start_time = datetime.now(UTC)
    sample_count = 0

    print(f"Recording for {args.duration}s (every {args.interval}s)... Walk around!")
    print(f"Output: {args.output}")
    print("Press Ctrl+C to stop early.\n")

    try:
        while True:
            elapsed = (datetime.now(UTC) - start_time).total_seconds()
            if elapsed >= args.duration:
                break

            pos = read_coords(args.pid, base)
            if pos:
                sample_count += 1
                key = pos_key(pos, args.grid_size)
                positions.append({
                    "x": pos["x"], "z": pos["z"], "y": pos.get("y", 0),
                    "t": round(elapsed, 2), "key": f"{key[0]},{key[1]}",
                })
                if args.verbose:
                    print(f"  [{elapsed:5.1f}s] ({pos['x']:.1f}, {pos['z']:.1f}) -> {key}")

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nStopped early.")

    # Build navmesh
    grid = build_navmesh(positions, args.grid_size)

    # Find path if target specified
    path = None
    if args.target_x is not None and args.target_z is not None and positions:
        start_key = pos_key(positions[-1], args.grid_size)  # end of recording
        end_key = (round(args.target_x / args.grid_size) * args.grid_size,
                   round(args.target_z / args.grid_size) * args.grid_size)
        if end_key not in grid:
            grid[end_key] = {"x": args.target_x, "z": args.target_z, "y": 0, "neighbors": []}
        path = find_path(grid, start_key, end_key)

    out = {
        "grid_size": args.grid_size,
        "samples": sample_count,
        "unique_positions": len(grid),
        "duration_seconds": round((datetime.now(UTC) - start_time).total_seconds(), 1),
        "positions": positions,
        "nodes": {f"{k[0]},{k[1]}": v for k, v in grid.items()},
    }
    if path:
        out["path"] = [{"x": grid[n]["x"], "z": grid[n]["z"]} for n in path]

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"\nRecorded {sample_count} samples, {len(grid)} unique positions")
    if path:
        print(f"Path to target: {len(path)} steps")

    print(json.dumps({
        "ok": True, "samples": sample_count, "positions": len(grid),
        "path_steps": len(path) if path else 0, "output": args.output,
    }, indent=2))


if __name__ == "__main__":
    main()
