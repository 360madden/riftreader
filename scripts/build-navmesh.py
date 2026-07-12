#!/usr/bin/env python3
"""Build a navmesh by exploring the terrain. Walk in directions, record walkable positions."""

import argparse
import ctypes
import json
import math
import subprocess
import sys
import time
from pathlib import Path

kernel32 = ctypes.windll.kernel32
COORD_RVA = 0x32EBDC0
SENDINPUT_DLL = str(Path(__file__).parent.parent / "tools" / "RiftReader.SendInput" / "bin" / "Release" / "net10.0-windows" / "RiftReader.SendInput.dll")
POST_KEY = str(Path(__file__).parent / "post-rift-key.ps1")


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


def walk():
    subprocess.run(["pwsh", "-File", POST_KEY, "-Key", "W", "-HoldMilliseconds", "400", "-SkipBackgroundFocus"],
                    capture_output=True, timeout=10)
    time.sleep(0.5)


def turn_right():
    subprocess.run(["dotnet", SENDINPUT_DLL, "--key", "D", "--hold-ms", "500", "--mode", "ScanCode"],
                    capture_output=True, timeout=10)
    time.sleep(0.5)


def turn_left():
    subprocess.run(["pwsh", "-File", POST_KEY, "-Key", "A", "-HoldMilliseconds", "400", "-SkipBackgroundFocus"],
                    capture_output=True, timeout=10)
    time.sleep(0.5)


def pos_key(pos, grid_size=2.0):
    """Snap position to grid cell."""
    gx = round(pos["x"] / grid_size) * grid_size
    gz = round(pos["z"] / grid_size) * grid_size
    return (round(gx, 1), round(gz, 1))


def explore_from(pid, base, start, grid, depth=0, max_depth=3, grid_size=2.0):
    """Try walking in 8 directions from start. Record walkable positions."""
    if depth > max_depth:
        return

    key = pos_key(start, grid_size)
    if key in grid and grid[key].get("explored", False):
        return

    grid[key] = {
        "x": start["x"], "z": start["z"],
        "y": start.get("y", 0),
        "explored": True,
        "neighbors": grid[key].get("neighbors", []) if key in grid else [],
    }

    # Try walking in current direction first
    walk()
    new_pos = read_coords(pid, base)
    if new_pos:
        new_key = pos_key(new_pos, grid_size)
        dist = math.sqrt((new_pos["x"] - start["x"])**2 + (new_pos["z"] - start["z"])**2)
        if dist > 0.5:  # actually moved
            if new_key not in grid:
                grid[new_key] = {"x": new_pos["x"], "z": new_pos["z"], "y": new_pos.get("y", 0),
                                 "explored": False, "neighbors": []}
            if new_key not in grid[key]["neighbors"]:
                grid[key]["neighbors"].append(new_key)
            if key not in grid[new_key]["neighbors"]:
                grid[new_key]["neighbors"].append(key)

            # Recurse from new position
            explore_from(pid, base, new_pos, grid, depth + 1, max_depth, grid_size)

            # Walk back
            turn_right()
            turn_right()
            walk()
            turn_right()
            turn_right()

    # Turn right and try next direction
    turn_right()


def find_path(grid, start_key, end_key):
    """BFS shortest path on grid."""
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
    p.add_argument("--explore-steps", type=int, default=20)
    p.add_argument("--grid-size", type=float, default=2.0)
    p.add_argument("--output", type=str, default="scripts/captures/navmesh.json")
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--target-x", type=float)
    p.add_argument("--target-z", type=float)
    args = p.parse_args()

    base = find_base(args.pid)
    if not base:
        print("ERROR: cannot find base"); sys.exit(1)

    pos = read_coords(args.pid, base)
    if not pos:
        print("ERROR: cannot read position"); sys.exit(1)

    grid = {}

    # Phase 1: Explore from current position
    if args.verbose:
        print(f"Exploring from ({pos['x']:.1f}, {pos['z']:.1f})...")
        print(f"  Grid size: {args.grid_size}, Max depth: {args.explore_steps // 5}")

    max_depth = min(args.explore_steps // 5, 4)
    explore_from(pid=args.pid, base=base, start=pos, grid=grid,
                 max_depth=max_depth, grid_size=args.grid_size)

    # Save navmesh
    out = {
        "grid_size": args.grid_size,
        "positions": len(grid),
        "nodes": {f"{k[0]},{k[1]}": v for k, v in grid.items()},
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out, indent=2), encoding="utf-8")

    if args.verbose:
        print(f"\nNavmesh: {len(grid)} walkable positions")
        for k, v in grid.items():
            print(f"  ({k[0]}, {k[1]}) -> {len(v.get('neighbors', []))} neighbors")

    # Phase 2: If target specified, find path
    if args.target_x is not None and args.target_z is not None:
        end_key = (round(args.target_x / args.grid_size) * args.grid_size,
                   round(args.target_z / args.grid_size) * args.grid_size)
        start_key = pos_key(pos, args.grid_size)

        # Add target to grid if not there
        if end_key not in grid:
            grid[end_key] = {"x": args.target_x, "z": args.target_z, "y": 0,
                             "explored": False, "neighbors": []}

        path = find_path(grid, start_key, end_key)
        if path:
            out["path"] = [{"x": grid[n]["x"], "z": grid[n]["z"]} for n in path]
            if args.verbose:
                print(f"\nPath to target ({len(path)} steps):")
                for i, n in enumerate(path):
                    print(f"  {i}: ({grid[n]['x']:.1f}, {grid[n]['z']:.1f})")
        else:
            if args.verbose:
                print(f"\nNo path found from {start_key} to {end_key}")

        Path(args.output).write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(json.dumps({"ok": True, "positions": len(grid), "output": args.output}, indent=2))


if __name__ == "__main__":
    main()
