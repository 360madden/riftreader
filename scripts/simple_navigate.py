#!/usr/bin/env python3
"""Simple navigation script using the promoted coordinate chain.

This script provides basic point-to-point navigation using the
confirmed coordinate chain [[rift_x64+0x32EBDC0]+0x320].

Usage:
    python simple_navigate.py --pid <pid> --target-x <x> --target-y <y> --target-z <z>
    python simple_navigate.py --pid <pid> --target-x <x> --target-y <y> --target-z <z> --dry-run
    python simple_navigate.py --pid <pid> --target-x <x> --target-y <y> --target-z <z> --verbose
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

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# --- Direct memory reading (fast, no subprocess) ---
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
        # Try known base first (ASLR usually gives same base for same binary)
        known_bases = [0x7FF728B80000, 0x7FF700000000, 0x7FF600000000]
        for base in known_bases:
            test_addr = base + COORD_GLOBAL_RVA
            buf = ctypes.create_string_buffer(8)
            bytes_read = ctypes.c_size_t(0)
            if kernel32.ReadProcessMemory(handle, ctypes.c_void_p(test_addr), buf, 8, ctypes.byref(bytes_read)):
                val = int.from_bytes(buf.raw[:8], 'little')
                if val > 0x10000 and val < 0x7FFFFFFFFFFFFFFF:
                    return base
        return None
    finally:
        kernel32.CloseHandle(handle)


def read_chain_coords(pid: int, base: int) -> dict[str, Any] | None:
    """Read coordinates directly from memory chain."""
    handle = kernel32.OpenProcess(PROCESS_VM_READ, False, pid)
    if not handle:
        return None

    try:
        # Read global pointer
        global_addr = base + COORD_GLOBAL_RVA
        buf = ctypes.create_string_buffer(8)
        bytes_read = ctypes.c_size_t(0)

        if not kernel32.ReadProcessMemory(handle, ctypes.c_void_p(global_addr), buf, 8, ctypes.byref(bytes_read)):
            return None

        obj_ptr = int.from_bytes(buf.raw[:8], 'little')
        if obj_ptr < 0x10000 or obj_ptr > 0x7FFFFFFFFFFFFFFF:
            return None

        # Read coordinates
        coords = {}
        for name, offset in [("x", OFFSET_X), ("y", OFFSET_Y), ("z", OFFSET_Z)]:
            addr = obj_ptr + offset
            if not kernel32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, 4, ctypes.byref(bytes_read)):
                return None
            coords[name] = ctypes.c_float.from_buffer(buf).value

        # Read heading
        addr = obj_ptr + OFFSET_HEADING_RAW
        if kernel32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, 4, ctypes.byref(bytes_read)):
            raw_heading = ctypes.c_float.from_buffer(buf).value
            # Convert rotation counter to degrees
            heading_deg = raw_heading % 360.0
            if heading_deg < 0:
                heading_deg += 360.0
            coords["heading"] = heading_deg
        else:
            coords["heading"] = 0.0

        return coords
    finally:
        kernel32.CloseHandle(handle)


def get_current_position(pid: int, base: int) -> dict[str, Any] | None:
    """Get current player position from the coordinate chain."""
    try:
        coords = read_chain_coords(pid, base)
        if coords:
            return {
                "x": coords["x"],
                "y": coords["y"],
                "z": coords["z"],
                "heading": coords.get("heading", 0.0),
            }
    except Exception:
        pass
    return None


def calculate_bearing(from_pos: dict, to_pos: dict) -> float:
    """Calculate bearing from current position to target in degrees."""
    dx = to_pos["x"] - from_pos["x"]
    dz = to_pos["z"] - from_pos["z"]
    
    # atan2 returns angle from positive x-axis, convert to compass bearing
    bearing_rad = math.atan2(dx, dz)
    bearing_deg = math.degrees(bearing_rad)
    
    # Normalize to 0-360
    return (bearing_deg + 360) % 360


def calculate_distance(from_pos: dict, to_pos: dict) -> float:
    """Calculate 3D distance between two positions."""
    dx = to_pos["x"] - from_pos["x"]
    dy = to_pos["y"] - from_pos["y"]
    dz = to_pos["z"] - from_pos["z"]
    return math.sqrt(dx*dx + dy*dy + dz*dz)


def calculate_height_delta(from_pos: dict, to_pos: dict) -> float:
    """Calculate height difference (positive = target is higher)."""
    return to_pos["y"] - from_pos["y"]


def send_key(key: str, hold_ms: int = 500) -> bool:
    """Send a key to RIFT using window message input."""
    try:
        # Use pwsh (PowerShell 7) which has different execution policy
        result = subprocess.run(
            ["pwsh", "-File", str(Path(__file__).parent / "post-rift-key.ps1"),
             "-Key", key,
             "-HoldMilliseconds", str(hold_ms),
             "-SkipBackgroundFocus"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def turn_to_heading(current_heading: float, target_heading: float) -> str | None:
    """Determine which key to press to turn towards target heading."""
    # Calculate shortest turn direction
    delta = (target_heading - current_heading + 180) % 360 - 180
    
    if abs(delta) < 10:  # Already facing target (within 10°)
        return None
    elif delta > 0:
        return "A"  # Turn left (positive delta means target is to the left)
    else:
        return "D"  # Turn right


def navigate_to_target(
    pid: int,
    base: int,
    target_x: float,
    target_y: float,
    target_z: float,
    arrival_radius: float = 5.0,
    max_steps: int = 50,
    step_delay: float = 0.5,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """Navigate to target coordinates."""
    target_pos = {"x": target_x, "y": target_y, "z": target_z}
    
    result = {
        "ok": False,
        "target": target_pos,
        "steps": [],
        "final_position": None,
        "blockers": [],
    }
    
    for step in range(max_steps):
        # Get current position (direct memory read, fast)
        current_coords = get_current_position(pid, base)
        if not current_coords:
            result["blockers"].append(f"Step {step}: Cannot read coordinates")
            break
        
        current_pos = {"x": current_coords["x"], "y": current_coords["y"], "z": current_coords["z"]}
        current_heading = current_coords["heading"]
        
        # Calculate distance and bearing
        distance = calculate_distance(current_pos, target_pos)
        bearing = calculate_bearing(current_pos, target_pos)
        height_delta = calculate_height_delta(current_pos, target_pos)
        
        step_info = {
            "step": step,
            "position": current_pos.copy(),
            "heading": current_heading,
            "distance": round(distance, 2),
            "bearing": round(bearing, 2),
            "height_delta": round(height_delta, 2),
        }
        
        if verbose:
            print(f"Step {step}: pos=({current_pos['x']:.1f}, {current_pos['y']:.1f}, {current_pos['z']:.1f}) "
                  f"heading={current_heading:.1f}° dist={distance:.1f} bearing={bearing:.1f}°")
        
        # Check if we've arrived
        if distance <= arrival_radius:
            step_info["action"] = "arrived"
            result["steps"].append(step_info)
            result["ok"] = True
            result["final_position"] = current_pos.copy()
            if verbose:
                print(f"  Arrived at target! Distance: {distance:.1f}")
            break
        
        # Determine action
        turn_key = turn_to_heading(current_heading, bearing)
        
        if turn_key:
            # Need to turn
            step_info["action"] = f"turn_{turn_key}"
            if verbose:
                print(f"  Turning {turn_key} to face bearing {bearing:.1f}°")
            
            if not dry_run:
                send_key(turn_key, hold_ms=200)
                time.sleep(step_delay)
        else:
            # Facing target, move forward
            step_info["action"] = "move_forward"
            if verbose:
                print(f"  Moving forward towards bearing {bearing:.1f}°")
            
            if not dry_run:
                send_key("W", hold_ms=500)
                time.sleep(step_delay)
        
        result["steps"].append(step_info)
    
    else:
        result["blockers"].append(f"Max steps ({max_steps}) reached")
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Simple navigation using coordinate chain")
    parser.add_argument("--pid", type=int, required=True, help="RIFT process ID")
    parser.add_argument("--target-x", type=float, required=True, help="Target X coordinate")
    parser.add_argument("--target-y", type=float, required=True, help="Target Y coordinate")
    parser.add_argument("--target-z", type=float, required=True, help="Target Z coordinate")
    parser.add_argument("--arrival-radius", type=float, default=5.0, help="Arrival radius (default: 5.0)")
    parser.add_argument("--max-steps", type=int, default=50, help="Maximum navigation steps (default: 50)")
    parser.add_argument("--step-delay", type=float, default=0.5, help="Delay between steps in seconds (default: 0.5)")
    parser.add_argument("--dry-run", action="store_true", help="Plan only, don't send input")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    # Find module base
    base = find_module_base(args.pid)
    if not base:
        print("ERROR: Cannot find rift_x64.exe base address", file=sys.stderr)
        sys.exit(1)
    
    if args.verbose:
        print(f"Module base: 0x{base:X}")
    
    # Run navigation
    result = navigate_to_target(
        pid=args.pid,
        base=base,
        target_x=args.target_x,
        target_y=args.target_y,
        target_z=args.target_z,
        arrival_radius=args.arrival_radius,
        max_steps=args.max_steps,
        step_delay=args.step_delay,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
    
    # Output
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["ok"]:
            print(f"Navigation complete! Final position: ({result['final_position']['x']:.1f}, "
                  f"{result['final_position']['y']:.1f}, {result['final_position']['z']:.1f})")
        else:
            for blocker in result["blockers"]:
                print(f"BLOCKER: {blocker}", file=sys.stderr)
    
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
