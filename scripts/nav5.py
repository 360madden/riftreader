#!/usr/bin/env python3
"""RIFT navigation: walk, check progress, turn once if needed. Repeat."""

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
    """One short right turn via C# SendInput (needs foreground)."""
    subprocess.run(["dotnet", SENDINPUT_DLL, "--key", "D", "--hold-ms", "500", "--mode", "ScanCode"],
                    capture_output=True, timeout=10)
    time.sleep(0.5)


def turn_left():
    """One short left turn via WindowMessage."""
    subprocess.run(["pwsh", "-File", POST_KEY, "-Key", "A", "-HoldMilliseconds", "400", "-SkipBackgroundFocus"],
                    capture_output=True, timeout=10)
    time.sleep(0.5)


def dist_to(pos, target):
    return math.sqrt((target["x"] - pos["x"]) ** 2 + (target["z"] - pos["z"]) ** 2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--target-x", type=float, required=True)
    p.add_argument("--target-z", type=float, required=True)
    p.add_argument("--radius", type=float, default=5.0)
    p.add_argument("--max-steps", type=int, default=30)
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    base = find_base(args.pid)
    if not base:
        print("ERROR: cannot find base"); sys.exit(1)

    target = {"x": args.target_x, "z": args.target_z}

    # Read starting position
    pos = read_coords(args.pid, base)
    if not pos:
        print("ERROR: cannot read starting position"); sys.exit(1)

    best_dist = dist_to(pos, target)
    history = [best_dist]  # track distance trend
    consecutive_worse = 0
    turn_dir = "right"  # alternate if one direction doesn't work

    if args.verbose:
        print(f"  start: ({pos['x']:.1f},{pos['z']:.1f}) dist={best_dist:.1f}")

    for i in range(args.max_steps):
        # Walk forward
        walk()

        # Read new position
        new_pos = read_coords(args.pid, base)
        if not new_pos:
            if args.verbose: print(f"  step {i}: cannot read"); break

        new_dist = dist_to(new_pos, target)
        history.append(new_dist)

        if new_dist <= args.radius:
            if args.verbose: print(f"  step {i}: ARRIVED dist={new_dist:.1f}")
            print(json.dumps({
                "ok": True, "steps": i + 1,
                "final": {"x": round(new_pos["x"], 1), "z": round(new_pos["z"], 1)},
                "dist": round(new_dist, 1), "history": [round(d, 1) for d in history],
            }, indent=2))
            return

        improved = best_dist - new_dist

        if improved > 0.1:
            # Got closer — keep walking, don't turn
            best_dist = new_dist
            consecutive_worse = 0
            if args.verbose:
                print(f"  step {i}: fwd dist {best_dist + improved:.1f} -> {new_dist:.1f} (closer {improved:.1f})")
        else:
            # Got worse or same — turn once, then walk again
            consecutive_worse += 1
            if args.verbose:
                print(f"  step {i}: worse dist {best_dist:.1f} -> {new_dist:.1f}, turn {turn_dir}")

            if turn_dir == "right":
                turn_right()
            else:
                turn_left()

            # Alternate turn direction after3 consecutive worse steps
            if consecutive_worse >= 3:
                turn_dir = "left" if turn_dir == "right" else "right"
                consecutive_worse = 0

            best_dist = new_dist

    # Didn't arrive but got close
    pos = read_coords(args.pid, base)
    final_dist = dist_to(pos, target) if pos else -1
    print(json.dumps({
        "ok": False, "steps": args.max_steps,
        "final": {"x": round(pos["x"], 1), "z": round(pos["z"], 1)} if pos else None,
        "dist": round(final_dist, 1), "history": [round(d, 1) for d in history],
    }, indent=2))
    sys.exit(1)


if __name__ == "__main__":
    main()
