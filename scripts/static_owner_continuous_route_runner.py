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
    from .static_owner_nav_route_step import (
        DEFAULT_CLEAR_UI_FOCUS_HOLD_MS,
        DEFAULT_CLEAR_UI_FOCUS_KEY,
        base_safety,
        clear_ui_focus_command,
        destination_args,
        load_json_object,
        preview,
        safe_mapping,
        write_json,
    )
    from .workflow_common import (
        full_summary_from_compact,
        repo_root,
        run_child,
        utc_iso,
        utc_stamp,
    )
except ImportError:  # pragma: no cover - direct script execution path
    from static_owner_nav_route_step import (  # type: ignore
        DEFAULT_CLEAR_UI_FOCUS_HOLD_MS,
        DEFAULT_CLEAR_UI_FOCUS_KEY,
        base_safety,
        clear_ui_focus_command,
        destination_args,
        load_json_object,
        preview,
        safe_mapping,
        write_json,
    )
    from workflow_common import (  # type: ignore
        full_summary_from_compact,
        repo_root,
        run_child,
        utc_iso,
        utc_stamp,
    )

SCHEMA_VERSION = 1

# Calibrated constants (from sweep data)
FORWARD_SPEED_M_PER_S = 6.1             # cruising speed (post-200ms acceleration)
FORWARD_ACCEL_DISTANCE_M = 1.0          # approx distance during first 200ms acceleration
FORWARD_ACCEL_TIME_MS = 200             # acceleration phase duration

# Safety limits
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

NO_PROGRESS_RECOVERY_PRIORITY = [
    "blocked-stationary-no-movement",
    "drifted-back-after-initial-progress",
    "insufficient-progress-below-threshold",
    "minimum-progress-not-met",
    "unspecified",
]

NO_PROGRESS_RECOVERY_ACTIONS = {
    "blocked-stationary-no-movement": {
        "recommendedAction": "plan-lateral-strafe-recovery-before-forward-rerun",
        "why": "The forward pulse produced no positional change; rule out chat/UI focus before treating it as terrain or obstacle blockage.",
    },
    "drifted-back-after-initial-progress": {
        "recommendedAction": "plan-opposite-strafe-recovery-before-forward-rerun",
        "why": "The character initially made progress and then lost it, which suggests terrain redirected or slid the character back.",
    },
    "insufficient-progress-below-threshold": {
        "recommendedAction": "replan-and-use-short-lateral-recovery-if-repeated",
        "why": "The character moved, but not enough to satisfy the route progress threshold.",
    },
    "minimum-progress-not-met": {
        "recommendedAction": "refresh-readback-and-replan-before-forward-rerun",
        "why": "The route step did not meet the minimum progress threshold without a more specific terrain classification.",
    },
    "unspecified": {
        "recommendedAction": "inspect-route-step-summary-before-forward-rerun",
        "why": "A no-progress route step lacked a sub-classification.",
    },
}



def compact_plan(summary: Mapping[str, Any]) -> dict[str, Any]:
    plan = safe_mapping(summary.get("plan"))
    target = safe_mapping(plan.get("navigationTarget"))
    source_state = safe_mapping(summary.get("sourceStateSummary"))
    # Extract current yaw from the plan source state if available (for target-bearing computation)
    current_yaw = None
    if isinstance(summary.get("latestState"), Mapping):
        current_yaw = summary["latestState"].get("yawDegrees")  # type: ignore
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
        "currentYawDegrees": current_yaw,
    }


def build_terrain_summary(iterations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    step_count = 0
    for item in iterations:
        forward = safe_mapping(item.get("forwardResult"))
        if forward.get("routeStatus") != "no-progress":
            continue
        step_count += 1
        sub_classification = str(forward.get("noProgressSubClassification") or "unspecified")
        counts[sub_classification] = counts.get(sub_classification, 0) + 1

    primary = None
    for candidate in NO_PROGRESS_RECOVERY_PRIORITY:
        if counts.get(candidate):
            primary = candidate
            break
    if primary is None and counts:
        primary = sorted(counts)[0]

    return {
        "noProgressStepCount": step_count,
        "terrainSubClassifications": counts,
        "primarySubClassification": primary,
        "terrainBlockerPresent": step_count > 0,
    }


def build_recovery_plan(terrain: Mapping[str, Any]) -> dict[str, Any]:
    primary = terrain.get("primarySubClassification")
    if not primary:
        return {
            "status": "not-needed",
            "advisoryOnly": True,
            "movementPermission": False,
            "inputSent": False,
            "recommendedAction": "none",
            "requiredGatesBeforeExecution": [],
            "candidateSequence": [],
        }

    action = NO_PROGRESS_RECOVERY_ACTIONS.get(str(primary), NO_PROGRESS_RECOVERY_ACTIONS["unspecified"])
    return {
        "status": "recommended",
        "reason": primary,
        "advisoryOnly": True,
        "movementPermission": False,
        "inputSent": False,
        "recommendedAction": action["recommendedAction"],
        "why": action["why"],
        "recoveryHelper": {
            "status": "candidate-only-advisory",
            "script": "scripts/static_owner_mouse_arc_recovery_probe.py",
            "commandTemplate": [
                "python",
                "scripts/static_owner_mouse_arc_recovery_probe.py",
                "--destination-x",
                "<destination-x>",
                "--destination-z",
                "<destination-z>",
                "--arc-approved",
                "--movement-approved",
                "--json",
            ],
            "notes": [
                "Use only after visual chat/UI focus is ruled out.",
                "Add --clear-ui-focus-before-input only when chat/menu focus is visually confirmed.",
                "Candidate-only recovery; it does not promote pointer truth.",
            ],
        },
        "requiredGatesBeforeExecution": [
            "explicit-current-session-movement-approval",
            "fresh-exact-target-static-readback",
            "same-pid-hwnd-process-start-module-base",
            "visual-chat-ui-focus-ruled-out",
            "no-debugger-or-cheat-engine",
        ],
        "candidateSequence": [
            "fresh-static-owner-nav-state-readback",
            "bounded-operator-approved-lateral-strafe-probe",
            "fresh-readback-and-turn-aware-replan",
            "try-opposite-lateral-strafe-if-still-stationary",
            "forward-rerun-only-after-replan-passes",
        ],
    }


def compute_turn_hold_ms(degrees_delta: float) -> int:
    """Compute turn hold duration from calibrated turn rate (legacy; used in tests).

    The route loop now uses the pulse-loop turn_completion_detector.py
    instead of fire-and-forget calibrated holds, but this function is
    retained for calibration-test validation.
    """
    TURN_RATE_DEGREES_PER_MS = 0.177
    DEFAULT_MIN_TURN_HOLD_MS = 150
    DEFAULT_MAX_TURN_HOLD_MS = 1200
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


def turn_completion_command(
    args: argparse.Namespace,
    root: Path,
    output_root: Path,
    direction: str,
    signed_bearing_delta_degrees: float,
) -> list[str]:
    """Build a turn-completion-detector subprocess command for pulse-loop convergence verification."""
    return [
        sys.executable,
        str(root / "scripts" / "turn_completion_detector.py"),
        "--repo-root", str(root),
        "--output-root", str(output_root),
        "--current-truth-json", str(args.current_truth_json),
        "--direction", direction,
        "--signed-bearing-delta-degrees", str(signed_bearing_delta_degrees),
        "--alignment-threshold-degrees", str(args.alignment_threshold_degrees),
        "--settle-ms", str(int(float(args.turn_settle_seconds) * 1000)),
        "--turn-backend", str(args.turn_backend),
        "--input-mode", str(args.input_mode),
        "--mouse-pixels-per-pulse", str(args.mouse_pixels_per_pulse),
        "--mouse-steps", str(args.mouse_steps),
        "--mouse-hold-ms", str(args.mouse_hold_ms),
        "--title-contains", str(args.title_contains),
        "--command-timeout-seconds", "60",
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
    if args.mouse_pixels_per_pulse <= 0:
        errors.append("mouse-pixels-per-pulse-must-be-positive")
    if args.mouse_steps < 1:
        errors.append("mouse-steps-must-be-positive")
    if args.mouse_hold_ms <= 0:
        errors.append("mouse-hold-ms-must-be-positive")
    if bool(getattr(args, "clear_ui_focus_before_input", False)):
        if int(getattr(args, "clear_ui_focus_hold_milliseconds", DEFAULT_CLEAR_UI_FOCUS_HOLD_MS)) <= 0:
            errors.append("clear-ui-focus-hold-milliseconds-must-be-positive")
        if not str(getattr(args, "clear_ui_focus_key", DEFAULT_CLEAR_UI_FOCUS_KEY) or "").strip():
            errors.append("clear-ui-focus-key-required")
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
    parser.add_argument("--turn-backend", choices=("key", "mouse-look"), default="key")
    parser.add_argument("--input-mode", choices=("ScanCode", "VirtualKey"), default="ScanCode")
    parser.add_argument("--mouse-pixels-per-pulse", type=int, default=40)
    parser.add_argument("--mouse-steps", type=int, default=8)
    parser.add_argument("--mouse-hold-ms", type=int, default=250)
    parser.add_argument("--title-contains", default="RIFT")
    parser.add_argument("--focus-delay-milliseconds", type=int, default=250)
    parser.add_argument(
        "--clear-ui-focus-before-input",
        action="store_true",
        help=(
            "Opt-in exact-target Escape once before the route loop to clear confirmed chat/menu focus. "
            "Not idempotent; do not enable unless UI focus is visually confirmed."
        ),
    )
    parser.add_argument("--clear-ui-focus-key", default=DEFAULT_CLEAR_UI_FOCUS_KEY)
    parser.add_argument("--clear-ui-focus-hold-milliseconds", type=int, default=DEFAULT_CLEAR_UI_FOCUS_HOLD_MS)
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
        arrival_radius_value = w.get("arrivalRadius")
        if "arrivalRadius" not in w and w.get("radius") is not None:
            arrival_radius_value = w.get("radius")
        result.append({
            "id": str(w.get("id", "") or ""),
            "label": str(w.get("label") or w.get("id") or "waypoint"),
            "x": float(w["x"]),
            "y": float(w["y"]),
            "z": float(w["z"]),
            "arrivalRadius": None if arrival_radius_value is None else float(arrival_radius_value),
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
        "legsPlanned": total.get("legsPlanned", 0),
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
        f"Planned: `{total.get('legsPlanned', 0)}`",
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
        "turnBackend": str(args.turn_backend),
        "mousePixelsPerPulse": int(args.mouse_pixels_per_pulse),
        "mouseSteps": int(args.mouse_steps),
        "mouseHoldMs": int(args.mouse_hold_ms),
        "clearUiFocusBeforeInput": bool(getattr(args, "clear_ui_focus_before_input", False)),
        "clearUiFocusKey": str(getattr(args, "clear_ui_focus_key", DEFAULT_CLEAR_UI_FOCUS_KEY)),
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
            "legsPlanned": 0,
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
                leg_verdict = str(leg_result.get("verdict") or "")
                if args.dry_run and leg_verdict == "dry-run-plan-built":
                    sequence_summary["total"]["legsPlanned"] += 1
                    sequence_summary["warnings"].append(
                        f"sequence-dry-run-stopped-after-leg-{i + 1}-plan-no-simulated-movement"
                    )
                    break
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
        legs_planned = int(sequence_summary["total"].get("legsPlanned") or 0)
        if legs_arrived == total_legs:
            sequence_summary["status"] = "passed"
            sequence_summary["verdict"] = "sequence-all-waypoints-reached"
        elif args.dry_run and legs_planned > 0:
            sequence_summary["status"] = "passed"
            sequence_summary["verdict"] = "sequence-dry-run-plan-built"
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
    terrain = safe_mapping(summary.get("terrain"))
    recovery = safe_mapping(summary.get("recoveryPlan"))
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

    if terrain.get("noProgressStepCount"):
        lines.extend(["## Terrain / drift classification", ""])
        lines.append(f"- No-progress steps: `{terrain.get('noProgressStepCount')}`")
        lines.append(f"- Primary classification: `{terrain.get('primarySubClassification')}`")
        sub_counts = safe_mapping(terrain.get("terrainSubClassifications"))
        for name, count in sorted(sub_counts.items()):
            lines.append(f"- `{name}`: `{count}`")
        lines.extend(["", "## Recovery plan", ""])
        lines.append(f"- Status: `{recovery.get('status')}`")
        lines.append(f"- Advisory only: `{recovery.get('advisoryOnly')}`")
        lines.append(f"- Movement permission from plan: `{recovery.get('movementPermission')}`")
        lines.append(f"- Recommended action: `{recovery.get('recommendedAction')}`")
        if recovery.get("why"):
            lines.append(f"- Why: {recovery.get('why')}")
        if recovery.get("candidateSequence"):
            lines.append("- Candidate sequence:")
            lines.extend(f"  - `{item}`" for item in recovery.get("candidateSequence", []))
        helper = safe_mapping(recovery.get("recoveryHelper"))
        if helper:
            lines.append("- Recovery helper:")
            lines.append(f"  - Status: `{helper.get('status')}`")
            if helper.get("script"):
                lines.append(f"  - Script: `{helper.get('script')}`")
            command_template = helper.get("commandTemplate")
            if isinstance(command_template, list) and command_template:
                lines.append(f"  - Command template: `{' '.join(str(item) for item in command_template)}`")
            notes = helper.get("notes")
            if isinstance(notes, list) and notes:
                lines.append("  - Notes:")
                lines.extend(f"    - {item}" for item in notes)
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
    terrain = safe_mapping(summary.get("terrain"))
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
        "terrain": terrain,
        "recoveryPlan": summary.get("recoveryPlan"),
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
        "turnBackend": str(args.turn_backend),
        "mousePixelsPerPulse": int(args.mouse_pixels_per_pulse),
        "mouseSteps": int(args.mouse_steps),
        "mouseHoldMs": int(args.mouse_hold_ms),
        "clearUiFocusBeforeInput": bool(getattr(args, "clear_ui_focus_before_input", False)),
        "clearUiFocusKey": str(getattr(args, "clear_ui_focus_key", DEFAULT_CLEAR_UI_FOCUS_KEY)),
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
        "terrain": {
            "noProgressStepCount": 0,
            "terrainSubClassifications": {},
            "primarySubClassification": None,
            "terrainBlockerPresent": False,
        },
        "recoveryPlan": build_recovery_plan({}),
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

    if not args.dry_run:
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

        if bool(getattr(args, "clear_ui_focus_before_input", False)) and not args.dry_run:
            clear_child = run_child(
                label="00-clear-ui-focus",
                command=clear_ui_focus_command(args, root, initial_full),
                cwd=root,
                child_dir=child_dir,
                timeout_seconds=float(args.command_timeout_seconds),
            )
            summary["childCommands"].append(clear_child)
            safety["inputSent"] = True
            summary["warnings"].append(
                "clear-ui-focus-before-input-sent-once; use only after visual chat/menu focus confirmation because Escape is not idempotent"
            )
            clear_json = safe_mapping(clear_child.get("json"))
            summary["artifacts"]["clearUiFocusStdout"] = clear_child.get("stdoutPath")
            if not clear_child["ok"] or clear_json.get("ok") is not True:
                summary["status"] = "failed"
                summary["verdict"] = "clear-ui-focus-before-input-failed"
                summary["errors"].append("clear-ui-focus-before-input-failed")
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

            # Pre-define iteration_record so it's safe in plan-failure early-return paths
            iteration_record: dict[str, Any] = {
                "iteration": iteration,
                "planarDistance": current_distance,
                "plan": None,
                "turnDirection": None,
                "computedTurnHoldMs": None,
                "turnResult": {"status": "not-needed"},
                "forwardResult": {"status": "not-needed"},
                "childCommands": [],
            }

            if not isinstance(plan_child.get("json"), Mapping):
                summary["warnings"].append(f"plan-failed-at-iteration-{iteration}")
                summary["total"]["finalPlanarDistance"] = current_distance
                summary["iterations"].append(iteration_record)
                break

            plan_full = full_summary_from_compact(plan_child["json"])
            plan_detail = compact_plan(plan_full)
            current_distance = plan_detail.get("planarDistance") or 0

            # Update iteration_record with plan data now that we have it
            iteration_record["planarDistance"] = current_distance
            iteration_record["plan"] = plan_detail

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
                signed_delta = float(plan_detail.get("signedBearingDeltaDegrees") or 0)
                iteration_record["turnDirection"] = suggested_turn
                iteration_record["turnMethod"] = f"turn-completion-detector-{args.turn_backend}-pulse-loop"

                turn_child = run_child(
                    label=f"turn-{iteration:03d}-{suggested_turn}",
                    command=turn_completion_command(args, root, child_output_root, suggested_turn, signed_delta),
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
                else:
                    turn_compact = safe_mapping(turn_child["json"])
                    turn_verdict = str(turn_compact.get("verdict") or "")
                    turn_ok = turn_compact.get("status") == "passed"
                    iteration_record["turnResult"] = {
                        "status": "passed" if turn_ok else "blocked",
                        "verdict": turn_verdict,
                        "preYawDegrees": turn_compact.get("preYawDegrees"),
                        "postYawDegrees": turn_compact.get("postYawDegrees"),
                        "achievedBearingDegrees": turn_compact.get("achievedBearingDegrees"),
                        "bearingErrorDegrees": turn_compact.get("bearingErrorDegrees"),
                        "totalPulses": turn_compact.get("totalPulses"),
                        "totalYawDeltaDegrees": turn_compact.get("totalYawDeltaDegrees"),
                    }
                    total_turns += 1
                    if turn_ok:
                        safety["movementSent"] = True
                        safety["navigationControl"] = True
                    elif turn_verdict == "turn-overcorrected":
                        summary["warnings"].append(f"turn-overcorrected-at-iteration-{iteration}")
                    elif turn_verdict == "turn-timeout":
                        summary["warnings"].append(f"turn-timeout-at-iteration-{iteration}")

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
                    no_progress_sub = route_result.get("noProgressSubClassification")
                    iteration_record["forwardResult"] = {
                        "status": "passed" if forward_ok else "blocked",
                        "routeStatus": route_status,
                        "totalProgressDistance": route_result.get("totalProgressDistance"),
                        "initialPlanarDistance": route_result.get("initialPlanarDistance"),
                        "finalPlanarDistance": route_result.get("finalPlanarDistance"),
                        "noProgressSubClassification": no_progress_sub,
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
                        consecutive_no_progress += 1
                        if not bool(getattr(args, "clear_ui_focus_before_input", False)):
                            summary["warnings"].append(
                                f"forward-no-progress-input-focus-not-ruled-out-at-iteration-{iteration}"
                            )
                        if consecutive_no_progress >= 3:
                            if no_progress_sub == "blocked-stationary-no-movement":
                                summary["blockers"].append("forward-no-progress-3-consecutive-blocked-stationary-terrain")
                            elif no_progress_sub == "drifted-back-after-initial-progress":
                                summary["blockers"].append("forward-no-progress-3-consecutive-drifted-back-terrain")
                            elif no_progress_sub == "insufficient-progress-below-threshold":
                                summary["blockers"].append("forward-no-progress-3-consecutive-insufficient-progress")
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
        summary["terrain"] = build_terrain_summary(
            [safe_mapping(item) for item in summary.get("iterations", []) if isinstance(item, Mapping)]
        )
        summary["recoveryPlan"] = build_recovery_plan(safe_mapping(summary.get("terrain")))
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
