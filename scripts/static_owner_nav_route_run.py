#!/usr/bin/env python3
"""Run a conservative multi-step static-owner navigation route.

This helper deliberately reuses ``static_owner_nav_route_step.py`` as the only
movement primitive. It never turns from candidate-only facing evidence; each
step must pass the one-step contract before the runner can continue.

It does not run ProofOnly, attach x64dbg, use Cheat Engine, write provider
repos, promote facing/actor/proof/current truth, or mutate Git state.
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
    from .static_owner_nav_route_step import (
        base_safety,
        destination_args,
        load_json_object,
        preview,
        safe_mapping,
        validate_args as validate_route_step_args,
        validate_route_step_summary_contract,
        write_json,
    )
except ImportError:  # pragma: no cover - direct script execution path
    from static_owner_nav_route_step import (  # type: ignore
        base_safety,
        destination_args,
        load_json_object,
        preview,
        safe_mapping,
        validate_args as validate_route_step_args,
        validate_route_step_summary_contract,
        write_json,
    )


SCHEMA_VERSION = 1
DEFAULT_MAX_STEPS = 3
LIVE_STEP_VERDICT = "route-step-live-movement-progress-validated"
DRY_RUN_STEP_VERDICTS = {"route-step-dry-run-plan-built", "route-step-no-movement-needed"}


def utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def validate_args(args: argparse.Namespace) -> list[str]:
    errors = validate_route_step_args(args)
    if args.max_steps <= 0:
        errors.append("max-steps-must-be-positive")
    if args.step_timeout_seconds <= 0:
        errors.append("step-timeout-seconds-must-be-positive")
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


def route_step_command(
    args: argparse.Namespace,
    *,
    root: Path,
    step_output_root: Path,
    dry_run: bool,
) -> list[str]:
    command = [
        sys.executable,
        str(root / "scripts" / "static_owner_nav_route_step.py"),
        "--repo-root",
        str(root),
        "--output-root",
        str(step_output_root),
        "--current-truth-json",
        str(args.current_truth_json),
        "--minimum-progress-distance",
        str(args.minimum_progress_distance),
        "--wrong-way-tolerance-distance",
        str(args.wrong_way_tolerance_distance),
        "--samples",
        str(args.samples),
        "--interval-seconds",
        str(args.interval_seconds),
        "--key",
        str(args.key),
        "--hold-milliseconds",
        str(args.hold_milliseconds),
        "--input-mode",
        str(args.input_mode),
        "--title-contains",
        str(args.title_contains),
        "--focus-delay-milliseconds",
        str(args.focus_delay_milliseconds),
        "--settle-seconds",
        str(args.settle_seconds),
        "--command-timeout-seconds",
        str(args.command_timeout_seconds),
        "--json",
    ]
    command += destination_args(args)
    if dry_run:
        command.append("--dry-run")
    else:
        command.append("--movement-approved")
    return command


def load_full_step_summary(compact_summary: Mapping[str, Any]) -> dict[str, Any]:
    path = compact_summary.get("summaryJson")
    if not path:
        raise ValueError("route-step-summary-json-missing")
    return load_json_object(str(path))


def route_run_step_record(step_number: int, step_summary: Mapping[str, Any]) -> dict[str, Any]:
    route_result = safe_mapping(step_summary.get("routeResult"))
    decision = safe_mapping(step_summary.get("initialDecision"))
    safety = safe_mapping(step_summary.get("safety"))
    artifacts = safe_mapping(step_summary.get("artifacts"))
    contract: dict[str, Any] = {}
    if step_summary.get("verdict") == LIVE_STEP_VERDICT:
        contract = validate_route_step_summary_contract(step_summary)
    return {
        "stepNumber": step_number,
        "status": step_summary.get("status"),
        "verdict": step_summary.get("verdict"),
        "initialDecisionReason": decision.get("reason"),
        "suggestedTurnDirection": decision.get("suggestedTurnDirection"),
        "initialPlanarDistance": route_result.get("initialPlanarDistance", decision.get("planarDistance")),
        "finalPlanarDistance": route_result.get("finalPlanarDistance"),
        "routeStatus": route_result.get("routeStatus"),
        "stopReason": route_result.get("stopReason"),
        "totalProgressDistance": route_result.get("totalProgressDistance"),
        "movementSent": safety.get("movementSent"),
        "inputSent": safety.get("inputSent"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "contract": contract,
        "blockers": list(step_summary.get("blockers", [])),
        "warnings": list(step_summary.get("warnings", [])),
        "errors": list(step_summary.get("errors", [])),
    }


def summarize_route_run_steps(
    step_summaries: Sequence[Mapping[str, Any]],
    *,
    max_steps: int,
    dry_run: bool = False,
) -> dict[str, Any]:
    records = [route_run_step_record(index + 1, summary) for index, summary in enumerate(step_summaries)]
    blockers: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    arrived = False
    arrival_step: int | None = None
    last_route_status: Any = None
    final_planar_distance: Any = None
    total_progress = 0.0
    movement_sent = False
    input_sent = False

    if max_steps <= 0:
        errors.append("max-steps-must-be-positive")
    if not records:
        blockers.append("route-run-no-steps")

    for record in records:
        step_number = record["stepNumber"]
        movement_sent = movement_sent or record.get("movementSent") is True
        input_sent = input_sent or record.get("inputSent") is True
        last_route_status = record.get("routeStatus") or last_route_status
        final_planar_distance = record.get("finalPlanarDistance", final_planar_distance)
        progress = record.get("totalProgressDistance")
        if isinstance(progress, (int, float)):
            total_progress += float(progress)

        if record.get("status") == "failed":
            errors.append(f"step-{step_number}-failed")
            errors.extend(str(item) for item in record.get("errors", []))
            break
        if record.get("status") == "blocked":
            blockers.append(f"step-{step_number}-blocked")
            blockers.extend(str(item) for item in record.get("blockers", []))
            break
        if record.get("status") != "passed":
            blockers.append(f"step-{step_number}-status-unrecognized:{record.get('status')}")
            break

        verdict = record.get("verdict")
        if dry_run:
            if verdict not in DRY_RUN_STEP_VERDICTS:
                blockers.append(f"step-{step_number}-dry-run-verdict-unexpected:{verdict}")
            if verdict == "route-step-no-movement-needed":
                arrived = True
                arrival_step = step_number
            break

        if verdict == "route-step-no-movement-needed":
            arrived = True
            arrival_step = step_number
            last_route_status = "arrived"
            break
        if verdict != LIVE_STEP_VERDICT:
            blockers.append(f"step-{step_number}-live-verdict-unexpected:{verdict}")
            break

        contract = safe_mapping(record.get("contract"))
        if contract.get("status") != "passed":
            blockers.append(f"step-{step_number}-contract-blocked")
            blockers.extend(str(item) for item in contract.get("blockers", []))
            break

        route_status = record.get("routeStatus")
        if route_status == "arrived":
            arrived = True
            arrival_step = step_number
            break
        if route_status == "progress":
            continue
        blockers.append(f"step-{step_number}-route-status-blocked:{route_status}")
        break

    if dry_run and not blockers and not errors:
        status = "passed"
        verdict = "route-run-dry-run-plan-built" if not arrived else "route-run-dry-run-already-arrived"
    elif errors:
        status = "failed"
        verdict = "route-run-step-failed"
    elif blockers:
        status = "blocked"
        verdict = "route-run-blocked"
    elif arrived:
        status = "passed"
        verdict = "route-run-arrived"
    elif len(records) >= max_steps:
        status = "blocked"
        verdict = "route-run-max-steps-reached-before-arrival"
        blockers.append("max-steps-reached-before-arrival")
        warnings.append("progress-observed-but-arrival-not-reached")
    else:
        status = "blocked"
        verdict = "route-run-incomplete-before-arrival"
        blockers.append("route-run-incomplete-before-arrival")

    return {
        "status": status,
        "verdict": verdict,
        "stepsRun": len(records),
        "maxSteps": max_steps,
        "arrived": arrived,
        "arrivalStep": arrival_step,
        "lastRouteStatus": last_route_status,
        "totalProgressDistance": total_progress,
        "finalPlanarDistance": final_planar_distance,
        "movementSent": movement_sent,
        "inputSent": input_sent,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
        "stepRecords": records,
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    aggregate = safe_mapping(summary.get("aggregate"))
    safety = safe_mapping(summary.get("safety"))
    artifacts = safe_mapping(summary.get("artifacts"))
    lines = [
        "# Static owner navigation route run",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Aggregate",
        "",
        f"- Steps run: `{aggregate.get('stepsRun')}` / `{aggregate.get('maxSteps')}`",
        f"- Arrived: `{aggregate.get('arrived')}`",
        f"- Last route status: `{aggregate.get('lastRouteStatus')}`",
        f"- Total progress: `{aggregate.get('totalProgressDistance')}`",
        f"- Final planar distance: `{aggregate.get('finalPlanarDistance')}`",
        "",
        "## Safety",
        "",
        f"- Movement sent: `{safety.get('movementSent')}`",
        f"- Input sent: `{safety.get('inputSent')}`",
        f"- Navigation control: `{safety.get('navigationControl')}`",
        f"- Cheat Engine: `{not bool(safety.get('noCheatEngine'))}`",
        f"- x64dbg attach: `{safety.get('x64dbgAttach')}`",
        f"- Provider writes: `{safety.get('providerWrites')}`",
        f"- Proof promotion: `{safety.get('proofPromotion')}`",
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


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-nav-route-run-{utc_stamp()}"
    child_dir = run_dir / "child-outputs"
    step_output_root = run_dir / "route-step-runs"
    run_dir.mkdir(parents=True, exist_ok=True)

    errors = validate_args(args)
    safety = base_safety()
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-nav-route-run",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "pending",
        "verdict": "invalid-arguments" if errors else None,
        "repoRoot": str(root),
        "operator": {
            "dryRun": bool(args.dry_run),
            "movementApproved": bool(args.movement_approved),
            "maxSteps": args.max_steps,
        },
        "input": {
            "key": args.key,
            "holdMilliseconds": args.hold_milliseconds,
            "inputMode": args.input_mode,
        },
        "aggregate": {},
        "steps": [],
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
    if not args.dry_run and not args.movement_approved:
        summary["status"] = "blocked"
        summary["verdict"] = "route-run-movement-approval-required"
        summary["blockers"].append("movement-approved-flag-required")
        return summary
    if args.dry_run and args.movement_approved:
        summary["warnings"].append("dry-run-ignores-movement-approved")

    step_summaries: list[dict[str, Any]] = []
    try:
        iterations = 1 if args.dry_run else args.max_steps
        for step_number in range(1, iterations + 1):
            label = f"{step_number:02d}-route-step"
            child = run_child(
                label=label,
                command=route_step_command(
                    args,
                    root=root,
                    step_output_root=step_output_root,
                    dry_run=bool(args.dry_run),
                ),
                cwd=root,
                child_dir=child_dir,
                timeout_seconds=args.step_timeout_seconds,
            )
            summary["childCommands"].append(child)
            child_json = safe_mapping(child.get("json"))
            if not isinstance(child.get("json"), Mapping):
                summary["status"] = "failed"
                summary["verdict"] = "route-run-step-json-missing"
                summary["errors"].append(f"step-{step_number}-json-missing")
                break
            try:
                full_step = load_full_step_summary(child_json)
            except Exception as exc:  # noqa: BLE001
                summary["status"] = "failed"
                summary["verdict"] = "route-run-step-summary-load-failed"
                summary["errors"].append(f"step-{step_number}-summary-load-failed:{type(exc).__name__}:{exc}")
                break
            step_summaries.append(full_step)
            step_record = route_run_step_record(step_number, full_step)
            summary["steps"].append(step_record)
            summary["safety"]["movementSent"] = summary["safety"]["movementSent"] or step_record.get("movementSent") is True
            summary["safety"]["inputSent"] = summary["safety"]["inputSent"] or step_record.get("inputSent") is True
            if not child["ok"] or child_json.get("status") != "passed":
                break
            if not args.dry_run and (
                step_record.get("verdict") == "route-step-no-movement-needed"
                or step_record.get("routeStatus") == "arrived"
            ):
                break
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "route-run-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")

    if summary["status"] == "pending":
        aggregate = summarize_route_run_steps(step_summaries, max_steps=args.max_steps, dry_run=bool(args.dry_run))
        summary["aggregate"] = {key: value for key, value in aggregate.items() if key != "stepRecords"}
        summary["status"] = aggregate["status"]
        summary["verdict"] = aggregate["verdict"]
        summary["blockers"].extend(aggregate["blockers"])
        summary["warnings"].extend(aggregate["warnings"])
        summary["errors"].extend(aggregate["errors"])
    else:
        aggregate = summarize_route_run_steps(step_summaries, max_steps=args.max_steps, dry_run=bool(args.dry_run))
        summary["aggregate"] = {key: value for key, value in aggregate.items() if key != "stepRecords"}

    summary["safety"]["movementSent"] = summary["safety"]["movementSent"] or summary["aggregate"].get("movementSent") is True
    summary["safety"]["inputSent"] = summary["safety"]["inputSent"] or summary["aggregate"].get("inputSent") is True
    summary["safety"]["navigationControl"] = (
        not args.dry_run and summary["safety"]["inputSent"] is True and int(summary["aggregate"].get("stepsRun") or 0) > 1
    )
    summary["blockers"] = sorted(set(summary["blockers"]))
    summary["warnings"] = sorted(set(summary["warnings"]))
    summary["errors"] = sorted(set(summary["errors"]))
    return summary


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    aggregate = safe_mapping(summary.get("aggregate"))
    safety = safe_mapping(summary.get("safety"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "stepsRun": aggregate.get("stepsRun"),
        "maxSteps": aggregate.get("maxSteps"),
        "arrived": aggregate.get("arrived"),
        "lastRouteStatus": aggregate.get("lastRouteStatus"),
        "totalProgressDistance": aggregate.get("totalProgressDistance"),
        "finalPlanarDistance": aggregate.get("finalPlanarDistance"),
        "movementSent": safety.get("movementSent"),
        "inputSent": safety.get("inputSent"),
        "navigationControl": safety.get("navigationControl"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a conservative multi-step static-owner navigation route")
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
    parser.add_argument("--key", default="w")
    parser.add_argument("--hold-milliseconds", type=int, default=250)
    parser.add_argument("--input-mode", choices=("ScanCode", "VirtualKey"), default="ScanCode")
    parser.add_argument("--title-contains", default="RIFT")
    parser.add_argument("--focus-delay-milliseconds", type=int, default=250)
    parser.add_argument("--settle-seconds", type=float, default=0.75)
    parser.add_argument("--command-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--step-timeout-seconds", type=float, default=240.0)
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS)
    parser.add_argument("--dry-run", action="store_true")
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
