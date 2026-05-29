#!/usr/bin/env python3
"""Forward movement calibration: measure planar distance traveled per W-key hold duration."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"

DEFAULT_DURATIONS_MS = [250, 500, 750, 1000]
SETTLE_SECONDS = 0.75
COMMAND_TIMEOUT = 60


def load_target(truth_path: Path) -> dict[str, str]:
    """Load PID and HWND from current-truth.json."""
    try:
        data = json.loads(truth_path.read_text(encoding="utf-8"))
        target = data.get("target") or {}
        pid = str(target.get("processId", ""))
        hwnd_hex = str(target.get("targetWindowHandle", ""))
        hwnd_is_hex = hwnd_hex.startswith("0x")
        if not pid or not hwnd_hex:
            return {"pid": pid, "hwnd": hwnd_hex}
        hwnd = str(int(hwnd_hex, 16)) if hwnd_is_hex else hwnd_hex
        return {"pid": pid, "hwnd": hwnd}
    except (FileNotFoundError, json.JSONDecodeError, ValueError, KeyError) as exc:
        return {"pid": "", "hwnd": "", "error": f"{type(exc).__name__}:{exc}"}


def read_state() -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "static_owner_facing_discovery.py"), "state",
         "--samples", "3", "--interval-seconds", "0.1", "--expect-stationary", "--json"],
        cwd=str(REPO_ROOT), text=True, capture_output=True, timeout=COMMAND_TIMEOUT, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"state readback failed: {result.stderr[:200]}")
    return json.loads(result.stdout)


def send_key(hold_ms: int, pid: str, hwnd: str) -> None:
    ps1 = SCRIPTS / "send-rift-key-csharp.ps1"
    subprocess.run(
        ["pwsh", "-NoProfile", "-NoLogo", "-ExecutionPolicy", "Bypass",
         "-File", str(ps1),
         "--key", "w",
         "--hold-ms", str(hold_ms),
         "--process-name", "rift_x64",
         "--pid", pid,
         "--hwnd", hwnd,
         "--input-mode", "ScanCode",
         "--focus-delay-ms", "250",
         "--json"],
        cwd=str(REPO_ROOT), text=True, capture_output=True, timeout=COMMAND_TIMEOUT, check=False,
    )


def run_calibration(*, durations_ms: list[int], pid: str, hwnd: str) -> dict[str, Any]:
    """Run forward movement calibration for each duration. Returns structured results."""
    results: list[dict[str, Any]] = []
    errors: list[str] = []

    for dur_ms in durations_ms:
        # 1. Pre-state
        pre = read_state()
        pre_coord = pre.get("coordinate", {}) or {}
        pre_x = pre_coord.get("x")
        pre_z = pre_coord.get("z")
        pre_yaw = pre.get("yawDegrees")

        # 2. Send W key
        send_key(dur_ms, pid, hwnd)
        time.sleep(SETTLE_SECONDS)

        # 3. Post-state
        post = read_state()
        post_coord = post.get("coordinate", {}) or {}
        post_x = post_coord.get("x")
        post_z = post_coord.get("z")
        post_yaw = post.get("yawDegrees")

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

    return {
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


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S") + f"-{datetime.now(UTC).microsecond // 1000:03d}"


def utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calibrate forward movement: measure planar distance per W-key hold duration")
    parser.add_argument("--current-truth-json", default="docs/recovery/current-truth.json")
    parser.add_argument("--durations-ms", nargs="+", type=int, default=DEFAULT_DURATIONS_MS)
    parser.add_argument("--output-root")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    truth_path = Path(str(args.current_truth_json))
    target = load_target(truth_path)
    pid = target.get("pid", "")
    hwnd = target.get("hwnd", "")
    if not pid or not hwnd:
        print(json.dumps({"status": "failed", "error": f"target-info-not-found:{target.get('error', 'missing-pid-or-hwnd')}"}))
        return 1

    output_root = Path(str(args.output_root)).resolve() if args.output_root else REPO_ROOT / "scripts" / "captures"
    run_dir = output_root / f"forward-movement-calibration-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    output = run_calibration(durations_ms=list(args.durations_ms), pid=pid, hwnd=hwnd)
    output["generatedAtUtc"] = utc_iso()
    output["summaryJson"] = str(run_dir / "summary.json")

    # Write artifacts
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    summary_md = run_dir / "summary.md"
    lines = ["# Forward movement calibration", "",
             f"Generated: `{output['generatedAtUtc']}`", "",
             "| Duration | Distance | Speed |", "|---|---|---|"]
    for r in output.get("results", []):
        speed = r.get("speedMetersPerSecond")
        speed_str = f"{speed:.2f} m/s" if speed is not None else "N/A"
        dist = r.get("planarDistance")
        dist_str = f"{dist:.3f}m" if dist is not None else "N/A"
        lines.append(f"| {r['holdMs']}ms | {dist_str} | {speed_str} |")
    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(output, indent=2) if not args.json else json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
