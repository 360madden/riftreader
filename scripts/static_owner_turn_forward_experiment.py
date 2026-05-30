#!/usr/bin/env python3
"""Run one gated turn-then-forward static-owner navigation experiment.

This helper is intentionally a narrow experiment, not a route loop.  It builds a
dry-run turn-aware plan, optionally performs one approved turn stimulus from
candidate yaw evidence, then delegates the forward pulse to the existing
route-step helper so a fresh exact-target static-chain readback happens before
forward movement.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .static_owner_nav_route_step import base_safety, destination_args, load_json_object, preview, safe_mapping, write_json
    from .static_owner_turn_aware_route_plan import DEFAULT_MAX_ROUTE_STEPS, validate_turn_aware_plan_contract
    from .static_owner_turn_stimulus_capture import validate_turn_capture_summary_contract
    from .workflow_common import (
        full_summary_from_compact,
        repo_root,
        run_child,
        utc_iso,
        utc_stamp,
    )
except ImportError:  # pragma: no cover - direct script execution path
    from static_owner_nav_route_step import base_safety, destination_args, load_json_object, preview, safe_mapping, write_json  # type: ignore
    from static_owner_turn_aware_route_plan import DEFAULT_MAX_ROUTE_STEPS, validate_turn_aware_plan_contract  # type: ignore
    from static_owner_turn_stimulus_capture import validate_turn_capture_summary_contract  # type: ignore
    from workflow_common import (  # type: ignore
        full_summary_from_compact,
        repo_root,
        run_child,
        utc_iso,
        utc_stamp,
    )

SCHEMA_VERSION = 1
DEFAULT_TURN_HOLD_MS = 175
DEFAULT_FORWARD_HOLD_MS = 250
DEFAULT_MAX_INITIAL_TURN_DEGREES = 90.0
DEFAULT_MAX_CUMULATIVE_TURN_DEGREES = 90.0
DEFAULT_MAX_OBSERVED_TURN_DEGREES = 90.0
DEFAULT_MAX_TOTAL_INPUT_MS = 600
DEFAULT_MINIMUM_YAW_DELTA_DEGREES = 1.0
DEFAULT_MAX_TURN_PLANAR_DRIFT = 1.0
LIVE_ROUTE_STEP_VERDICT = "route-step-live-movement-progress-validated"

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
    if args.arrival_radius is not None and args.arrival_radius < 0:
        errors.append("arrival-radius-must-be-nonnegative")
    if args.alignment_threshold_degrees < 0:
        errors.append("alignment-threshold-degrees-must-be-nonnegative")
    if args.turn_hold_milliseconds <= 0:
        errors.append("turn-hold-milliseconds-must-be-positive")
    if args.forward_hold_milliseconds <= 0:
        errors.append("forward-hold-milliseconds-must-be-positive")
    if args.max_initial_turn_degrees <= 0:
        errors.append("max-initial-turn-degrees-must-be-positive")
    if args.max_cumulative_turn_degrees <= 0:
        errors.append("max-cumulative-turn-degrees-must-be-positive")
    if args.max_observed_turn_degrees <= 0:
        errors.append("max-observed-turn-degrees-must-be-positive")
    if args.max_total_input_milliseconds <= 0:
        errors.append("max-total-input-milliseconds-must-be-positive")
    if args.max_route_steps != DEFAULT_MAX_ROUTE_STEPS:
        errors.append("turn-forward-experiment-supports-exactly-one-route-step")
    if args.turn_hold_milliseconds + args.forward_hold_milliseconds > args.max_total_input_milliseconds:
        errors.append("planned-input-duration-exceeds-max-total-input-milliseconds")
    if args.samples < 1:
        errors.append("samples-must-be-positive")
    if args.interval_seconds < 0:
        errors.append("interval-seconds-must-be-nonnegative")
    if args.turn_settle_seconds < 0 or args.forward_settle_seconds < 0:
        errors.append("settle-seconds-must-be-nonnegative")
    if args.command_timeout_seconds <= 0:
        errors.append("command-timeout-seconds-must-be-positive")
    if args.minimum_yaw_delta_degrees < 0:
        errors.append("minimum-yaw-delta-degrees-must-be-nonnegative")
    if args.max_turn_planar_drift < 0:
        errors.append("max-turn-planar-drift-must-be-nonnegative")
    return sorted(set(errors))


def turn_plan_command(args: argparse.Namespace, root: Path, output_root: Path) -> list[str]:
    command = [
        sys.executable,
        str(root / "scripts" / "static_owner_turn_aware_route_plan.py"),
        "--repo-root",
        str(root),
        "--output-root",
        str(output_root),
        "--current-truth-json",
        str(args.current_truth_json),
        "--alignment-threshold-degrees",
        str(args.alignment_threshold_degrees),
        "--max-initial-turn-degrees",
        str(args.max_initial_turn_degrees),
        "--max-cumulative-turn-degrees",
        str(args.max_cumulative_turn_degrees),
        "--max-total-input-milliseconds",
        str(args.max_total_input_milliseconds),
        "--max-route-steps",
        str(args.max_route_steps),
        "--samples",
        str(args.samples),
        "--interval-seconds",
        str(args.interval_seconds),
        "--command-timeout-seconds",
        str(args.command_timeout_seconds),
        "--json",
    ]
    command += destination_args(args)
    if args.allow_candidate_turn_control:
        command.append("--allow-candidate-turn-control")
    return command


def turn_stimulus_command(args: argparse.Namespace, root: Path, output_root: Path, direction: str) -> list[str]:
    return [
        sys.executable,
        str(root / "scripts" / "static_owner_turn_stimulus_capture.py"),
        "--repo-root",
        str(root),
        "--output-root",
        str(output_root),
        "--current-truth-json",
        str(args.current_truth_json),
        "--direction",
        direction,
        "--hold-milliseconds",
        str(args.turn_hold_milliseconds),
        "--minimum-yaw-delta-degrees",
        str(args.minimum_yaw_delta_degrees),
        "--max-planar-drift",
        str(args.max_turn_planar_drift),
        "--samples",
        str(args.samples),
        "--interval-seconds",
        str(args.interval_seconds),
        "--settle-seconds",
        str(args.turn_settle_seconds),
        "--input-mode",
        str(args.input_mode),
        "--title-contains",
        str(args.title_contains),
        "--focus-delay-milliseconds",
        str(args.focus_delay_milliseconds),
        "--command-timeout-seconds",
        str(args.command_timeout_seconds),
        "--turn-approved",
        "--json",
    ]


def route_step_command(args: argparse.Namespace, root: Path, output_root: Path) -> list[str]:
    command = [
        sys.executable,
        str(root / "scripts" / "static_owner_nav_route_step.py"),
        "--repo-root",
        str(root),
        "--output-root",
        str(output_root),
        "--current-truth-json",
        str(args.current_truth_json),
        "--alignment-threshold-degrees",
        str(args.alignment_threshold_degrees),
        "--minimum-progress-distance",
        str(args.minimum_progress_distance),
        "--wrong-way-tolerance-distance",
        str(args.wrong_way_tolerance_distance),
        "--samples",
        str(args.samples),
        "--interval-seconds",
        str(args.interval_seconds),
        "--key",
        str(args.forward_key),
        "--hold-milliseconds",
        str(args.forward_hold_milliseconds),
        "--input-mode",
        str(args.input_mode),
        "--title-contains",
        str(args.title_contains),
        "--focus-delay-milliseconds",
        str(args.focus_delay_milliseconds),
        "--settle-seconds",
        str(args.forward_settle_seconds),
        "--command-timeout-seconds",
        str(args.command_timeout_seconds),
        "--movement-approved",
        "--json",
    ]
    command += destination_args(args)
    return command


def validate_turn_forward_experiment_contract(summary: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if summary.get("kind") != "static-owner-turn-forward-experiment":
        blockers.append("experiment-kind-must-be-static-owner-turn-forward-experiment")
    if summary.get("status") != "passed":
        blockers.append("experiment-status-must-be-passed")
    if summary.get("verdict") not in {
        "turn-forward-experiment-dry-run-plan-built",
        "turn-forward-live-progress-validated",
        "turn-forward-live-arrived",
        "turn-forward-no-movement-needed",
    }:
        blockers.append("experiment-verdict-unrecognized")
    plan_summary = safe_mapping(summary.get("turnAwarePlanSummary"))
    if plan_summary:
        plan_contract = validate_turn_aware_plan_contract(plan_summary)
        if plan_contract.get("status") != "passed":
            blockers.append("turn-aware-plan-contract-not-passed")
            blockers.extend(str(item) for item in plan_contract.get("blockers", []))
        warnings.extend(str(item) for item in plan_contract.get("warnings", []))
    else:
        blockers.append("turn-aware-plan-summary-required")

    safety = safe_mapping(summary.get("safety"))
    if safety.get("noCheatEngine") is not True:
        blockers.append("safety-no-cheat-engine-must-be-true")
    for key in (
        "reloaduiSent",
        "screenshotKeySent",
        "x64dbgAttach",
        "debuggerAttached",
        "providerWrites",
        "gitMutation",
        "proofPromotion",
        "actorChainPromotion",
        "facingPromotion",
        "savedVariablesUsedAsLiveTruth",
    ):
        if safety.get(key) is not False:
            blockers.append(f"safety-{key}-must-be-false")
    operator = safe_mapping(summary.get("operator"))
    if operator.get("dryRun") is True:
        if safety.get("movementSent") is not False or safety.get("inputSent") is not False:
            blockers.append("dry-run-safety-input-and-movement-must-be-false")
        if safety.get("navigationControl") is not False:
            blockers.append("dry-run-navigation-control-must-be-false")
    else:
        if safety.get("inputSent") is not True:
            blockers.append("live-experiment-input-sent-must-be-true")
        if safety.get("navigationControl") is not True:
            blockers.append("live-experiment-navigation-control-must-be-true")
    return {
        "status": "blocked" if blockers else "passed",
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "verdict": summary.get("verdict"),
        "movementSent": safety.get("movementSent"),
        "inputSent": safety.get("inputSent"),
        "navigationControl": safety.get("navigationControl"),
    }


def summarize_forward_result(step_summary: Mapping[str, Any]) -> dict[str, Any]:
    route_result = safe_mapping(step_summary.get("routeResult"))
    verdict = step_summary.get("verdict")
    route_status = route_result.get("routeStatus")
    if step_summary.get("status") == "passed" and verdict == "route-step-no-movement-needed":
        return {
            "status": "passed",
            "verdict": "turn-forward-no-movement-needed",
            "routeStatus": "arrived",
            "blockers": [],
        }
    if step_summary.get("status") == "passed" and verdict == LIVE_ROUTE_STEP_VERDICT and route_status in {"progress", "arrived"}:
        return {
            "status": "passed",
            "verdict": "turn-forward-live-arrived" if route_status == "arrived" else "turn-forward-live-progress-validated",
            "routeStatus": route_status,
            "blockers": [],
            "totalProgressDistance": route_result.get("totalProgressDistance"),
            "initialPlanarDistance": route_result.get("initialPlanarDistance"),
            "finalPlanarDistance": route_result.get("finalPlanarDistance"),
        }
    return {
        "status": "blocked" if step_summary.get("status") == "blocked" else "failed",
        "verdict": "forward-route-step-blocked" if step_summary.get("status") == "blocked" else "forward-route-step-failed",
        "routeStatus": route_status,
        "blockers": list(step_summary.get("blockers", [])) or [f"route-step-status:{step_summary.get('status')}"],
        "errors": list(step_summary.get("errors", [])),
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    plan = safe_mapping(safe_mapping(summary.get("turnAwarePlanSummary")).get("plan"))
    forward = safe_mapping(summary.get("forwardResult"))
    safety = safe_mapping(summary.get("safety"))
    artifacts = safe_mapping(summary.get("artifacts"))
    lines = [
        "# Static owner turn-forward experiment",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Plan",
        "",
        f"- First action: `{plan.get('firstAction')}`",
        f"- Turn magnitude: `{plan.get('turnMagnitudeClass')}`",
        f"- Execution blocked: `{plan.get('executionBlocked')}`",
        "",
        "## Forward result",
        "",
        f"- Route status: `{forward.get('routeStatus')}`",
        f"- Progress: `{forward.get('totalProgressDistance')}`",
        f"- Initial distance: `{forward.get('initialPlanarDistance')}`",
        f"- Final distance: `{forward.get('finalPlanarDistance')}`",
        "",
        "## Safety",
        "",
        f"- Movement sent: `{safety.get('movementSent')}`",
        f"- Input sent: `{safety.get('inputSent')}`",
        f"- Navigation control: `{safety.get('navigationControl')}`",
        f"- Facing promotion: `{safety.get('facingPromotion')}`",
        "",
        "## Artifacts",
        "",
        f"- Summary JSON: `{artifacts.get('summaryJson')}`",
        f"- Run directory: `{artifacts.get('runDirectory')}`",
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


def build_validation_markdown(summary: Mapping[str, Any]) -> str:
    contract = safe_mapping(summary.get("contract"))
    artifacts = safe_mapping(summary.get("artifacts"))
    lines = [
        "# Static owner turn-forward experiment validation",
        "",
        f"Status: `{summary.get('status')}`",
        f"Source summary: `{summary.get('sourceSummaryJson')}`",
        "",
        "## Contract",
        "",
        f"- Status: `{contract.get('status')}`",
        f"- Verdict: `{contract.get('verdict')}`",
        f"- Movement sent: `{contract.get('movementSent')}`",
        f"- Input sent: `{contract.get('inputSent')}`",
        f"- Navigation control: `{contract.get('navigationControl')}`",
        "",
        "## Artifacts",
        "",
        f"- Summary JSON: `{artifacts.get('summaryJson')}`",
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
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-turn-forward-experiment-{utc_stamp()}"
    child_dir = run_dir / "child-outputs"
    child_output_root = run_dir / "child-runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    errors = validate_args(args)
    safety = base_safety()
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-turn-forward-experiment",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "pending",
        "verdict": "invalid-arguments" if errors else None,
        "repoRoot": str(root),
        "operator": {
            "dryRun": bool(args.dry_run),
            "movementApproved": bool(args.movement_approved),
            "turnApproved": bool(args.turn_approved),
            "allowCandidateTurnControl": bool(args.allow_candidate_turn_control),
        },
        "input": {
            "turnHoldMilliseconds": args.turn_hold_milliseconds,
            "forwardKey": args.forward_key,
            "forwardHoldMilliseconds": args.forward_hold_milliseconds,
            "inputMode": args.input_mode,
        },
        "limits": {
            "maxInitialTurnDegrees": args.max_initial_turn_degrees,
            "maxCumulativeTurnDegrees": args.max_cumulative_turn_degrees,
            "maxObservedTurnDegrees": args.max_observed_turn_degrees,
            "maxTotalInputMilliseconds": args.max_total_input_milliseconds,
            "maxRouteSteps": args.max_route_steps,
        },
        "turnAwarePlanSummary": {},
        "turnStimulusSummary": {},
        "forwardStepSummary": {},
        "forwardResult": {},
        "contract": {},
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
    try:
        plan_child = run_child(
            label="01-turn-aware-plan",
            command=turn_plan_command(args, root, child_output_root),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=float(args.command_timeout_seconds),
        )
        summary["childCommands"].append(plan_child)
        if not isinstance(plan_child.get("json"), Mapping):
            summary["status"] = "failed"
            summary["verdict"] = "turn-aware-plan-failed"
            summary["errors"].append("turn-aware-plan-json-missing")
            return summary
        plan_summary = full_summary_from_compact(plan_child["json"])
        summary["turnAwarePlanSummary"] = plan_summary
        summary["artifacts"]["turnAwarePlanSummaryJson"] = safe_mapping(plan_child["json"]).get("summaryJson")
        if plan_summary.get("status") != "passed":
            summary["status"] = "blocked" if plan_summary.get("status") == "blocked" else "failed"
            summary["verdict"] = "turn-aware-plan-not-passed"
            summary["blockers"].extend(str(item) for item in plan_summary.get("blockers", []))
            summary["errors"].extend(str(item) for item in plan_summary.get("errors", []))
            return summary

        plan = safe_mapping(plan_summary.get("plan"))
        first_action = str(plan.get("firstAction") or "")
        if args.dry_run:
            summary["status"] = "passed"
            summary["verdict"] = "turn-forward-experiment-dry-run-plan-built"
            summary["warnings"].append("dry-run-only-no-input-sent")
            summary["contract"] = validate_turn_forward_experiment_contract(summary)
            return summary
        if first_action == "stop":
            summary["status"] = "passed"
            summary["verdict"] = "turn-forward-no-movement-needed"
            summary["warnings"].append("already-arrived-no-input-sent")
            summary["contract"] = validate_turn_forward_experiment_contract(summary)
            return summary
        if not args.movement_approved:
            summary["status"] = "blocked"
            summary["verdict"] = "movement-approval-required"
            summary["blockers"].append("movement-approved-flag-required")
            return summary

        if first_action in {"turn-left", "turn-right"}:
            if not args.allow_candidate_turn_control:
                summary["status"] = "blocked"
                summary["verdict"] = "candidate-turn-control-approval-required"
                summary["blockers"].append("allow-candidate-turn-control-flag-required")
                return summary
            if not args.turn_approved:
                summary["status"] = "blocked"
                summary["verdict"] = "turn-approval-required"
                summary["blockers"].append("turn-approved-flag-required")
                return summary
            if plan.get("executionBlocked") is True:
                summary["status"] = "blocked"
                summary["verdict"] = "turn-aware-plan-execution-blocked"
                summary["blockers"].extend(str(item) for item in plan.get("executionBlockers", []))
                return summary
            direction = "left" if first_action == "turn-left" else "right"
            turn_child = run_child(
                label="02-turn-stimulus",
                command=turn_stimulus_command(args, root, child_output_root, direction),
                cwd=root,
                child_dir=child_dir,
                timeout_seconds=float(args.command_timeout_seconds),
            )
            summary["childCommands"].append(turn_child)
            summary["safety"]["movementSent"] = True
            summary["safety"]["inputSent"] = True
            summary["safety"]["navigationControl"] = True
            if not isinstance(turn_child.get("json"), Mapping):
                summary["status"] = "failed"
                summary["verdict"] = "turn-stimulus-json-missing"
                summary["errors"].append("turn-stimulus-json-missing")
                return summary
            turn_summary = full_summary_from_compact(turn_child["json"])
            summary["turnStimulusSummary"] = turn_summary
            summary["artifacts"]["turnStimulusSummaryJson"] = safe_mapping(turn_child["json"]).get("summaryJson")
            turn_contract = validate_turn_capture_summary_contract(turn_summary)
            if turn_contract.get("status") != "passed":
                summary["status"] = "blocked" if turn_summary.get("status") == "blocked" else "failed"
                summary["verdict"] = "turn-stimulus-contract-not-passed"
                summary["blockers"].extend(str(item) for item in turn_contract.get("blockers", []))
                summary["errors"].extend(str(item) for item in turn_summary.get("errors", []))
                return summary
            observed_turn = abs(float(turn_contract.get("signedYawDeltaDegrees") or 0.0))
            if observed_turn > float(args.max_observed_turn_degrees):
                summary["status"] = "blocked"
                summary["verdict"] = "observed-turn-exceeded-max-observed-turn-degrees"
                summary["blockers"].append("observed-turn-exceeded-max-observed-turn-degrees")
                summary["turnStimulusSummary"]["observedTurnGuard"] = {
                    "observedTurnDegrees": observed_turn,
                    "maxObservedTurnDegrees": float(args.max_observed_turn_degrees),
                }
                return summary
        elif first_action != "forward":
            summary["status"] = "blocked"
            summary["verdict"] = "first-action-not-executable"
            summary["blockers"].append(f"first-action-not-executable:{first_action}")
            return summary

        forward_child = run_child(
            label="03-forward-route-step",
            command=route_step_command(args, root, child_output_root),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=float(args.command_timeout_seconds),
        )
        summary["childCommands"].append(forward_child)
        if not isinstance(forward_child.get("json"), Mapping):
            summary["status"] = "failed"
            summary["verdict"] = "forward-route-step-json-missing"
            summary["errors"].append("forward-route-step-json-missing")
            return summary
        forward_summary = full_summary_from_compact(forward_child["json"])
        summary["forwardStepSummary"] = forward_summary
        summary["artifacts"]["forwardStepSummaryJson"] = safe_mapping(forward_child["json"]).get("summaryJson")
        forward_safety = safe_mapping(forward_summary.get("safety"))
        if forward_safety.get("inputSent") is True:
            summary["safety"]["movementSent"] = True
            summary["safety"]["inputSent"] = True
            summary["safety"]["navigationControl"] = True
        forward_result = summarize_forward_result(forward_summary)
        summary["forwardResult"] = forward_result
        summary["status"] = forward_result["status"]
        summary["verdict"] = forward_result["verdict"]
        summary["blockers"].extend(str(item) for item in forward_result.get("blockers", []))
        summary["errors"].extend(str(item) for item in forward_result.get("errors", []))
        if summary["status"] == "passed":
            summary["warnings"].extend(
                [
                    "candidate-facing-yaw-not-promoted",
                    "single-step-experiment-only-not-route-loop",
                ]
            )
            summary["contract"] = validate_turn_forward_experiment_contract(summary)
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "turn-forward-experiment-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    summary["blockers"] = sorted(set(summary["blockers"]))
    summary["warnings"] = sorted(set(summary["warnings"]))
    summary["errors"] = sorted(set(summary["errors"]))
    return summary


def validate_saved_summary(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-turn-forward-experiment-contract-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    source = Path(str(args.validate_experiment_summary_json)).resolve() if args.validate_experiment_summary_json else None
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-turn-forward-experiment-contract-validation",
        "generatedAtUtc": utc_iso(),
        "status": "pending",
        "repoRoot": str(root),
        "sourceSummaryJson": str(source) if source else None,
        "contract": {},
        "blockers": [],
        "warnings": [],
        "errors": [],
        "safety": base_safety(),
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
    }
    if not source:
        summary["status"] = "failed"
        summary["errors"].append("validate-experiment-summary-json-required")
        return summary
    try:
        experiment_summary = load_json_object(source)
        contract = validate_turn_forward_experiment_contract(experiment_summary)
        summary["contract"] = contract
        summary["blockers"].extend(contract["blockers"])
        summary["warnings"].extend(contract["warnings"])
        summary["status"] = "passed" if contract["status"] == "passed" else "blocked"
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    summary["blockers"] = sorted(set(summary["blockers"]))
    summary["warnings"] = sorted(set(summary["warnings"]))
    summary["errors"] = sorted(set(summary["errors"]))
    return summary


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    plan = safe_mapping(safe_mapping(summary.get("turnAwarePlanSummary")).get("plan"))
    forward = safe_mapping(summary.get("forwardResult"))
    safety = safe_mapping(summary.get("safety"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "firstAction": plan.get("firstAction"),
        "turnMagnitudeClass": plan.get("turnMagnitudeClass"),
        "routeStatus": forward.get("routeStatus"),
        "totalProgressDistance": forward.get("totalProgressDistance"),
        "initialPlanarDistance": forward.get("initialPlanarDistance"),
        "finalPlanarDistance": forward.get("finalPlanarDistance"),
        "movementSent": safety.get("movementSent"),
        "inputSent": safety.get("inputSent"),
        "navigationControl": safety.get("navigationControl"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "turnAwarePlanSummaryJson": artifacts.get("turnAwarePlanSummaryJson"),
        "turnStimulusSummaryJson": artifacts.get("turnStimulusSummaryJson"),
        "forwardStepSummaryJson": artifacts.get("forwardStepSummaryJson"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def compact_validation(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    contract = safe_mapping(summary.get("contract"))
    return {
        "status": summary.get("status"),
        "contractStatus": contract.get("status"),
        "verdict": contract.get("verdict"),
        "movementSent": contract.get("movementSent"),
        "inputSent": contract.get("inputSent"),
        "navigationControl": contract.get("navigationControl"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one gated static-owner turn-then-forward experiment")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--validate-experiment-summary-json", nargs="?", const="")
    parser.add_argument("--current-truth-json", default="docs/recovery/current-truth.json")
    parser.add_argument("--destination-x", type=float)
    parser.add_argument("--destination-y", type=float)
    parser.add_argument("--destination-z", type=float)
    parser.add_argument("--destination-label")
    parser.add_argument("--destination-waypoint-json")
    parser.add_argument("--destination-waypoint-id")
    parser.add_argument("--arrival-radius", type=float)
    parser.add_argument("--alignment-threshold-degrees", type=float, default=7.5)
    parser.add_argument("--minimum-progress-distance", type=float, default=0.05)
    parser.add_argument("--wrong-way-tolerance-distance", type=float, default=0.75)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--interval-seconds", type=float, default=0.1)
    parser.add_argument("--turn-hold-milliseconds", type=int, default=DEFAULT_TURN_HOLD_MS)
    parser.add_argument("--forward-key", default="w")
    parser.add_argument("--forward-hold-milliseconds", type=int, default=DEFAULT_FORWARD_HOLD_MS)
    parser.add_argument("--input-mode", choices=("ScanCode", "VirtualKey"), default="ScanCode")
    parser.add_argument("--title-contains", default="RIFT")
    parser.add_argument("--focus-delay-milliseconds", type=int, default=250)
    parser.add_argument("--turn-settle-seconds", type=float, default=0.75)
    parser.add_argument("--forward-settle-seconds", type=float, default=0.75)
    parser.add_argument("--minimum-yaw-delta-degrees", type=float, default=DEFAULT_MINIMUM_YAW_DELTA_DEGREES)
    parser.add_argument("--max-turn-planar-drift", type=float, default=DEFAULT_MAX_TURN_PLANAR_DRIFT)
    parser.add_argument("--max-initial-turn-degrees", type=float, default=DEFAULT_MAX_INITIAL_TURN_DEGREES)
    parser.add_argument("--max-cumulative-turn-degrees", type=float, default=DEFAULT_MAX_CUMULATIVE_TURN_DEGREES)
    parser.add_argument("--max-observed-turn-degrees", type=float, default=DEFAULT_MAX_OBSERVED_TURN_DEGREES)
    parser.add_argument("--max-total-input-milliseconds", type=int, default=DEFAULT_MAX_TOTAL_INPUT_MS)
    parser.add_argument("--max-route-steps", type=int, default=DEFAULT_MAX_ROUTE_STEPS)
    parser.add_argument("--command-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--movement-approved", action="store_true")
    parser.add_argument("--turn-approved", action="store_true")
    parser.add_argument("--allow-candidate-turn-control", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validation_mode = args.validate_experiment_summary_json is not None
    summary = validate_saved_summary(args) if validation_mode else run(args)
    artifacts = safe_mapping(summary.get("artifacts"))
    write_json(Path(str(artifacts["summaryJson"])), summary)
    markdown = build_validation_markdown(summary) if validation_mode else build_markdown(summary)
    Path(str(artifacts["summaryMarkdown"])).write_text(markdown, encoding="utf-8")
    compact_summary = compact_validation(summary) if validation_mode else compact(summary)
    print(json.dumps(compact_summary) if args.json else json.dumps(compact_summary, indent=2))
    return 0 if summary.get("status") == "passed" else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    sys.exit(main())
