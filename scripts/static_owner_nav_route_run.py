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
        _read_nav_state,
    )
    from .static_owner_turn_forward_experiment import validate_turn_forward_experiment_contract
    from .static_owner_turn_stimulus_capture import validate_turn_capture_summary_contract
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
        _read_nav_state,
    )
    from static_owner_turn_forward_experiment import validate_turn_forward_experiment_contract  # type: ignore
    from static_owner_turn_stimulus_capture import validate_turn_capture_summary_contract  # type: ignore


SCHEMA_VERSION = 1
DEFAULT_MAX_STEPS = 3
DEFAULT_MAX_ARRIVAL_RADIUS = 10.0
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
    if args.max_arrival_radius <= 0:
        errors.append("max-arrival-radius-must-be-positive")
    if args.arrival_radius is not None and args.arrival_radius > args.max_arrival_radius:
        errors.append("arrival-radius-exceeds-max-arrival-radius")
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
        "noProgressSubClassification": route_result.get("noProgressSubClassification"),
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


def validate_route_run_summary_contract(run_summary: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if run_summary.get("kind") != "static-owner-nav-route-run":
        blockers.append("route-run-kind-must-be-static-owner-nav-route-run")
    if run_summary.get("status") != "passed":
        blockers.append("route-run-status-must-be-passed")
    if run_summary.get("verdict") != "route-run-arrived":
        blockers.append("route-run-verdict-must-be-route-run-arrived")
    if run_summary.get("blockers"):
        blockers.append("route-run-blockers-must-be-empty")
    if run_summary.get("errors"):
        blockers.append("route-run-errors-must-be-empty")

    aggregate = safe_mapping(run_summary.get("aggregate"))
    steps = [safe_mapping(item) for item in run_summary.get("steps", []) if isinstance(item, Mapping)]
    steps_run = aggregate.get("stepsRun")
    if aggregate.get("status") != "passed":
        blockers.append("aggregate-status-must-be-passed")
    if aggregate.get("verdict") != "route-run-arrived":
        blockers.append("aggregate-verdict-must-be-route-run-arrived")
    if aggregate.get("arrived") is not True:
        blockers.append("aggregate-arrived-must-be-true")
    if aggregate.get("lastRouteStatus") != "arrived":
        blockers.append("aggregate-last-route-status-must-be-arrived")
    if not isinstance(steps_run, int) or steps_run < 1:
        blockers.append("aggregate-steps-run-must-be-positive")
    elif steps_run != len(steps):
        blockers.append("aggregate-steps-run-must-match-steps-length")
    if aggregate.get("movementSent") is not True:
        blockers.append("aggregate-movement-sent-must-be-true")
    if aggregate.get("inputSent") is not True:
        blockers.append("aggregate-input-sent-must-be-true")

    safety = safe_mapping(run_summary.get("safety"))
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
    if isinstance(steps_run, int) and steps_run > 1 and safety.get("navigationControl") is not True:
        blockers.append("safety-navigation-control-must-be-true-for-multi-step-live-run")

    if not steps:
        blockers.append("steps-required")
    for index, step in enumerate(steps, start=1):
        if step.get("stepNumber") != index:
            blockers.append(f"step-{index}-number-mismatch")
        if step.get("status") != "passed":
            blockers.append(f"step-{index}-status-must-be-passed")
        if step.get("verdict") != LIVE_STEP_VERDICT:
            blockers.append(f"step-{index}-verdict-must-be-live-progress-validated")
        if step.get("movementSent") is not True:
            blockers.append(f"step-{index}-movement-sent-must-be-true")
        if step.get("inputSent") is not True:
            blockers.append(f"step-{index}-input-sent-must-be-true")
        if step.get("blockers"):
            blockers.append(f"step-{index}-blockers-must-be-empty")
        if step.get("errors"):
            blockers.append(f"step-{index}-errors-must-be-empty")
        route_status = step.get("routeStatus")
        if route_status not in {"progress", "arrived"}:
            blockers.append(f"step-{index}-route-status-must-be-progress-or-arrived")
        contract = safe_mapping(step.get("contract"))
        if contract.get("status") != "passed":
            blockers.append(f"step-{index}-contract-status-must-be-passed")
        if contract.get("blockers"):
            blockers.append(f"step-{index}-contract-blockers-must-be-empty")
    if steps and steps[-1].get("routeStatus") != "arrived":
        blockers.append("last-step-route-status-must-be-arrived")

    child_labels = [safe_mapping(item).get("label") for item in run_summary.get("childCommands", []) if isinstance(item, Mapping)]
    if isinstance(steps_run, int):
        expected_labels = [f"{index:02d}-route-step" for index in range(1, steps_run + 1)]
        missing_labels = [label for label in expected_labels if label not in child_labels]
        if missing_labels:
            warnings.append(f"child-command-labels-missing:{','.join(missing_labels)}")

    return {
        "status": "blocked" if blockers else "passed",
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "stepsRun": steps_run,
        "arrived": aggregate.get("arrived"),
        "movementSent": safety.get("movementSent"),
        "inputSent": safety.get("inputSent"),
        "navigationControl": safety.get("navigationControl"),
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


def build_validation_markdown(summary: Mapping[str, Any]) -> str:
    contract = safe_mapping(summary.get("contract"))
    safety = safe_mapping(summary.get("safety"))
    artifacts = safe_mapping(summary.get("artifacts"))
    lines = [
        "# Static owner navigation route-run contract validation",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Source summary: `{summary.get('sourceSummaryJson')}`",
        "",
        "## Contract",
        "",
        f"- Status: `{contract.get('status')}`",
        f"- Steps run: `{contract.get('stepsRun')}`",
        f"- Arrived: `{contract.get('arrived')}`",
        f"- Movement sent: `{contract.get('movementSent')}`",
        f"- Input sent: `{contract.get('inputSent')}`",
        f"- Navigation control: `{contract.get('navigationControl')}`",
        "",
        "## Safety",
        "",
        f"- Movement sent: `{safety.get('movementSent')}`",
        f"- Input sent: `{safety.get('inputSent')}`",
        f"- Cheat Engine: `{not bool(safety.get('noCheatEngine'))}`",
        f"- x64dbg attach: `{safety.get('x64dbgAttach')}`",
        f"- Provider writes: `{safety.get('providerWrites')}`",
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


def build_report_markdown(summary: Mapping[str, Any]) -> str:
    source = safe_mapping(summary.get("source"))
    aggregate = safe_mapping(source.get("aggregate"))
    safety = safe_mapping(source.get("safety"))
    contract = safe_mapping(summary.get("contract"))
    turn_evidence = [safe_mapping(item) for item in summary.get("turnEvidence", []) if isinstance(item, Mapping)]
    turn_forward_evidence = [safe_mapping(item) for item in summary.get("turnForwardEvidence", []) if isinstance(item, Mapping)]
    artifacts = safe_mapping(summary.get("artifacts"))
    lines = [
        "# Static owner navigation route-run report",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Source summary: `{summary.get('sourceSummaryJson')}`",
        f"Source verdict: `{source.get('verdict')}`",
        f"Contract status: `{contract.get('status')}`",
        "",
        "## Aggregate",
        "",
        f"- Steps run: `{aggregate.get('stepsRun')}` / `{aggregate.get('maxSteps')}`",
        f"- Arrived: `{aggregate.get('arrived')}`",
        f"- Last route status: `{aggregate.get('lastRouteStatus')}`",
        f"- Total progress: `{aggregate.get('totalProgressDistance')}`",
        f"- Final planar distance: `{aggregate.get('finalPlanarDistance')}`",
        "",
        "## Steps",
        "",
        "| Step | Status | Route status | No-progress reason | Progress | Initial distance | Final distance |",
        "|---:|---|---|---|---:|---:|---:|",
    ]
    for step in source.get("steps", []):
        row = safe_mapping(step)
        lines.append(
            "| {step} | `{status}` | `{route}` | {no_progress} | `{progress}` | `{initial}` | `{final}` |".format(
                step=row.get("stepNumber"),
                status=row.get("status"),
                route=row.get("routeStatus"),
                no_progress="`" + str(row.get("noProgressSubClassification")) + "`" if row.get("noProgressSubClassification") else "—",
                progress=row.get("totalProgressDistance"),
                initial=row.get("initialPlanarDistance"),
                final=row.get("finalPlanarDistance"),
            )
        )
    # Terrain summary: aggregate no-progress sub-classifications across steps
    no_progress_steps = [
        safe_mapping(s) for s in source.get("steps", [])
        if safe_mapping(s).get("routeStatus") == "no-progress"
    ]
    if no_progress_steps:
        sub_class_counts: dict[str, int] = {}
        for s in no_progress_steps:
            sub = s.get("noProgressSubClassification") or "unspecified"
            sub_class_counts[sub] = sub_class_counts.get(sub, 0) + 1
        lines.extend([
            "",
            "## Terrain classification",
            "",
            "| Sub-classification | Count | Meaning |",
            "|---|---|---|",
        ])
        terrain_meanings = {
            "blocked-stationary-no-movement": "Player position did not change — likely blocked by terrain or obstacle",
            "drifted-back-after-initial-progress": "Player initially moved forward then drifted back — terrain may have redirected",
            "insufficient-progress-below-threshold": "Player moved slightly but did not meet the minimum progress threshold",
            "minimum-progress-not-met": "Progress below minimum threshold (no sub-classification available)",
            "unspecified": "No-progress without sub-classification",
        }
        for sub, count in sorted(sub_class_counts.items()):
            meaning = terrain_meanings.get(sub, "Unknown")
            lines.append(f"| `{sub}` | {count} | {meaning} |")
        lines.extend([
            "",
            f"**Total no-progress steps:** {len(no_progress_steps)}",
            "",
            "> **Operator note:** Steps classified as `blocked-stationary-no-movement` indicate terrain collision.",
            "> Consider adjusting the waypoint destination to avoid the obstacle before rerunning.",
            "> `drifted-back-after-initial-progress` suggests the terrain may have pushed the player off-course.",
        ])
    if turn_evidence:
        lines.extend(
            [
                "",
                "## Turn evidence",
                "",
                "| # | Direction | Contract | Signed yaw delta | Planar drift | Candidate only | Movement permission |",
                "|---:|---|---|---:|---:|---|---|",
            ]
        )
        for row in turn_evidence:
            lines.append(
                "| {index} | `{direction}` | `{contract}` | `{delta}` | `{drift}` | `{candidate}` | `{permission}` |".format(
                    index=row.get("index"),
                    direction=row.get("direction"),
                    contract=row.get("contractStatus"),
                    delta=row.get("signedYawDeltaDegrees"),
                    drift=row.get("planarDrift"),
                    candidate=row.get("candidateOnly"),
                    permission=row.get("movementPermission"),
                )
            )
    if turn_forward_evidence:
        lines.extend(
            [
                "",
                "## Turn-forward evidence",
                "",
                "| # | Contract | Verdict | Action | Observed yaw delta | Route status | Progress | Final distance |",
                "|---:|---|---|---|---:|---|---:|---:|",
            ]
        )
        for row in turn_forward_evidence:
            lines.append(
                "| {index} | `{contract}` | `{verdict}` | `{action}` | `{observed}` | `{route}` | `{progress}` | `{final}` |".format(
                    index=row.get("index"),
                    contract=row.get("contractStatus"),
                    verdict=row.get("verdict"),
                    action=row.get("firstAction"),
                    observed=row.get("observedYawDeltaDegrees"),
                    route=row.get("routeStatus"),
                    progress=row.get("totalProgressDistance"),
                    final=row.get("finalPlanarDistance"),
                )
            )
    lines.extend(
        [
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

    nav_state_data: dict[str, Any] | None = None
    if args.nav_state:
        nav_state_data = _read_nav_state(
            root=root,
            current_truth_json=args.current_truth_json,
            command_timeout_seconds=args.command_timeout_seconds,
            repo_root_path=str(root),
        )
        summary["navStateReadback"] = nav_state_data
        summary["safety"]["navStateCandidateOnly"] = True
        summary["safety"]["actionableForNavigation"] = False
        if nav_state_data.get("error"):
            summary["warnings"].append(f"nav-state-readback-warning:{nav_state_data['error']}")

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
        if nav_state_data and nav_state_data.get("ok"):
            nav_json = safe_mapping(nav_state_data.get("json"))
            nav = safe_mapping(nav_json.get("navState"))
            if nav_json.get("status") not in ("unavailable", "readback-failed", "parse-error"):
                summary["aggregate"]["navStateYawDegrees"] = nav.get("yawDegrees")
                summary["aggregate"]["navStateTurnRate0x304"] = nav.get("turnRate0x304")
                summary["aggregate"]["navStateTurnRateClassification"] = nav.get("turnRateClassification")
                summary["aggregate"]["navStateAvailable"] = True
            else:
                summary["aggregate"]["navStateAvailable"] = False
                summary["aggregate"]["navStateError"] = f"nav-state-status:{nav_json.get('status')}"
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


def validate_saved_summary(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-nav-route-run-contract-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    safety = base_safety()
    source = Path(str(args.validate_route_run_summary_json)).resolve() if args.validate_route_run_summary_json else None
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-nav-route-run-contract-validation",
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
        summary["errors"].append("validate-route-run-summary-json-required")
        return summary
    try:
        route_run_summary = load_json_object(source)
        contract = validate_route_run_summary_contract(route_run_summary)
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


def summarize_turn_evidence(paths: Sequence[str] | None) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    evidence: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    for index, raw_path in enumerate(paths or [], start=1):
        path = Path(str(raw_path)).resolve()
        try:
            turn_summary = load_json_object(path)
            contract = validate_turn_capture_summary_contract(turn_summary)
            analysis = safe_mapping(turn_summary.get("analysis"))
            evidence.append(
                {
                    "index": index,
                    "path": str(path),
                    "kind": turn_summary.get("kind"),
                    "status": turn_summary.get("status"),
                    "verdict": turn_summary.get("verdict"),
                    "contractStatus": contract.get("status"),
                    "direction": contract.get("direction"),
                    "key": contract.get("key"),
                    "signedYawDeltaDegrees": contract.get("signedYawDeltaDegrees"),
                    "absoluteYawDeltaDegrees": contract.get("absoluteYawDeltaDegrees"),
                    "planarDrift": contract.get("planarDrift"),
                    "candidateOnly": analysis.get("candidateOnly"),
                    "actionableForNavigation": analysis.get("actionableForNavigation"),
                    "movementPermission": analysis.get("movementPermission"),
                    "blockers": contract.get("blockers", []),
                    "warnings": contract.get("warnings", []),
                }
            )
            if contract.get("status") != "passed":
                blockers.append(f"turn-evidence-{index}-contract-not-passed")
                blockers.extend(str(item) for item in contract.get("blockers", []))
            warnings.extend(str(item) for item in contract.get("warnings", []))
        except Exception as exc:  # noqa: BLE001
            blockers.append(f"turn-evidence-{index}-load-or-contract-failed")
            warnings.append(f"{type(exc).__name__}:{exc}")
    return evidence, sorted(set(blockers)), sorted(set(warnings))


def summarize_turn_forward_evidence(paths: Sequence[str] | None) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    evidence: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    for index, raw_path in enumerate(paths or [], start=1):
        path = Path(str(raw_path)).resolve()
        try:
            experiment_summary = load_json_object(path)
            contract = validate_turn_forward_experiment_contract(experiment_summary)
            plan = safe_mapping(safe_mapping(experiment_summary.get("turnAwarePlanSummary")).get("plan"))
            navigation_target = safe_mapping(plan.get("navigationTarget"))
            turn_analysis = safe_mapping(safe_mapping(experiment_summary.get("turnStimulusSummary")).get("analysis"))
            forward_result = safe_mapping(experiment_summary.get("forwardResult"))
            evidence.append(
                {
                    "index": index,
                    "path": str(path),
                    "kind": experiment_summary.get("kind"),
                    "status": experiment_summary.get("status"),
                    "verdict": experiment_summary.get("verdict"),
                    "contractStatus": contract.get("status"),
                    "firstAction": plan.get("firstAction"),
                    "controlIntent": plan.get("controlIntent"),
                    "turnMagnitudeClass": plan.get("turnMagnitudeClass"),
                    "signedBearingDeltaDegrees": navigation_target.get("signedBearingDeltaDegrees"),
                    "absoluteBearingDeltaDegrees": navigation_target.get("absoluteBearingDeltaDegrees"),
                    "observedYawDeltaDegrees": turn_analysis.get("signedYawDeltaDegrees"),
                    "observedPlanarDrift": safe_mapping(turn_analysis.get("coordinateDelta")).get("planar"),
                    "routeStatus": forward_result.get("routeStatus"),
                    "totalProgressDistance": forward_result.get("totalProgressDistance"),
                    "initialPlanarDistance": forward_result.get("initialPlanarDistance"),
                    "finalPlanarDistance": forward_result.get("finalPlanarDistance"),
                    "movementSent": contract.get("movementSent"),
                    "inputSent": contract.get("inputSent"),
                    "navigationControl": contract.get("navigationControl"),
                    "blockers": contract.get("blockers", []),
                    "warnings": contract.get("warnings", []),
                }
            )
            if contract.get("status") != "passed":
                blockers.append(f"turn-forward-evidence-{index}-contract-not-passed")
                blockers.extend(str(item) for item in contract.get("blockers", []))
            warnings.extend(str(item) for item in contract.get("warnings", []))
        except Exception as exc:  # noqa: BLE001
            blockers.append(f"turn-forward-evidence-{index}-load-or-contract-failed")
            warnings.append(f"{type(exc).__name__}:{exc}")
    return evidence, sorted(set(blockers)), sorted(set(warnings))


def report_saved_summary(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"static-owner-nav-route-run-report-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    safety = base_safety()
    source = Path(str(args.report_route_run_summary_json)).resolve() if args.report_route_run_summary_json else None
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "static-owner-nav-route-run-report",
        "generatedAtUtc": utc_iso(),
        "status": "pending",
        "repoRoot": str(root),
        "sourceSummaryJson": str(source) if source else None,
        "turnSummaryJson": [str(Path(path).resolve()) for path in (getattr(args, "turn_summary_json", None) or [])],
        "turnForwardSummaryJson": [str(Path(path).resolve()) for path in (getattr(args, "turn_forward_summary_json", None) or [])],
        "source": {},
        "turnEvidence": [],
        "turnForwardEvidence": [],
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
        summary["errors"].append("report-route-run-summary-json-required")
        return summary
    try:
        route_run_summary = load_json_object(source)
        contract = validate_route_run_summary_contract(route_run_summary)
        summary["source"] = {
            "kind": route_run_summary.get("kind"),
            "status": route_run_summary.get("status"),
            "verdict": route_run_summary.get("verdict"),
            "generatedAtUtc": route_run_summary.get("generatedAtUtc"),
            "operator": route_run_summary.get("operator"),
            "input": route_run_summary.get("input"),
            "aggregate": route_run_summary.get("aggregate"),
            "steps": route_run_summary.get("steps", []),
            "safety": route_run_summary.get("safety"),
            "artifacts": route_run_summary.get("artifacts"),
        }
        summary["contract"] = contract
        summary["blockers"].extend(contract["blockers"])
        summary["warnings"].extend(contract["warnings"])
        turn_evidence, turn_blockers, turn_warnings = summarize_turn_evidence(getattr(args, "turn_summary_json", None))
        summary["turnEvidence"] = turn_evidence
        summary["blockers"].extend(turn_blockers)
        summary["warnings"].extend(turn_warnings)
        turn_forward_evidence, turn_forward_blockers, turn_forward_warnings = summarize_turn_forward_evidence(
            getattr(args, "turn_forward_summary_json", None)
        )
        summary["turnForwardEvidence"] = turn_forward_evidence
        summary["blockers"].extend(turn_forward_blockers)
        summary["warnings"].extend(turn_forward_warnings)
        summary["status"] = "passed" if contract["status"] == "passed" else "blocked"
        if turn_blockers or turn_forward_blockers:
            summary["status"] = "blocked"
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
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


def compact_validation(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    contract = safe_mapping(summary.get("contract"))
    return {
        "status": summary.get("status"),
        "contractStatus": contract.get("status"),
        "stepsRun": contract.get("stepsRun"),
        "arrived": contract.get("arrived"),
        "movementSent": contract.get("movementSent"),
        "inputSent": contract.get("inputSent"),
        "navigationControl": contract.get("navigationControl"),
        "sourceSummaryJson": summary.get("sourceSummaryJson"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }


def compact_report(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    contract = safe_mapping(summary.get("contract"))
    source = safe_mapping(summary.get("source"))
    aggregate = safe_mapping(source.get("aggregate"))
    turn_evidence = [safe_mapping(item) for item in summary.get("turnEvidence", []) if isinstance(item, Mapping)]
    turn_forward_evidence = [safe_mapping(item) for item in summary.get("turnForwardEvidence", []) if isinstance(item, Mapping)]
    # Terrain classification counts across source steps
    terrain_sub_counts: dict[str, int] = {}
    no_progress_step_count = 0
    for step in source.get("steps", []):
        row = safe_mapping(step)
        if row.get("routeStatus") == "no-progress":
            no_progress_step_count += 1
            sub = row.get("noProgressSubClassification") or "unspecified"
            terrain_sub_counts[sub] = terrain_sub_counts.get(sub, 0) + 1
    return {
        "status": summary.get("status"),
        "contractStatus": contract.get("status"),
        "sourceStatus": source.get("status"),
        "sourceVerdict": source.get("verdict"),
        "stepsRun": aggregate.get("stepsRun"),
        "arrived": aggregate.get("arrived"),
        "lastRouteStatus": aggregate.get("lastRouteStatus"),
        "totalProgressDistance": aggregate.get("totalProgressDistance"),
        "finalPlanarDistance": aggregate.get("finalPlanarDistance"),
        "sourceSummaryJson": summary.get("sourceSummaryJson"),
        "turnEvidenceCount": len(turn_evidence),
        "turnDirections": [item.get("direction") for item in turn_evidence],
        "turnEvidenceStatuses": [item.get("contractStatus") for item in turn_evidence],
        "turnForwardEvidenceCount": len(turn_forward_evidence),
        "turnForwardVerdicts": [item.get("verdict") for item in turn_forward_evidence],
        "turnForwardEvidenceStatuses": [item.get("contractStatus") for item in turn_forward_evidence],
        "noProgressStepCount": no_progress_step_count,
        "terrainSubClassifications": terrain_sub_counts,
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
    parser.add_argument("--validate-route-run-summary-json", nargs="?", const="")
    parser.add_argument("--report-route-run-summary-json", nargs="?", const="")
    parser.add_argument("--turn-summary-json", action="append")
    parser.add_argument("--turn-forward-summary-json", action="append")
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
    parser.add_argument("--max-arrival-radius", type=float, default=DEFAULT_MAX_ARRIVAL_RADIUS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--nav-state", action="store_true", help="Read live pointer-chain nav-state (yaw, turn rate) before executing route steps")
    parser.add_argument("--movement-approved", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validation_mode = args.validate_route_run_summary_json is not None
    report_mode = args.report_route_run_summary_json is not None
    if validation_mode and report_mode:
        raise SystemExit("--validate-route-run-summary-json and --report-route-run-summary-json are mutually exclusive")
    summary = validate_saved_summary(args) if validation_mode else report_saved_summary(args) if report_mode else run(args)
    artifacts = safe_mapping(summary.get("artifacts"))
    write_json(Path(str(artifacts["summaryJson"])), summary)
    markdown = build_validation_markdown(summary) if validation_mode else build_report_markdown(summary) if report_mode else build_markdown(summary)
    compact_summary = compact_validation(summary) if validation_mode else compact_report(summary) if report_mode else compact(summary)
    Path(str(artifacts["summaryMarkdown"])).write_text(markdown, encoding="utf-8")
    print(json.dumps(compact_summary) if args.json else json.dumps(compact_summary, indent=2))
    return 0 if summary.get("status") == "passed" else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    sys.exit(main())
