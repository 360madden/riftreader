#!/usr/bin/env python3
"""Build a dry-run turn-aware static-owner route plan.

This helper is deliberately non-mutating: it may read the promoted static owner
coordinate/facing-candidate state, but it never sends input and never promotes
candidate yaw/facing into actor truth.  Its main purpose is to make turn control
explicitly fail closed until an outer live experiment supplies separate
``--allow-candidate-turn-control`` / approval gates.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .static_owner_facing_discovery import navigation_target_from_state, resolve_navigation_target_request
    from .static_owner_nav_route_step import base_safety, load_json_object, preview, safe_mapping, write_json
    from .workflow_common import (
        full_summary_from_compact,
        repo_root,
        run_child,
        utc_iso,
        utc_stamp,
    )
except ImportError:  # pragma: no cover - direct script execution path
    from static_owner_facing_discovery import navigation_target_from_state, resolve_navigation_target_request  # type: ignore
    from static_owner_nav_route_step import base_safety, load_json_object, preview, safe_mapping, write_json  # type: ignore
    from workflow_common import (  # type: ignore
        full_summary_from_compact,
        repo_root,
        run_child,
        utc_iso,
        utc_stamp,
    )


SCHEMA_VERSION = 1
DEFAULT_ALIGNMENT_THRESHOLD_DEGREES = 7.5
DEFAULT_OPPOSITE_THRESHOLD_DEGREES = 150.0
DEFAULT_MAX_INITIAL_TURN_DEGREES = 90.0
DEFAULT_MAX_CUMULATIVE_TURN_DEGREES = 90.0
DEFAULT_MAX_TOTAL_INPUT_MS = 700
DEFAULT_MAX_ROUTE_STEPS = 1


def destination_args(args: argparse.Namespace) -> list[str]:
    parts: list[str] = []
    if args.destination_waypoint_json:
        parts += ["--destination-waypoint-json", str(args.destination_waypoint_json)]
        if args.destination_waypoint_id:
            parts += ["--destination-waypoint-id", str(args.destination_waypoint_id)]
    else:
        parts += ["--destination-x", str(args.destination_x), "--destination-z", str(args.destination_z)]
        if args.destination_y is not None:
            parts += ["--destination-y", str(args.destination_y)]
    if args.destination_label:
        parts += ["--destination-label", str(args.destination_label)]
    if args.arrival_radius is not None:
        parts += ["--arrival-radius", str(args.arrival_radius)]
    parts += ["--alignment-threshold-degrees", str(args.alignment_threshold_degrees)]
    return parts


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
    if args.state_summary_json is not None and not str(args.state_summary_json).strip():
        errors.append("state-summary-json-must-not-be-empty")
    if args.arrival_radius is not None and args.arrival_radius < 0:
        errors.append("arrival-radius-must-be-nonnegative")
    if args.alignment_threshold_degrees < 0:
        errors.append("alignment-threshold-degrees-must-be-nonnegative")
    if args.opposite_threshold_degrees <= 0 or args.opposite_threshold_degrees > 180:
        errors.append("opposite-threshold-degrees-must-be-between-zero-and-180")
    if args.max_initial_turn_degrees <= 0:
        errors.append("max-initial-turn-degrees-must-be-positive")
    if args.max_cumulative_turn_degrees <= 0:
        errors.append("max-cumulative-turn-degrees-must-be-positive")
    if args.max_total_input_milliseconds <= 0:
        errors.append("max-total-input-milliseconds-must-be-positive")
    if args.max_route_steps <= 0:
        errors.append("max-route-steps-must-be-positive")
    if args.samples < 1:
        errors.append("samples-must-be-positive")
    if args.interval_seconds < 0:
        errors.append("interval-seconds-must-be-nonnegative")
    if args.command_timeout_seconds <= 0:
        errors.append("command-timeout-seconds-must-be-positive")
    return sorted(set(errors))



def state_command(args: argparse.Namespace, root: Path) -> list[str]:
    command = [
        sys.executable,
        str(root / "scripts" / "static_owner_facing_discovery.py"),
        "state",
        "--repo-root",
        str(root),
        "--current-truth-json",
        str(args.current_truth_json),
        "--samples",
        str(args.samples),
        "--interval-seconds",
        str(args.interval_seconds),
        "--expect-stationary",
        "--json",
    ]
    if args.output_root:
        command += ["--output-root", str(args.output_root)]
    command += destination_args(args)
    return command


def load_or_read_state(args: argparse.Namespace, root: Path, child_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if args.state_summary_json:
        path = Path(str(args.state_summary_json))
        if not path.is_absolute():
            path = root / path
        return load_json_object(path), []
    state = run_child(
        label="01-state-readback",
        command=state_command(args, root),
        cwd=root,
        child_dir=child_dir,
        timeout_seconds=float(args.command_timeout_seconds),
    )
    if not state["ok"] or not isinstance(state.get("json"), Mapping):
        raise RuntimeError("state-readback-failed")
    return full_summary_from_compact(state["json"]), [state]


def turn_magnitude_class(
    navigation_target: Mapping[str, Any],
    *,
    opposite_threshold_degrees: float = DEFAULT_OPPOSITE_THRESHOLD_DEGREES,
) -> str:
    if navigation_target.get("withinArrivalRadius") is True:
        return "arrived"
    absolute_delta = float(navigation_target.get("absoluteBearingDeltaDegrees") or 0.0)
    if navigation_target.get("withinAlignmentThreshold") is True:
        return "aligned" if absolute_delta == 0 else "small-angle"
    if absolute_delta >= float(opposite_threshold_degrees):
        return "opposite-facing"
    return "turn-needed"


def build_turn_control_gate(
    navigation_target: Mapping[str, Any],
    *,
    allow_candidate_turn_control: bool,
    max_initial_turn_degrees: float,
    max_cumulative_turn_degrees: float,
    max_total_input_milliseconds: int,
    max_route_steps: int,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    absolute_delta = float(navigation_target.get("absoluteBearingDeltaDegrees") or 0.0)
    turn_direction = str(navigation_target.get("suggestedTurnDirection") or "unknown")
    turn_required = navigation_target.get("withinArrivalRadius") is not True and turn_direction in {"left", "right"}
    if turn_required:
        if not allow_candidate_turn_control:
            blockers.append("candidate-turn-control-not-enabled")
        if max_route_steps > DEFAULT_MAX_ROUTE_STEPS:
            blockers.append("multi-step-turn-aware-routing-not-enabled")
        if absolute_delta > float(max_initial_turn_degrees):
            blockers.append("initial-turn-exceeds-max-initial-turn-degrees")
        if absolute_delta > float(max_cumulative_turn_degrees):
            blockers.append("initial-turn-exceeds-max-cumulative-turn-degrees")
    else:
        warnings.append("turn-control-not-required-for-current-plan")
    if max_route_steps > DEFAULT_MAX_ROUTE_STEPS:
        warnings.append("multi-step-turn-aware-routing-not-enabled-by-default")
    return {
        "status": "blocked" if blockers else "passed" if turn_required else "not-required",
        "candidateOnly": True,
        "allowCandidateTurnControl": bool(allow_candidate_turn_control),
        "turnRequired": turn_required,
        "turnDirection": turn_direction if turn_required else None,
        "absoluteBearingDeltaDegrees": absolute_delta,
        "maxInitialTurnDegrees": float(max_initial_turn_degrees),
        "maxCumulativeTurnDegrees": float(max_cumulative_turn_degrees),
        "maxTotalInputMilliseconds": int(max_total_input_milliseconds),
        "maxRouteSteps": int(max_route_steps),
        "movementPermission": False,
        "navigationControl": False,
        "facingPromotion": False,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
    }


def _read_nav_state(
    *,
    root: Path,
    current_truth_json: str = "docs/recovery/current-truth.json",
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Run a pointer-chain nav-state readback and return the parsed payload.

    Delegates to the shared nav_state_readback helper.
    """
    try:
        from .nav_state_readback import read_nav_state
    except ImportError:  # pragma: no cover - direct script execution path
        from nav_state_readback import read_nav_state  # type: ignore
    result = read_nav_state(
        root=root,
        use_current_truth=True,
        current_truth_json=current_truth_json,
        timeout_seconds=timeout_seconds,
    )
    return {
        "ok": result["ok"],
        "exitCode": result["exitCode"],
        "status": result["status"],
        "verdict": result["verdict"],
        "navState": safe_mapping(result["rawJson"].get("navState")) if result["rawJson"] else {},
        "yawDegrees": result["yawDegrees"],
        "turnRate0x304": result["turnRate0x304"],
        "turnRateClassification": result["turnRateClassification"],
        "stderrPreview": result["stderrPreview"],
        "error": result.get("error"),
    }


def _build_nav_state_cross_check(
    latest_state: Mapping[str, Any],
    nav_state_readback: dict[str, Any] | None,
) -> dict[str, Any]:
    """Cross-check pointer-chain nav-state against facing-discovery state."""
    if nav_state_readback is None or not nav_state_readback.get("ok"):
        return {
            "available": False,
            "status": "unavailable",
            "reason": nav_state_readback.get("error", "readback-not-requested") if nav_state_readback else "readback-not-requested",
            "candidateOnly": True,
            "actionableForNavigation": False,
        }

    ptr_yaw = nav_state_readback.get("yawDegrees")
    ptr_turn = nav_state_readback.get("turnRate0x304")
    ptr_class = str(nav_state_readback.get("turnRateClassification") or "unknown")

    fd_class = str(latest_state.get("turnRateClassification") or "unknown")
    fd_turn = latest_state.get("turnRateDiscriminator")
    fd_yaw = latest_state.get("yawDegrees")

    warnings: list[str] = []
    agreements: list[str] = []

    # Compare turn-rate classifications
    if ptr_class != "unknown" and fd_class != "unknown":
        if ptr_class == fd_class:
            agreements.append(f"turn-rate-classification-agrees:{ptr_class}")
        else:
            warnings.append(f"turn-rate-classification-disagrees:pointer-chain={ptr_class},facing-discovery={fd_class}")

    # Compare turn-rate discriminator values (0x304)
    if isinstance(ptr_turn, (int, float)) and isinstance(fd_turn, (int, float)):
        turn_delta = abs(float(ptr_turn) - float(fd_turn))
        if turn_delta < 0.01:
            agreements.append(f"turn-rate-discriminator-agrees:delta={turn_delta:.4f}")
        elif turn_delta < 0.5:
            warnings.append(f"turn-rate-discriminator-close:delta={turn_delta:.4f}")
        else:
            warnings.append(f"turn-rate-discriminator-diverges:delta={turn_delta:.4f},pointer-chain={ptr_turn:.4f},facing-discovery={fd_turn:.4f}")

    # Compare yaw values
    if isinstance(ptr_yaw, (int, float)) and isinstance(fd_yaw, (int, float)):
        yaw_delta = abs(float(ptr_yaw) - float(fd_yaw))
        if yaw_delta < 1.0:
            agreements.append(f"yaw-agrees:delta={yaw_delta:.2f}deg")
        elif yaw_delta < 5.0:
            warnings.append(f"yaw-close:delta={yaw_delta:.2f}deg")
        else:
            warnings.append(f"yaw-diverges:delta={yaw_delta:.2f}deg,pointer-chain={ptr_yaw:.2f},facing-discovery={fd_yaw:.2f}")

    return {
        "available": True,
        "status": "dissonance" if warnings else "agreement",
        "agreements": agreements,
        "warnings": warnings,
        "pointerChain": {
            "yawDegrees": ptr_yaw,
            "turnRate0x304": ptr_turn,
            "turnRateClassification": ptr_class,
        },
        "facingDiscovery": {
            "yawDegrees": fd_yaw,
            "turnRateDiscriminator": fd_turn,
            "turnRateClassification": fd_class,
        },
        "candidateOnly": True,
        "actionableForNavigation": False,
    }


def build_turn_aware_plan(
    latest_state: Mapping[str, Any],
    target_request: Mapping[str, Any],
    *,
    allow_candidate_turn_control: bool = False,
    max_initial_turn_degrees: float = DEFAULT_MAX_INITIAL_TURN_DEGREES,
    max_cumulative_turn_degrees: float = DEFAULT_MAX_CUMULATIVE_TURN_DEGREES,
    max_total_input_milliseconds: int = DEFAULT_MAX_TOTAL_INPUT_MS,
    max_route_steps: int = DEFAULT_MAX_ROUTE_STEPS,
    opposite_threshold_degrees: float = DEFAULT_OPPOSITE_THRESHOLD_DEGREES,
    nav_state_readback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    navigation_target = navigation_target_from_state(
        latest_state,
        destination_x=float(target_request["destinationX"]),
        destination_y=None if target_request.get("destinationY") is None else float(target_request["destinationY"]),
        destination_z=float(target_request["destinationZ"]),
        destination_label=target_request.get("destinationLabel"),
        arrival_radius=float(target_request["arrivalRadius"]),
        alignment_threshold_degrees=float(target_request["alignmentThresholdDegrees"]),
    )
    magnitude = turn_magnitude_class(navigation_target, opposite_threshold_degrees=opposite_threshold_degrees)
    suggested_turn = str(navigation_target.get("suggestedTurnDirection") or "")
    if magnitude == "arrived":
        first_action = "stop"
        control_intent = "stop"
        reason = "within-arrival-radius"
    elif suggested_turn == "aligned":
        first_action = "forward"
        control_intent = "forward"
        reason = "bearing-within-alignment-threshold"
    elif suggested_turn in {"left", "right"}:
        first_action = f"turn-{suggested_turn}"
        control_intent = first_action
        reason = "candidate-bearing-requires-turn"
    else:
        first_action = "blocked"
        control_intent = "blocked"
        reason = "suggested-turn-direction-unrecognized"

    gate = build_turn_control_gate(
        navigation_target,
        allow_candidate_turn_control=allow_candidate_turn_control,
        max_initial_turn_degrees=max_initial_turn_degrees,
        max_cumulative_turn_degrees=max_cumulative_turn_degrees,
        max_total_input_milliseconds=max_total_input_milliseconds,
        max_route_steps=max_route_steps,
    )
    execution_blockers = list(gate["blockers"]) if first_action.startswith("turn-") else []

    # Cross-check atan2-derived turn direction against the engine's 0x304 turn rate.
    # 0x304 sign-flip pattern: positive = left turn, negative = right turn.
    # This is a single 4-byte float read vs. the full atan2 (6 floats, 24 bytes).
    engine_turn_classification = str(latest_state.get("turnRateClassification") or "unknown")
    if engine_turn_classification == "unknown":
        gate.setdefault("warnings", []).append("turn-rate-discriminator-unavailable-stale-or-old-state-format")
    if suggested_turn in {"left", "right"} and engine_turn_classification in {"left", "right"}:
        if suggested_turn != engine_turn_classification:
            conflict_msg = (
                f"turn-direction-mismatch-atan2-wants-{suggested_turn}"
                f"-but-engine-0x304-is-turning-{engine_turn_classification}"
            )
            gate["blockers"].append(conflict_msg)
            gate["blockers"] = sorted(set(gate["blockers"]))
            gate["status"] = "blocked"
            execution_blockers.append(conflict_msg)

    nav_cross_check = _build_nav_state_cross_check(latest_state, nav_state_readback)
    return {
        "status": "passed",
        "candidateOnly": True,
        "dryRunOnly": True,
        "actionableForNavigation": False,
        "movementPermission": False,
        "navigationControl": False,
        "facingPromotion": False,
        "requiresFreshPreflightBeforeLiveUse": True,
        "firstAction": first_action,
        "controlIntent": control_intent,
        "reason": reason,
        "turnMagnitudeClass": magnitude,
        "engineTurnRateClassification": engine_turn_classification,
        "engineTurnRateDiscriminator": latest_state.get("turnRateDiscriminator"),
        "executionBlocked": bool(execution_blockers),
        "executionBlockers": sorted(set(execution_blockers)),
        "navigationTarget": navigation_target,
        "turnControlGate": gate,
        "navStateCrossCheck": nav_cross_check,
    }


def validate_turn_aware_plan_contract(summary: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if summary.get("kind") != "static-owner-turn-aware-route-plan":
        blockers.append("plan-kind-must-be-static-owner-turn-aware-route-plan")
    if summary.get("status") != "passed":
        blockers.append("plan-status-must-be-passed")
    if summary.get("verdict") != "turn-aware-route-plan-built":
        blockers.append("plan-verdict-must-be-turn-aware-route-plan-built")
    plan = safe_mapping(summary.get("plan"))
    if plan.get("candidateOnly") is not True:
        blockers.append("plan-candidate-only-must-be-true")
    if plan.get("dryRunOnly") is not True:
        blockers.append("plan-dry-run-only-must-be-true")
    if plan.get("movementPermission") is not False:
        blockers.append("plan-movement-permission-must-be-false")
    if plan.get("navigationControl") is not False:
        blockers.append("plan-navigation-control-must-be-false")
    if plan.get("facingPromotion") is not False:
        blockers.append("plan-facing-promotion-must-be-false")

    safety = safe_mapping(summary.get("safety"))
    if safety.get("movementSent") is not False:
        blockers.append("safety-movement-sent-must-be-false")
    if safety.get("inputSent") is not False:
        blockers.append("safety-input-sent-must-be-false")
    for key in ("noCheatEngine",):
        if safety.get(key) is not True:
            blockers.append(f"safety-{key}-must-be-true")
    for key in (
        "x64dbgAttach",
        "debuggerAttached",
        "providerWrites",
        "gitMutation",
        "proofPromotion",
        "actorChainPromotion",
        "facingPromotion",
        "navigationControl",
        "savedVariablesUsedAsLiveTruth",
    ):
        if safety.get(key) is not False:
            blockers.append(f"safety-{key}-must-be-false")

    gate = safe_mapping(plan.get("turnControlGate"))
    if plan.get("firstAction") in {"turn-left", "turn-right"} and gate.get("allowCandidateTurnControl") is not True:
        if gate.get("status") != "blocked":
            blockers.append("candidate-turn-control-must-block-when-not-enabled")
        if "candidate-turn-control-not-enabled" not in gate.get("blockers", []):
            blockers.append("candidate-turn-control-blocker-required")
    if plan.get("turnMagnitudeClass") == "opposite-facing":
        warnings.append("opposite-facing-plan-is-dry-run-only")
    return {
        "status": "blocked" if blockers else "passed",
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "firstAction": plan.get("firstAction"),
        "turnMagnitudeClass": plan.get("turnMagnitudeClass"),
        "engineTurnRateClassification": plan.get("engineTurnRateClassification"),
        "executionBlocked": plan.get("executionBlocked"),
        "turnControlGateStatus": gate.get("status"),
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    plan = safe_mapping(summary.get("plan"))
    target = safe_mapping(plan.get("navigationTarget"))
    gate = safe_mapping(plan.get("turnControlGate"))
    artifacts = safe_mapping(summary.get("artifacts"))
    lines = [
        "# Static owner turn-aware route plan",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Plan",
        "",
        f"- First action: `{plan.get('firstAction')}`",
        f"- Turn magnitude: `{plan.get('turnMagnitudeClass')}`",
        f"- Suggested turn: `{target.get('suggestedTurnDirection')}`",
        f"- Signed bearing delta: `{target.get('signedBearingDeltaDegrees')}`",
        f"- Planar distance: `{target.get('planarDistance')}`",
        f"- Execution blocked: `{plan.get('executionBlocked')}`",
        f"- Gate status: `{gate.get('status')}`",
        "",
        "Dry-run only; no input, no movement, and no facing/actor/proof promotion.",
        "",
        "## Artifacts",
        "",
        f"- Summary JSON: `{artifacts.get('summaryJson')}`",
        f"- Run directory: `{artifacts.get('runDirectory')}`",
    ]
    # Pointer-chain nav-state cross-check section
    cross_check = safe_mapping(plan.get("navStateCrossCheck"))
    if cross_check.get("available"):
        ptr_chain = safe_mapping(cross_check.get("pointerChain"))
        fd = safe_mapping(cross_check.get("facingDiscovery"))
        lines.extend([
            "",
            "## Pointer-chain nav-state cross-check (candidate-only)",
            "",
            f"- Status: `{cross_check.get('status')}`",
            f"- Pointer-chain yaw: `{ptr_chain.get('yawDegrees')}`",
            f"- Pointer-chain turn rate: `{ptr_chain.get('turnRateClassification')}`",
            f"- Facing-discovery yaw: `{fd.get('yawDegrees')}`",
            f"- Facing-discovery turn rate: `{fd.get('turnRateClassification')}`",
        ])
        if cross_check.get("agreements"):
            lines.append("")
            lines.extend(f"- :white_check_mark: {a}" for a in cross_check.get("agreements", []))
        if cross_check.get("warnings"):
            lines.append("")
            lines.extend(f"- :warning: {w}" for w in cross_check.get("warnings", []))
        lines.extend([
            "",
            "> **Note:** Pointer-chain nav-state is candidate-only and not used for auto-turn control.",
        ])
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
        "# Static owner turn-aware route plan validation",
        "",
        f"Status: `{summary.get('status')}`",
        f"Source summary: `{summary.get('sourceSummaryJson')}`",
        "",
        "## Contract",
        "",
        f"- Status: `{contract.get('status')}`",
        f"- First action: `{contract.get('firstAction')}`",
        f"- Turn magnitude: `{contract.get('turnMagnitudeClass')}`",
        f"- Gate status: `{contract.get('turnControlGateStatus')}`",
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
    run_dir = output_root / f"static-owner-turn-aware-route-plan-{utc_stamp()}"
    child_dir = run_dir / "child-outputs"
    run_dir.mkdir(parents=True, exist_ok=True)
    errors = validate_args(args)
    safety = base_safety()
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-turn-aware-route-plan",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "pending",
        "verdict": "invalid-arguments" if errors else None,
        "repoRoot": str(root),
        "operator": {
            "dryRun": True,
            "allowCandidateTurnControl": bool(args.allow_candidate_turn_control),
        },
        "inputLimits": {
            "maxInitialTurnDegrees": args.max_initial_turn_degrees,
            "maxCumulativeTurnDegrees": args.max_cumulative_turn_degrees,
            "maxTotalInputMilliseconds": args.max_total_input_milliseconds,
            "maxRouteSteps": args.max_route_steps,
        },
        "sourceStateSummary": {},
        "navigationTargetRequest": {},
        "plan": {},
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
        state_summary, children = load_or_read_state(args, root, child_dir)
        summary["childCommands"].extend(children)
        summary["sourceStateSummary"] = {
            "path": str(Path(str(args.state_summary_json)).resolve()) if args.state_summary_json else safe_mapping(children[0].get("json")).get("summaryJson") if children else None,
            "kind": state_summary.get("kind"),
            "status": state_summary.get("status"),
            "verdict": state_summary.get("verdict"),
            "generatedAtUtc": state_summary.get("generatedAtUtc"),
        }
        if state_summary.get("status") != "passed":
            summary["status"] = "blocked"
            summary["verdict"] = "state-summary-not-passed"
            summary["blockers"].append("state-summary-not-passed")
            return summary
        latest_state = safe_mapping(state_summary.get("latestState"))
        if not latest_state or not latest_state.get("coordinate") or latest_state.get("yawDegrees") is None:
            raise ValueError("state-summary-missing-latest-state-coordinate-or-yaw")
        target_request = resolve_navigation_target_request(args, root)
        if not target_request:
            raise ValueError("navigation-target-required")
        summary["navigationTargetRequest"] = target_request

        # Optional pointer-chain nav-state cross-check
        nav_state_readback: dict[str, Any] | None = None
        if args.nav_state:
            nav_state_readback = _read_nav_state(
                root=root,
                current_truth_json=str(args.current_truth_json),
                timeout_seconds=float(args.command_timeout_seconds),
            )

        summary["plan"] = build_turn_aware_plan(
            latest_state,
            target_request,
            allow_candidate_turn_control=bool(args.allow_candidate_turn_control),
            max_initial_turn_degrees=float(args.max_initial_turn_degrees),
            max_cumulative_turn_degrees=float(args.max_cumulative_turn_degrees),
            max_total_input_milliseconds=int(args.max_total_input_milliseconds),
            max_route_steps=int(args.max_route_steps),
            opposite_threshold_degrees=float(args.opposite_threshold_degrees),
            nav_state_readback=nav_state_readback,
        )
        summary["contract"] = validate_turn_aware_plan_contract(summary | {"status": "passed", "verdict": "turn-aware-route-plan-built"})
        summary["status"] = "passed"
        summary["verdict"] = "turn-aware-route-plan-built"
        summary["warnings"].extend(
            [
                "dry-run-only-no-input-sent",
                "candidate-facing-yaw-not-promoted",
                "fresh-exact-target-readback-required-before-live-use",
            ]
        )
        summary["warnings"].extend(summary["contract"]["warnings"])
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "turn-aware-route-plan-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    summary["blockers"] = sorted(set(summary["blockers"]))
    summary["warnings"] = sorted(set(summary["warnings"]))
    summary["errors"] = sorted(set(summary["errors"]))
    return summary


def validate_saved_summary(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-turn-aware-route-plan-contract-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    source = Path(str(args.validate_plan_summary_json)).resolve() if args.validate_plan_summary_json else None
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-turn-aware-route-plan-contract-validation",
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
        summary["errors"].append("validate-plan-summary-json-required")
        return summary
    try:
        plan_summary = load_json_object(source)
        contract = validate_turn_aware_plan_contract(plan_summary)
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
    plan = safe_mapping(summary.get("plan"))
    target = safe_mapping(plan.get("navigationTarget"))
    gate = safe_mapping(plan.get("turnControlGate"))
    cross_check = safe_mapping(plan.get("navStateCrossCheck"))
    result = {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "firstAction": plan.get("firstAction"),
        "turnMagnitudeClass": plan.get("turnMagnitudeClass"),
        "suggestedTurnDirection": target.get("suggestedTurnDirection"),
        "signedBearingDeltaDegrees": target.get("signedBearingDeltaDegrees"),
        "absoluteBearingDeltaDegrees": target.get("absoluteBearingDeltaDegrees"),
        "planarDistance": target.get("planarDistance"),
        "executionBlocked": plan.get("executionBlocked"),
        "executionBlockers": plan.get("executionBlockers", []),
        "turnControlGateStatus": gate.get("status"),
        "engineTurnRateClassification": plan.get("engineTurnRateClassification"),
        "movementSent": safe_mapping(summary.get("safety")).get("movementSent"),
        "inputSent": safe_mapping(summary.get("safety")).get("inputSent"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }
    if cross_check.get("available"):
        result["navStateCrossCheck"] = {
            "status": cross_check.get("status"),
            "agreements": cross_check.get("agreements", []),
            "warnings": cross_check.get("warnings", []),
            "ptrYaw": cross_check.get("pointerChain", {}).get("yawDegrees"),
            "ptrTurnClass": cross_check.get("pointerChain", {}).get("turnRateClassification"),
        }
    return result


def compact_validation(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    contract = safe_mapping(summary.get("contract"))
    return {
        "status": summary.get("status"),
        "contractStatus": contract.get("status"),
        "firstAction": contract.get("firstAction"),
        "turnMagnitudeClass": contract.get("turnMagnitudeClass"),
        "executionBlocked": contract.get("executionBlocked"),
        "turnControlGateStatus": contract.get("turnControlGateStatus"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a dry-run turn-aware static-owner route plan")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--validate-plan-summary-json", nargs="?", const="")
    parser.add_argument("--current-truth-json", default="docs/recovery/current-truth.json")
    parser.add_argument("--state-summary-json")
    parser.add_argument("--destination-x", type=float)
    parser.add_argument("--destination-y", type=float)
    parser.add_argument("--destination-z", type=float)
    parser.add_argument("--destination-label")
    parser.add_argument("--destination-waypoint-json")
    parser.add_argument("--destination-waypoint-id")
    parser.add_argument("--arrival-radius", type=float)
    parser.add_argument("--alignment-threshold-degrees", type=float, default=DEFAULT_ALIGNMENT_THRESHOLD_DEGREES)
    parser.add_argument("--opposite-threshold-degrees", type=float, default=DEFAULT_OPPOSITE_THRESHOLD_DEGREES)
    parser.add_argument("--allow-candidate-turn-control", action="store_true")
    parser.add_argument("--max-initial-turn-degrees", type=float, default=DEFAULT_MAX_INITIAL_TURN_DEGREES)
    parser.add_argument("--max-cumulative-turn-degrees", type=float, default=DEFAULT_MAX_CUMULATIVE_TURN_DEGREES)
    parser.add_argument("--max-total-input-milliseconds", type=int, default=DEFAULT_MAX_TOTAL_INPUT_MS)
    parser.add_argument("--max-route-steps", type=int, default=DEFAULT_MAX_ROUTE_STEPS)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--interval-seconds", type=float, default=0.1)
    parser.add_argument("--command-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--dry-run", action="store_true", help="Accepted for interface clarity; this helper is always dry-run.")
    parser.add_argument("--nav-state", action="store_true", help="Run pointer-chain nav-state readback for cross-check against facing discovery.")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validation_mode = args.validate_plan_summary_json is not None
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
