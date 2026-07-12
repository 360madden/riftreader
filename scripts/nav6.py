#!/usr/bin/env python3
"""RIFT nav6: Aim-then-walk navigation using heading angle.

Reads heading from [[0x330]+0x158] (radians, 0° offset).
Turns to face waypoint, then walks forward. Repeat until close.
"""

import argparse
import ctypes
import ctypes.wintypes
import json
import math
import subprocess
import struct
import sys
import time
from pathlib import Path

kernel32 = ctypes.windll.kernel32
COORD_RVA = 0x32EBDC0
SENDINPUT_DLL = str(Path(__file__).parent.parent / "tools" / "RiftReader.SendInput" / "bin" / "Release" / "net10.0-windows" / "RiftReader.SendInput.exe")


def find_base(pid):
    TH32CS_SNAPMODULE = 0x00000010
    TH32CS_SNAPMODULE32 = 0x00000008
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snapshot == ctypes.wintypes.HANDLE(-1).value:
        return None
    class ME(ctypes.Structure):
        _fields_ = [("dwSize", ctypes.wintypes.DWORD), ("th32ModuleID", ctypes.wintypes.DWORD),
                     ("th32ProcessID", ctypes.wintypes.DWORD), ("GlblcntUsage", ctypes.wintypes.DWORD),
                     ("ProccntUsage", ctypes.wintypes.DWORD), ("modBaseAddr", ctypes.c_void_p),
                     ("modBaseSize", ctypes.wintypes.DWORD), ("hModule", ctypes.wintypes.HMODULE),
                     ("szModule", ctypes.c_char * 256), ("szExePath", ctypes.c_char * 260)]
    me = ME()
    me.dwSize = ctypes.sizeof(me)
    base = None
    try:
        if kernel32.Module32First(snapshot, ctypes.byref(me)):
            while True:
                if b"rift_x64" in me.szModule.lower():
                    base = me.modBaseAddr
                    break
                if not kernel32.Module32Next(snapshot, ctypes.byref(me)):
                    break
    finally:
        kernel32.CloseHandle(snapshot)
    return base


def read_bytes(pid, addr, length):
    h = kernel32.OpenProcess(0x0010, False, pid)
    buf = ctypes.create_string_buffer(length)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, length, ctypes.byref(br))
    kernel32.CloseHandle(h)
    return buf.raw[:br.value] if ok else None


def read_ptr(pid, addr):
    d = read_bytes(pid, addr, 8)
    return struct.unpack('<Q', d)[0] if d and len(d) == 8 else None


def read_f32(pid, addr):
    d = read_bytes(pid, addr, 4)
    return struct.unpack('<f', d)[0] if d and len(d) == 4 else None


def read_state(pid, base):
    """Read position and heading in one pass."""
    obj = read_ptr(pid, base + COORD_RVA)
    if not obj or obj < 0x10000:
        return None

    x = read_f32(pid, obj + 0x320)
    y = read_f32(pid, obj + 0x324)
    z = read_f32(pid, obj + 0x328)
    if x is None or y is None or z is None:
        return None

    child330 = read_ptr(pid, obj + 0x330)
    if not child330 or child330 < 0x10000:
        return {"x": x, "y": y, "z": z, "heading": None}

    heading = read_f32(pid, child330 + 0x158)
    return {"x": x, "y": y, "z": z, "heading": heading}


def send_key(key, hold_ms):
    """Send key via C# SendInput (requires RIFT foreground)."""
    subprocess.run([SENDINPUT_DLL, "--key", key, "--hold-ms", str(hold_ms), "--json"],
                   capture_output=True, text=True, timeout=5)


def normalize_angle(a):
    """Normalize angle to [-180, 180)."""
    while a >= 180:
        a -= 360
    while a < -180:
        a += 360
    return a


def distance(a, b):
    return math.sqrt((b["x"] - a["x"]) ** 2 + (b["z"] - a["z"]) ** 2)


def bearing_deg(from_pos, to_pos):
    """Bearing from from_pos to to_pos in degrees (0=north/+Z, 90=east/+X)."""
    dx = to_pos["x"] - from_pos["x"]
    dz = to_pos["z"] - from_pos["z"]
    return math.degrees(math.atan2(dx, dz))


TURN_RATE_DEG_PER_SEC = 172.0  # Calibrated: ~172°/s for both left and right


def turn_to_heading(current_heading, target_heading, verbose=False):
    """Calculate turn needed and execute it. Returns (direction, degrees)."""
    diff = normalize_angle(target_heading - current_heading)

    if abs(diff) < 2.0:
        if verbose:
            print(f"  already aligned (diff={diff:+.1f}°)")
        return "none", 0

    # Calibrated: 172°/s, so hold_ms = abs(diff) / 172 * 1000
    # Cap at 1000ms for safety
    hold_ms = min(1000, max(150, int(abs(diff) / TURN_RATE_DEG_PER_SEC * 1000)))

    # RIFT: D = right turn = heading decreases, A = left turn = heading increases
    # So positive diff means turn left (A), negative means turn right (D)
    if diff > 0:
        if verbose:
            print(f"  turn LEFT {abs(diff):.1f}° (hold {hold_ms}ms)")
        send_key("A", hold_ms)
        return "left", diff
    else:
        if verbose:
            print(f"  turn RIGHT {abs(diff):.1f}° (hold {hold_ms}ms)")
        send_key("D", hold_ms)
        return "right", diff


def main():
    p = argparse.ArgumentParser(description="RIFT nav6: aim-then-walk navigation")
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--target-x", type=float, required=True)
    p.add_argument("--target-z", type=float, required=True)
    p.add_argument("--radius", type=float, default=5.0)
    p.add_argument("--max-steps", type=int, default=40)
    p.add_argument("--walk-ms", type=int, default=400, help="Walk hold duration ms")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    base = find_base(args.pid)
    if not base:
        print("ERROR: cannot find rift_x64.exe base")
        sys.exit(1)

    target = {"x": args.target_x, "z": args.target_z}

    # Read starting state
    state = read_state(args.pid, base)
    if not state or state["heading"] is None:
        print("ERROR: cannot read position/heading")
        sys.exit(1)

    best_dist = distance(state, target)
    history = [{"x": round(state["x"], 1), "z": round(state["z"], 1),
                "heading": round(math.degrees(state["heading"]), 1),
                "dist": round(best_dist, 1)}]

    if args.verbose:
        print(f"start: ({state['x']:.1f}, {state['z']:.1f}) heading={math.degrees(state['heading']):.1f}° dist={best_dist:.1f}")

    for i in range(args.max_steps):
        # Read current state
        state = read_state(args.pid, base)
        if not state:
            if args.verbose:
                print(f"  step {i}: cannot read state")
            break

        cur_dist = distance(state, target)
        heading_deg = math.degrees(state["heading"]) if state["heading"] is not None else 0

        # Check arrival
        if cur_dist <= args.radius:
            result = {
                "ok": True, "steps": i, "method": "aim-then-walk",
                "final": {"x": round(state["x"], 1), "z": round(state["z"], 1)},
                "dist": round(cur_dist, 1), "history": history,
            }
            if args.verbose:
                print(f"  ARRIVED at ({state['x']:.1f}, {state['z']:.1f}) dist={cur_dist:.1f}")
            print(json.dumps(result, indent=2))
            return

        # Calculate bearing to target
        target_bearing = bearing_deg(state, target)
        turn_dir, turn_deg = turn_to_heading(heading_deg, target_bearing, args.verbose)

        # If we just turned, re-read heading to verify
        if turn_dir != "none":
            time.sleep(0.3)
            state2 = read_state(args.pid, base)
            if state2 and state2["heading"] is not None:
                new_heading = math.degrees(state2["heading"])
                if args.verbose:
                    print(f"    heading after turn: {new_heading:.1f}° (target was {target_bearing:.1f}°)")

        # Walk forward
        send_key("W", args.walk_ms)
        time.sleep(0.5)

        # Read new position
        new_state = read_state(args.pid, base)
        if not new_state:
            if args.verbose:
                print(f"  step {i}: cannot read after walk")
            break

        new_dist = distance(new_state, target)
        new_heading = math.degrees(new_state["heading"]) if new_state["heading"] is not None else 0
        history.append({"x": round(new_state["x"], 1), "z": round(new_state["z"], 1),
                        "heading": round(new_heading, 1), "dist": round(new_dist, 1)})

        if args.verbose:
            delta = best_dist - new_dist
            print(f"  step {i}: ({new_state['x']:.1f}, {new_state['z']:.1f}) heading={new_heading:.1f}° "
                  f"dist={new_dist:.1f} ({'closer' if delta > 0 else 'worse'} {abs(delta):.1f})")

        best_dist = new_dist

    # Did not arrive
    state = read_state(args.pid, base)
    final_dist = distance(state, target) if state else -1
    result = {
        "ok": False, "steps": args.max_steps, "method": "aim-then-walk",
        "final": {"x": round(state["x"], 1), "z": round(state["z"], 1)} if state else None,
        "dist": round(final_dist, 1), "history": history,
    }
    print(json.dumps(result, indent=2))
    sys.exit(1)


if __name__ == "__main__":
    main()
