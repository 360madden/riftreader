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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .static_owner_facing_discovery import navigation_target_from_state, resolve_navigation_target_request
    from .static_owner_nav_route_step import base_safety, load_json_object, preview, safe_mapping, write_json
except ImportError:  # pragma: no cover - direct script execution path
    from static_owner_facing_discovery import navigation_target_from_state, resolve_navigation_target_request  # type: ignore
    from static_owner_nav_route_step import base_safety, load_json_object, preview, safe_mapping, write_json  # type: ignore


SCHEMA_VERSION = 1
DEFAULT_ALIGNMENT_THRESHOLD_DEGREES = 7.5
DEFAULT_OPPOSITE_THRESHOLD_DEGREES = 150.0
DEFAULT_MAX_INITIAL_TURN_DEGREES = 90.0
DEFAULT_MAX_CUMULATIVE_TURN_DEGREES = 90.0
DEFAULT_MAX_TOTAL_INPUT_MS = 700
DEFAULT_MAX_ROUTE_STEPS = 1


def utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


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


def full_summary_from_compact(compact: Mapping[str, Any]) -> dict[str, Any]:
    path = compact.get("summaryJson")
    if not path:
        raise ValueError("child-compact-summary-json-missing")
    return load_json_object(str(path))


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
        "executionBlocked": bool(execution_blockers),
        "executionBlockers": sorted(set(execution_blockers)),
        "navigationTarget": navigation_target,
        "turnControlGate": gate,
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
        summary["plan"] = build_turn_aware_plan(
            latest_state,
            target_request,
            allow_candidate_turn_control=bool(args.allow_candidate_turn_control),
            max_initial_turn_degrees=float(args.max_initial_turn_degrees),
            max_cumulative_turn_degrees=float(args.max_cumulative_turn_degrees),
            max_total_input_milliseconds=int(args.max_total_input_milliseconds),
            max_route_steps=int(args.max_route_steps),
            opposite_threshold_degrees=float(args.opposite_threshold_degrees),
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
    return {
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
        "movementSent": safe_mapping(summary.get("safety")).get("movementSent"),
        "inputSent": safe_mapping(summary.get("safety")).get("inputSent"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
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
