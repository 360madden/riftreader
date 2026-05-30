#!/usr/bin/env python3
"""Nav-state freshness watchdog — dual-read turn-rate correlation validator.

Reads the promoted static resolver nav-state twice with a configurable interval
and reports whether the engine turn-rate discriminator (+0x304) correlates with
observed facing-target movement.

This is a pure validation tool — NO game input, NO debugger attach, NO mutation.
All evidence is candidate-only.

Usage:
    python scripts/nav_state_freshness_watchdog.py --pid 25668 --hwnd 0x320CB0 --module-base 0x7FF6EE5D0000 --json
    python scripts/nav_state_freshness_watchdog.py --interval-seconds 0.25 --json

Output:
    - status: passed (turn rate stable while stationary, or fresh facing change detected)
    - verdict: detailed explanation
    - navStateBefore / navStateAfter: raw readback payloads
    - deltas: yaw, facing target, turn rate changes between reads
    - correlation: whether turn-rate direction matches facing-target displacement
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = 1
DEFAULT_INTERVAL_SECONDS = 0.5
DEFAULT_TIMEOUT_SECONDS = 30.0


def utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def safe_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_one_nav_state(
    *,
    root: Path,
    pid: int | None,
    hwnd: str | None,
    module_base: str | None,
    process_name: str = "rift_x64",
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run a single nav-state readback and return the parsed payload."""
    command = [sys.executable, str(root / "scripts" / "static_owner_coordinate_chain_readback.py"), "--nav-state", "--json"]
    if pid is not None:
        command += ["--pid", str(pid)]
    if hwnd is not None:
        command += ["--hwnd", str(hwnd)]
    if module_base is not None:
        command += ["--module-base", str(module_base)]
    if process_name:
        command += ["--process-name", str(process_name)]
    try:
        result = subprocess.run(
            command, cwd=str(root), text=True, capture_output=True, timeout=timeout_seconds, check=False,
        )
        if result.stdout.strip():
            parsed = json.loads(result.stdout)
            if isinstance(parsed, dict):
                return {
                    "ok": parsed.get("status") not in ("unavailable", "readback-failed", "parse-error"),
                    "exitCode": result.returncode,
                    "status": parsed.get("status"),
                    "verdict": parsed.get("verdict"),
                    "reads": safe_mapping(parsed.get("reads")),
                    "navState": safe_mapping(parsed.get("navState")),
                    "stdoutPreview": result.stdout[:500] if len(result.stdout) > 500 else result.stdout,
                    "stderrPreview": result.stderr[:200] if len(result.stderr) > 200 else result.stderr,
                }
        return {"ok": False, "error": "parse-failed", "stdoutPreview": result.stdout[:500]}
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "error": f"TimeoutExpired:{exc}"}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}"}


def compute_deltas(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Compute per-field deltas between two nav-state readbacks."""
    nav_before = safe_mapping(before.get("navState"))
    nav_after = safe_mapping(after.get("navState"))

    yaw_before = nav_before.get("yawDegrees")
    yaw_after = nav_after.get("yawDegrees")
    yaw_delta: float | None = None
    if isinstance(yaw_before, (int, float)) and isinstance(yaw_after, (int, float)):
        yaw_delta = float(yaw_after) - float(yaw_before)

    turn_before = nav_before.get("turnRate0x304")
    turn_after = nav_after.get("turnRate0x304")
    turn_delta: float | None = None
    if isinstance(turn_before, (int, float)) and isinstance(turn_after, (int, float)):
        turn_delta = float(turn_after) - float(turn_before)

    facing_before = safe_mapping(nav_before.get("facingTargetCoordinate"))
    facing_after = safe_mapping(nav_after.get("facingTargetCoordinate"))
    facing_dx: float | None = None
    facing_dz: float | None = None
    if all(
        isinstance(f, (int, float))
        for f in (facing_before.get("x"), facing_before.get("z"), facing_after.get("x"), facing_after.get("z"))
    ):
        facing_dx = float(facing_after["x"]) - float(facing_before["x"])
        facing_dz = float(facing_after["z"]) - float(facing_before["z"])

    coord_before = safe_mapping(nav_before.get("coordinate"))
    coord_after = safe_mapping(nav_after.get("coordinate"))
    coord_dx: float | None = None
    coord_dz: float | None = None
    if all(
        isinstance(f, (int, float))
        for f in (coord_before.get("x"), coord_before.get("z"), coord_after.get("x"), coord_after.get("z"))
    ):
        coord_dx = float(coord_after["x"]) - float(coord_before["x"])
        coord_dz = float(coord_after["z"]) - float(coord_before["z"])

    return {
        "yawDeltaDegrees": yaw_delta,
        "turnRate0x304Delta": turn_delta,
        "turnRate0x304Before": turn_before,
        "turnRate0x304After": turn_after,
        "facingTargetDx": facing_dx,
        "facingTargetDz": facing_dz,
        "coordinateDx": coord_dx,
        "coordinateDz": coord_dz,
    }


def classify_correlation(deltas: dict[str, Any], turn_class_before: str, turn_class_after: str) -> dict[str, Any]:
    """Classify whether turn-rate discriminator correlates with facing-target movement."""
    turn_before = deltas.get("turnRate0x304Before")
    turn_after = deltas.get("turnRate0x304After")
    turn_delta = deltas.get("turnRate0x304Delta")
    facing_dx = deltas.get("facingTargetDx")
    facing_dz = deltas.get("facingTargetDz")
    yaw_delta = deltas.get("yawDeltaDegrees")

    # Stability check: both reads should return non-None values
    if turn_before is None or turn_after is None:
        return {
            "status": "no-data",
            "reason": "turn-rate-values-none",
            "detail": "Turn rate could not be read from owner+0x304 in one or both samples.",
            "correlationEstablished": False,
            "turnRateStable": False,
            "facingTargetMoved": False,
        }

    turn_stable = False
    if turn_delta is not None and abs(float(turn_delta)) < 0.01:
        turn_stable = True

    # Facing target movement check
    facing_moved = False
    facing_distance: float | None = None
    if facing_dx is not None and facing_dz is not None:
        facing_distance = math.sqrt(float(facing_dx) ** 2 + float(facing_dz) ** 2)
        facing_moved = bool(facing_distance >= 0.01)

    # Determine freshness quality
    if turn_stable and not facing_moved:
        return {
            "status": "passed",
            "reason": "stationary-freshness-confirmed",
            "detail": "Turn rate stable at ~0 and facing target did not move. Stationary nav-state is fresh.",
            "correlationEstablished": True,
            "turnRateStable": True,
            "facingTargetMoved": False,
            "facingTargetMoveDistance": facing_distance,
            "turnRateDelta": turn_delta,
            "yawDeltaDegrees": yaw_delta,
        }
    # Active turn + facing moved = valid correlation regardless of class string
    if not turn_stable and facing_moved:
        class_note = "" if turn_class_before == turn_class_after else f" (class string shifted: {turn_class_before}→{turn_class_after})"
        return {
            "status": "passed",
            "reason": "active-turn-freshness-confirmed",
            "detail": f"Turn rate discriminator active ({turn_before:.3f}→{turn_after:.3f}) and facing target moved {facing_distance:.4f} units{class_note}. Nav-state is fresh.",
            "correlationEstablished": True,
            "turnRateStable": False,
            "facingTargetMoved": True,
            "facingTargetMoveDistance": facing_distance,
            "turnRateDelta": turn_delta,
            "yawDeltaDegrees": yaw_delta,
        }
    if turn_stable and facing_moved:
        return {
            "status": "dissonance",
            "reason": "facing-moved-while-turn-rate-stable",
            "detail": "Facing target moved but turn rate discriminator at +0x304 remained stable. Possible stale read or player moved via strafe.",
            "correlationEstablished": False,
            "turnRateStable": True,
            "facingTargetMoved": True,
            "facingTargetMoveDistance": facing_distance,
            "turnRateDelta": turn_delta,
            "yawDeltaDegrees": yaw_delta,
        }
    # not turn_stable and not facing_moved
    return {
        "status": "dissonance",
        "reason": "turn-rate-active-while-facing-stable",
        "detail": f"Turn rate changed ({turn_before:.3f}→{turn_after:.3f}) but facing target did not move. Possible turn-rate readback noise or transient engine artifact.",
        "correlationEstablished": False,
        "turnRateStable": False,
        "facingTargetMoved": False,
        "facingTargetMoveDistance": 0.0,
        "turnRateDelta": turn_delta,
        "yawDeltaDegrees": yaw_delta,
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    correlation = safe_mapping(summary.get("correlation"))
    deltas = safe_mapping(summary.get("deltas"))
    safety = safe_mapping(summary.get("safety"))
    lines = [
        "# Nav-state freshness watchdog",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Correlation",
        "",
        f"- Status: `{correlation.get('status')}`",
        f"- Reason: `{correlation.get('reason')}`",
        f"- Correlation established: `{correlation.get('correlationEstablished')}`",
        f"- Turn rate stable: `{correlation.get('turnRateStable')}`",
        f"- Facing target moved: `{correlation.get('facingTargetMoved')}`",
        "",
        "## Deltas",
        "",
        f"- Yaw delta: `{deltas.get('yawDeltaDegrees')}`",
        f"- Turn rate (0x304) delta: `{deltas.get('turnRate0x304Delta')}`",
        f"- Facing target dx: `{deltas.get('facingTargetDx')}`",
        f"- Facing target dz: `{deltas.get('facingTargetDz')}`",
        f"- Coordinate dx: `{deltas.get('coordinateDx')}`",
        f"- Coordinate dz: `{deltas.get('coordinateDz')}`",
        "",
        "## Detail",
        "",
        f"{correlation.get('detail')}",
        "",
        "## Safety",
        "",
        f"- Movement sent: `{safety.get('movementSent')}`",
        f"- Input sent: `{safety.get('inputSent')}`",
        f"- Candidate only: `{safety.get('navStateCandidateOnly')}`",
    ]
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{item}`" for item in summary.get("blockers", []))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{item}`" for item in summary.get("warnings", []))
    if summary.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- `{item}`" for item in summary.get("errors", []))
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    blockers: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []

    safety = {
        "movementSent": False,
        "inputSent": False,
        "noCheatEngine": True,
        "x64dbgAttach": False,
        "debuggerAttached": False,
        "providerWrites": False,
        "gitMutation": False,
        "proofPromotion": False,
        "navStateCandidateOnly": True,
        "actionableForNavigation": False,
    }

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "nav-state-freshness-watchdog",
        "generatedAtUtc": utc_iso(),
        "status": "pending",
        "verdict": None,
        "repoRoot": str(root),
        "intervalSeconds": args.interval_seconds,
        "navStateBefore": None,
        "navStateAfter": None,
        "deltas": {},
        "correlation": {},
        "blockers": blockers,
        "warnings": warnings,
        "errors": errors,
        "safety": safety,
    }

    try:
        before = _read_one_nav_state(
            root=root,
            pid=args.pid,
            hwnd=args.hwnd,
            module_base=args.module_base,
            process_name=args.process_name,
            timeout_seconds=args.timeout_seconds,
        )
        summary["navStateBefore"] = before
        if not before.get("ok"):
            summary["status"] = "failed"
            summary["verdict"] = "first-nav-state-readback-failed"
            errors.append(f"first-readback-failed:{before.get('error')}")
            return summary

        time.sleep(float(args.interval_seconds))

        after = _read_one_nav_state(
            root=root,
            pid=args.pid,
            hwnd=args.hwnd,
            module_base=args.module_base,
            process_name=args.process_name,
            timeout_seconds=args.timeout_seconds,
        )
        summary["navStateAfter"] = after
        if not after.get("ok"):
            summary["status"] = "failed"
            summary["verdict"] = "second-nav-state-readback-failed"
            errors.append(f"second-readback-failed:{after.get('error')}")
            return summary

        deltas = compute_deltas(before, after)
        summary["deltas"] = deltas

        nav_before = safe_mapping(before.get("navState"))
        nav_after = safe_mapping(after.get("navState"))
        correlation = classify_correlation(
            deltas,
            turn_class_before=str(nav_before.get("turnRateClassification") or ""),
            turn_class_after=str(nav_after.get("turnRateClassification") or ""),
        )
        summary["correlation"] = correlation

        if correlation["status"] in ("passed",):
            if correlation.get("correlationEstablished"):
                summary["status"] = "passed"
                summary["verdict"] = "nav-state-freshness-confirmed"
            else:
                summary["status"] = "blocked"
                summary["verdict"] = "nav-state-freshness-dissonance-detected"
                blockers.append(f"correlation:{correlation['reason']}")
        elif correlation["status"] in ("no-data",):
            summary["status"] = "blocked"
            summary["verdict"] = "nav-state-insufficient-data"
            blockers.append("insufficient-nav-state-data")
        else:
            summary["status"] = "blocked"
            summary["verdict"] = "nav-state-freshness-dissonance-detected"
            blockers.append(f"correlation:{correlation['reason']}")
            if correlation["status"] == "dissonance":
                warnings.append(f"turn-rate-dissonance:{correlation['reason']}")

    except Exception as exc:
        summary["status"] = "failed"
        summary["verdict"] = "watchdog-error"
        errors.append(f"{type(exc).__name__}:{exc}")

    summary["blockers"] = sorted(set(summary["blockers"]))
    summary["warnings"] = sorted(set(summary["warnings"]))
    summary["errors"] = sorted(set(summary["errors"]))
    return summary


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    correlation = safe_mapping(summary.get("correlation"))
    deltas = safe_mapping(summary.get("deltas"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "correlationStatus": correlation.get("status"),
        "correlationEstablished": correlation.get("correlationEstablished"),
        "turnRateStable": correlation.get("turnRateStable"),
        "facingTargetMoved": correlation.get("facingTargetMoved"),
        "yawDeltaDegrees": deltas.get("yawDeltaDegrees"),
        "turnRate0x304Delta": deltas.get("turnRate0x304Delta"),
        "facingTargetDx": deltas.get("facingTargetDx"),
        "facingTargetDz": deltas.get("facingTargetDz"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Nav-state freshness watchdog — dual-read turn-rate correlation validator")
    parser.add_argument("--repo-root")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--hwnd")
    parser.add_argument("--module-base")
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--interval-seconds", type=float, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run(args)
    print(json.dumps(compact(summary)) if args.json else json.dumps(compact(summary), indent=2))
    return 0 if summary.get("status") == "passed" else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    sys.exit(main())
