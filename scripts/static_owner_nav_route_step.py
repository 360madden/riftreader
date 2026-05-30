#!/usr/bin/env python3
"""Run one bounded static-owner navigation route step.

This helper is intentionally narrow:

* it reads the promoted static owner-coordinate/facing candidate state before
  and after a step;
* it only sends one configured C# SendInput ScanCode key when
  ``--movement-approved`` is supplied;
* it refuses to turn from candidate-only facing/yaw evidence;
* it writes durable JSON/Markdown evidence and child command envelopes.

It does not run ProofOnly, attach x64dbg, use Cheat Engine, write provider
repos, promote facing/actor truth, or push Git state.
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


SCHEMA_VERSION = 1
DEFAULT_KEY = "w"
DEFAULT_HOLD_MS = 250
PASS_ROUTE_STATUSES = {"progress", "arrived"}
BLOCK_ROUTE_STATUSES = {"no-progress", "wrong-way", "overshot"}
NO_PROGRESS_SUB_CLASSIFICATIONS = {
    "blocked-stationary-no-movement": "Player position did not change — likely blocked by terrain or obstacle",
    "drifted-back-after-initial-progress": "Player initially moved forward then drifted back — terrain may have redirected",
    "insufficient-progress-below-threshold": "Player moved slightly but did not meet the minimum progress threshold",
    "minimum-progress-not-met": "Progress below minimum threshold (no sub-classification available)",
}


def utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def safe_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def preview(text: str, *, limit: int = 2000) -> str:
    return text if len(text) <= limit else text[:limit] + "...<truncated>"


def load_json_object(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON file is not an object: {path}")
    return data


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def base_safety() -> dict[str, Any]:
    return {
        "movementSent": False,
        "inputSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "noCheatEngine": True,
        "x64dbgAttach": False,
        "debuggerAttached": False,
        "providerWrites": False,
        "gitMutation": False,
        "proofPromotion": False,
        "actorChainPromotion": False,
        "facingPromotion": False,
        "navigationControl": False,
        "savedVariablesUsedAsLiveTruth": False,
        "navStateCandidateOnly": True,
        "actionableForNavigation": False,
    }


def _read_nav_state(*, root: Path, current_truth_json: str, command_timeout_seconds: float, repo_root_path: str | None = None) -> dict[str, Any]:
    """Run the promoted static resolver with --nav-state as a read-only subprocess.

    Delegates to the shared nav_state_readback helper. Returns a dict with
    keys: ok, json, stdoutPreview, stderrPreview, error — compatible with
    the existing enrich_decision_with_nav_state() consumer.
    """
    from scripts.nav_state_readback import read_nav_state
    repo = Path(repo_root_path).resolve() if repo_root_path else root
    result = read_nav_state(
        root=repo,
        use_current_truth=True,
        current_truth_json=current_truth_json,
        timeout_seconds=command_timeout_seconds,
    )
    return {
        "ok": result["ok"],
        "exitCode": result["exitCode"],
        "json": result.get("rawJson"),
        "jsonParseError": None if result.get("rawJson") else result.get("error"),
        "stdoutPreview": result["stdoutPreview"],
        "stderrPreview": result["stderrPreview"],
        "error": result.get("error"),
    }


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
    if args.arrival_radius is not None and args.arrival_radius < 0:
        errors.append("arrival-radius-must-be-nonnegative")
    if args.alignment_threshold_degrees < 0:
        errors.append("alignment-threshold-degrees-must-be-nonnegative")
    if args.samples < 1:
        errors.append("samples-must-be-positive")
    if args.interval_seconds < 0:
        errors.append("interval-seconds-must-be-nonnegative")
    if args.hold_milliseconds <= 0:
        errors.append("hold-milliseconds-must-be-positive")
    if args.settle_seconds < 0:
        errors.append("settle-seconds-must-be-nonnegative")
    if args.command_timeout_seconds <= 0:
        errors.append("command-timeout-seconds-must-be-positive")
    return errors


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
    result = subprocess.run(
        list(command),
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    duration = time.perf_counter() - started
    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")
    parsed: Any = None
    parse_error: str | None = None
    if result.stdout.strip():
        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            parse_error = f"JSONDecodeError:{exc}"
    envelope = {
        "label": label,
        "command": list(command),
        "cwd": str(cwd),
        "startedAtUtc": started_utc,
        "endedAtUtc": utc_iso(),
        "durationSeconds": duration,
        "exitCode": result.returncode,
        "ok": result.returncode == 0,
        "stdoutPath": str(stdout_path),
        "stderrPath": str(stderr_path),
        "stdoutPreview": preview(result.stdout),
        "stderrPreview": preview(result.stderr),
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


def enrich_decision_with_nav_state(decision: dict[str, Any], nav_state_result: dict[str, Any] | None) -> dict[str, Any]:
    """Enrich an initial-step decision with live pointer-chain nav-state data.

    Reads yaw, turn rate, and facing target from the nav-state payload and
    attaches them to the decision for correlation with navigation-target bearing.
    Does NOT change the decision status — nav-state is candidate-only evidence.
    """
    decision["navStateAvailable"] = False
    decision["navStateError"] = None
    if nav_state_result is None:
        return decision
    if not nav_state_result.get("ok"):
        decision["navStateAvailable"] = False
        decision["navStateError"] = nav_state_result.get("error") or nav_state_result.get("jsonParseError") or "nav-state-readback-not-ok"
        return decision
    nav_json = safe_mapping(nav_state_result.get("json"))
    if nav_json.get("status") in ("unavailable", "readback-failed", "parse-error"):
        decision["navStateAvailable"] = False
        decision["navStateError"] = f"nav-state-status:{nav_json.get('status')}"
        return decision
    nav = safe_mapping(nav_json.get("navState"))
    decision["navStateAvailable"] = True
    decision["navStateYawDegrees"] = nav.get("yawDegrees")
    decision["navStatePitchDegrees"] = nav.get("pitchDegrees")
    decision["navStateTurnRate0x304"] = nav.get("turnRate0x304")
    decision["navStateTurnRateClassification"] = nav.get("turnRateClassification")
    decision["navStateFacingTargetCoordinate"] = nav.get("facingTargetCoordinate")
    decision["navStateOwnerAddress"] = nav_json.get("reads", {}).get("ownerAddress") if isinstance(nav_json.get("reads"), Mapping) else None
    # Cross-check: if turn rate says turning right and nav target says turn left, surface dissonance
    suggested_turn = str(decision.get("suggestedTurnDirection") or "")
    turn_class = str(nav.get("turnRateClassification") or "")
    if suggested_turn and turn_class and suggested_turn != "aligned":
        if (suggested_turn == "left" and turn_class == "right") or (suggested_turn == "right" and turn_class == "left"):
            decision["navStateTurnRateDissonance"] = f"nav-target:{suggested_turn}-vs-engine:{turn_class}"
    return decision


def classify_initial_step(pre_state: Mapping[str, Any]) -> dict[str, Any]:
    navigation_target = safe_mapping(pre_state.get("navigationTarget"))
    if not navigation_target:
        return {
            "status": "blocked",
            "reason": "pre-state-navigation-target-missing",
            "movementRequired": False,
            "controlIntent": "blocked",
        }
    if navigation_target.get("withinArrivalRadius") is True:
        return {
            "status": "passed",
            "reason": "already-within-arrival-radius",
            "movementRequired": False,
            "controlIntent": "stop",
            "suggestedTurnDirection": navigation_target.get("suggestedTurnDirection"),
            "planarDistance": navigation_target.get("planarDistance"),
        }
    suggested_turn = str(navigation_target.get("suggestedTurnDirection") or "")
    if suggested_turn != "aligned":
        return {
            "status": "blocked",
            "reason": f"initial-bearing-not-aligned:{suggested_turn or 'unknown'}",
            "movementRequired": False,
            "controlIntent": "blocked-candidate-turn-not-implemented",
            "suggestedTurnDirection": suggested_turn,
            "signedBearingDeltaDegrees": navigation_target.get("signedBearingDeltaDegrees"),
            "absoluteBearingDeltaDegrees": navigation_target.get("absoluteBearingDeltaDegrees"),
            "planarDistance": navigation_target.get("planarDistance"),
        }
    return {
        "status": "passed",
        "reason": "initial-bearing-aligned-forward-step-eligible",
        "movementRequired": True,
        "controlIntent": "forward",
        "suggestedTurnDirection": suggested_turn,
        "signedBearingDeltaDegrees": navigation_target.get("signedBearingDeltaDegrees"),
        "absoluteBearingDeltaDegrees": navigation_target.get("absoluteBearingDeltaDegrees"),
        "planarDistance": navigation_target.get("planarDistance"),
    }


def classify_route_result(route_summary: Mapping[str, Any], validation_summary: Mapping[str, Any]) -> dict[str, Any]:
    analysis = safe_mapping(route_summary.get("analysis"))
    controller = safe_mapping(route_summary.get("controllerRecommendation"))
    validation_contract = safe_mapping(validation_summary.get("contract"))
    blockers: list[str] = []
    route_status = str(analysis.get("status") or "unknown")
    if validation_summary.get("status") != "passed":
        blockers.append("route-contract-validation-not-passed")
    if route_status in BLOCK_ROUTE_STATUSES:
        if route_status == "no-progress":
            sub_classification = analysis.get("noProgressSubClassification") or "minimum-progress-not-met"
            sub_label = NO_PROGRESS_SUB_CLASSIFICATIONS.get(sub_classification, sub_classification)
            blockers.append(f"route-step-no-progress:{sub_classification}")
        else:
            blockers.append(f"route-step-{route_status}")
    elif route_status not in PASS_ROUTE_STATUSES:
        blockers.append(f"route-step-status-unrecognized:{route_status}")
    return {
        "status": "blocked" if blockers else "passed",
        "routeStatus": route_status,
        "stopReason": analysis.get("stopReason"),
        "noProgressSubClassification": analysis.get("noProgressSubClassification") if route_status == "no-progress" else None,
        "controllerRecommendedAction": controller.get("recommendedAction"),
        "controllerControlIntent": controller.get("controlIntent"),
        "totalProgressDistance": analysis.get("totalProgressDistance"),
        "initialPlanarDistance": analysis.get("initialPlanarDistance"),
        "finalPlanarDistance": analysis.get("finalPlanarDistance"),
        "contractStatus": validation_summary.get("status"),
        "contractMovementPermission": validation_contract.get("movementPermission"),
        "blockers": blockers,
    }


def validate_route_step_summary_contract(step_summary: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if step_summary.get("kind") != "static-owner-nav-route-step":
        blockers.append("route-step-kind-must-be-static-owner-nav-route-step")
    if step_summary.get("status") != "passed":
        blockers.append("route-step-status-must-be-passed")
    if step_summary.get("verdict") != "route-step-live-movement-progress-validated":
        blockers.append("route-step-verdict-must-be-live-movement-progress-validated")

    decision = safe_mapping(step_summary.get("initialDecision"))
    if decision.get("status") != "passed":
        blockers.append("initial-decision-status-must-be-passed")
    if decision.get("movementRequired") is not True:
        blockers.append("initial-decision-movement-required-must-be-true")
    if decision.get("controlIntent") != "forward":
        blockers.append("initial-decision-control-intent-must-be-forward")
    if decision.get("suggestedTurnDirection") != "aligned":
        blockers.append("initial-decision-suggested-turn-must-be-aligned")

    route_result = safe_mapping(step_summary.get("routeResult"))
    if route_result.get("status") != "passed":
        blockers.append("route-result-status-must-be-passed")
    if route_result.get("routeStatus") not in PASS_ROUTE_STATUSES:
        blockers.append("route-result-route-status-must-be-progress-or-arrived")
    if route_result.get("contractStatus") != "passed":
        blockers.append("route-result-contract-status-must-be-passed")
    if route_result.get("contractMovementPermission") is not False:
        blockers.append("route-result-contract-movement-permission-must-be-false")
    if route_result.get("totalProgressDistance") is None:
        blockers.append("route-result-total-progress-distance-required")

    safety = safe_mapping(step_summary.get("safety"))
    safety_required_true = {
        "movementSent": "safety-movement-sent-must-be-true",
        "inputSent": "safety-input-sent-must-be-true",
        "noCheatEngine": "safety-no-cheat-engine-must-be-true",
    }
    safety_required_false = {
        "reloaduiSent": "safety-reloadui-sent-must-be-false",
        "screenshotKeySent": "safety-screenshot-key-sent-must-be-false",
        "x64dbgAttach": "safety-x64dbg-attach-must-be-false",
        "debuggerAttached": "safety-debugger-attached-must-be-false",
        "providerWrites": "safety-provider-writes-must-be-false",
        "gitMutation": "safety-git-mutation-must-be-false",
        "proofPromotion": "safety-proof-promotion-must-be-false",
        "actorChainPromotion": "safety-actor-chain-promotion-must-be-false",
        "facingPromotion": "safety-facing-promotion-must-be-false",
        "savedVariablesUsedAsLiveTruth": "safety-savedvariables-live-truth-must-be-false",
    }
    for key, blocker in safety_required_true.items():
        if safety.get(key) is not True:
            blockers.append(blocker)
    for key, blocker in safety_required_false.items():
        if safety.get(key) is not False:
            blockers.append(blocker)

    artifacts = safe_mapping(step_summary.get("artifacts"))
    for key in ("preStateSummaryJson", "postStateSummaryJson", "routeSummaryJson", "routeContractSummaryJson"):
        if not artifacts.get(key):
            blockers.append(f"artifact-{key}-required")

    labels = [safe_mapping(item).get("label") for item in step_summary.get("childCommands", []) if isinstance(item, Mapping)]
    required_labels = ["01-pre-state", "02-sendinput-step", "03-post-state", "04-route-analysis", "05-route-contract"]
    missing_labels = [label for label in required_labels if label not in labels]
    if missing_labels:
        warnings.append(f"child-command-labels-missing:{','.join(missing_labels)}")

    return {
        "status": "blocked" if blockers else "passed",
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "routeStatus": route_result.get("routeStatus"),
        "routeVerdict": step_summary.get("verdict"),
        "movementSent": safety.get("movementSent"),
        "inputSent": safety.get("inputSent"),
        "totalProgressDistance": route_result.get("totalProgressDistance"),
    }


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


def route_command(args: argparse.Namespace, root: Path, pre_state_path: str, post_state_path: str) -> list[str]:
    command = [
        sys.executable,
        str(root / "scripts" / "static_owner_facing_discovery.py"),
        "route",
        "--repo-root",
        str(root),
        "--state-summary-json",
        pre_state_path,
        post_state_path,
        "--minimum-progress-distance",
        str(args.minimum_progress_distance),
        "--wrong-way-tolerance-distance",
        str(args.wrong_way_tolerance_distance),
        "--json",
    ]
    if args.output_root:
        command += ["--output-root", str(args.output_root)]
    command += destination_args(args)
    return command


def validate_route_command(args: argparse.Namespace, root: Path, route_summary_path: str) -> list[str]:
    command = [
        sys.executable,
        str(root / "scripts" / "static_owner_facing_discovery.py"),
        "validate-route",
        "--repo-root",
        str(root),
        "--route-summary-json",
        route_summary_path,
        "--json",
    ]
    if args.output_root:
        command += ["--output-root", str(args.output_root)]
    return command


def send_key_command(args: argparse.Namespace, root: Path, pre_state: Mapping[str, Any]) -> list[str]:
    target = safe_mapping(pre_state.get("target"))
    return [
        "pwsh",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(root / "scripts" / "send-rift-key-csharp.ps1"),
        "--key",
        str(args.key),
        "--hold-ms",
        str(args.hold_milliseconds),
        "--process-name",
        str(target.get("processName") or "rift_x64"),
        "--pid",
        str(target.get("processId")),
        "--hwnd",
        str(target.get("targetWindowHandle")),
        "--title-contains",
        str(args.title_contains),
        "--input-mode",
        str(args.input_mode),
        "--focus-delay-ms",
        str(args.focus_delay_milliseconds),
        "--json",
    ]


def build_markdown(summary: Mapping[str, Any]) -> str:
    decision = safe_mapping(summary.get("initialDecision"))
    route_result = safe_mapping(summary.get("routeResult"))
    safety = safe_mapping(summary.get("safety"))
    artifacts = safe_mapping(summary.get("artifacts"))
    lines = [
        "# Static owner navigation route step",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Initial decision",
        "",
        f"- Status: `{decision.get('status')}`",
        f"- Reason: `{decision.get('reason')}`",
        f"- Control intent: `{decision.get('controlIntent')}`",
        f"- Movement required: `{decision.get('movementRequired')}`",
        "",
    ]
    if decision.get("navStateAvailable") is True:
        yaw = decision.get("navStateYawDegrees")
        turn_rate = decision.get("navStateTurnRate0x304")
        turn_class = decision.get("navStateTurnRateClassification")
        facing = decision.get("navStateFacingTargetCoordinate")
        yaw_str = f"{yaw:.2f}°" if isinstance(yaw, (int, float)) else str(yaw)
        lines.extend([
            "### Pointer-chain nav-state (candidate-only)",
            "",
            f"- Yaw: `{yaw_str}`",
            f"- Turn rate (0x304): `{turn_rate}`",
            f"- Turn classification: `{turn_class}`",
            f"- Facing target: `{facing}`",
            f"- Nav-state available: `{decision.get('navStateAvailable')}`",
            "",
            "> **Note:** Nav-state is candidate-only evidence. It does not authorize turns.",
            "",
        ])
        if decision.get("navStateTurnRateDissonance"):
            lines.extend([
                f"> ⚠ **Turn-rate dissonance detected:** `{decision['navStateTurnRateDissonance']}`",
                f"> The engine turn-rate discriminator (+0x304) disagrees with the atan2 bearing. Movement blocked.",
                "",
            ])
    lines.extend(["", "## Route result", "",
        f"- Route status: `{route_result.get('routeStatus')}`",
        f"- Stop reason: `{route_result.get('stopReason')}`",
        f"- Total progress: `{route_result.get('totalProgressDistance')}`",
        f"- Controller action: `{route_result.get('controllerRecommendedAction')}`",
        "",
        "## Safety",
        "",
        f"- Movement sent: `{safety.get('movementSent')}`",
        f"- Input sent: `{safety.get('inputSent')}`",
        f"- Cheat Engine: `{not bool(safety.get('noCheatEngine'))}`",
        f"- x64dbg attach: `{safety.get('x64dbgAttach')}`",
        f"- Provider writes: `{safety.get('providerWrites')}`",
        f"- Proof promotion: `{safety.get('proofPromotion')}`",
        "",
        "## Artifacts",
        "",
        f"- Summary JSON: `{artifacts.get('summaryJson')}`",
        f"- Run directory: `{artifacts.get('runDirectory')}`",
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


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-nav-route-step-{utc_stamp()}"
    child_dir = run_dir / "child-outputs"
    run_dir.mkdir(parents=True, exist_ok=True)
    errors = validate_args(args)
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-nav-route-step",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "pending",
        "verdict": "invalid-arguments" if errors else None,
        "repoRoot": str(root),
        "operator": {
            "dryRun": bool(args.dry_run),
            "movementApproved": bool(args.movement_approved),
        },
        "input": {
            "key": args.key,
            "holdMilliseconds": args.hold_milliseconds,
            "inputMode": args.input_mode,
        },
        "initialDecision": {},
        "routeResult": {},
        "childCommands": [],
        "blockers": [],
        "warnings": [],
        "errors": errors,
        "safety": base_safety(),
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
    }
    if errors:
        return summary
    try:
        pre = run_child(
            label="01-pre-state",
            command=state_command(args, root),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=args.command_timeout_seconds,
        )
        summary["childCommands"].append(pre)
        if not pre["ok"] or not isinstance(pre.get("json"), Mapping):
            summary["status"] = "failed"
            summary["verdict"] = "pre-state-readback-failed"
            summary["errors"].append("pre-state-readback-failed")
            return summary
        pre_full = full_summary_from_compact(pre["json"])
        summary["artifacts"]["preStateSummaryJson"] = safe_mapping(pre["json"]).get("summaryJson")
        if pre_full.get("status") != "passed":
            summary["status"] = "blocked"
            summary["verdict"] = "pre-state-readback-blocked"
            summary["blockers"].append("pre-state-readback-not-passed")
            return summary
        decision = classify_initial_step(pre_full)
        if args.nav_state:
            nav_state_result = _read_nav_state(
                root=root,
                current_truth_json=args.current_truth_json,
                command_timeout_seconds=args.command_timeout_seconds,
                repo_root_path=args.repo_root,
            )
            summary["navStateReadback"] = nav_state_result
            summary["safety"]["navStateCandidateOnly"] = True
            summary["safety"]["actionableForNavigation"] = False
            decision = enrich_decision_with_nav_state(decision, nav_state_result)
            if nav_state_result.get("error"):
                summary["warnings"].append(f"nav-state-readback-warning:{nav_state_result['error']}")
        summary["initialDecision"] = decision
        if decision["status"] != "passed":
            summary["status"] = "blocked"
            summary["verdict"] = "route-step-initial-decision-blocked"
            summary["blockers"].append(str(decision["reason"]))
            return summary
        if not decision.get("movementRequired"):
            summary["status"] = "passed"
            summary["verdict"] = "route-step-no-movement-needed"
            summary["warnings"].append("already-arrived-no-input-sent")
            return summary
        if args.dry_run:
            summary["status"] = "passed"
            summary["verdict"] = "route-step-dry-run-plan-built"
            summary["warnings"].append("dry-run-only-no-input-sent")
            return summary
        if not args.movement_approved:
            summary["status"] = "blocked"
            summary["verdict"] = "route-step-movement-approval-required"
            summary["blockers"].append("movement-approved-flag-required")
            return summary

        send = run_child(
            label="02-sendinput-step",
            command=send_key_command(args, root, pre_full),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=args.command_timeout_seconds,
        )
        summary["childCommands"].append(send)
        summary["safety"]["movementSent"] = True
        summary["safety"]["inputSent"] = True
        send_json = safe_mapping(send.get("json"))
        summary["artifacts"]["stimulusStdout"] = send.get("stdoutPath")
        if not send["ok"] or send_json.get("ok") is not True:
            summary["status"] = "failed"
            summary["verdict"] = "sendinput-step-failed"
            summary["errors"].append("sendinput-step-failed")
            return summary
        if args.settle_seconds:
            time.sleep(float(args.settle_seconds))

        post = run_child(
            label="03-post-state",
            command=state_command(args, root),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=args.command_timeout_seconds,
        )
        summary["childCommands"].append(post)
        if not post["ok"] or not isinstance(post.get("json"), Mapping):
            summary["status"] = "failed"
            summary["verdict"] = "post-state-readback-failed"
            summary["errors"].append("post-state-readback-failed")
            return summary
        post_full = full_summary_from_compact(post["json"])
        summary["artifacts"]["postStateSummaryJson"] = safe_mapping(post["json"]).get("summaryJson")
        if post_full.get("status") != "passed":
            summary["status"] = "blocked"
            summary["verdict"] = "post-state-readback-blocked"
            summary["blockers"].append("post-state-readback-not-passed")
            return summary

        route = run_child(
            label="04-route-analysis",
            command=route_command(
                args,
                root,
                str(summary["artifacts"]["preStateSummaryJson"]),
                str(summary["artifacts"]["postStateSummaryJson"]),
            ),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=args.command_timeout_seconds,
        )
        summary["childCommands"].append(route)
        if not route["ok"] or not isinstance(route.get("json"), Mapping):
            summary["status"] = "failed"
            summary["verdict"] = "route-analysis-failed"
            summary["errors"].append("route-analysis-failed")
            return summary
        route_full = full_summary_from_compact(route["json"])
        summary["artifacts"]["routeSummaryJson"] = safe_mapping(route["json"]).get("summaryJson")

        validation = run_child(
            label="05-route-contract",
            command=validate_route_command(args, root, str(summary["artifacts"]["routeSummaryJson"])),
            cwd=root,
            child_dir=child_dir,
            timeout_seconds=args.command_timeout_seconds,
        )
        summary["childCommands"].append(validation)
        if not validation["ok"] or not isinstance(validation.get("json"), Mapping):
            summary["status"] = "failed"
            summary["verdict"] = "route-contract-validation-failed"
            summary["errors"].append("route-contract-validation-failed")
            return summary
        validation_full = full_summary_from_compact(validation["json"])
        summary["artifacts"]["routeContractSummaryJson"] = safe_mapping(validation["json"]).get("summaryJson")
        route_result = classify_route_result(route_full, validation_full)
        summary["routeResult"] = route_result
        if route_result["status"] == "passed":
            summary["status"] = "passed"
            summary["verdict"] = "route-step-live-movement-progress-validated"
        else:
            summary["status"] = "blocked"
            summary["verdict"] = "route-step-post-movement-analysis-blocked"
            summary["blockers"].extend(route_result["blockers"])
    except subprocess.TimeoutExpired as exc:
        summary["status"] = "failed"
        summary["verdict"] = "child-command-timeout"
        summary["errors"].append(f"TimeoutExpired:{exc}")
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "route-step-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    summary["blockers"] = sorted(set(summary["blockers"]))
    summary["warnings"] = sorted(set(summary["warnings"]))
    return summary


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    route_result = safe_mapping(summary.get("routeResult"))
    decision = safe_mapping(summary.get("initialDecision"))
    nav_state_readback = safe_mapping(summary.get("navStateReadback"))
    compact_dict: dict[str, Any] = {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "initialDecision": decision or None,
        "routeResult": route_result or None,
        "movementSent": safe_mapping(summary.get("safety")).get("movementSent"),
        "inputSent": safe_mapping(summary.get("safety")).get("inputSent"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "preStateSummaryJson": artifacts.get("preStateSummaryJson"),
        "postStateSummaryJson": artifacts.get("postStateSummaryJson"),
        "routeSummaryJson": artifacts.get("routeSummaryJson"),
        "routeContractSummaryJson": artifacts.get("routeContractSummaryJson"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }
    if nav_state_readback:
        compact_dict["navStateAvailable"] = decision.get("navStateAvailable")
        compact_dict["navStateYawDegrees"] = decision.get("navStateYawDegrees")
        compact_dict["navStateTurnRate0x304"] = decision.get("navStateTurnRate0x304")
        compact_dict["navStateTurnRateClassification"] = decision.get("navStateTurnRateClassification")
        compact_dict["navStateError"] = decision.get("navStateError")
        compact_dict["navStateTurnRateDissonance"] = decision.get("navStateTurnRateDissonance")
    return compact_dict


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one bounded static-owner navigation route step")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
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
    parser.add_argument("--key", default=DEFAULT_KEY)
    parser.add_argument("--hold-milliseconds", type=int, default=DEFAULT_HOLD_MS)
    parser.add_argument("--input-mode", choices=("ScanCode", "VirtualKey"), default="ScanCode")
    parser.add_argument("--title-contains", default="RIFT")
    parser.add_argument("--focus-delay-milliseconds", type=int, default=250)
    parser.add_argument("--settle-seconds", type=float, default=0.75)
    parser.add_argument("--command-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--nav-state", action="store_true", help="Read live pointer-chain nav-state (yaw, turn rate) from the promoted static resolver alongside pre-state")
    parser.add_argument("--movement-approved", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run(args)
    artifacts = safe_mapping(summary.get("artifacts"))
    write_json(Path(str(artifacts["summaryJson"])), summary)
    Path(str(artifacts["summaryMarkdown"])).write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(compact(summary)) if args.json else json.dumps(compact(summary), indent=2))
    return 0 if summary.get("status") == "passed" else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    sys.exit(main())
