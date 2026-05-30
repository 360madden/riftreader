#!/usr/bin/env python3
"""Run a continuous static-owner route loop: plan -> turn -> forward -> repeat until arrival.

This script loops the calibrated turn-forward pipeline until the destination is
reached or a safety limit is hit.  Each iteration calls the same sub-scripts
that the single-step experiment uses:

  1. static_owner_facing_discovery.py state  -- read current position + yaw
  2. static_owner_turn_aware_route_plan.py   -- plan (bearing delta + 0x304 cross-check)
  3. static_owner_turn_stimulus_capture.py   -- execute turn (if needed)
  4. static_owner_nav_route_step.py          -- execute forward (if aligned)

Calibrated controllers (from sweep data):
  - Turn rate: ~0.177 degrees/ms (average of left & right at 400-800ms)
  - Forward cruising speed: ~6.1 m/s (post-200ms acceleration)
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .static_owner_nav_route_step import base_safety, destination_args, load_json_object, preview, safe_mapping, write_json
except ImportError:  # pragma: no cover - direct script execution path
    from static_owner_nav_route_step import base_safety, destination_args, load_json_object, preview, safe_mapping, write_json  # type: ignore


SCHEMA_VERSION = 1

# Calibrated constants (from sweep data)
TURN_RATE_DEGREES_PER_MS = 0.177        # average of left & right at 400-800ms
FORWARD_SPEED_M_PER_S = 6.1             # cruising speed (post-200ms acceleration)
FORWARD_ACCEL_DISTANCE_M = 1.0          # approx distance during first 200ms acceleration
FORWARD_ACCEL_TIME_MS = 200             # acceleration phase duration

# Safety limits
DEFAULT_MIN_TURN_HOLD_MS = 150
DEFAULT_MAX_TURN_HOLD_MS = 1200
DEFAULT_MIN_FORWARD_HOLD_MS = 400
DEFAULT_MAX_FORWARD_HOLD_MS = 5000
DEFAULT_ALIGNMENT_THRESHOLD_DEGREES = 7.5
DEFAULT_ARRIVAL_RADIUS = 2.0
DEFAULT_MAX_ITERATIONS = 20
DEFAULT_MAX_TOTAL_SECONDS = 300
DEFAULT_MIN_PROGRESS_DISTANCE = 0.35
DEFAULT_WRONG_WAY_TOLERANCE = 1.0
DEFAULT_TURN_SETTLE_SECONDS = 1.0
DEFAULT_FORWARD_SETTLE_SECONDS = 0.75
DEFAULT_SAMPLES = 3
DEFAULT_INTERVAL_SECONDS = 0.1
DEFAULT_WAYPOINT_SEQUENCE_TIMEOUT = 3600


def utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def compact_plan(summary: Mapping[str, Any]) -> dict[str, Any]:
    plan = safe_mapping(summary.get("plan"))
    target = safe_mapping(plan.get("navigationTarget"))
    return {
        "firstAction": plan.get("firstAction"),
        "turnMagnitudeClass": plan.get("turnMagnitudeClass"),
        "suggestedTurnDirection": target.get("suggestedTurnDirection"),
        "signedBearingDeltaDegrees": target.get("signedBearingDeltaDegrees"),
        "absoluteBearingDeltaDegrees": target.get("absoluteBearingDeltaDegrees"),
        "planarDistance": target.get("planarDistance"),
        "withinArrivalRadius": target.get("withinArrivalRadius"),
        "withinAlignmentThreshold": target.get("withinAlignmentThreshold"),
        "executionBlocked": plan.get("executionBlocked"),
        "executionBlockers": plan.get("executionBlockers", []),
        "engineTurnRateClassification": plan.get("engineTurnRateClassification"),
    }


def compute_turn_hold_ms(degrees_delta: float) -> int:
    """Compute turn hold duration from calibrated turn rate."""
    clamped = max(0.5, min(abs(degrees_delta), 180.0))
    hold = int(clamped / TURN_RATE_DEGREES_PER_MS)
    return max(DEFAULT_MIN_TURN_HOLD_MS, min(hold, DEFAULT_MAX_TURN_HOLD_MS))


def compute_forward_hold_ms(planar_distance: float) -> int:
    """Compute forward hold duration from calibrated speed, accounting for acceleration."""
    if planar_distance <= 0:
        return DEFAULT_MIN_FORWARD_HOLD_MS
    # Subtract the distance covered during acceleration
    cruising_distance = planar_distance - FORWARD_ACCEL_DISTANCE_M
    if cruising_distance <= 0:
        return DEFAULT_MIN_FORWARD_HOLD_MS
    cruising_time_s = cruising_distance / FORWARD_SPEED_M_PER_S
    total_ms = FORWARD_ACCEL_TIME_MS + int(cruising_time_s * 1000)
    return max(DEFAULT_MIN_FORWARD_HOLD_MS, min(total_ms, DEFAULT_MAX_FORWARD_HOLD_MS))


def run_child(
    *,
    label: str,
    command: Sequence[str],
    cwd: Path,
    child_dir: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    child_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = child_dir / f"{label}.stdout.txt"
    stderr_path = child_dir / f"{label}.stderr.txt"
    command_path = child_dir / f"{label}.command.json"
    started = time.perf_counter()
    started_utc = utc_iso()
    parsed: Any = None
    parse_error: str | None = None
    try:
        result = subprocess.run(
            list(command),
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
        if stdout.strip():
            try:
                parsed = json.loads(stdout)
            except json.JSONDecodeError as exc:
                parse_error = f"JSONDecodeError:{exc}"
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        exit_code = 124
        parse_error = f"TimeoutExpired:{exc}"

    duration = time.perf_counter() - started
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    envelope = {
        "label": label,
        "command": list(command),
        "cwd": str(cwd),
        "startedAtUtc": started_utc,
        "endedAtUtc": utc_iso(),
        "durationSeconds": duration,
        "exitCode": exit_code,
        "ok": exit_code == 0,
        "stdoutPath": str(stdout_path),
        "stderrPath": str(stderr_path),
        "stdoutPreview": preview(stdout),
        "stderrPreview": preview(stderr),
        "json": parsed,
        "jsonParseError": parse_error,
    }
    write_json(command_path, {key: value for key, value in envelope.items() if key != "json"})
    envelope["commandPath"] = str(command_path)
    return envelope


def full_summary_from_compact(compact: Mapping[str, Any]) -> dict[str, Any]:
    path = compact.get("summaryJson")
    if not path:
        raise ValueError("child-compact-summary-json-missing")
    return load_json_object(str(path))


def state_command(args: argparse.Namespace, root: Path, output_root: Path) -> list[str]:
    command = [
        sys.executable,
        str(root / "scripts" / "static_owner_facing_discovery.py"),
        "state",
        "--repo-root", str(root),
        "--output-root", str(output_root),
        "--current-truth-json", str(args.current_truth_json),
        "--samples", str(DEFAULT_SAMPLES),
        "--interval-seconds", str(DEFAULT_INTERVAL_SECONDS),
        "--expect-stationary",
        "--json",
    ]
    return command


def plan_command(args: argparse.Namespace, root: Path, output_root: Path) -> list[str]:
    command = [
        sys.executable,
        str(root / "scripts" / "static_owner_turn_aware_route_plan.py"),
        "--repo-root", str(root),
        "--output-root", str(output_root),
        "--current-truth-json", str(args.current_truth_json),
        "--alignment-threshold-degrees", str(args.alignment_threshold_degrees),
        "--arrival-radius", str(args.arrival_radius),
        "--allow-candidate-turn-control",
        "--max-route-steps", "1",
        "--samples", str(DEFAULT_SAMPLES),
        "--interval-seconds", str(DEFAULT_INTERVAL_SECONDS),
        "--command-timeout-seconds", "30",
        "--json",
    ]
    if args.nav_state:
        command += ["--nav-state"]
    command += destination_args(args)
    return command


def turn_command(args: argparse.Namespace, root: Path, output_root: Path, direction: str, hold_ms: int) -> list[str]:
    return [
        sys.executable,
        str(root / "scripts" / "static_owner_turn_stimulus_capture.py"),
        "--repo-root", str(root),
        "--output-root", str(output_root),
        "--current-truth-json", str(args.current_truth_json),
        "--direction", direction,
        "--hold-milliseconds", str(hold_ms),
        "--minimum-yaw-delta-degrees", "1.0",
        "--max-planar-drift", "1.0",
        "--samples", str(DEFAULT_SAMPLES),
        "--interval-seconds", str(DEFAULT_INTERVAL_SECONDS),
        "--settle-seconds", str(args.turn_settle_seconds),
        "--input-mode", str(args.input_mode),
        "--title-contains", str(args.title_contains),
        "--focus-delay-milliseconds", "250",
        "--command-timeout-seconds", "30",
        "--turn-approved",
        "--json",
    ]


def readback_freshness_command(args: argparse.Namespace, root: Path, output_root: Path) -> list[str]:
    """Pre-flight static resolver readback freshness gate."""
    return [
        sys.executable,
        str(root / "scripts" / "static_owner_coordinate_chain_readback.py"),
        "--repo-root", str(root),
        "--output-root", str(output_root),
        "--use-current-truth",
        "--current-truth-json", str(args.current_truth_json),
        "--samples", "1",
        "--json",
    ]


def forward_command(args: argparse.Namespace, root: Path, output_root: Path, hold_ms: int) -> list[str]:
    command = [
        sys.executable,
        str(root / "scripts" / "static_owner_nav_route_step.py"),
        "--repo-root", str(root),
        "--output-root", str(output_root),
        "--current-truth-json", str(args.current_truth_json),
        "--alignment-threshold-degrees", str(args.alignment_threshold_degrees),
        "--minimum-progress-distance", str(args.minimum_progress_distance),
        "--wrong-way-tolerance-distance", str(args.wrong_way_tolerance),
        "--samples", str(DEFAULT_SAMPLES),
        "--interval-seconds", str(DEFAULT_INTERVAL_SECONDS),
        "--key", str(args.forward_key),
        "--hold-milliseconds", str(hold_ms),
        "--input-mode", str(args.input_mode),
        "--title-contains", str(args.title_contains),
        "--focus-delay-milliseconds", "250",
        "--settle-seconds", str(args.forward_settle_seconds),
        "--command-timeout-seconds", "60",
        "--movement-approved",
        "--json",
    ]
    command += destination_args(args)
    return command


def validate_args(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    direct_requested = args.destination_x is not None or args.destination_y is not None or args.destination_z is not None
    waypoint_requested = args.destination_waypoint_json is not None or args.destination_waypoint_id is not None
    if direct_requested and waypoint_requested:
        errors.append("destination-waypoint-and-direct-coordinates-mutually-exclusive")
    if waypoint_requested:
        if not args.destination_waypoint_json:
            errors.append("destination-waypoint-json-required")
        if not args.destination_waypoint_id:
            errors.append("destination-waypoint-id-required")
    elif args.destination_x is None or args.destination_z is None:
        errors.append("destination-x-and-z-required")
    if args.arrival_radius < 0:
        errors.append("arrival-radius-must-be-nonnegative")
    if args.alignment_threshold_degrees < 0:
        errors.append("alignment-threshold-degrees-must-be-nonnegative")
    if args.max_iterations < 1:
        errors.append("max-iterations-must-be-positive")
    if args.max_total_seconds < 10:
        errors.append("max-total-seconds-must-be-at-least-10")
    if args.minimum_progress_distance < 0:
        errors.append("minimum-progress-distance-must-be-nonnegative")
    if args.wrong_way_tolerance < 0:
        errors.append("wrong-way-tolerance-must-be-nonnegative")
    if args.turn_settle_seconds < 0 or args.forward_settle_seconds < 0:
        errors.append("settle-seconds-must-be-nonnegative")
    if args.command_timeout_seconds <= 0:
        errors.append("command-timeout-seconds-must-be-positive")
    return sorted(set(errors))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a continuous static-owner route loop to a destination")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--current-truth-json", default="docs/recovery/current-truth.json")
    parser.add_argument("--destination-x", type=float)
    parser.add_argument("--destination-y", type=float)
    parser.add_argument("--destination-z", type=float)
    parser.add_argument("--destination-label")
    parser.add_argument("--destination-waypoint-json")
    parser.add_argument("--destination-waypoint-id")
    parser.add_argument("--arrival-radius", type=float, default=DEFAULT_ARRIVAL_RADIUS)
    parser.add_argument("--alignment-threshold-degrees", type=float, default=DEFAULT_ALIGNMENT_THRESHOLD_DEGREES)
    parser.add_argument("--minimum-progress-distance", type=float, default=DEFAULT_MIN_PROGRESS_DISTANCE)
    parser.add_argument("--wrong-way-tolerance", type=float, default=DEFAULT_WRONG_WAY_TOLERANCE)
    parser.add_argument("--forward-key", default="w")
    parser.add_argument("--input-mode", choices=("ScanCode", "VirtualKey"), default="ScanCode")
    parser.add_argument("--title-contains", default="RIFT")
    parser.add_argument("--turn-settle-seconds", type=float, default=DEFAULT_TURN_SETTLE_SECONDS)
    parser.add_argument("--forward-settle-seconds", type=float, default=DEFAULT_FORWARD_SETTLE_SECONDS)
    parser.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS)
    parser.add_argument("--max-total-seconds", type=float, default=DEFAULT_MAX_TOTAL_SECONDS)
    parser.add_argument("--command-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--turn-approved", action="store_true", help="Required: approve sending turn key input")
    parser.add_argument("--movement-approved", action="store_true", help="Required: approve sending forward movement input")
    parser.add_argument("--allow-candidate-turn-control", action="store_true", help="Required: approve candidate yaw turning")
    parser.add_argument("--waypoint-sequence-json", help="JSON file with waypoint array for multi-waypoint sequencing")
    parser.add_argument("--waypoint-sequence-ids", help="Comma-separated waypoint IDs to visit (omit for all in file)")
    parser.add_argument("--dry-run", action="store_true", help="Read-only: plan only, no input sent")
    parser.add_argument(
        "--skip-readback-freshness-gate",
        action="store_true",
        help="Skip the pre-movement static resolver readback freshness gate (testing escape hatch).",
    )
    parser.add_argument("--nav-state", action="store_true",
        help="Run pointer-chain nav-state readback for per-iteration yaw/turn-rate health monitoring.")
    parser.add_argument("--json", action="store_true")
    return parser


def load_waypoint_sequence(
    root: Path,
    sequence_json: str,
    sequence_ids: str | None = None,
) -> list[dict[str, Any]]:
    """Load waypoints from a JSON file, optionally filtered by comma-separated IDs."""
    path = Path(sequence_json)
    if not path.is_absolute():
        path = root / path
    data = load_json_object(path)
    waypoints = data.get("waypoints")
    if not isinstance(waypoints, list):
        raise ValueError("waypoint-sequence-missing-waypoints-array")
    if not waypoints:
        raise ValueError("waypoint-sequence-empty")
    if sequence_ids is not None:
        id_order = [s.strip() for s in sequence_ids.split(",") if s.strip()]
        if not id_order:
            raise ValueError("waypoint-sequence-ids-empty")
        id_map: dict[str, Any] = {}
        for w in waypoints:
            if isinstance(w, Mapping):
                wid = str(w.get("id", ""))
                if wid:
                    id_map[wid] = w
        missing = [wid for wid in id_order if wid not in id_map]
        if missing:
            raise ValueError(f"waypoint-ids-not-found:{','.join(missing)}")
        waypoints = [id_map[wid] for wid in id_order]
    result: list[dict[str, Any]] = []
    for w in waypoints:
        if not isinstance(w, Mapping):
            raise ValueError("waypoint-item-must-be-object")
        missing_axes = [axis for axis in ("x", "y", "z") if w.get(axis) is None]
        if missing_axes:
            raise ValueError(f"waypoint-missing-coordinate:{','.join(missing_axes)}")
        result.append({
            "id": str(w.get("id", "") or ""),
            "label": str(w.get("label") or w.get("id") or "waypoint"),
            "x": float(w["x"]),
            "y": float(w["y"]),
            "z": float(w["z"]),
            "arrivalRadius": None if w.get("arrivalRadius") is None else float(w["arrivalRadius"]),
        })
    return result


def make_waypoint_args(args: argparse.Namespace, waypoint: Mapping[str, Any], leg_index: int, output_root: Path) -> argparse.Namespace:
    """Create a new args Namespace for a single waypoint leg."""
    d = vars(args).copy()
    d.update({
        "destination_x": float(waypoint["x"]),
        "destination_y": float(waypoint["y"]),
        "destination_z": float(waypoint["z"]),
        "destination_label": str(waypoint.get("label") or waypoint.get("id") or f"waypoint-{leg_index}"),
        "destination_waypoint_json": None,
        "destination_waypoint_id": None,
        "output_root": str(output_root / f"leg-{leg_index:02d}"),
    })
    if waypoint.get("arrivalRadius") is not None:
        d["arrival_radius"] = float(waypoint["arrivalRadius"])
    return argparse.Namespace(**d)


def compact_sequence_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Compact a multi-waypoint sequence summary."""
    total = safe_mapping(summary.get("total"))
    safety = safe_mapping(summary.get("safety"))
    artifacts = safe_mapping(summary.get("artifacts"))
    destination_request = safe_mapping(summary.get("destinationRequest"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "kind": summary.get("kind"),
        "totalLegs": total.get("totalLegs"),
        "legsArrived": total.get("legsArrived"),
        "legsFailed": total.get("legsFailed"),
        "totalDurationSeconds": total.get("totalDurationSeconds"),
        "totalTurnsExecuted": total.get("totalTurnsExecuted"),
        "totalForwardSteps": total.get("totalForwardSteps"),
        "totalProgressDistance": total.get("totalProgressDistance"),
        "movementSent": safety.get("movementSent"),
        "inputSent": safety.get("inputSent"),
        "destinationRequest": destination_request,
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def build_sequence_markdown(summary: Mapping[str, Any]) -> str:
    """Build markdown for a multi-waypoint sequence summary."""
    total = safe_mapping(summary.get("total"))
    safety = safe_mapping(summary.get("safety"))
    legs = summary.get("legs", []) if isinstance(summary.get("legs"), list) else []
    waypoints = summary.get("waypointSequence", [])
    errors = summary.get("errors", [])
    blockers = summary.get("blockers", [])
    warnings = summary.get("warnings", [])

    lines: list[str] = [
        "# Static owner continuous route sequence",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Waypoint sequence",
        "",
        f"Total legs: `{total.get('totalLegs')}`",
        f"Arrived: `{total.get('legsArrived')}`",
        f"Failed: `{total.get('legsFailed')}`",
        "",
        "## Totals",
        "",
        f"- Total time: `{total.get('totalDurationSeconds')}`",
        f"- Total turns: `{total.get('totalTurnsExecuted')}`",
        f"- Total forward steps: `{total.get('totalForwardSteps')}`",
        f"- Total progress: `{total.get('totalProgressDistance')}`",
        "",
        "## Safety",
        "",
        f"- Movement sent: `{safety.get('movementSent')}`",
        f"- Input sent: `{safety.get('inputSent')}`",
        f"- Navigation control: `{safety.get('navigationControl')}`",
        "",
        "## Legs",
        "",
    ]

    for i, leg in enumerate(legs):
        leg_safe = safe_mapping(leg)
        waypoint = waypoints[i] if i < len(waypoints) else {}
        wp_label = waypoint.get("label", f"leg-{i}") if isinstance(waypoint, Mapping) else f"leg-{i}"
        leg_total = safe_mapping(leg_safe.get("total"))
        lines.append(f"### Leg {i + 1}: {wp_label}")
        lines.append(f"- Status: `{leg_safe.get('status')}`")
        lines.append(f"- Verdict: `{leg_safe.get('verdict')}`")
        lines.append(f"- Iterations: `{leg_total.get('iterationCount')}`")
        lines.append(f"- Turns: `{leg_total.get('turnsExecuted')}`")
        lines.append(f"- Forward steps: `{leg_total.get('forwardSteps')}`")
        lines.append("")

    if blockers:
        lines.extend(["## Blockers", ""])
        lines.extend(f"- `{item}`" for item in blockers)
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{item}`" for item in warnings)
    if errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- `{item}`" for item in errors)
    return "\n".join(lines) + "\n"


def run_sequence(args: argparse.Namespace) -> dict[str, Any]:
    """Run a multi-waypoint route sequence, navigating to each waypoint in order.

    Each leg reuses the single-destination run() function with per-waypoint args.
    The sequence advances to the next waypoint upon arrival and stops on any failure.
    """
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-continuous-route-sequence-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    operator = {
        "dryRun": bool(args.dry_run),
        "movementApproved": bool(args.movement_approved),
        "turnApproved": bool(args.turn_approved),
        "allowCandidateTurnControl": bool(args.allow_candidate_turn_control),
        "maxIterations": int(args.max_iterations),
        "maxTotalSeconds": float(args.max_total_seconds),
    }
    safety = base_safety()
    safety["facingPromotion"] = False
    safety["navigationControl"] = False

    # Initialize summary with safe defaults before try block so the except
    # handler can safely access blockers/warnings/errors fields
    sequence_summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-continuous-route-sequence",
        "generatedAtUtc": utc_iso(),
        "status": "pending",
        "verdict": None,
        "repoRoot": str(root),
        "destinationRequest": {
            "waypointSequenceJson": args.waypoint_sequence_json,
            "waypointSequenceIds": args.waypoint_sequence_ids,
            "arrivalRadius": float(args.arrival_radius),
            "alignmentThresholdDegrees": float(args.alignment_threshold_degrees),
        },
        "operator": operator,
        "waypointSequence": [],
        "legs": [],
        "total": {
            "totalLegs": 0,
            "legsArrived": 0,
            "legsFailed": 0,
            "totalDurationSeconds": 0.0,
            "totalTurnsExecuted": 0,
            "totalForwardSteps": 0,
            "totalProgressDistance": 0.0,
        },
        "blockers": [],
        "warnings": [],
        "errors": [],
        "safety": safety,
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
    }

    started = time.perf_counter()
    try:
        waypoints = load_waypoint_sequence(root, args.waypoint_sequence_json, args.waypoint_sequence_ids)
        sequence_summary["waypointSequence"] = waypoints
        sequence_summary["total"]["totalLegs"] = len(waypoints)

        for i, waypoint in enumerate(waypoints):
            leg_args = make_waypoint_args(args, waypoint, i + 1, run_dir)
            leg_result = run(leg_args)
            sequence_summary["legs"].append(leg_result)

            if leg_result.get("status") == "passed":
                sequence_summary["total"]["legsArrived"] += 1
            else:
                sequence_summary["total"]["legsFailed"] += 1
                if leg_result.get("blockers"):
                    sequence_summary["blockers"].extend(
                        f"leg-{i + 1}-{blocker}" for blocker in leg_result.get("blockers", [])
                    )
                if leg_result.get("warnings"):
                    sequence_summary["warnings"].extend(
                        f"leg-{i + 1}-{w}" for w in leg_result.get("warnings", [])
                    )
                if leg_result.get("errors"):
                    sequence_summary["errors"].extend(
                        f"leg-{i + 1}-{err}" for err in leg_result.get("errors", [])
                    )
                # Stop on first failure — don't attempt remaining waypoints
                break

            # Check sequence-level timeout between legs
            elapsed = time.perf_counter() - started
            if elapsed > DEFAULT_WAYPOINT_SEQUENCE_TIMEOUT:
                sequence_summary["blockers"].append(f"sequence-timeout-after-leg-{i + 1}")
                break

        # Aggregate totals
        legs_arrived = sequence_summary["total"]["legsArrived"]
        sequence_summary["total"]["totalDurationSeconds"] = time.perf_counter() - started
        for leg in sequence_summary["legs"]:
            leg_safe = safe_mapping(leg)
            leg_total = safe_mapping(leg_safe.get("total"))
            sequence_summary["total"]["totalTurnsExecuted"] += int(leg_total.get("turnsExecuted") or 0)
            sequence_summary["total"]["totalForwardSteps"] += int(leg_total.get("forwardSteps") or 0)
            sequence_summary["total"]["totalProgressDistance"] += float(leg_total.get("totalProgressDistance") or 0)
            leg_safety = safe_mapping(leg_safe.get("safety"))
            if leg_safety.get("movementSent"):
                safety["movementSent"] = True
            if leg_safety.get("inputSent"):
                safety["inputSent"] = True
            if leg_safety.get("navigationControl"):
                safety["navigationControl"] = True

        # Determine final status
        total_legs = len(waypoints)
        if legs_arrived == total_legs:
            sequence_summary["status"] = "passed"
            sequence_summary["verdict"] = "sequence-all-waypoints-reached"
        elif sequence_summary.get("blockers"):
            sequence_summary["status"] = "blocked"
            sequence_summary["verdict"] = "sequence-blocked"
        else:
            sequence_summary["status"] = "blocked"
            sequence_summary["verdict"] = "sequence-incomplete"
            sequence_summary["blockers"].append(
                f"sequence-incomplete-{legs_arrived}-of-{total_legs}-waypoints-reached"
            )

    except Exception as exc:  # noqa: BLE001
        sequence_summary["status"] = "failed"
        sequence_summary["verdict"] = "sequence-error"
        sequence_summary["errors"].append(f"{type(exc).__name__}:{exc}")

    sequence_summary["blockers"] = sorted(set(sequence_summary["blockers"]))
    sequence_summary["warnings"] = sorted(set(sequence_summary["warnings"]))
    sequence_summary["errors"] = sorted(set(sequence_summary["errors"]))
    return sequence_summary


def build_markdown(summary: Mapping[str, Any]) -> str:
    total = safe_mapping(summary.get("total"))
    iterations_list = summary.get("iterations", [])
    artifacts = safe_mapping(summary.get("artifacts"))
    safety = safe_mapping(summary.get("safety"))
    lines = [
        "# Static owner continuous route run",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        f"Iterations: `{total.get('iterationCount')}`",
        "",
        "## Total",
        "",
        f"- Iterations: `{total.get('iterationCount')}`",
        f"- Total time: `{total.get('totalDurationSeconds')}`",
        f"- Initial distance: `{total.get('initialPlanarDistance')}`",
        f"- Final distance: `{total.get('finalPlanarDistance')}`",
        f"- Total progress: `{total.get('totalProgressDistance')}`",
        f"- Turns executed: `{total.get('turnsExecuted')}`",
        f"- Forward steps: `{total.get('forwardSteps')}`",
        "",
        "## Safety",
        "",
        f"- Movement sent: `{safety.get('movementSent')}`",
        f"- Input sent: `{safety.get('inputSent')}`",
        f"- Navigation control: `{safety.get('navigationControl')}`",
        f"- Facing promotion: `{safety.get('facingPromotion')}`",
        "",
        "## Iterations",
        "",
    ]
    for it in iterations_list:
        it_map = safe_mapping(it)
        plan = safe_mapping(it_map.get("plan"))
        turn = safe_mapping(it_map.get("turnResult"))
        forward = safe_mapping(it_map.get("forwardResult"))
        lines.append(f"### Iteration {it_map.get('iteration')}")
        lines.append(f"- Distance: `{it_map.get('planarDistance')}`")
        lines.append(f"- Turn: `{it_map.get('turnDirection')}` ({it_map.get('computedTurnHoldMs')}ms)")
        lines.append(f"- Turn result: `{turn.get('status')}`")
        lines.append(f"- Forward result: `{forward.get('status')}`")
        sub_class = forward.get("noProgressSubClassification")
        if sub_class:
            lines.append(f"- No-progress reason: `{sub_class}`")
        lines.append("")

    if summary.get("blockers"):
        lines.extend(["## Blockers", ""])
        lines.extend(f"- `{item}`" for item in summary.get("blockers", []))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{item}`" for item in summary.get("warnings", []))
    if summary.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- `{item}`" for item in summary.get("errors", []))
    return "\n".join(lines) + "\n"


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    total = safe_mapping(summary.get("total"))
    artifacts = safe_mapping(summary.get("artifacts"))
    safety = safe_mapping(summary.get("safety"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "iterationCount": total.get("iterationCount"),
        "totalDurationSeconds": total.get("totalDurationSeconds"),
        "initialPlanarDistance": total.get("initialPlanarDistance"),
        "finalPlanarDistance": total.get("finalPlanarDistance"),
        "totalProgressDistance": total.get("totalProgressDistance"),
        "turnsExecuted": total.get("turnsExecuted"),
        "forwardSteps": total.get("forwardSteps"),
        "movementSent": safety.get("movementSent"),
        "inputSent": safety.get("inputSent"),
        "navigationControl": safety.get("navigationControl"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-continuous-route-{utc_stamp()}"
    child_dir = run_dir / "child-outputs"
    child_output_root = run_dir / "child-runs"
    run_dir.mkdir(parents=True, exist_ok=True)

    errors = validate_args(args)
    operator = {
        "dryRun": bool(args.dry_run),
        "movementApproved": bool(args.movement_approved),
        "turnApproved": bool(args.turn_approved),
        "allowCandidateTurnControl": bool(args.allow_candidate_turn_control),
        "maxIterations": int(args.max_iterations),
        "maxTotalSeconds": float(args.max_total_seconds),
    }
    safety = base_safety()
    safety["facingPromotion"] = False
    safety["navigationControl"] = False

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-continuous-route",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "pending",
        "verdict": "invalid-arguments" if errors else None,
        "repoRoot": str(root),
        "destinationRequest": {
            "destinationX": args.destination_x,
            "destinationZ": args.destination_z,
            "destinationY": args.destination_y,
            "destinationLabel": args.destination_label,
            "arrivalRadius": float(args.arrival_radius),
            "alignmentThresholdDegrees": float(args.alignment_threshold_degrees),
        },
        "operator": operator,
        "total": {
            "iterationCount": 0,
            "totalDurationSeconds": 0.0,
            "initialPlanarDistance": None,
            "finalPlanarDistance": None,
            "totalProgressDistance": None,
            "turnsExecuted": 0,
            "forwardSteps": 0,
        },
        "iterations": [],
        "blockers": [],
        "warnings": [],
        "errors": errors,
        "safety": safety,
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
    }
    if errors:
        return summary

    if not args.turn_approved:
        summary["status"] = "blocked"
        summary["verdict"] = "turn-approval-required"
        summary["blockers"].append("turn-approved-flag-required")
        return summary

    if not args.movement_approved:
        summary["status"] = "blocked"
        summary["verdict"] = "movement-approval-required"
        summary["blockers"].append("movement-approved-flag-required")
        return summary

    if not args.allow_candidate_turn_control:
        summary["status"] = "blocked"
        summary["verdict"] = "candidate-turn-control-approval-required"
        summary["blockers"].append("allow-candidate-turn-control-flag-required")
        return summary

    # --- Pre-flight static resolver readback freshness gate ---
    if not args.skip_readback_freshness_gate:
        readback_child = run_child(
            label="00-readback-freshness",
            command=readback_freshness_command(args, root, child_output_root),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=float(args.command_timeout_seconds),
        )
        summary["childCommands"] = summary.get("childCommands", []) + [readback_child]

        if not isinstance(readback_child.get("json"), Mapping):
            summary["status"] = "failed"
            summary["verdict"] = "static-resolver-readback-freshness-failed"
            summary["blockers"].append("static-resolver-readback-freshness-gate-no-json")
            summary["errors"].append("readback-freshness-gate-json-parse-failed")
            return summary

        readback_compact = safe_mapping(readback_child["json"])
        readback_status = str(readback_compact.get("status") or "")
        if readback_status != "passed":
            if readback_status == "blocked":
                summary["status"] = "blocked"
                summary["verdict"] = "static-resolver-readback-freshness-blocked"
            else:
                summary["status"] = "failed"
                summary["verdict"] = "static-resolver-readback-freshness-failed"
            summary["blockers"].append(f"static-resolver-readback-freshness-gate:{readback_status}")
            summary["warnings"].append(
                f"Static resolver readback pre-flight returned status={readback_status}. "
                "Re-run readback or validate resolver health before attempting movement."
            )
            return summary

    started = time.perf_counter()
    try:
        # --- Initial state read ---
        initial_state = run_child(
            label="00-initial-state",
            command=state_command(args, root, child_output_root),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=float(args.command_timeout_seconds),
        )
        summary["childCommands"] = summary.get("childCommands", []) + [initial_state]
        if not initial_state["ok"] or not isinstance(initial_state.get("json"), Mapping):
            summary["status"] = "failed"
            summary["verdict"] = "initial-state-readback-failed"
            summary["errors"].append("initial-state-readback-failed")
            return summary
        initial_full = full_summary_from_compact(initial_state["json"])
        initial_state_data = safe_mapping(initial_full.get("latestState"))
        initial_coord = safe_mapping(initial_state_data.get("coordinate"))
        if not initial_coord:
            summary["status"] = "failed"
            summary["verdict"] = "initial-state-missing-coordinate"
            summary["errors"].append("initial-state-missing-coordinate")
            return summary

        # --- Initial plan ---
        plan_child = run_child(
            label="00-initial-plan",
            command=plan_command(args, root, child_output_root),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=float(args.command_timeout_seconds),
        )
        summary["childCommands"].append(plan_child)
        if not isinstance(plan_child.get("json"), Mapping):
            summary["status"] = "failed"
            summary["verdict"] = "initial-plan-failed"
            summary["errors"].append("initial-plan-failed")
            return summary
        plan_full = full_summary_from_compact(plan_child["json"])
        plan_detail = compact_plan(plan_full)
        initial_distance = plan_detail.get("planarDistance")
        summary["total"]["initialPlanarDistance"] = initial_distance
        summary["total"]["finalPlanarDistance"] = initial_distance

        if plan_detail.get("withinArrivalRadius") is True:
            summary["status"] = "passed"
            summary["verdict"] = "already-arrived"
            summary["warnings"].append("destination-already-within-arrival-radius")
            return summary

        if args.dry_run:
            summary["status"] = "passed"
            summary["verdict"] = "dry-run-plan-built"
            summary["warnings"].append("dry-run-only-no-input-sent")
            return summary

        # --- Loop ---
        iteration = 0
        arrived = False
        prev_distance = initial_distance
        current_distance = initial_distance
        total_turns = 0
        total_forwards = 0
        total_progress = 0.0
        consecutive_no_progress = 0

        while iteration < args.max_iterations:
            elapsed = time.perf_counter() - started
            if elapsed > args.max_total_seconds:
                summary["blockers"].append(f"max-total-seconds-reached:{args.max_total_seconds}")
                break

            iteration += 1

            # Plan current step
            plan_child = run_child(
                label=f"plan-{iteration:03d}",
                command=plan_command(args, root, child_output_root),
                cwd=root,
                child_dir=child_dir,
                timeout_seconds=float(args.command_timeout_seconds),
            )
            summary["childCommands"].append(plan_child)

            if not isinstance(plan_child.get("json"), Mapping):
                summary["warnings"].append(f"plan-failed-at-iteration-{iteration}")
                summary["total"]["finalPlanarDistance"] = current_distance
                summary["iterations"].append(iteration_record)
                break

            plan_full = full_summary_from_compact(plan_child["json"])
            plan_detail = compact_plan(plan_full)
            current_distance = plan_detail.get("planarDistance") or 0

            iteration_record = {
                "iteration": iteration,
                "planarDistance": current_distance,
                "plan": plan_detail,
                "turnDirection": None,
                "computedTurnHoldMs": None,
                "turnResult": {"status": "not-needed"},
                "forwardResult": {"status": "not-needed"},
                "childCommands": [],
            }

            # Arrived?
            if plan_detail.get("withinArrivalRadius") is True:
                arrived = True
                summary["iterations"].append(iteration_record)
                break

            # Turn if needed
            suggested_turn = str(plan_detail.get("suggestedTurnDirection") or "")
            bearing_delta = float(plan_detail.get("absoluteBearingDeltaDegrees") or 0)

            if plan_detail.get("executionBlocked") is True:
                summary["status"] = "blocked"
                summary["verdict"] = "route-loop-plan-execution-blocked"
                summary["blockers"].extend(plan_detail.get("executionBlockers", []))
                summary["iterations"].append(iteration_record)
                break

            if suggested_turn in {"left", "right"}:
                turn_ms = compute_turn_hold_ms(bearing_delta)
                iteration_record["turnDirection"] = suggested_turn
                iteration_record["computedTurnHoldMs"] = turn_ms

                turn_child = run_child(
                    label=f"turn-{iteration:03d}-{suggested_turn}",
                    command=turn_command(args, root, child_output_root, suggested_turn, turn_ms),
                    cwd=root,
                    child_dir=child_dir,
                    timeout_seconds=float(args.command_timeout_seconds),
                )
                summary["childCommands"].append(turn_child)
                iteration_record["childCommands"].append(turn_child)
                safety["inputSent"] = True

                if not isinstance(turn_child.get("json"), Mapping):
                    iteration_record["turnResult"] = {"status": "failed", "reason": "turn-json-missing"}
                    summary["warnings"].append(f"turn-json-missing-at-iteration-{iteration}")
                    # Continue anyway — yaw may have changed
                else:
                    turn_full = full_summary_from_compact(turn_child["json"])
                    turn_ok = turn_full.get("status") == "passed"
                    iteration_record["turnResult"] = {"status": "passed" if turn_ok else "blocked"}
                    total_turns += 1
                    if turn_ok:
                        safety["movementSent"] = True
                        safety["navigationControl"] = True
                        # Update yaw info from turn result for diagnostics
                        turn_sample = safe_mapping(turn_full.get("turnSamples") or [None]) if isinstance(turn_full.get("turnSamples"), list) else {}
                        if turn_sample:
                            iteration_record["postTurnYaw"] = turn_sample.get("postYawDegrees")
                            iteration_record["turnYawDelta"] = turn_sample.get("absoluteYawDeltaDegrees")

                # Re-plan after turn (bearing will have changed)
                re_plan = run_child(
                    label=f"replan-{iteration:03d}",
                    command=plan_command(args, root, child_output_root),
                    cwd=root,
                    child_dir=child_dir,
                    timeout_seconds=float(args.command_timeout_seconds),
                )
                summary["childCommands"].append(re_plan)
                if isinstance(re_plan.get("json"), Mapping):
                    replan_full = full_summary_from_compact(re_plan["json"])
                    replan_detail = compact_plan(replan_full)
                    suggested_turn = str(replan_detail.get("suggestedTurnDirection") or "")
                    current_distance = replan_detail.get("planarDistance") or 0
                    iteration_record["planarDistance"] = current_distance
                    if replan_detail.get("withinArrivalRadius") is True:
                        arrived = True
                        summary["iterations"].append(iteration_record)
                        break

            # Forward only if aligned
            if suggested_turn == "aligned":
                forward_ms = compute_forward_hold_ms(current_distance)
                iteration_record["computedForwardHoldMs"] = forward_ms

                forward_child = run_child(
                    label=f"forward-{iteration:03d}",
                    command=forward_command(args, root, child_output_root, forward_ms),
                    cwd=root,
                    child_dir=child_dir,
                    timeout_seconds=float(args.command_timeout_seconds),
                )
                summary["childCommands"].append(forward_child)
                iteration_record["childCommands"].append(forward_child)
                safety["inputSent"] = True

                if not isinstance(forward_child.get("json"), Mapping):
                    iteration_record["forwardResult"] = {"status": "failed", "reason": "forward-json-missing"}
                    summary["warnings"].append(f"forward-json-missing-at-iteration-{iteration}")
                else:
                    forward_full = full_summary_from_compact(forward_child["json"])
                    route_result = safe_mapping(forward_full.get("routeResult"))
                    route_status = route_result.get("routeStatus")
                    forward_ok = forward_full.get("status") == "passed" and route_status in {"progress", "arrived"}
                    iteration_record["forwardResult"] = {
                        "status": "passed" if forward_ok else "blocked",
                        "routeStatus": route_status,
                        "totalProgressDistance": route_result.get("totalProgressDistance"),
                        "initialPlanarDistance": route_result.get("initialPlanarDistance"),
                        "finalPlanarDistance": route_result.get("finalPlanarDistance"),
                        "noProgressSubClassification": route_result.get("noProgressSubClassification"),
                    }
                    if forward_ok:
                        safety["movementSent"] = True
                        safety["navigationControl"] = True
                        total_forwards += 1
                        total_route_progress = float(route_result.get("totalProgressDistance") or 0)
                        total_progress += total_route_progress
                        consecutive_no_progress = 0
                        current_distance = float(route_result.get("finalPlanarDistance") or current_distance)
                        iteration_record["planarDistance"] = current_distance

                        if route_status == "arrived":
                            arrived = True
                            summary["iterations"].append(iteration_record)
                            break

                        # Check if we're making progress
                        if total_route_progress < args.minimum_progress_distance:
                            summary["blockers"].append("insufficient-progress-after-forward")
                            summary["iterations"].append(iteration_record)
                            arrived = False
                            break
                        prev_distance = current_distance
                    else:
                        # Forward no-progress — track consecutive failures
                        # Terrain sub-classification differentiates stuck from slight movement
                        no_progress_sub = route_result.get("noProgressSubClassification")
                        consecutive_no_progress += 1
                        if consecutive_no_progress >= 3:
                            if no_progress_sub == "blocked-stationary-no-movement":
                                summary["blockers"].append("forward-no-progress-3-consecutive-blocked-stationary-terrain")
                            else:
                                summary["blockers"].append("forward-no-progress-3-consecutive-stuck")
                            summary["iterations"].append(iteration_record)
                            break

            summary["total"]["finalPlanarDistance"] = current_distance
            summary["iterations"].append(iteration_record)

        # End of loop — set totals here so they're correct regardless of which break fired
        summary["total"]["iterationCount"] = iteration
        summary["total"]["turnsExecuted"] = total_turns
        summary["total"]["forwardSteps"] = total_forwards
        summary["total"]["totalDurationSeconds"] = time.perf_counter() - started
        summary["total"]["totalProgressDistance"] = total_progress
        summary["total"]["finalPlanarDistance"] = current_distance if not arrived else None
        if arrived:
            summary["status"] = "passed"
            summary["verdict"] = "route-loop-arrived"
        elif summary.get("status") in ("pending", None):
            if summary.get("iterations"):
                last_it = safe_mapping(summary["iterations"][-1]) if summary["iterations"] else {}
                last_dist = last_it.get("planarDistance") or 0
                if last_dist <= args.arrival_radius:
                    summary["status"] = "passed"
                    summary["verdict"] = "route-loop-arrived"
                elif summary.get("blockers"):
                    summary["status"] = "blocked"
                    summary["verdict"] = "route-loop-blocked"
                else:
                    summary["status"] = "blocked"
                    summary["verdict"] = "route-loop-max-iterations-reached"
                    summary["blockers"].append(f"max-iterations-reached:{args.max_iterations}")
            else:
                summary["status"] = "blocked"
                summary["verdict"] = "route-loop-no-iterations"

    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "route-loop-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")

    summary["blockers"] = sorted(set(summary["blockers"]))
    summary["warnings"] = sorted(set(summary["warnings"]))
    summary["errors"] = sorted(set(summary["errors"]))
    return summary


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.waypoint_sequence_json:
        summary = run_sequence(args)
        artifacts = safe_mapping(summary.get("artifacts"))
        write_json(Path(str(artifacts["summaryJson"])), summary)
        Path(str(artifacts["summaryMarkdown"])).write_text(build_sequence_markdown(summary), encoding="utf-8")
        print(json.dumps(compact_sequence_summary(summary)) if args.json else json.dumps(compact_sequence_summary(summary), indent=2))
    else:
        summary = run(args)
        artifacts = safe_mapping(summary.get("artifacts"))
        write_json(Path(str(artifacts["summaryJson"])), summary)
        Path(str(artifacts["summaryMarkdown"])).write_text(build_markdown(summary), encoding="utf-8")
        print(json.dumps(compact(summary)) if args.json else json.dumps(compact(summary), indent=2))
    return 0 if summary.get("status") == "passed" else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    sys.exit(main())
