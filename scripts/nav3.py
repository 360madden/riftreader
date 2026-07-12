#!/usr/bin/env python3
"""RIFT navigation: measure facing, turn to target, walk forward."""

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


def walk_forward():
    """Walk forward using W key via WindowMessage (works without foreground)."""
    subprocess.run(
        ["pwsh", "-File", str(Path(__file__).parent / "post-rift-key.ps1"),
         "-Key", "W", "-HoldMilliseconds", "300", "-SkipBackgroundFocus"],
        capture_output=True, timeout=10,
    )
    time.sleep(0.45)


def measure_facing(pid, base):
    """Walk forward briefly and measure displacement direction.

    Returns bearing in degrees where:
      0=South(Z+), 90=East(X+), 180=North(Z-), 270=West(X-)
    """
    before = read_coords(pid, base)
    if not before:
        return None
    walk_forward()
    after = read_coords(pid, base)
    if not after:
        return None
    dx = after["x"] - before["x"]
    dz = after["z"] - before["z"]
    dist = math.sqrt(dx * dx + dz * dz)
    if dist < 0.3:
        return None  # didn't move
    # bearing: 0=South, 90=East, 180=North, 270=West
    bearing = (math.degrees(math.atan2(dx, dz)) + 360) % 360
    return bearing


def bearing_to_target(pos, target):
    """Calculate bearing from pos to target."""
    dx = target["x"] - pos["x"]
    dz = target["z"] - pos["z"]
    return (math.degrees(math.atan2(dx, dz)) + 360) % 360


def turn_right():
    """Turn right using C# SendInput D key (requires foreground)."""
    exe = Path(__file__).parent.parent / "tools" / "RiftReader.SendInput" / "bin" / "Release" / "net10.0-windows" / "RiftReader.SendInput.dll"
    subprocess.run(
        ["dotnet", str(exe), "--key", "D", "--hold-ms", "500", "--mode", "ScanCode"],
        capture_output=True, timeout=10,
    )
    time.sleep(0.5)


def turn_left():
    """Turn left using WindowMessage A key."""
    subprocess.run(
        ["pwsh", "-File", str(Path(__file__).parent / "post-rift-key.ps1"),
         "-Key", "A", "-HoldMilliseconds", "400", "-SkipBackgroundFocus"],
        capture_output=True, timeout=10,
    )
    time.sleep(0.5)


def navigate(pid, base, target, radius=3.0, max_steps=20, verbose=False):
    steps = []

    for i in range(max_steps):
        pos = read_coords(pid, base)
        if not pos:
            print(f"step {i}: cannot read"); break

        d = math.sqrt((target["x"] - pos["x"]) ** 2 + (target["z"] - pos["z"]) ** 2)
        if d <= radius:
            steps.append({"step": i, "action": "arrived", "dist": round(d, 1)})
            if verbose: print(f"  step {i}: ARRIVED dist={d:.1f}")
            return True, steps

        # Measure current facing
        facing = measure_facing(pid, base)
        if facing is None:
            # Can't measure facing - just walk and hope
            steps.append({"step": i, "action": "walk-blind", "dist": round(d, 1)})
            if verbose: print(f"  step {i}: can't measure facing, walking blind")
            walk_forward()
            continue

        # Calculate needed bearing
        needed = bearing_to_target(pos, target)

        # Calculate turn delta
        delta = (needed - facing + 360) % 360
        if delta > 180:
            delta -= 360  # now in range -180..180

        rec = {
            "step": i,
            "dist": round(d, 1),
            "facing": round(facing, 0),
            "needed": round(needed, 0),
            "delta": round(delta, 0),
        }

        if abs(delta) < 20:
            # Close enough - walk forward
            rec["action"] = "forward"
            steps.append(rec)
            if verbose: print(f"  step {i}: fwd dist={d:.1f} facing={facing:.0f} need={needed:.0f} delta={delta:.0f}")
            walk_forward()
        elif delta > 0:
            # Need to turn right (clockwise)
            turns = max(1, round(abs(delta) / 80))
            rec["action"] = f"right x{turns}"
            steps.append(rec)
            if verbose: print(f"  step {i}: RIGHT x{turns} dist={d:.1f} delta={delta:.0f}")
            for _ in range(turns):
                turn_right()
        else:
            # Need to turn left (counter-clockwise)
            turns = max(1, round(abs(delta) / 70))
            rec["action"] = f"left x{turns}"
            steps.append(rec)
            if verbose: print(f"  step {i}: LEFT x{turns} dist={d:.1f} delta={delta:.0f}")
            for _ in range(turns):
                turn_left()

    return False, steps


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--target-x", type=float, required=True)
    p.add_argument("--target-z", type=float, required=True)
    p.add_argument("--radius", type=float, default=3.0)
    p.add_argument("--max-steps", type=int, default=20)
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    base = find_base(args.pid)
    if not base:
        print("ERROR: cannot find base"); sys.exit(1)

    target = {"x": args.target_x, "z": args.target_z}
    ok, steps = navigate(args.pid, base, target, args.radius, args.max_steps, args.verbose)
    print(json.dumps({"ok": ok, "steps": steps}, indent=2))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
