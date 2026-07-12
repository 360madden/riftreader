#!/usr/bin/env python3
"""RIFT nav7: Multi-waypoint router using nav6 heading-based navigation.

Takes a list of waypoints and navigates to each in sequence.
Can read waypoints from JSON file or command line.
"""

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

NAV6 = str(Path(__file__).parent / "nav6.py")


def load_waypoints(args):
    """Load waypoints from file or command line."""
    if args.waypoints_file:
        with open(args.waypoints_file, 'r') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            elif "waypoints" in data:
                return data["waypoints"]
            elif "history" in data:
                # Convert navmesh history to waypoints
                return [{"x": w["x"], "z": w["z"]} for w in data["history"]]
    elif args.waypoints:
        return [{"x": float(w.split(",")[0]), "z": float(w.split(",")[1])}
                for w in args.waypoints]
    return []


def navigate_to_waypoint(pid, wp, radius, walk_ms, verbose):
    """Navigate to a single waypoint using nav6."""
    cmd = [
        sys.executable, NAV6,
        "--pid", str(pid),
        "--target-x", str(wp["x"]),
        "--target-z", str(wp["z"]),
        "--radius", str(radius),
        "--walk-ms", str(walk_ms),
    ]
    if verbose:
        cmd.append("--verbose")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    # Parse nav6 output
    try:
        # Find JSON in output (last line that starts with {)
        lines = result.stdout.strip().split('\n')
        json_start = -1
        for i, line in enumerate(lines):
            if line.strip().startswith('{'):
                json_start = i
                break
        if json_start >= 0:
            return json.loads('\n'.join(lines[json_start:]))
    except (json.JSONDecodeError, IndexError):
        pass

    return {"ok": False, "error": result.stdout + result.stderr}


def main():
    p = argparse.ArgumentParser(description="RIFT nav7: multi-waypoint router")
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--waypoints-file", type=str, help="JSON file with waypoints")
    p.add_argument("--waypoints", nargs="+", help="Waypoints as x,z pairs")
    p.add_argument("--radius", type=float, default=5.0)
    p.add_argument("--walk-ms", type=int, default=400)
    p.add_argument("--pause", type=float, default=1.0, help="Pause between waypoints (seconds)")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    waypoints = load_waypoints(args)
    if not waypoints:
        print("ERROR: no waypoints provided")
        sys.exit(1)

    print(f"Navigating {len(waypoints)} waypoints (radius={args.radius})")
    results = []
    total_steps = 0

    for i, wp in enumerate(waypoints):
        print(f"\n{'='*50}")
        print(f"Waypoint {i+1}/{len(waypoints)}: ({wp['x']:.1f}, {wp['z']:.1f})")
        print(f"{'='*50}")

        result = navigate_to_waypoint(args.pid, wp, args.radius, args.walk_ms, args.verbose)
        results.append({"waypoint": wp, "result": result})

        if result.get("ok"):
            steps = result.get("steps", 0)
            dist = result.get("dist", 0)
            final = result.get("final", {})
            total_steps += steps
            print(f"  ARRIVED in {steps} steps (dist={dist:.1f})")
        else:
            print(f"  FAILED: {result.get('error', 'unknown')}")
            if args.verbose:
                print(f"  Stopping navigation")
                break

        if i < len(waypoints) - 1:
            time.sleep(args.pause)

    # Summary
    print(f"\n{'='*50}")
    print(f"NAVIGATION COMPLETE")
    print(f"  Waypoints: {len(results)}/{len(waypoints)}")
    print(f"  Total steps: {total_steps}")
    successes = sum(1 for r in results if r["result"].get("ok"))
    print(f"  Successes: {successes}/{len(results)}")
    print(f"{'='*50}")

    print(json.dumps({
        "total_waypoints": len(waypoints),
        "completed": successes,
        "total_steps": total_steps,
        "results": results,
    }, indent=2))


if __name__ == "__main__":
    main()
