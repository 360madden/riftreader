#!/usr/bin/env python3
"""Probe bounded mouse-look arc recovery after stationary forward blocks.

This helper addresses the current live navigation state: mouse-look turns are
validated, but straight forward route steps can classify as
``blocked-stationary-no-movement``.  It tests a bounded set of target bearings
relative to a fresh baseline yaw, using the existing mouse-look turn completion
detector and exact-target ``W`` SendInput pulses, then classifies whether the
player actually moved.

It is evidence collection only.  It does not attach a debugger, use Cheat
Engine, promote proof/truth, write provider repos, or mutate Git state.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .static_owner_facing_discovery import normalize_degrees
    from .static_owner_mouse_turn_probe import target_from_summary
    from .static_owner_nav_route_step import (
        DEFAULT_CLEAR_UI_FOCUS_HOLD_MS,
        DEFAULT_CLEAR_UI_FOCUS_KEY,
        clear_ui_focus_command,
    )
    from .workflow_common import (
        base_safety,
        full_summary_from_compact,
        repo_root,
        run_child,
        safe_mapping,
        utc_iso,
        utc_stamp,
        write_json,
    )
except ImportError:  # pragma: no cover - direct script execution path
    from static_owner_facing_discovery import normalize_degrees  # type: ignore
    from static_owner_mouse_turn_probe import target_from_summary  # type: ignore
    from static_owner_nav_route_step import (  # type: ignore
        DEFAULT_CLEAR_UI_FOCUS_HOLD_MS,
        DEFAULT_CLEAR_UI_FOCUS_KEY,
        clear_ui_focus_command,
    )
    from workflow_common import (  # type: ignore
        base_safety,
        full_summary_from_compact,
        repo_root,
        run_child,
        safe_mapping,
        utc_iso,
        utc_stamp,
        write_json,
    )


SCHEMA_VERSION = 1
DEFAULT_ARC_OFFSETS = (45.0, -45.0, 90.0, -90.0, 180.0)
DEFAULT_FORWARD_HOLD_MS = 450
DEFAULT_MIN_MOVEMENT_DISTANCE = 0.35
DEFAULT_MAX_TOTAL_DISPLACEMENT = 10.0


def state_command(args: argparse.Namespace, root: Path, output_root: Path) -> list[str]:
    return [
        sys.executable,
        str(root / "scripts" / "static_owner_facing_discovery.py"),
        "state",
        "--repo-root",
        str(root),
        "--output-root",
        str(output_root),
        "--current-truth-json",
        str(args.current_truth_json),
        "--samples",
        str(args.samples),
        "--interval-seconds",
        str(args.interval_seconds),
        "--expect-stationary",
        "--json",
    ]


def readback_freshness_command(args: argparse.Namespace, root: Path, output_root: Path) -> list[str]:
    return [
        sys.executable,
        str(root / "scripts" / "static_owner_coordinate_chain_readback.py"),
        "--repo-root",
        str(root),
        "--output-root",
        str(output_root),
        "--use-current-truth",
        "--current-truth-json",
        str(args.current_truth_json),
        "--samples",
        "1",
        "--json",
    ]


def turn_completion_command(
    *,
    args: argparse.Namespace,
    root: Path,
    output_root: Path,
    target: Mapping[str, Any],
    direction: str,
    signed_delta_degrees: float,
) -> list[str]:
    return [
        sys.executable,
        str(root / "scripts" / "turn_completion_detector.py"),
        "--repo-root",
        str(root),
        "--output-root",
        str(output_root),
        "--current-truth-json",
        str(args.current_truth_json),
        "--direction",
        direction,
        "--signed-bearing-delta-degrees",
        str(signed_delta_degrees),
        "--alignment-threshold-degrees",
        str(args.alignment_threshold_degrees),
        "--max-pulses",
        str(args.max_turn_pulses),
        "--settle-ms",
        str(args.turn_settle_milliseconds),
        "--pulse-interval-ms",
        str(args.turn_pulse_interval_milliseconds),
        "--turn-backend",
        "mouse-look",
        "--mouse-pixels-per-pulse",
        str(args.mouse_pixels_per_pulse),
        "--mouse-steps",
        str(args.mouse_steps),
        "--mouse-hold-ms",
        str(args.mouse_hold_milliseconds),
        "--process-name",
        str(target.get("processName") or args.process_name),
        "--pid",
        str(target["processId"]),
        "--hwnd",
        str(target["targetWindowHandle"]),
        "--title-contains",
        str(args.title_contains),
        "--command-timeout-seconds",
        str(args.command_timeout_seconds),
        "--turn-approved",
        "--json",
    ]


def forward_command(
    *,
    args: argparse.Namespace,
    root: Path,
    target: Mapping[str, Any],
) -> list[str]:
    return [
        "pwsh",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(root / "scripts" / "send-rift-key-csharp.ps1"),
        "--key",
        str(args.forward_key),
        "--hold-ms",
        str(args.forward_hold_milliseconds),
        "--process-name",
        str(target.get("processName") or args.process_name),
        "--pid",
        str(target["processId"]),
        "--hwnd",
        str(target["targetWindowHandle"]),
        "--title-contains",
        str(args.title_contains),
        "--input-mode",
        str(args.input_mode),
        "--focus-delay-ms",
        str(args.focus_delay_milliseconds),
        "--json",
    ]


def release_command(args: argparse.Namespace, root: Path, target: Mapping[str, Any]) -> list[str]:
    return [
        sys.executable,
        str(root / "scripts" / "rift_live_test" / "emergency_key_release.py"),
        "--pid",
        str(target["processId"]),
        "--hwnd",
        str(target["targetWindowHandle"]),
        "--process-name",
        str(target.get("processName") or args.process_name),
        "--key",
        "w,a,s,d,left,right,q,e",
        "--include-mouse-buttons",
        "--mouse-button",
        "right,left,middle",
        "--json",
    ]


def coordinate_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, float]:
    dx = float(after["x"]) - float(before["x"])
    dy = float(after["y"]) - float(before["y"])
    dz = float(after["z"]) - float(before["z"])
    return {
        "x": dx,
        "y": dy,
        "z": dz,
        "planar": math.hypot(dx, dz),
        "distance3d": math.sqrt((dx * dx) + (dy * dy) + (dz * dz)),
    }


def destination_progress(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    destination: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not destination:
        return {}
    before_distance = math.hypot(float(destination["x"]) - float(before["x"]), float(destination["z"]) - float(before["z"]))
    after_distance = math.hypot(float(destination["x"]) - float(after["x"]), float(destination["z"]) - float(after["z"]))
    return {
        "initialPlanarDistance": before_distance,
        "finalPlanarDistance": after_distance,
        "distanceDelta": before_distance - after_distance,
        "movedTowardDestination": after_distance < before_distance,
    }


def parse_destination(args: argparse.Namespace) -> dict[str, float] | None:
    if args.destination_x is None and args.destination_z is None:
        return None
    if args.destination_x is None or args.destination_z is None:
        raise ValueError("destination-x-and-z-required-together")
    return {
        "x": float(args.destination_x),
        "z": float(args.destination_z),
    }


def bearing_to_destination(coordinate: Mapping[str, Any], destination: Mapping[str, Any]) -> float:
    dx = float(destination["x"]) - float(coordinate["x"])
    dz = float(destination["z"]) - float(coordinate["z"])
    return normalize_degrees(math.degrees(math.atan2(dz, dx)))


def target_bearing_for_offset(baseline_yaw: float, offset_degrees: float) -> float:
    return normalize_degrees(float(baseline_yaw) + float(offset_degrees))


def direction_for_signed_delta(signed_delta_degrees: float) -> str:
    return "right" if signed_delta_degrees > 0 else "left"


def analyze_attempt(
    *,
    arc_offset_degrees: float,
    target_bearing_degrees: float,
    pre_summary: Mapping[str, Any],
    post_summary: Mapping[str, Any],
    minimum_movement_distance: float,
    destination: Mapping[str, Any] | None,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    pre_state = safe_mapping(pre_summary.get("latestState"))
    post_state = safe_mapping(post_summary.get("latestState"))
    pre_coord = safe_mapping(pre_state.get("coordinate"))
    post_coord = safe_mapping(post_state.get("coordinate"))
    if not pre_coord or not post_coord:
        return {
            "status": "blocked",
            "arcOffsetDegrees": arc_offset_degrees,
            "targetBearingDegrees": target_bearing_degrees,
            "blockers": ["pre-post-coordinate-required"],
            "warnings": [],
        }
    movement = coordinate_delta(pre_coord, post_coord)
    if movement["planar"] < minimum_movement_distance:
        blockers.append("movement-below-threshold")
    progress = destination_progress(pre_coord, post_coord, destination)
    if progress and progress.get("distanceDelta", 0.0) < 0:
        warnings.append("moved-away-from-destination")
    return {
        "status": "passed" if not blockers else "blocked",
        "candidateOnly": True,
        "actionableForNavigation": False,
        "movementPermission": False,
        "facingPromotion": False,
        "arcOffsetDegrees": arc_offset_degrees,
        "targetBearingDegrees": target_bearing_degrees,
        "preYawDegrees": pre_state.get("yawDegrees"),
        "postYawDegrees": post_state.get("yawDegrees"),
        "movementDelta": movement,
        "minimumMovementDistance": float(minimum_movement_distance),
        "destinationProgress": progress,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
    }


def validate_args(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    if not args.arc_offsets_degrees:
        errors.append("arc-offsets-degrees-required")
    if args.samples < 1:
        errors.append("samples-must-be-positive")
    if args.interval_seconds < 0:
        errors.append("interval-seconds-must-be-nonnegative")
    if args.alignment_threshold_degrees < 0:
        errors.append("alignment-threshold-degrees-must-be-nonnegative")
    if args.max_turn_pulses < 1:
        errors.append("max-turn-pulses-must-be-positive")
    if args.mouse_pixels_per_pulse <= 0:
        errors.append("mouse-pixels-per-pulse-must-be-positive")
    if args.mouse_steps < 1:
        errors.append("mouse-steps-must-be-positive")
    if args.mouse_hold_milliseconds <= 0:
        errors.append("mouse-hold-milliseconds-must-be-positive")
    if args.forward_hold_milliseconds <= 0:
        errors.append("forward-hold-milliseconds-must-be-positive")
    if args.post_forward_wait_milliseconds < 0:
        errors.append("post-forward-wait-milliseconds-must-be-nonnegative")
    if args.minimum_movement_distance < 0:
        errors.append("minimum-movement-distance-must-be-nonnegative")
    if args.max_total_displacement < 0:
        errors.append("max-total-displacement-must-be-nonnegative")
    if args.command_timeout_seconds <= 0:
        errors.append("command-timeout-seconds-must-be-positive")
    if bool(getattr(args, "clear_ui_focus_before_input", False)):
        if int(getattr(args, "clear_ui_focus_hold_milliseconds", DEFAULT_CLEAR_UI_FOCUS_HOLD_MS)) <= 0:
            errors.append("clear-ui-focus-hold-milliseconds-must-be-positive")
        if not str(getattr(args, "clear_ui_focus_key", DEFAULT_CLEAR_UI_FOCUS_KEY) or "").strip():
            errors.append("clear-ui-focus-key-required")
    if (args.destination_x is None) != (args.destination_z is None):
        errors.append("destination-x-and-z-required-together")
    return sorted(set(errors))


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-mouse-arc-recovery-{utc_stamp()}"
    child_dir = run_dir / "child-outputs"
    child_output_root = run_dir / "child-runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    errors = validate_args(args)
    safety = base_safety()
    destination = parse_destination(args) if not errors else None
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-mouse-arc-recovery-probe",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "pending",
        "verdict": "invalid-arguments" if errors else None,
        "repoRoot": str(root),
        "operator": {
            "dryRun": bool(args.dry_run),
            "arcApproved": bool(args.arc_approved),
            "movementApproved": bool(args.movement_approved),
            "arcOffsetsDegrees": [float(item) for item in args.arc_offsets_degrees],
            "forwardKey": args.forward_key,
            "forwardHoldMilliseconds": int(args.forward_hold_milliseconds),
            "mousePixelsPerPulse": int(args.mouse_pixels_per_pulse),
            "clearUiFocusBeforeInput": bool(getattr(args, "clear_ui_focus_before_input", False)),
            "clearUiFocusKey": str(getattr(args, "clear_ui_focus_key", DEFAULT_CLEAR_UI_FOCUS_KEY)),
            "stopOnFirstSuccess": bool(args.stop_on_first_success),
        },
        "destination": destination,
        "preflight": {},
        "baseline": {},
        "attempts": [],
        "successfulAttempts": [],
        "childCommands": [],
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
    if not args.dry_run and (not args.arc_approved or not args.movement_approved):
        summary["status"] = "blocked"
        summary["verdict"] = "arc-and-movement-approval-required"
        if not args.arc_approved:
            summary["blockers"].append("arc-approved-flag-required")
        if not args.movement_approved:
            summary["blockers"].append("movement-approved-flag-required")
        return summary

    release_target: dict[str, Any] | None = None
    try:
        if not args.skip_readback_freshness_gate:
            readback = run_child(
                label="00-readback-freshness",
                command=readback_freshness_command(args, root, child_output_root),
                cwd=root,
                child_dir=child_dir,
                timeout_seconds=float(args.command_timeout_seconds),
            )
            summary["childCommands"].append(readback)
            summary["preflight"]["readbackFreshness"] = readback
            if not isinstance(readback.get("json"), Mapping):
                summary["status"] = "failed"
                summary["verdict"] = "static-resolver-readback-freshness-failed"
                summary["errors"].append("readback-freshness-gate-json-parse-failed")
                return summary
            readback_status = str(safe_mapping(readback["json"]).get("status") or "")
            if readback_status != "passed":
                summary["status"] = "blocked" if readback_status == "blocked" else "failed"
                summary["verdict"] = "static-resolver-readback-freshness-blocked"
                summary["blockers"].append(f"static-resolver-readback-freshness-gate:{readback_status}")
                return summary

        baseline_child = run_child(
            label="00-baseline-state",
            command=state_command(args, root, child_output_root),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=float(args.command_timeout_seconds),
        )
        summary["childCommands"].append(baseline_child)
        if not baseline_child["ok"] or not isinstance(baseline_child.get("json"), Mapping):
            summary["status"] = "failed"
            summary["verdict"] = "baseline-state-readback-failed"
            summary["errors"].append("baseline-state-readback-failed")
            return summary
        baseline_full = full_summary_from_compact(baseline_child["json"])
        baseline_state = safe_mapping(baseline_full.get("latestState"))
        baseline_coord = safe_mapping(baseline_state.get("coordinate"))
        baseline_yaw = baseline_state.get("yawDegrees")
        if not baseline_coord or baseline_yaw is None:
            summary["status"] = "failed"
            summary["verdict"] = "baseline-coordinate-or-yaw-missing"
            summary["errors"].append("baseline-coordinate-or-yaw-missing")
            return summary
        release_target = target_from_summary(baseline_full)
        reference_bearing = (
            bearing_to_destination(baseline_coord, destination)
            if destination is not None
            else float(baseline_yaw)
        )
        summary["baseline"] = {
            "summaryJson": safe_mapping(baseline_child["json"]).get("summaryJson"),
            "coordinate": baseline_coord,
            "yawDegrees": baseline_yaw,
            "referenceBearingDegrees": reference_bearing,
            "referenceBearingSource": "destination" if destination is not None else "baseline-yaw",
            "target": release_target,
        }

        stop = False
        clear_ui_focus_sent = False
        for index, offset in enumerate(args.arc_offsets_degrees, start=1):
            if stop:
                break
            label_prefix = f"{index:03d}-arc-{float(offset):+07.2f}".replace("+", "p").replace("-", "m").replace(".", "_")
            pre = run_child(
                label=f"{label_prefix}-pre-state",
                command=state_command(args, root, child_output_root),
                cwd=root,
                child_dir=child_dir,
                timeout_seconds=float(args.command_timeout_seconds),
            )
            summary["childCommands"].append(pre)
            attempt: dict[str, Any] = {
                "attemptIndex": index,
                "arcOffsetDegrees": float(offset),
                "status": "failed",
                "preStateCommand": pre,
                "turnCommand": None,
                "clearUiFocusCommand": None,
                "forwardCommand": None,
                "postStateCommand": None,
                "analysis": None,
                "blockers": [],
                "warnings": [],
                "errors": [],
                "inputSent": False,
                "movementSent": False,
            }
            if not pre["ok"] or not isinstance(pre.get("json"), Mapping):
                attempt["errors"].append("pre-state-readback-failed")
                summary["attempts"].append(attempt)
                continue
            pre_full = full_summary_from_compact(pre["json"])
            attempt["preStateSummaryJson"] = safe_mapping(pre["json"]).get("summaryJson")
            if pre_full.get("status") != "passed":
                attempt["status"] = "blocked"
                attempt["blockers"].append("pre-state-readback-not-passed")
                summary["attempts"].append(attempt)
                continue
            pre_state = safe_mapping(pre_full.get("latestState"))
            current_yaw = pre_state.get("yawDegrees")
            if current_yaw is None:
                attempt["status"] = "blocked"
                attempt["blockers"].append("pre-yaw-required")
                summary["attempts"].append(attempt)
                continue
            target = target_from_summary(pre_full)
            release_target = target
            target_bearing = target_bearing_for_offset(reference_bearing, float(offset))
            signed_delta = normalize_degrees(target_bearing - float(current_yaw))
            direction = direction_for_signed_delta(signed_delta)
            attempt["targetBearingDegrees"] = target_bearing
            attempt["signedDeltaFromCurrentYawDegrees"] = signed_delta
            attempt["turnDirection"] = direction
            if abs(signed_delta) > float(args.alignment_threshold_degrees):
                if args.dry_run:
                    attempt["turnCommandPlan"] = turn_completion_command(
                        args=args,
                        root=root,
                        output_root=child_output_root,
                        target=target,
                        direction=direction,
                        signed_delta_degrees=signed_delta,
                    )
                else:
                    turn = run_child(
                        label=f"{label_prefix}-turn",
                        command=turn_completion_command(
                            args=args,
                            root=root,
                            output_root=child_output_root,
                            target=target,
                            direction=direction,
                            signed_delta_degrees=signed_delta,
                        ),
                        cwd=root,
                        child_dir=child_dir,
                        timeout_seconds=float(args.command_timeout_seconds),
                    )
                    summary["childCommands"].append(turn)
                    attempt["turnCommand"] = turn
                    safety["inputSent"] = True
                    safety["movementSent"] = True
                    attempt["inputSent"] = True
                    attempt["movementSent"] = True
                    if not turn["ok"]:
                        attempt["status"] = "blocked"
                        attempt["blockers"].append("turn-completion-failed-or-blocked")
                        summary["attempts"].append(attempt)
                        continue
            else:
                attempt["turnSkipped"] = "already-within-alignment-threshold"

            if args.dry_run:
                attempt["status"] = "planned"
                attempt["forwardCommandPlan"] = forward_command(args=args, root=root, target=target)
                summary["attempts"].append(attempt)
                continue

            if bool(getattr(args, "clear_ui_focus_before_input", False)) and not clear_ui_focus_sent:
                clear = run_child(
                    label=f"{label_prefix}-clear-ui-focus",
                    command=clear_ui_focus_command(args, root, {"target": target}),
                    cwd=root,
                    child_dir=child_dir,
                    timeout_seconds=float(args.command_timeout_seconds),
                )
                summary["childCommands"].append(clear)
                attempt["clearUiFocusCommand"] = clear
                clear_ui_focus_sent = True
                safety["inputSent"] = True
                attempt["inputSent"] = True
                attempt["warnings"].append(
                    "clear-ui-focus-before-input-sent; use only after visual chat/menu focus confirmation because Escape is not idempotent"
                )
                clear_json = safe_mapping(clear.get("json"))
                if not clear["ok"] or clear_json.get("ok") is not True:
                    attempt["status"] = "failed"
                    attempt["errors"].append("clear-ui-focus-before-input-failed")
                    summary["attempts"].append(attempt)
                    continue

            forward = run_child(
                label=f"{label_prefix}-forward",
                command=forward_command(args=args, root=root, target=target),
                cwd=root,
                child_dir=child_dir,
                timeout_seconds=float(args.command_timeout_seconds),
            )
            summary["childCommands"].append(forward)
            attempt["forwardCommand"] = forward
            safety["inputSent"] = True
            safety["movementSent"] = True
            safety["navigationControl"] = True
            attempt["inputSent"] = True
            attempt["movementSent"] = True
            if not forward["ok"] or safe_mapping(forward.get("json")).get("ok") is not True:
                attempt["status"] = "failed"
                attempt["errors"].append("forward-input-failed")
                summary["attempts"].append(attempt)
                continue

            if args.post_forward_wait_milliseconds:
                time.sleep(float(args.post_forward_wait_milliseconds) / 1000.0)

            post = run_child(
                label=f"{label_prefix}-post-state",
                command=state_command(args, root, child_output_root),
                cwd=root,
                child_dir=child_dir,
                timeout_seconds=float(args.command_timeout_seconds),
            )
            summary["childCommands"].append(post)
            attempt["postStateCommand"] = post
            if not post["ok"] or not isinstance(post.get("json"), Mapping):
                attempt["status"] = "failed"
                attempt["errors"].append("post-state-readback-failed")
                summary["attempts"].append(attempt)
                continue
            post_full = full_summary_from_compact(post["json"])
            attempt["postStateSummaryJson"] = safe_mapping(post["json"]).get("summaryJson")
            if post_full.get("status") != "passed":
                attempt["status"] = "blocked"
                attempt["blockers"].append("post-state-readback-not-passed")
                summary["attempts"].append(attempt)
                continue
            analysis = analyze_attempt(
                arc_offset_degrees=float(offset),
                target_bearing_degrees=target_bearing,
                pre_summary=pre_full,
                post_summary=post_full,
                minimum_movement_distance=float(args.minimum_movement_distance),
                destination=destination,
            )
            attempt["analysis"] = analysis
            attempt["status"] = analysis["status"]
            attempt["blockers"].extend(analysis["blockers"])
            attempt["warnings"].extend(analysis["warnings"])
            summary["attempts"].append(attempt)
            baseline_to_post = coordinate_delta(baseline_coord, safe_mapping(safe_mapping(post_full.get("latestState")).get("coordinate")))
            attempt["baselineToPostDelta"] = baseline_to_post
            if baseline_to_post["planar"] > float(args.max_total_displacement):
                summary["blockers"].append("max-total-displacement-exceeded")
                stop = True
            if analysis["status"] == "passed":
                success = {
                    "attemptIndex": index,
                    "arcOffsetDegrees": float(offset),
                    "targetBearingDegrees": target_bearing,
                    "movementDelta": analysis["movementDelta"],
                    "destinationProgress": analysis["destinationProgress"],
                    "warnings": analysis["warnings"],
                }
                summary["successfulAttempts"].append(success)
                if args.stop_on_first_success:
                    stop = True

        if args.dry_run:
            summary["status"] = "passed"
            summary["verdict"] = "mouse-arc-recovery-dry-run-built"
            summary["warnings"].append("dry-run-only-no-input-sent")
        elif summary["successfulAttempts"]:
            summary["status"] = "passed"
            summary["verdict"] = "mouse-arc-recovery-movement-validated"
            summary["warnings"].append("candidate-recovery-evidence-not-promoted")
        else:
            summary["status"] = "blocked"
            summary["verdict"] = "mouse-arc-recovery-no-movement"
            summary["blockers"].append("no-arc-forward-attempt-met-movement-threshold")
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "mouse-arc-recovery-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    finally:
        if release_target and not args.dry_run and safety.get("inputSent"):
            try:
                release = run_child(
                    label="zz-emergency-release",
                    command=release_command(args, root, release_target),
                    cwd=root,
                    child_dir=child_dir,
                    timeout_seconds=float(args.command_timeout_seconds),
                )
                summary["childCommands"].append(release)
                summary["artifacts"]["emergencyReleaseCommand"] = release.get("commandPath")
                safety["inputSent"] = True
            except Exception as exc:  # noqa: BLE001
                summary["warnings"].append(f"emergency-release-failed:{type(exc).__name__}:{exc}")

    summary["blockers"] = sorted(set(summary["blockers"]))
    summary["warnings"] = sorted(set(summary["warnings"]))
    summary["errors"] = sorted(set(summary["errors"]))
    return summary


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    attempts = summary.get("attempts", [])
    successes = summary.get("successfulAttempts", [])
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "attemptCount": len(attempts) if isinstance(attempts, Sequence) else 0,
        "successfulAttemptCount": len(successes) if isinstance(successes, Sequence) else 0,
        "successfulAttempts": successes,
        "movementSent": safe_mapping(summary.get("safety")).get("movementSent"),
        "inputSent": safe_mapping(summary.get("safety")).get("inputSent"),
        "navigationControl": safe_mapping(summary.get("safety")).get("navigationControl"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    artifacts = safe_mapping(summary.get("artifacts"))
    lines = [
        "# Static owner mouse arc recovery probe",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Results",
        "",
        f"- Attempts: `{len(summary.get('attempts', []))}`",
        f"- Successful attempts: `{len(summary.get('successfulAttempts', []))}`",
        "",
        "## Successful attempts",
        "",
    ]
    successes = summary.get("successfulAttempts", [])
    if successes:
        for item in successes:
            item_map = safe_mapping(item)
            movement = safe_mapping(item_map.get("movementDelta"))
            progress = safe_mapping(item_map.get("destinationProgress"))
            lines.append(
                f"- Offset `{item_map.get('arcOffsetDegrees')}` deg, bearing "
                f"`{item_map.get('targetBearingDegrees')}`: moved "
                f"`{movement.get('planar')}`m, destination delta "
                f"`{progress.get('distanceDelta')}`"
            )
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Summary JSON: `{artifacts.get('summaryJson')}`",
            f"- Run directory: `{artifacts.get('runDirectory')}`",
        ]
    )
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe bounded mouse-look arc recovery after stationary forward blocks")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--current-truth-json", default="docs/recovery/current-truth.json")
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--destination-x", type=float)
    parser.add_argument("--destination-z", type=float)
    parser.add_argument("--arc-offsets-degrees", nargs="+", type=float, default=list(DEFAULT_ARC_OFFSETS))
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--interval-seconds", type=float, default=0.1)
    parser.add_argument("--alignment-threshold-degrees", type=float, default=7.5)
    parser.add_argument("--max-turn-pulses", type=int, default=5)
    parser.add_argument("--turn-settle-milliseconds", type=int, default=350)
    parser.add_argument("--turn-pulse-interval-milliseconds", type=int, default=100)
    parser.add_argument("--mouse-pixels-per-pulse", type=int, default=40)
    parser.add_argument("--mouse-steps", type=int, default=8)
    parser.add_argument("--mouse-hold-milliseconds", type=int, default=250)
    parser.add_argument("--forward-key", default="w")
    parser.add_argument("--forward-hold-milliseconds", type=int, default=DEFAULT_FORWARD_HOLD_MS)
    parser.add_argument("--post-forward-wait-milliseconds", type=int, default=750)
    parser.add_argument("--input-mode", choices=("ScanCode", "VirtualKey"), default="ScanCode")
    parser.add_argument("--focus-delay-milliseconds", type=int, default=250)
    parser.add_argument("--title-contains", default="RIFT")
    parser.add_argument(
        "--clear-ui-focus-before-input",
        action="store_true",
        help=(
            "Opt-in exact-target Escape once before the first forward pulse to clear confirmed chat/menu focus. "
            "Not idempotent; do not enable unless UI focus is visually confirmed."
        ),
    )
    parser.add_argument("--clear-ui-focus-key", default=DEFAULT_CLEAR_UI_FOCUS_KEY)
    parser.add_argument("--clear-ui-focus-hold-milliseconds", type=int, default=DEFAULT_CLEAR_UI_FOCUS_HOLD_MS)
    parser.add_argument("--minimum-movement-distance", type=float, default=DEFAULT_MIN_MOVEMENT_DISTANCE)
    parser.add_argument("--max-total-displacement", type=float, default=DEFAULT_MAX_TOTAL_DISPLACEMENT)
    parser.add_argument("--command-timeout-seconds", type=float, default=90.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--arc-approved", action="store_true")
    parser.add_argument("--movement-approved", action="store_true")
    parser.add_argument(
        "--skip-readback-freshness-gate",
        action="store_true",
        help="Skip static resolver preflight freshness gate; intended only for tests/diagnostics.",
    )
    parser.add_argument("--no-stop-on-first-success", dest="stop_on_first_success", action="store_false")
    parser.set_defaults(stop_on_first_success=True)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run(args)
    artifacts = safe_mapping(summary.get("artifacts"))
    write_json(Path(str(artifacts["summaryJson"])), summary)
    Path(str(artifacts["summaryMarkdown"])).write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(compact(summary)) if args.json else json.dumps(compact(summary), indent=2))
    if summary.get("status") == "passed":
        return 0
    if summary.get("status") == "blocked":
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
