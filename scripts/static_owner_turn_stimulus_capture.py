#!/usr/bin/env python3
"""Capture a bounded turn/yaw stimulus against the static-owner facing lane.

This helper sends one approved turn-risk key press between two exact-target
static-owner state readbacks, then classifies the candidate yaw delta. It is
evidence collection only: the +0x30C/+0x310/+0x314 facing/yaw lane remains
candidate-only and is not promoted to navigation truth.
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
from typing import Any, Mapping, Sequence

try:
    from .static_owner_facing_discovery import normalize_degrees
    from .static_owner_nav_route_step import base_safety, load_json_object, preview, safe_mapping, write_json
except ImportError:  # pragma: no cover - direct script execution path
    from static_owner_facing_discovery import normalize_degrees  # type: ignore
    from static_owner_nav_route_step import base_safety, load_json_object, preview, safe_mapping, write_json  # type: ignore


SCHEMA_VERSION = 1
DEFAULT_HOLD_MS = 350
DEFAULT_MIN_YAW_DELTA_DEGREES = 2.0
DEFAULT_MAX_PLANAR_DRIFT = 1.0
DEFAULT_KEYS = {
    "left": "left",
    "right": "right",
}
EXPECTED_SIGN = {
    "left": -1,
    "right": 1,
}


def utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


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


def validate_args(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    if args.direction not in EXPECTED_SIGN:
        errors.append("direction-must-be-left-or-right")
    if args.samples < 1:
        errors.append("samples-must-be-positive")
    if args.interval_seconds < 0:
        errors.append("interval-seconds-must-be-nonnegative")
    if args.hold_milliseconds <= 0:
        errors.append("hold-milliseconds-must-be-positive")
    if args.settle_seconds < 0:
        errors.append("settle-seconds-must-be-nonnegative")
    if args.minimum_yaw_delta_degrees < 0:
        errors.append("minimum-yaw-delta-degrees-must-be-nonnegative")
    if args.max_planar_drift < 0:
        errors.append("max-planar-drift-must-be-nonnegative")
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


def full_summary_from_compact(compact: Mapping[str, Any]) -> dict[str, Any]:
    path = compact.get("summaryJson")
    if not path:
        raise ValueError("child-compact-summary-json-missing")
    return load_json_object(str(path))


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
    return command


def send_key_command(args: argparse.Namespace, root: Path, pre_state: Mapping[str, Any]) -> list[str]:
    target = safe_mapping(pre_state.get("target"))
    key = args.key or DEFAULT_KEYS[str(args.direction)]
    return [
        "pwsh",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(root / "scripts" / "send-rift-key-csharp.ps1"),
        "--key",
        str(key),
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


def classify_turn_analysis(
    pre_summary: Mapping[str, Any],
    post_summary: Mapping[str, Any],
    *,
    direction: str,
    key: str,
    minimum_yaw_delta_degrees: float,
    max_planar_drift: float,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    pre_state = safe_mapping(pre_summary.get("latestState"))
    post_state = safe_mapping(post_summary.get("latestState"))
    pre_coord = safe_mapping(pre_state.get("coordinate"))
    post_coord = safe_mapping(post_state.get("coordinate"))
    pre_yaw = pre_state.get("yawDegrees")
    post_yaw = post_state.get("yawDegrees")
    if pre_yaw is None or post_yaw is None:
        blockers.append("pre-post-yaw-required")
        signed_delta = None
        absolute_delta = None
    else:
        signed_delta = normalize_degrees(float(post_yaw) - float(pre_yaw))
        absolute_delta = abs(signed_delta)
        if absolute_delta < minimum_yaw_delta_degrees:
            blockers.append("yaw-delta-below-threshold")
        expected_sign = EXPECTED_SIGN[str(direction)]
        if absolute_delta >= minimum_yaw_delta_degrees and math.copysign(1, signed_delta or 0.0) != expected_sign:
            blockers.append("yaw-delta-opposite-expected-direction")
    if pre_coord and post_coord:
        drift = coordinate_delta(pre_coord, post_coord)
        if drift["planar"] > max_planar_drift:
            blockers.append("planar-drift-exceeded")
    else:
        drift = {}
        blockers.append("pre-post-coordinate-required")

    if str(key).lower() in {"a", "d", "q", "e", "w", "s", "up", "down"}:
        warnings.append("key-is-movement-risk-binding-captured-with-explicit-approval")

    return {
        "status": "blocked" if blockers else "passed",
        "candidateOnly": True,
        "actionableForNavigation": False,
        "movementPermission": False,
        "facingPromotion": False,
        "direction": direction,
        "key": key,
        "preYawDegrees": pre_yaw,
        "postYawDegrees": post_yaw,
        "signedYawDeltaDegrees": signed_delta,
        "absoluteYawDeltaDegrees": absolute_delta,
        "minimumYawDeltaDegrees": minimum_yaw_delta_degrees,
        "coordinateDelta": drift,
        "maxPlanarDrift": max_planar_drift,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
    }


def validate_turn_capture_summary_contract(summary: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if summary.get("kind") != "static-owner-turn-stimulus-capture":
        blockers.append("turn-capture-kind-must-be-static-owner-turn-stimulus-capture")
    if summary.get("status") != "passed":
        blockers.append("turn-capture-status-must-be-passed")
    if summary.get("verdict") != "turn-yaw-delta-validated":
        blockers.append("turn-capture-verdict-must-be-turn-yaw-delta-validated")

    analysis = safe_mapping(summary.get("analysis"))
    if analysis.get("status") != "passed":
        blockers.append("analysis-status-must-be-passed")
    if analysis.get("candidateOnly") is not True:
        blockers.append("analysis-candidate-only-must-be-true")
    if analysis.get("actionableForNavigation") is not False:
        blockers.append("analysis-actionable-for-navigation-must-be-false")
    if analysis.get("movementPermission") is not False:
        blockers.append("analysis-movement-permission-must-be-false")
    if analysis.get("facingPromotion") is not False:
        blockers.append("analysis-facing-promotion-must-be-false")
    if analysis.get("absoluteYawDeltaDegrees") is None:
        blockers.append("analysis-absolute-yaw-delta-required")

    safety = safe_mapping(summary.get("safety"))
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
        "navigationControl": "safety-navigation-control-must-be-false",
        "savedVariablesUsedAsLiveTruth": "safety-savedvariables-live-truth-must-be-false",
    }
    for key, blocker in safety_required_true.items():
        if safety.get(key) is not True:
            blockers.append(blocker)
    for key, blocker in safety_required_false.items():
        if safety.get(key) is not False:
            blockers.append(blocker)

    artifacts = safe_mapping(summary.get("artifacts"))
    for key in ("preStateSummaryJson", "postStateSummaryJson"):
        if not artifacts.get(key):
            blockers.append(f"artifact-{key}-required")

    labels = [safe_mapping(item).get("label") for item in summary.get("childCommands", []) if isinstance(item, Mapping)]
    required_labels = ["01-pre-state", "02-turn-stimulus", "03-post-state"]
    missing_labels = [label for label in required_labels if label not in labels]
    if missing_labels:
        warnings.append(f"child-command-labels-missing:{','.join(missing_labels)}")

    return {
        "status": "blocked" if blockers else "passed",
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "direction": analysis.get("direction"),
        "key": analysis.get("key"),
        "signedYawDeltaDegrees": analysis.get("signedYawDeltaDegrees"),
        "absoluteYawDeltaDegrees": analysis.get("absoluteYawDeltaDegrees"),
        "planarDrift": safe_mapping(analysis.get("coordinateDelta")).get("planar"),
        "movementSent": safety.get("movementSent"),
        "inputSent": safety.get("inputSent"),
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    analysis = safe_mapping(summary.get("analysis"))
    safety = safe_mapping(summary.get("safety"))
    artifacts = safe_mapping(summary.get("artifacts"))
    lines = [
        "# Static owner turn stimulus capture",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Analysis",
        "",
        f"- Direction: `{analysis.get('direction')}`",
        f"- Key: `{analysis.get('key')}`",
        f"- Pre yaw: `{analysis.get('preYawDegrees')}`",
        f"- Post yaw: `{analysis.get('postYawDegrees')}`",
        f"- Signed yaw delta: `{analysis.get('signedYawDeltaDegrees')}`",
        f"- Planar drift: `{safe_mapping(analysis.get('coordinateDelta')).get('planar')}`",
        "",
        "## Safety",
        "",
        f"- Movement sent: `{safety.get('movementSent')}`",
        f"- Input sent: `{safety.get('inputSent')}`",
        f"- Cheat Engine: `{not bool(safety.get('noCheatEngine'))}`",
        f"- x64dbg attach: `{safety.get('x64dbgAttach')}`",
        f"- Provider writes: `{safety.get('providerWrites')}`",
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
        "# Static owner turn stimulus contract validation",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Source summary: `{summary.get('sourceSummaryJson')}`",
        "",
        "## Contract",
        "",
        f"- Status: `{contract.get('status')}`",
        f"- Direction: `{contract.get('direction')}`",
        f"- Key: `{contract.get('key')}`",
        f"- Signed yaw delta: `{contract.get('signedYawDeltaDegrees')}`",
        f"- Planar drift: `{contract.get('planarDrift')}`",
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


def validate_saved_summary(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-turn-stimulus-contract-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    safety = base_safety()
    source = Path(str(args.validate_turn_summary_json)).resolve() if args.validate_turn_summary_json else None
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-turn-stimulus-contract-validation",
        "generatedAtUtc": utc_iso(),
        "status": "pending",
        "repoRoot": str(root),
        "sourceSummaryJson": str(source) if source else None,
        "contract": {},
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
    if not source:
        summary["status"] = "failed"
        summary["errors"].append("validate-turn-summary-json-required")
        return summary
    try:
        turn_summary = load_json_object(source)
        contract = validate_turn_capture_summary_contract(turn_summary)
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


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-turn-stimulus-{utc_stamp()}"
    child_dir = run_dir / "child-outputs"
    run_dir.mkdir(parents=True, exist_ok=True)
    errors = validate_args(args)
    key = args.key or DEFAULT_KEYS.get(str(args.direction), "")
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-turn-stimulus-capture",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "pending",
        "verdict": "invalid-arguments" if errors else None,
        "repoRoot": str(root),
        "operator": {
            "dryRun": bool(args.dry_run),
            "turnApproved": bool(args.turn_approved),
        },
        "input": {
            "direction": args.direction,
            "key": key,
            "holdMilliseconds": args.hold_milliseconds,
            "inputMode": args.input_mode,
        },
        "analysis": {},
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
        if args.dry_run:
            latest = safe_mapping(pre_full.get("latestState"))
            summary["analysis"] = {
                "status": "passed",
                "candidateOnly": True,
                "actionableForNavigation": False,
                "movementPermission": False,
                "facingPromotion": False,
                "direction": args.direction,
                "key": key,
                "preYawDegrees": latest.get("yawDegrees"),
                "preCoordinate": latest.get("coordinate"),
            }
            summary["status"] = "passed"
            summary["verdict"] = "turn-capture-dry-run-plan-built"
            summary["warnings"].append("dry-run-only-no-input-sent")
            return summary
        if not args.turn_approved:
            summary["status"] = "blocked"
            summary["verdict"] = "turn-stimulus-approval-required"
            summary["blockers"].append("turn-approved-flag-required")
            return summary

        send = run_child(
            label="02-turn-stimulus",
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
            summary["verdict"] = "turn-stimulus-failed"
            summary["errors"].append("turn-stimulus-failed")
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
        analysis = classify_turn_analysis(
            pre_full,
            post_full,
            direction=str(args.direction),
            key=str(key),
            minimum_yaw_delta_degrees=float(args.minimum_yaw_delta_degrees),
            max_planar_drift=float(args.max_planar_drift),
        )
        summary["analysis"] = analysis
        summary["warnings"].extend(analysis["warnings"])
        if analysis["status"] == "passed":
            summary["status"] = "passed"
            summary["verdict"] = "turn-yaw-delta-validated"
            summary["warnings"].append("candidate-facing-yaw-not-promoted")
        else:
            summary["status"] = "blocked"
            summary["verdict"] = "turn-yaw-analysis-blocked"
            summary["blockers"].extend(analysis["blockers"])
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "turn-capture-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    summary["blockers"] = sorted(set(summary["blockers"]))
    summary["warnings"] = sorted(set(summary["warnings"]))
    summary["errors"] = sorted(set(summary["errors"]))
    return summary


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    analysis = safe_mapping(summary.get("analysis"))
    safety = safe_mapping(summary.get("safety"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "direction": analysis.get("direction"),
        "key": analysis.get("key"),
        "signedYawDeltaDegrees": analysis.get("signedYawDeltaDegrees"),
        "absoluteYawDeltaDegrees": analysis.get("absoluteYawDeltaDegrees"),
        "planarDrift": safe_mapping(analysis.get("coordinateDelta")).get("planar"),
        "candidateOnly": analysis.get("candidateOnly"),
        "movementSent": safety.get("movementSent"),
        "inputSent": safety.get("inputSent"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "preStateSummaryJson": artifacts.get("preStateSummaryJson"),
        "postStateSummaryJson": artifacts.get("postStateSummaryJson"),
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
        "direction": contract.get("direction"),
        "key": contract.get("key"),
        "signedYawDeltaDegrees": contract.get("signedYawDeltaDegrees"),
        "absoluteYawDeltaDegrees": contract.get("absoluteYawDeltaDegrees"),
        "planarDrift": contract.get("planarDrift"),
        "sourceSummaryJson": summary.get("sourceSummaryJson"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture a bounded static-owner turn/yaw stimulus")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--validate-turn-summary-json", nargs="?", const="")
    parser.add_argument("--current-truth-json", default="docs/recovery/current-truth.json")
    parser.add_argument("--direction", choices=("left", "right"), default="left")
    parser.add_argument("--key")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--interval-seconds", type=float, default=0.1)
    parser.add_argument("--hold-milliseconds", type=int, default=DEFAULT_HOLD_MS)
    parser.add_argument("--input-mode", choices=("ScanCode", "VirtualKey"), default="ScanCode")
    parser.add_argument("--title-contains", default="RIFT")
    parser.add_argument("--focus-delay-milliseconds", type=int, default=250)
    parser.add_argument("--settle-seconds", type=float, default=0.75)
    parser.add_argument("--minimum-yaw-delta-degrees", type=float, default=DEFAULT_MIN_YAW_DELTA_DEGREES)
    parser.add_argument("--max-planar-drift", type=float, default=DEFAULT_MAX_PLANAR_DRIFT)
    parser.add_argument("--command-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--turn-approved", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validation_mode = args.validate_turn_summary_json is not None
    summary = validate_saved_summary(args) if validation_mode else run(args)
    artifacts = safe_mapping(summary.get("artifacts"))
    write_json(Path(str(artifacts["summaryJson"])), summary)
    markdown = build_validation_markdown(summary) if validation_mode else build_markdown(summary)
    compact_summary = compact_validation(summary) if validation_mode else compact(summary)
    Path(str(artifacts["summaryMarkdown"])).write_text(markdown, encoding="utf-8")
    print(json.dumps(compact_summary) if args.json else json.dumps(compact_summary, indent=2))
    return 0 if summary.get("status") == "passed" else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    sys.exit(main())
