#!/usr/bin/env python3
"""Autonomous navigation using the promoted coordinate chain.

Uses a hill-climbing approach: move forward, check if distance decreased.
If not, try turning the other way. No heading counter or facing measurement needed.

Usage:
    python simple_navigate.py --pid <pid> --target-x <x> --target-y <y> --target-z <z>
    python simple_navigate.py --pid <pid> --route route.json
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
# Direct memory reading
# ---------------------------------------------------------------------------
kernel32 = ctypes.windll.kernel32
COORD_GLOBAL_RVA = 0x32EBDC0
OFFSET_X = 0x320
OFFSET_Y = 0x324
OFFSET_Z = 0x328


def find_module_base(pid: int) -> int | None:
    handle = kernel32.OpenProcess(0x0010, False, pid)
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


def read_coords(pid: int, base: int) -> dict[str, float] | None:
    handle = kernel32.OpenProcess(0x0010, False, pid)
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
        return coords
    finally:
        kernel32.CloseHandle(handle)


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def distance_planar(a: dict, b: dict) -> float:
    return math.sqrt((b["x"] - a["x"]) ** 2 + (b["z"] - a["z"]) ** 2)


def bearing_deg(from_pos: dict, to_pos: dict) -> float:
    dx = to_pos["x"] - from_pos["x"]
    dz = to_pos["z"] - from_pos["z"]
    return (math.degrees(math.atan2(dx, dz)) + 360) % 360


# ---------------------------------------------------------------------------
# Input backend
# ---------------------------------------------------------------------------
CSharp_SENDINPUT = str(
    Path(__file__).parent.parent / "tools" / "RiftReader.SendInput"
    / "bin" / "Release" / "net10.0-windows" / "RiftReader.SendInput.dll"
)


def _send_wm(key: str, hold_ms: int) -> bool:
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
    try:
        r = subprocess.run(
            ["dotnet", CSharp_SENDINPUT,
             "--key", key, "--hold-ms", str(hold_ms), "--mode", "ScanCode"],
            capture_output=True, text=True, timeout=10,
        )
        return r.returncode == 0 and "SUCCESS" in r.stdout
    except Exception:
        return False


def turn_left(hold_ms: int = 400) -> bool:
    """WindowMessage A key — ~70° left."""
    return _send_wm("A", hold_ms)


def turn_right(hold_ms: int = 500) -> bool:
    """C# SendInput D key — ~88° right."""
    return _send_scan("D", hold_ms)


def move_forward(hold_ms: int = 400) -> bool:
    """WindowMessage W key."""
    return _send_wm("W", hold_ms)


def move_backward(hold_ms: int = 400) -> bool:
    """WindowMessage S key."""
    return _send_wm("S", hold_ms)


# ---------------------------------------------------------------------------
# Navigation — hill climbing
# ---------------------------------------------------------------------------
def navigate_single_target(
    pid: int,
    base: int,
    target: dict[str, float],
    *,
    arrival_radius: float = 5.0,
    max_steps: int = 30,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """Navigate to target using hill-climbing: move, check, adjust."""
    steps: list[dict[str, Any]] = []
    consecutive_closer = 0
    consecutive_further = 0
    consecutive_stuck = 0
    last_dist = None

    for step in range(max_steps):
        pos = read_coords(pid, base)
        if not pos:
            steps.append({"step": step, "error": "cannot-read-coords"})
            break

        dist = distance_planar(pos, target)
        brg = bearing_deg(pos, target)

        rec: dict[str, Any] = {
            "step": step,
            "pos": {k: round(v, 2) for k, v in pos.items()},
            "bearing": round(brg, 1),
            "dist": round(dist, 2),
        }

        if verbose:
            print(f"  step={step:2d}  pos=({pos['x']:.1f},{pos['y']:.1f},{pos['z']:.1f})  "
                  f"brg={brg:.0f}  dist={dist:.1f}")

        # --- Arrival check ---
        if dist <= arrival_radius:
            rec["action"] = "arrived"
            steps.append(rec)
            return {"ok": True, "steps": steps, "final_pos": pos, "total_steps": step + 1}

        # --- Hill climbing: move, check distance change ---
        if dry_run:
            rec["action"] = "dry-run"
            steps.append(rec)
            continue

        # First move: just go forward
        if last_dist is None:
            rec["action"] = "initial_move"
            steps.append(rec)
            move_forward(hold_ms=400)
            time.sleep(0.4)
            last_dist = dist
            continue

        # Check if we got closer or further
        improvement = last_dist - dist

        if improvement > 0:
            # Got closer — keep going, don't turn
            consecutive_closer += 1
            consecutive_further = 0
            rec["action"] = "closer"
            rec["improvement"] = round(improvement, 2)
            steps.append(rec)
            if verbose:
                print(f"    closer by {improvement:.2f}")
            move_forward(hold_ms=400)
            time.sleep(0.4)
        elif improvement < -1.5:
            # Clearly going wrong way — back up and turn
            consecutive_further += 1
            consecutive_closer = 0
            rec["action"] = "wrong-way"
            rec["improvement"] = round(improvement, 2)
            steps.append(rec)
            if verbose:
                print(f"    WRONG WAY by {improvement:.2f} — turning")

            move_backward(hold_ms=300)
            time.sleep(0.3)

            if consecutive_further % 2 == 1:
                turn_left(hold_ms=400)
            else:
                turn_right(hold_ms=500)
            time.sleep(0.3)
        else:
            # Small change or small regression — just keep moving forward
            consecutive_stuck += 1
            rec["action"] = "nudge"
            rec["stuck_count"] = consecutive_stuck
            steps.append(rec)
            if verbose:
                print(f"    nudge ({improvement:+.2f}) #{consecutive_stuck}")
            move_forward(hold_ms=400)
            time.sleep(0.4)
            time.sleep(0.3)

        last_dist = dist

    return {"ok": False, "steps": steps, "final_pos": pos if 'pos' in dir() else None,
            "total_steps": max_steps}


# ---------------------------------------------------------------------------
# Multi-waypoint route
# ---------------------------------------------------------------------------
def navigate_route(
    pid: int,
    base: int,
    waypoints: list[dict[str, Any]],
    *,
    arrival_radius: float = 5.0,
    max_steps_per_waypoint: int = 30,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
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
    return {
        "ok": all(r["ok"] for r in results),
        "waypoints_total": len(waypoints),
        "waypoints_completed": sum(1 for r in results if r["ok"]),
        "total_steps": total_steps,
        "elapsed_seconds": round(elapsed, 2),
        "results": results,
    }


def load_route(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("waypoints", [])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser(description="Autonomous RIFT navigation")
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--target-x", type=float)
    p.add_argument("--target-y", type=float)
    p.add_argument("--target-z", type=float)
    p.add_argument("--route", type=str)
    p.add_argument("--arrival-radius", type=float, default=5.0)
    p.add_argument("--max-steps", type=int, default=30)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--output", type=str)
    args = p.parse_args()

    base = find_module_base(args.pid)
    if not base:
        print("ERROR: Cannot find rift_x64.exe base address", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"Module base: 0x{base:X}")

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

    if len(waypoints) == 1:
        target = waypoints[0]
        res = navigate_single_target(
            args.pid, base,
            {"x": target["x"], "y": target["y"], "z": target["z"]},
            arrival_radius=args.arrival_radius,
            max_steps=args.max_steps,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
    else:
        res = navigate_route(
            args.pid, base, waypoints,
            arrival_radius=args.arrival_radius,
            max_steps_per_waypoint=args.max_steps,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        status = "ARRIVED" if res["ok"] else "BLOCKED"
        if "waypoints_completed" in res:
            print(f"{status}: {res['waypoints_completed']}/{res['waypoints_total']} waypoints "
                  f"in {res['total_steps']} steps ({res.get('elapsed_seconds', '?')}s)")
        else:
            print(f"{status}: {res['total_steps']} steps")
        if res.get("final_pos"):
            fp = res["final_pos"]
            print(f"  Final: ({fp['x']:.1f}, {fp['y']:.1f}, {fp['z']:.1f})")

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(res, indent=2), encoding="utf-8")
        if args.verbose:
            print(f"Summary written to {args.output}")

    sys.exit(0 if res["ok"] else 1)


if __name__ == "__main__":
    main()
