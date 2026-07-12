#!/usr/bin/env python3
"""RIFT navigation: walk, check distance, turn if wrong direction. No facing measurement."""

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


def dist_to(pos, target):
    return math.sqrt((target["x"] - pos["x"]) ** 2 + (target["z"] - pos["z"]) ** 2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--target-x", type=float, required=True)
    p.add_argument("--target-z", type=float, required=True)
    p.add_argument("--radius", type=float, default=3.0)
    p.add_argument("--max-steps", type=int, default=30)
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    base = find_base(args.pid)
    if not base:
        print("ERROR: cannot find base"); sys.exit(1)

    target = {"x": args.target_x, "z": args.target_z}
    steps = []

    # Strategy: walk forward repeatedly.
    # If we get closer, keep walking.
    # If we get further, we were facing wrong. Turn right and try again.
    # If we try the same direction twice without improvement, turn left instead.
    last_action = None
    wrong_count = 0

    for i in range(args.max_steps):
        pos = read_coords(args.pid, base)
        if not pos:
            print(f"step {i}: cannot read"); break

        d = dist_to(pos, target)
        if d <= args.radius:
            steps.append({"step": i, "action": "arrived", "dist": round(d, 1)})
            if args.verbose: print(f"  step {i}: ARRIVED dist={d:.1f}")
            print(json.dumps({"ok": True, "steps": steps}, indent=2))
            return

        # Walk forward
        walk()
        new_pos = read_coords(args.pid, base)
        if not new_pos:
            print(f"step {i}: cannot read after walk"); break

        new_d = dist_to(new_pos, target)
        improved = d - new_d

        rec = {"step": i, "dist": round(d, 1), "new_dist": round(new_d, 1), "improved": round(improved, 1)}

        if improved > 0.2:
            # Got closer! Keep walking same direction.
            rec["action"] = "forward"
            wrong_count = 0
            steps.append(rec)
            if args.verbose: print(f"  step {i}: fwd dist {d:.1f} -> {new_d:.1f}")
        else:
            # Got further or stuck. We were facing wrong.
            wrong_count += 1
            if wrong_count <= 3:
                # Try turning right
                rec["action"] = "turn-right"
                steps.append(rec)
                if args.verbose: print(f"  step {i}: WRONG dist {d:.1f} -> {new_d:.1f}, turning RIGHT")
                turn_right()
            elif wrong_count <= 6:
                # Right isn't working, try left
                rec["action"] = "turn-left"
                steps.append(rec)
                if args.verbose: print(f"  step {i}: WRONG dist {d:.1f} -> {new_d:.1f}, turning LEFT")
                turn_left()
            else:
                # Neither direction works, try right again with bigger turn
                rec["action"] = "turn-right-2x"
                steps.append(rec)
                if args.verbose: print(f"  step {i}: stuck, turning RIGHT 2x")
                turn_right()
                turn_right()
                wrong_count = 0

    print(json.dumps({"ok": False, "steps": steps}, indent=2))
    sys.exit(1)


if __name__ == "__main__":
    main()
