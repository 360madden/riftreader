#!/usr/bin/env python3
"""Forward movement calibration: measure planar distance traveled per W-key hold duration."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
PID = "34176"
HWND = "4003140"

DURATIONS_MS = [250, 500, 750, 1000]
SETTLE_SECONDS = 0.75
COMMAND_TIMEOUT = 60


def read_state() -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "static_owner_facing_discovery.py"), "state",
         "--samples", "3", "--interval-seconds", "0.1", "--expect-stationary", "--json"],
        cwd=str(REPO_ROOT), text=True, capture_output=True, timeout=COMMAND_TIMEOUT, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"state readback failed: {result.stderr[:200]}")
    return json.loads(result.stdout)


def send_key(hold_ms: int) -> dict[str, Any]:
    ps1 = SCRIPTS / "send-rift-key-csharp.ps1"
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-NoLogo", "-ExecutionPolicy", "Bypass",
         "-File", str(ps1),
         "--key", "w",
         "--hold-ms", str(hold_ms),
         "--process-name", "rift_x64",
         "--pid", PID,
         "--hwnd", HWND,
         "--input-mode", "ScanCode",
         "--focus-delay-ms", "250",
         "--json"],
        cwd=str(REPO_ROOT), text=True, capture_output=True, timeout=COMMAND_TIMEOUT, check=False,
    )
    try:
        return json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        return {"raw": result.stdout[:200], "error": "JSON parse failed"}


def main() -> int:
    results: list[dict[str, Any]] = []
    errors: list[str] = []

    for i, dur_ms in enumerate(DURATIONS_MS):
        print(f"\n=== Calibration {i+1}/{len(DURATIONS_MS)}: {dur_ms}ms forward ===")

        # 1. Pre-state
        pre = read_state()
        pre_coord = pre.get("coordinate", {}) or {}
        pre_x = pre_coord.get("x")
        pre_z = pre_coord.get("z")
        pre_yaw = pre.get("yawDegrees")
        print(f"  Pre:  ({pre_x:.2f}, {pre_z:.2f})  yaw={pre_yaw:.2f}°")

        # 2. Send W key
        print(f"  Sending W for {dur_ms}ms...")
        send_result = send_key(dur_ms)
        if send_result.get("ok") is None:
            print(f"  ⚠ Send JSON unusual: {json.dumps(send_result, default=str)[:100]}")
        print(f"  Waiting {SETTLE_SECONDS}s settle...")
        time.sleep(SETTLE_SECONDS)

        # 3. Post-state
        post = read_state()
        post_coord = post.get("coordinate", {}) or {}
        post_x = post_coord.get("x")
        post_z = post_coord.get("z")
        post_yaw = post.get("yawDegrees")
        print(f"  Post: ({post_x:.2f}, {post_z:.2f})  yaw={post_yaw:.2f}°")

        # 4. Compute planar distance
        if None not in (pre_x, pre_z, post_x, post_z):
            dx = float(post_x) - float(pre_x)
            dz = float(post_z) - float(pre_z)
            planar = math.hypot(dx, dz)
        else:
            dx = dz = planar = None

        cal = {
            "holdMs": dur_ms,
            "pre": {"x": pre_x, "z": pre_z, "yawDegrees": pre_yaw},
            "post": {"x": post_x, "z": post_z, "yawDegrees": post_yaw},
            "dx": dx,
            "dz": dz,
            "planarDistance": planar,
            "speedMetersPerSecond": (planar / (dur_ms / 1000.0)) if planar is not None and dur_ms > 0 else None,
            "yawDelta": (float(post_yaw) - float(pre_yaw)) if pre_yaw is not None and post_yaw is not None else None,
        }
        results.append(cal)
        speed = cal.get("speedMetersPerSecond")
        if speed is not None:
            print(f"  -> Planar distance: {planar:.3f}m  (speed: {speed:.2f} m/s)")
        else:
            print(f"  -> Planar distance: {planar:.3f}m")

    # Summary
    print("\n" + "=" * 60)
    print("FORWARD MOVEMENT CALIBRATION SUMMARY")
    print("=" * 60)
    for r in results:
        print(f"  {r['holdMs']:5d}ms → {r['planarDistance']:.3f}m  ({r['speedMetersPerSecond']:.2f} m/s)")

    output = {
        "kind": "forward-movement-calibration",
        "count": len(results),
        "results": results,
        "errors": errors,
        "calibrationCurve": {
            "durationsMs": [r["holdMs"] for r in results],
            "planarDistances": [r["planarDistance"] for r in results],
            "speedsMpS": [r["speedMetersPerSecond"] for r in results],
        },
    }

    print(f"\n{json.dumps(output, indent=2)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
