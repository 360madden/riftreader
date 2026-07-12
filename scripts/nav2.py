#!/usr/bin/env python3
"""Minimal RIFT navigation: turn, move, check. Repeat."""

import argparse
import ctypes
import json
import math
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

kernel32 = ctypes.windll.kernel32
COORD_RVA = 0x32EBDC0


def read_coords(pid: int, base: int) -> dict[str, float] | None:
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
        coords = {}
        for name, off in [("x", 0x320), ("y", 0x324), ("z", 0x328)]:
            if not kernel32.ReadProcessMemory(h, ctypes.c_void_p(obj + off), buf, 4, ctypes.byref(br)):
                return None
            coords[name] = ctypes.c_float.from_buffer(buf).value
        return coords
    finally:
        kernel32.CloseHandle(h)


def find_base(pid: int) -> int | None:
    h = kernel32.OpenProcess(0x0010, False, pid)
    if not h:
        return None
    try:
        for b in [0x7FF728B80000, 0x7FF700000000, 0x7FF600000000]:
            buf = ctypes.create_string_buffer(8)
            br = ctypes.c_size_t(0)
            if kernel32.ReadProcessMemory(h, ctypes.c_void_p(b + COORD_RVA), buf, 8, ctypes.byref(br)):
                val = int.from_bytes(buf.raw[:8], "little")
                if 0x10000 < val < 0x7FFFFFFFFFFFFFFF:
                    return b
        return None
    finally:
        kernel32.CloseHandle(h)


def dist(a: dict, b: dict) -> float:
    return math.sqrt((b["x"] - a["x"]) ** 2 + (b["z"] - a["z"]) ** 2)


def turn_left():
    subprocess.run(
        ["pwsh", "-File", str(Path(__file__).parent / "post-rift-key.ps1"),
         "-Key", "A", "-HoldMilliseconds", "400", "-SkipBackgroundFocus"],
        capture_output=True, timeout=10,
    )


def turn_right():
    exe = Path(__file__).parent.parent / "tools" / "RiftReader.SendInput" / "bin" / "Release" / "net10.0-windows" / "RiftReader.SendInput.dll"
    subprocess.run(
        ["dotnet", str(exe), "--key", "D", "--hold-ms", "500", "--mode", "ScanCode"],
        capture_output=True, timeout=10,
    )


def move_forward():
    subprocess.run(
        ["pwsh", "-File", str(Path(__file__).parent / "post-rift-key.ps1"),
         "-Key", "W", "-HoldMilliseconds", "400", "-SkipBackgroundFocus"],
        capture_output=True, timeout=10,
    )


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
    steps = []

    for i in range(args.max_steps):
        pos = read_coords(args.pid, base)
        if not pos:
            print(f"step {i}: cannot read coords"); break

        d = dist(pos, target)
        rec = {"step": i, "x": round(pos["x"], 1), "z": round(pos["z"], 1), "dist": round(d, 1)}

        if d <= args.radius:
            rec["action"] = "arrived"
            steps.append(rec)
            if args.verbose: print(f"  step {i}: ARRIVED dist={d:.1f}")
            print(json.dumps({"ok": True, "steps": steps}, indent=2))
            return

        # Move forward, then check
        move_forward()
        time.sleep(0.5)

        new_pos = read_coords(args.pid, base)
        if not new_pos:
            print(f"step {i}: cannot read after move"); break

        new_d = dist(new_pos, target)
        improved = d - new_d  # positive = closer

        rec["new_x"] = round(new_pos["x"], 1)
        rec["new_z"] = round(new_pos["z"], 1)
        rec["new_dist"] = round(new_d, 1)
        rec["improved"] = round(improved, 1)

        if improved > 0.3:
            # Got closer - keep going same direction
            rec["action"] = "forward"
            if args.verbose: print(f"  step {i}: forward dist {d:.1f} -> {new_d:.1f} (closer {improved:.1f})")
        elif improved < -0.3:
            # Got further - turn and try again
            rec["action"] = "turn"
            if args.verbose: print(f"  step {i}: WRONG dist {d:.1f} -> {new_d:.1f} (further {improved:.1f})")
            # Alternate turn direction
            if i % 2 == 0:
                turn_left()
            else:
                turn_right()
            time.sleep(0.5)
        else:
            # Same spot - try turning
            rec["action"] = "stuck-turn"
            if args.verbose: print(f"  step {i}: stuck at dist {d:.1f}, turning")
            if i % 2 == 0:
                turn_left()
            else:
                turn_right()
            time.sleep(0.5)

        steps.append(rec)

    print(json.dumps({"ok": False, "steps": steps}, indent=2))
    sys.exit(1)


if __name__ == "__main__":
    main()
