#!/usr/bin/env python3
"""
Resolve player coordinates from RIFT process memory.

Chain: rift_x64+0x32EBDC0 -> heap object -> +0x320/+0x324/+0x328 (X/Y/Z)
Facing: +0x300 % 360 = heading in degrees

Usage:
    python resolve-player-coords.py --pid <pid>                  # one-shot, human output
    python resolve-player-coords.py --pid <pid> --json           # one-shot, JSON
    python resolve-player-coords.py --pid <pid> --watch          # continuous poll, writes latest.json
    python resolve-player-coords.py --pid <pid> --watch --interval 100
"""

import argparse
import ctypes
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

kernel32 = ctypes.windll.kernel32

# --- Chain configuration ---
COORD_GLOBAL_RVA = 0x32EBDC0
OFFSET_X = 0x320
OFFSET_Y = 0x324
OFFSET_Z = 0x328
OFFSET_HEADING_RAW = 0x300
OFFSET_SPEED = 0x304
PROCESS_VM_READ = 0x0010


def find_module_base(pid):
    """Find rift_x64.exe base address in target process."""
    handle = kernel32.OpenProcess(PROCESS_VM_READ, False, pid)
    if not handle:
        return None, "Cannot open process with VM_READ"

    # Fast path: try known bases
    known_bases = [0x7FF728B80000, 0x7FF728A00000, 0x7FF728C00000, 0x7FF6EE5D0000]
    for addr in known_bases:
        data = _read_bytes(handle, addr, 2)
        if data == b"MZ":
            kernel32.CloseHandle(handle)
            return addr, None

    # Broader scan
    try:
        for page in range(0x7FF00000, 0x7FFF0000, 0x1000):
            addr = page * 0x10000
            data = _read_bytes(handle, addr, 2)
            if data == b"MZ":
                kernel32.CloseHandle(handle)
                return addr, None
    except Exception:
        pass

    kernel32.CloseHandle(handle)
    return None, "Cannot find MZ header in expected address range"


def _read_bytes(handle, address, size):
    """Read raw bytes from process memory."""
    buf = ctypes.create_string_buffer(size)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(handle, ctypes.c_void_p(address), buf, size, ctypes.byref(br))
    if not ok or br.value != size:
        return None
    return buf.raw


def _read_u64(handle, address):
    data = _read_bytes(handle, address, 8)
    return ctypes.c_ulonglong.from_buffer_copy(data).value if data else None


def _read_f32(handle, address):
    data = _read_bytes(handle, address, 4)
    return ctypes.c_float.from_buffer_copy(data).value if data else None


def resolve_state(pid):
    """Read full player state from memory. Returns dict matching watch_rift.py output shape."""
    now = datetime.now(timezone.utc)
    state = {
        "ok": False,
        "source": "memory-reader",
        "transport": "memory-chain",
        "updatedAt": now.isoformat(timespec="milliseconds"),
        "capturedAt": now.isoformat(timespec="milliseconds"),
        "pid": pid,
        "chain": {
            "globalRva": hex(COORD_GLOBAL_RVA),
            "offsets": {"x": hex(OFFSET_X), "y": hex(OFFSET_Y), "z": hex(OFFSET_Z), "heading": hex(OFFSET_HEADING_RAW)},
        },
        "position": None,
        "navigation": None,
        "player": None,
        "protocol": {"version": 1, "valid": True, "transport": "memory-chain"},
        "blockers": [],
        "warnings": [],
    }

    # Find module base
    base, err = find_module_base(pid)
    if err:
        state["blockers"].append(err)
        return state
    state["moduleBase"] = hex(base)

    # Open process
    handle = kernel32.OpenProcess(PROCESS_VM_READ, False, pid)
    if not handle:
        state["blockers"].append("Cannot open process with VM_READ")
        return state

    try:
        # Read global pointer
        obj_ptr = _read_u64(handle, base + COORD_GLOBAL_RVA)
        if obj_ptr is None:
            state["blockers"].append("Cannot read global pointer")
            return state

        if obj_ptr == 0 or obj_ptr < 0x10000:
            state["blockers"].append("Global pointer invalid: " + hex(obj_ptr) if obj_ptr else "Global pointer null (not in world?)")
            return state

        # Read coordinates
        x = _read_f32(handle, obj_ptr + OFFSET_X)
        y = _read_f32(handle, obj_ptr + OFFSET_Y)
        z = _read_f32(handle, obj_ptr + OFFSET_Z)
        heading_raw = _read_f32(handle, obj_ptr + OFFSET_HEADING_RAW)
        speed = _read_f32(handle, obj_ptr + OFFSET_SPEED)

        if any(v is None for v in (x, y, z, heading_raw)):
            state["blockers"].append("Cannot read coordinate fields from object")
            return state

        # Validate
        if any(math.isnan(v) or math.isinf(v) for v in (x, y, z)):
            state["blockers"].append("Coordinate contains NaN or Infinity")
            return state

        if abs(x) > 100000 or abs(y) > 100000 or abs(z) > 100000:
            state["warnings"].append("Coordinates look unreasonable")

        if x == 0.0 and y == 0.0 and z == 0.0:
            state["warnings"].append("All coordinates zero — player may not be loaded")

        # Compute heading (cumulative rotation mod 360)
        heading_deg = round(heading_raw % 360, 4) if heading_raw is not None else None

        # Detect movement (speed threshold)
        is_moving = abs(speed) > 0.1 if speed is not None else False

        state["position"] = {"x": round(x, 4), "y": round(y, 4), "z": round(z, 4)}
        state["navigation"] = {
            "yawDeg": heading_deg,
            "isMoving": is_moving,
            "speed": round(speed, 4) if speed is not None else None,
            "facingSource": "memory-chain",
        }
        state["ok"] = True
        return state

    finally:
        kernel32.CloseHandle(handle)


def _write_atomic(path, payload):
    """Write JSON atomically."""
    tmp = Path(str(path) + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def watch_loop(pid, output_path, interval_ms):
    """Continuous polling loop matching watch_rift.py output format."""
    print(f"Memory reader started. pid={pid} interval={interval_ms}ms output={output_path}")
    print("Press Ctrl+C to stop.", flush=True)

    iteration = 0
    while True:
        iteration += 1
        t0 = time.monotonic()

        state = resolve_state(pid)
        state["iteration"] = iteration

        payload = json.dumps(state, separators=(",", ":"), sort_keys=True)
        try:
            _write_atomic(output_path, payload)
        except OSError as exc:
            print(f"  write failed: {exc}", flush=True)

        # Compact status line
        if state["ok"]:
            p = state["position"]
            n = state["navigation"]
            heading = n.get("yawDeg", "?") if n else "?"
            print(f"  #{iteration} X={p['x']:.1f} Y={p['y']:.1f} Z={p['z']:.1f} H={heading}°", flush=True)
        else:
            print(f"  #{iteration} BLOCKED: {'; '.join(state['blockers'])}", flush=True)

        elapsed_ms = (time.monotonic() - t0) * 1000
        remaining = interval_ms - int(elapsed_ms)
        if remaining > 0:
            time.sleep(remaining / 1000.0)


def main():
    parser = argparse.ArgumentParser(description="Resolve RIFT player coordinates from memory")
    parser.add_argument("--pid", type=int, required=True, help="RIFT process ID")
    parser.add_argument("--json", action="store_true", help="Output as JSON (one-shot)")
    parser.add_argument("--watch", action="store_true", help="Continuous polling mode")
    parser.add_argument("--interval", type=int, default=200, help="Poll interval in ms (default: 200)")
    parser.add_argument("--output", type=str, default=None, help="Output path for --watch mode")
    args = parser.parse_args()

    if args.pid <= 0:
        err = {"ok": False, "blockers": ["Invalid PID: " + str(args.pid)]}
        if args.json:
            print(json.dumps(err, indent=2))
        else:
            print("BLOCKER: Invalid PID", file=sys.stderr)
        sys.exit(1)

    if args.watch:
        output = Path(args.output) if args.output else Path(".local") / "state" / "latest.json"
        try:
            watch_loop(args.pid, output, args.interval)
        except KeyboardInterrupt:
            print("\nStopped.")
        sys.exit(0)

    # One-shot mode
    state = resolve_state(args.pid)

    if args.json:
        print(json.dumps(state, indent=2))
    else:
        if state["ok"]:
            p = state["position"]
            n = state["navigation"]
            heading = n.get("yawDeg", "?") if n else "?"
            print("X={:.4f} Y={:.4f} Z={:.4f} heading={:.1f}°".format(p["x"], p["y"], p["z"], heading))
        else:
            for b in state["blockers"]:
                print("BLOCKER: " + b, file=sys.stderr)

    sys.exit(0 if state["ok"] else 1)


if __name__ == "__main__":
    main()
