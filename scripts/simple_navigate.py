#!/usr/bin/env python3
"""Autonomous navigation using the promoted coordinate chain.

Provides single-target and multi-waypoint navigation with stuck detection,
recovery, and detailed JSON summary output.

Usage:
    # Single target
    python simple_navigate.py --pid <pid> --target-x <x> --target-y <y> --target-z <z>

    # Multi-waypoint route from JSON file
    python simple_navigate.py --pid <pid> --route route.json

    # Dry run
    python simple_navigate.py --pid <pid> --route route.json --dry-run

Route JSON format:
    {
        "name": "Silverwood Run",
        "waypoints": [
            {"x": 7000.0, "y": 842.0, "z": 3300.0, "label": "Start"},
            {"x": 7050.0, "y": 850.0, "z": 3350.0, "label": "Midpoint"},
            {"x": 7100.0, "y": 860.0, "z": 3400.0, "label": "End"}
        ]
    }
"""

from __future__ import annotations

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

# ---------------------------------------------------------------------------
# Direct memory reading (fast, no subprocess overhead)
# ---------------------------------------------------------------------------
kernel32 = ctypes.windll.kernel32
PROCESS_VM_READ = 0x0010
COORD_GLOBAL_RVA = 0x32EBDC0
OFFSET_X = 0x320
OFFSET_Y = 0x324
OFFSET_Z = 0x328
OFFSET_HEADING_RAW = 0x300


def find_module_base(pid: int) -> int | None:
    """Find rift_x64.exe base address in target process."""
    handle = kernel32.OpenProcess(PROCESS_VM_READ, False, pid)
    if not handle:
        return None
    try:
        for base in [0x7FF728B80000, 0x7FF700000000, 0x7FF600000000]:
            buf = ctypes.create_string_buffer(8)
            br = ctypes.c_size_t(0)
            if kernel32.ReadProcessMemory(
                handle, ctypes.c_void_p(base + COORD_GLOBAL_RVA), buf, 8, ctypes.byref(br)
            ):
                val = int.from_bytes(buf.raw[:8], "little")
                if 0x10000 < val < 0x7FFFFFFFFFFFFFFF:
                    return base
        return None
    finally:
        kernel32.CloseHandle(handle)


def read_chain_coords(pid: int, base: int) -> dict[str, float] | None:
    """Read X/Y/Z/heading directly from the promoted memory chain."""
    handle = kernel32.OpenProcess(PROCESS_VM_READ, False, pid)
    if not handle:
        return None
    try:
        buf = ctypes.create_string_buffer(8)
        br = ctypes.c_size_t(0)
        if not kernel32.ReadProcessMemory(
            handle, ctypes.c_void_p(base + COORD_GLOBAL_RVA), buf, 8, ctypes.byref(br)
        ):
            return None
        obj = int.from_bytes(buf.raw[:8], "little")
        if not (0x10000 < obj < 0x7FFFFFFFFFFFFFFF):
            return None
        coords: dict[str, float] = {}
        for name, off in [("x", OFFSET_X), ("y", OFFSET_Y), ("z", OFFSET_Z)]:
            if not kernel32.ReadProcessMemory(
                handle, ctypes.c_void_p(obj + off), buf, 4, ctypes.byref(br)
            ):
                return None
            coords[name] = ctypes.c_float.from_buffer(buf).value
        if kernel32.ReadProcessMemory(
            handle, ctypes.c_void_p(obj + OFFSET_HEADING_RAW), buf, 4, ctypes.byref(br)
        ):
            raw = ctypes.c_float.from_buffer(buf).value
            coords["heading"] = raw % 360.0 if raw % 360.0 >= 0 else raw % 360.0 + 360.0
        else:
            coords["heading"] = 0.0
        return coords
    finally:
        kernel32.CloseHandle(handle)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def bearing_deg(from_pos: dict, to_pos: dict) -> float:
    dx = to_pos["x"] - from_pos["x"]
    dz = to_pos["z"] - from_pos["z"]
    return (math.degrees(math.atan2(dx, dz)) + 360) % 360


def distance_3d(a: dict, b: dict) -> float:
    return math.sqrt((b["x"] - a["x"]) ** 2 + (b["y"] - a["y"]) ** 2 + (b["z"] - a["z"]) ** 2)


def distance_planar(a: dict, b: dict) -> float:
    return math.sqrt((b["x"] - a["x"]) ** 2 + (b["z"] - a["z"]) ** 2)


# ---------------------------------------------------------------------------
# Input backend
# ---------------------------------------------------------------------------
CSharp_SENDINPUT = str(Path(__file__).parent.parent / "tools" / "RiftReader.SendInput" / "bin" / "Release" / "net10.0-windows" / "RiftReader.SendInput.dll")


def send_key(key: str, hold_ms: int = 500) -> bool:
    """Send a key to RIFT.

    Uses C# SendInput ScanCode for A/D (turning) since WindowMessage doesn't
    process turn keys. Uses WindowMessage for W/S (movement) since it works
    without requiring foreground focus.
    """
    if key in ("A", "D", "a", "d"):
        return _send_scan(key, hold_ms)
    else:
        return _send_wm(key, hold_ms)


def _send_wm(key: str, hold_ms: int) -> bool:
    """WindowMessage backend — works for W/S movement."""
    try:
        r = subprocess.run(
            ["pwsh", "-File", str(Path(__file__).parent / "post-rift-key.ps1"),
             "-Key", key, "-HoldMilliseconds", str(hold_ms), "-SkipBackgroundFocus"],
            capture_output=True, text=True, timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


def _send_scan(key: str, hold_ms: int) -> bool:
    """C# SendInput ScanCode backend — works for A/D turning."""
    try:
        r = subprocess.run(
            ["dotnet", CSharp_SENDINPUT,
             "--key", key, "--hold-ms", str(hold_ms), "--mode", "ScanCode"],
            capture_output=True, text=True, timeout=10,
        )
        return r.returncode == 0 and "SUCCESS" in r.stdout
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Navigation primitives
# ---------------------------------------------------------------------------
def turn_to_bearing(current_hdg: float, target_brg: float, threshold: float = 10.0) -> str | None:
    """Return 'A' (turn left via ScanCode) or 'D' (turn right via ScanCode) to face target bearing.

    Uses shortest-path rotation. ScanCode: A = turn left (counterclockwise),
    D = turn right (clockwise).
    """
    # Signed shortest delta: positive means target is clockwise (right) from current
    delta = (target_brg - current_hdg) % 360
    if delta > 180:
        delta -= 360  # now negative = counterclockwise (left)

    if abs(delta) < threshold:
        return None
    # ScanCode: A = turn left, D = turn right
    return "D" if delta > 0 else "A"


def navigate_single_target(
    pid: int,
    base: int,
    target: dict[str, float],
    *,
    arrival_radius: float = 5.0,
    max_steps: int = 50,
    step_delay: float = 0.3,
    stuck_threshold: int = 5,
    stuck_recovery_delay: float = 1.0,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """Navigate to a single target, returning step history and outcome."""
    steps: list[dict[str, Any]] = []
    stuck_count = 0
    last_pos: dict[str, float] | None = None

    for step in range(max_steps):
        coords = read_chain_coords(pid, base)
        if not coords:
            steps.append({"step": step, "error": "cannot-read-coords"})
            break

        pos = {"x": coords["x"], "y": coords["y"], "z": coords["z"]}
        hdg = coords["heading"]
        dist = distance_planar(pos, target)
        dist3 = distance_3d(pos, target)
        brg = bearing_deg(pos, target)

        rec: dict[str, Any] = {
            "step": step,
            "pos": {k: round(v, 2) for k, v in pos.items()},
            "heading": round(hdg, 1),
            "bearing": round(brg, 1),
            "dist_planar": round(dist, 2),
            "dist_3d": round(dist3, 2),
        }

        if verbose:
            print(
                f"  step={step:2d}  pos=({pos['x']:.1f},{pos['y']:.1f},{pos['z']:.1f})  "
                f"hdg={hdg:.0f}  brg={brg:.0f}  dist={dist:.1f}"
            )

        # --- Arrival check ---
        if dist <= arrival_radius:
            rec["action"] = "arrived"
            steps.append(rec)
            return {"ok": True, "steps": steps, "final_pos": pos, "total_steps": step + 1}

        # --- Stuck detection ---
        if last_pos is not None:
            movement = distance_planar(last_pos, pos)
            if movement < 0.3:
                stuck_count += 1
            else:
                stuck_count = 0
        last_pos = pos.copy()

        if stuck_count >= stuck_threshold:
            if verbose:
                print(f"  STUCK at step {step} (no movement for {stuck_threshold} reads)")
            rec["action"] = "stuck"
            steps.append(rec)
            # Recovery: back up, turn right, then try again
            if not dry_run:
                send_key("S", hold_ms=500)
                time.sleep(0.3)
                send_key("D", hold_ms=500)
                time.sleep(0.3)
            stuck_count = 0
            continue

        # --- Turn or move ---
        turn = turn_to_bearing(hdg, brg)
        if turn:
            rec["action"] = f"turn_{turn}"
            steps.append(rec)
            if not dry_run:
                # Calculate how many pulses needed
                delta_to_target = (brg - hdg) % 360
                if delta_to_target > 180:
                    delta_to_target -= 360
                pulses = max(2, min(6, int(abs(delta_to_target) / 15)))
                for _ in range(pulses):
                    send_key(turn, hold_ms=300)
                    time.sleep(0.05)
                time.sleep(step_delay)
        else:
            rec["action"] = "move_forward"
            steps.append(rec)
            if not dry_run:
                # Adaptive hold: shorter when close, longer when far
                hold = max(300, min(600, int(dist * 30)))
                send_key("W", hold_ms=hold)
                time.sleep(step_delay)

    return {"ok": False, "steps": steps, "final_pos": pos if coords else None, "total_steps": max_steps}


# ---------------------------------------------------------------------------
# Multi-waypoint route
# ---------------------------------------------------------------------------
def navigate_route(
    pid: int,
    base: int,
    waypoints: list[dict[str, Any]],
    *,
    arrival_radius: float = 5.0,
    max_steps_per_waypoint: int = 40,
    step_delay: float = 0.3,
    stuck_threshold: int = 5,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """Navigate through a list of waypoints in order."""
    results: list[dict[str, Any]] = []
    total_steps = 0
    start_time = datetime.now(UTC)

    for i, wp in enumerate(waypoints):
        label = wp.get("label", f"waypoint-{i}")
        target = {"x": wp["x"], "y": wp["y"], "z": wp["z"]}
        if verbose:
            print(f"\n--- Waypoint {i}: {label} ({target['x']:.1f}, {target['y']:.1f}, {target['z']:.1f}) ---")

        res = navigate_single_target(
            pid, base, target,
            arrival_radius=arrival_radius,
            max_steps=max_steps_per_waypoint,
            step_delay=step_delay,
            stuck_threshold=stuck_threshold,
            dry_run=dry_run,
            verbose=verbose,
        )
        res["waypoint_index"] = i
        res["waypoint_label"] = label
        res["waypoint_target"] = target
        results.append(res)
        total_steps += res["total_steps"]

        if not res["ok"]:
            if verbose:
                print(f"  BLOCKED at waypoint {i}: {label}")
            break
        if verbose:
            print(f"  ARRIVED at waypoint {i}: {label}")

    elapsed = (datetime.now(UTC) - start_time).total_seconds()
    all_ok = all(r["ok"] for r in results)
    return {
        "ok": all_ok,
        "waypoints_total": len(waypoints),
        "waypoints_completed": sum(1 for r in results if r["ok"]),
        "total_steps": total_steps,
        "elapsed_seconds": round(elapsed, 2),
        "results": results,
    }


# ---------------------------------------------------------------------------
# Route file I/O
# ---------------------------------------------------------------------------
def load_route(path: str | Path) -> list[dict[str, Any]]:
    """Load waypoints from a JSON route file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("waypoints", [])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser(description="Autonomous RIFT navigation via coordinate chain")
    p.add_argument("--pid", type=int, required=True, help="RIFT process ID")
    p.add_argument("--target-x", type=float, help="Single target X")
    p.add_argument("--target-y", type=float, help="Single target Y")
    p.add_argument("--target-z", type=float, help="Single target Z")
    p.add_argument("--route", type=str, help="JSON route file with waypoints")
    p.add_argument("--arrival-radius", type=float, default=5.0)
    p.add_argument("--max-steps", type=int, default=50, help="Max steps per waypoint")
    p.add_argument("--step-delay", type=float, default=0.3)
    p.add_argument("--stuck-threshold", type=int, default=5)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--output", type=str, help="Write summary JSON to this path")
    args = p.parse_args()

    base = find_module_base(args.pid)
    if not base:
        print("ERROR: Cannot find rift_x64.exe base address", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"Module base: 0x{base:X}")

    # Build waypoints
    if args.route:
        waypoints = load_route(args.route)
        if not waypoints:
            print("ERROR: Route file has no waypoints", file=sys.stderr)
            sys.exit(1)
    elif args.target_x is not None and args.target_y is not None and args.target_z is not None:
        waypoints = [{"x": args.target_x, "y": args.target_y, "z": args.target_z, "label": "target"}]
    else:
        print("ERROR: Provide --target-x/y/z or --route", file=sys.stderr)
        sys.exit(1)

    # Navigate
    if len(waypoints) == 1:
        target = waypoints[0]
        res = navigate_single_target(
            args.pid, base,
            {"x": target["x"], "y": target["y"], "z": target["z"]},
            arrival_radius=args.arrival_radius,
            max_steps=args.max_steps,
            step_delay=args.step_delay,
            stuck_threshold=args.stuck_threshold,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
    else:
        res = navigate_route(
            args.pid, base, waypoints,
            arrival_radius=args.arrival_radius,
            max_steps_per_waypoint=args.max_steps,
            step_delay=args.step_delay,
            stuck_threshold=args.stuck_threshold,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

    # Output
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        status = "ARRIVED" if res["ok"] else "BLOCKED"
        if "waypoints_completed" in res:
            print(f"{status}: {res['waypoints_completed']}/{res['waypoints_total']} waypoints "
                  f"in {res['total_steps']} steps ({res['elapsed_seconds']}s)")
        else:
            print(f"{status}: {res['total_steps']} steps")
        if res.get("final_pos"):
            fp = res["final_pos"]
            print(f"  Final: ({fp['x']:.1f}, {fp['y']:.1f}, {fp['z']:.1f})")

    # Write summary
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(res, indent=2), encoding="utf-8")
        if args.verbose:
            print(f"Summary written to {args.output}")

    sys.exit(0 if res["ok"] else 1)


if __name__ == "__main__":
    main()
