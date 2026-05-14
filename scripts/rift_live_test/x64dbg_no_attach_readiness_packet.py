from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from contextlib import redirect_stdout
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any

from . import (
    chromalink_world_state_reference,
    x64dbg_access_event_template,
    x64dbg_coord_chain_plan,
    x64dbg_preflight,
)
from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_CURRENT_TRUTH_JSON = Path("docs") / "recovery" / "current-truth.json"


ToolMain = Callable[[list[str] | None], int]
ToolRunner = Callable[[str, ToolMain, list[str]], dict[str, Any]]


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def choose_run_dir(repo_root: Path, output_root: Path | None) -> Path:
    run_dir = output_root.resolve() if output_root else repo_root / "scripts" / "captures" / f"x64dbg-no-attach-readiness-packet-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def parse_json_stdout(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def run_json_tool(name: str, main_fn: ToolMain, argv: list[str]) -> dict[str, Any]:
    capture = StringIO()
    with redirect_stdout(capture):
        exit_code = main_fn([*argv, "--json"])
    stdout = capture.getvalue()
    payload = parse_json_stdout(stdout)
    return {
        "name": name,
        "argv": [*argv, "--json"],
        "exitCode": int(exit_code),
        "payload": payload,
        "stdout": stdout.strip(),
    }


def step_status(step: dict[str, Any]) -> str:
    payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
    return str(payload.get("status") or ("passed" if int(step.get("exitCode") or 0) == 0 else "blocked"))


def step_blockers(step: dict[str, Any]) -> list[str]:
    payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
    if payload.get("fallbackRecovered") is True:
        return []
    blockers = [str(blocker) for blocker in payload.get("blockers", []) if blocker]
    if int(step.get("exitCode") or 0) != 0 and not blockers:
        blockers.append(f"{step.get('name')}-failed:{step.get('exitCode')}")
    return blockers


def step_warnings(step: dict[str, Any]) -> list[str]:
    payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
    warnings = [str(warning) for warning in payload.get("warnings", []) if warning]
    if payload.get("fallbackRecovered") is True:
        warnings.extend(f"fallback-recovered:{blocker}" for blocker in payload.get("blockers", []) if blocker)
    return warnings


def argv_value(argv: list[str], flag: str) -> str | None:
    try:
        index = argv.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(argv):
        return None
    return argv[index + 1]


def read_optional_json(path_value: Any) -> dict[str, Any] | None:
    if not path_value:
        return None
    path = Path(str(path_value))
    if not path.exists():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return document if isinstance(document, dict) else None


def resolve_repo_path(repo_root: Path, path_value: Path | str | None) -> Path | None:
    if path_value is None:
        return None
    path = Path(str(path_value))
    return path if path.is_absolute() else repo_root / path


def append_target_mismatch(
    blockers: list[str],
    *,
    name: str,
    requested: Any,
    current_truth: Any,
    normalize: Callable[[Any], Any] | None = None,
) -> None:
    if requested in (None, "") or current_truth in (None, ""):
        return
    requested_value = normalize(requested) if normalize else requested
    truth_value = normalize(current_truth) if normalize else current_truth
    if requested_value != truth_value:
        blockers.append(f"current-truth-target-{name}-mismatch:{requested_value}!={truth_value}")


def current_truth_target_blockers(args: argparse.Namespace, document: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    target = document.get("target") if isinstance(document.get("target"), dict) else {}
    truth_pid = x64dbg_coord_chain_plan.to_int_or_none(
        target.get("processId") or target.get("pid") or target.get("Pid")
    )
    truth_hwnd = target.get("targetWindowHandle") or target.get("hwnd") or target.get("hwndHex")
    truth_start = target.get("processStartUtc") or target.get("startTimeUtc")
    truth_module_base = target.get("moduleBase") or target.get("moduleBaseAddressHex") or target.get("moduleBaseAddress")

    if args.target_pid is not None and truth_pid is None:
        blockers.append("current-truth-target-pid-missing")
    if args.target_hwnd and not truth_hwnd:
        blockers.append("current-truth-target-hwnd-missing")
    if args.expected_start_time_utc and not truth_start:
        blockers.append("current-truth-target-start-missing")
    if args.expected_module_base and not truth_module_base:
        blockers.append("current-truth-target-module-base-missing")

    append_target_mismatch(
        blockers,
        name="pid",
        requested=args.target_pid,
        current_truth=truth_pid,
        normalize=lambda value: int(value),
    )
    append_target_mismatch(
        blockers,
        name="hwnd",
        requested=args.target_hwnd,
        current_truth=truth_hwnd,
        normalize=lambda value: x64dbg_coord_chain_plan.normalize_hwnd(str(value)),
    )
    append_target_mismatch(
        blockers,
        name="start",
        requested=args.expected_start_time_utc,
        current_truth=truth_start,
        normalize=lambda value: str(value).strip(),
    )
    append_target_mismatch(
        blockers,
        name="module-base",
        requested=args.expected_module_base,
        current_truth=truth_module_base,
        normalize=lambda value: x64dbg_coord_chain_plan.normalize_hex_int(value),
    )
    return blockers


def latest_candidate_selection(args: argparse.Namespace) -> tuple[str, str, list[str], list[str]]:
    warnings = [
        "latest-candidate-fallback-explicitly-allowed",
        "latest-candidate-fallback-is-not-default; prefer current-truth or explicit candidate selection",
    ]
    args.candidate_selection_source = "latest-fallback"
    args.candidate_selection_current_truth_json = None
    args.candidate_selection_candidate_file = "latest"
    args.candidate_selection_candidate_id = "best"
    return "latest", "best", [], warnings


def resolve_candidate_selection(args: argparse.Namespace, repo_root: Path) -> tuple[str | None, str | None, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    args.candidate_selection_source = None
    args.candidate_selection_current_truth_json = None
    args.candidate_selection_candidate_file = None
    args.candidate_selection_candidate_id = None

    if args.candidate_file:
        raw_candidate_file = str(args.candidate_file).strip()
        if raw_candidate_file.lower() == "latest":
            candidate_id = args.candidate_id or "best"
            if not args.allow_latest_candidate_fallback:
                blockers.append("candidate-file-latest-requires-allow-latest-candidate-fallback")
            warnings.append("candidate-file-latest-explicitly-requested")
            args.candidate_selection_source = "explicit-latest"
            args.candidate_selection_candidate_file = "latest"
            args.candidate_selection_candidate_id = candidate_id
            return "latest", candidate_id, blockers, warnings

        candidate_file = resolve_repo_path(repo_root, args.candidate_file)
        candidate_id = args.candidate_id or "best"
        if candidate_file is None:
            blockers.append("candidate-file-resolve-failed")
        elif not candidate_file.exists():
            blockers.append(f"candidate-file-not-found:{candidate_file}")
        if not args.candidate_id:
            warnings.append("candidate-id-not-supplied-defaulted-to-best")
        args.candidate_selection_source = "explicit"
        args.candidate_selection_candidate_file = str(candidate_file if candidate_file else args.candidate_file)
        args.candidate_selection_candidate_id = candidate_id
        return args.candidate_selection_candidate_file, candidate_id, blockers, warnings

    current_truth_path = resolve_repo_path(
        repo_root,
        args.current_truth_json if args.current_truth_json else DEFAULT_CURRENT_TRUTH_JSON,
    )
    args.candidate_selection_current_truth_json = str(current_truth_path) if current_truth_path else None
    if current_truth_path is None or not current_truth_path.exists():
        blockers.append(f"current-truth-json-not-found:{current_truth_path}")
    else:
        try:
            document = json.loads(current_truth_path.read_text(encoding="utf-8"))
        except Exception as exc:
            blockers.append(f"current-truth-json-read-failed:{type(exc).__name__}:{exc}")
            document = None
        if not isinstance(document, dict):
            blockers.append("current-truth-json-must-be-object")
        else:
            blockers.extend(current_truth_target_blockers(args, document))
            candidate = document.get("bestCurrentCandidate")
            if not isinstance(candidate, dict):
                blockers.append("current-truth-best-current-candidate-missing")
            else:
                candidate_file_value = candidate.get("candidateFile")
                candidate_id_value = candidate.get("candidateId")
                if not candidate_file_value:
                    blockers.append("current-truth-candidate-file-missing")
                if not candidate_id_value:
                    blockers.append("current-truth-candidate-id-missing")
                candidate_file = resolve_repo_path(repo_root, candidate_file_value) if candidate_file_value else None
                if candidate_file is not None and not candidate_file.exists():
                    blockers.append(f"current-truth-candidate-file-not-found:{candidate_file}")
                if candidate_file is not None and candidate_id_value:
                    args.candidate_selection_source = "current-truth"
                    args.candidate_selection_candidate_file = str(candidate_file)
                    args.candidate_selection_candidate_id = str(candidate_id_value)

    if blockers and args.allow_latest_candidate_fallback:
        _, _, _, fallback_warnings = latest_candidate_selection(args)
        warnings.extend([f"current-truth-candidate-selection-blocker:{blocker}" for blocker in blockers])
        warnings.extend(fallback_warnings)
        return "latest", "best", [], warnings

    if blockers:
        return None, None, blockers, warnings

    if args.candidate_selection_candidate_file and args.candidate_selection_candidate_id:
        return args.candidate_selection_candidate_file, args.candidate_selection_candidate_id, blockers, warnings

    blockers.append("current-truth-candidate-selection-unresolved")
    return None, None, blockers, warnings


def template_candidate_evidence(template_payload: dict[str, Any]) -> dict[str, Any] | None:
    summary = read_optional_json(template_payload.get("summaryJson"))
    if isinstance(summary, dict) and isinstance(summary.get("candidateEvidence"), dict):
        return summary["candidateEvidence"]
    template = read_optional_json(template_payload.get("templateJson"))
    if isinstance(template, dict) and isinstance(template.get("candidateEvidence"), dict):
        return template["candidateEvidence"]
    return None


def build_preflight_argv(args: argparse.Namespace, repo_root: Path) -> tuple[list[str] | None, list[str]]:
    blockers: list[str] = []
    if args.target_pid is None:
        blockers.append("target-pid-required-for-preflight")
    if not args.target_hwnd:
        blockers.append("target-hwnd-required-for-preflight")
    if blockers:
        return None, blockers

    argv = [
        "--repo-root",
        str(repo_root),
        "--require-exact-target",
        "--require-no-debugger-process",
        "--target-pid",
        str(args.target_pid),
        "--target-hwnd",
        str(args.target_hwnd),
    ]
    if args.expected_start_time_utc:
        argv.extend(["--expected-start-time-utc", str(args.expected_start_time_utc)])
    if args.expected_module_base:
        argv.extend(["--expected-module-base", str(args.expected_module_base)])
    return argv, blockers


def blocked_step(name: str, blockers: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "argv": [],
        "exitCode": 2,
        "payload": {
            "status": "blocked",
            "blockers": blockers,
            "warnings": [],
        },
        "stdout": "",
    }


def markdown_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# x64dbg no-attach readiness packet",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Readiness: `{summary.get('readinessStatus')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Movement sent: `{str(summary.get('safety', {}).get('movementSent')).lower()}`",
        f"- x64dbg live attach started: `{str(summary.get('safety', {}).get('x64dbgLiveAttachStarted')).lower()}`",
        f"- x64dbg commands executed: `{str(summary.get('safety', {}).get('x64dbgCommandsExecuted')).lower()}`",
        f"- Summary JSON: `{summary.get('artifacts', {}).get('summaryJson')}`",
        f"- Planner summary: `{summary.get('artifacts', {}).get('plannerSummaryJson')}`",
        f"- Access-event template: `{summary.get('artifacts', {}).get('accessEventTemplateJson')}`",
        f"- Compact handoff: `{summary.get('artifacts', {}).get('compactHandoffMarkdown')}`",
        "",
        "## Steps",
        "",
        "| Step | Exit | Status | Key artifact |",
        "|---|---:|---|---|",
    ]
    for step in summary.get("steps", []):
        payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
        key_artifact = (
            payload.get("summaryJson")
            or payload.get("referenceJson")
            or payload.get("compactHandoffMarkdown")
            or payload.get("summaryMarkdown")
            or ""
        )
        lines.append(
            f"| `{step.get('name')}` | `{step.get('exitCode')}` | `{step_status(step)}` | `{key_artifact}` |"
        )
    if summary.get("candidate"):
        candidate = summary["candidate"]
        lines.extend(
            [
                "",
                "## Candidate",
                "",
                f"- Candidate id: `{candidate.get('candidateId')}`",
                f"- Address: `{candidate.get('address')}`",
                f"- Artifact: `{candidate.get('artifactPath')}`",
                "- Promotion state: `candidate-only`",
            ]
        )
    if summary.get("candidateSelection"):
        selection = summary["candidateSelection"]
        lines.extend(
            [
                "",
                "## Candidate selection",
                "",
                f"- Source: `{selection.get('source')}`",
                f"- Current-truth JSON: `{selection.get('currentTruthJson')}`",
                f"- Candidate file: `{selection.get('candidateFile')}`",
                f"- Candidate id: `{selection.get('candidateId')}`",
                f"- Latest fallback allowed: `{str(selection.get('allowLatestCandidateFallback')).lower()}`",
            ]
        )
    if summary.get("candidateEvidence"):
        evidence = summary["candidateEvidence"]
        selected = evidence.get("selectedAddress") if isinstance(evidence.get("selectedAddress"), dict) else {}
        lines.extend(
            [
                "",
                "## Candidate evidence",
                "",
                f"- Evidence kind: `{evidence.get('kind')}`",
                f"- Evidence path: `{evidence.get('path')}`",
                f"- Selected address: `{selected.get('addressHex')}`",
                f"- Pose support: `{selected.get('supportPoseCount')}`",
                f"- Pose groups: `{evidence.get('poseGroupCount')}`",
                f"- Candidate-only: `{str(evidence.get('candidateOnly')).lower()}`",
                f"- Promotion eligible: `{str(evidence.get('promotionEligible')).lower()}`",
            ]
        )
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{warning}`" for warning in summary["warnings"])
    return "\n".join(lines).rstrip() + "\n"


def build_summary(args: argparse.Namespace, run_dir: Path, steps: list[dict[str, Any]]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    for step in steps:
        blockers.extend(f"{step.get('name')}:{blocker}" for blocker in step_blockers(step))
        warnings.extend(f"{step.get('name')}:{warning}" for warning in step_warnings(step))

    planner_step = next((step for step in steps if step.get("name") == "x64dbg_coord_chain_plan"), None)
    planner_payload = planner_step.get("payload") if planner_step and isinstance(planner_step.get("payload"), dict) else {}
    planner_argv = planner_step.get("argv") if planner_step and isinstance(planner_step.get("argv"), list) else []
    template_step = next((step for step in steps if step.get("name") == "x64dbg_access_event_template"), None)
    template_payload = template_step.get("payload") if template_step and isinstance(template_step.get("payload"), dict) else {}
    candidate_evidence = template_candidate_evidence(template_payload)
    planner_summary: dict[str, Any] = {}
    planner_summary_path = planner_payload.get("summaryJson")
    if planner_summary_path:
        try:
            loaded = json.loads(Path(planner_summary_path).read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                planner_summary = loaded
        except Exception as exc:
            blockers.append(f"x64dbg_coord_chain_plan:planner-summary-read-failed:{type(exc).__name__}")

    candidate = planner_summary.get("candidate") if isinstance(planner_summary.get("candidate"), dict) else None
    readiness = planner_summary.get("readiness") if isinstance(planner_summary.get("readiness"), dict) else {}
    readiness_status = readiness.get("status")
    status = "passed" if not blockers and planner_summary.get("status") == "planned" else "blocked"
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "x64dbg-no-attach-readiness-packet",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "readinessStatus": readiness_status,
        "target": {
            "processName": args.process_name,
            "pid": args.target_pid,
            "hwnd": args.target_hwnd,
            "expectedStartTimeUtc": args.expected_start_time_utc,
            "expectedModuleBase": args.expected_module_base,
        },
        "safety": {
            "movementSent": False,
            "gameInputSent": False,
            "memoryWritten": False,
            "breakpointsSet": False,
            "watchpointsSet": False,
            "x64dbgLiveAttachStarted": False,
            "x64dbgCommandsExecuted": False,
            "noAttachWorkflow": True,
        },
        "candidate": candidate,
        "candidateSelection": {
            "source": getattr(args, "candidate_selection_source", None),
            "currentTruthJson": getattr(args, "candidate_selection_current_truth_json", None),
            "candidateFile": getattr(args, "candidate_selection_candidate_file", None),
            "candidateId": getattr(args, "candidate_selection_candidate_id", None),
            "allowLatestCandidateFallback": bool(getattr(args, "allow_latest_candidate_fallback", False)),
        },
        "candidateEvidence": candidate_evidence,
        "plannerStatus": planner_summary.get("status"),
        "steps": steps,
        "blockers": blockers,
        "warnings": warnings,
        "apiCoordinateSource": {
            "plannerArgument": argv_value([str(item) for item in planner_argv], "--api-coordinate-file")
            if planner_argv
            else None,
            "chromalinkReferenceJson": next(
                (
                    step.get("payload", {}).get("referenceJson")
                    for step in steps
                    if step.get("name") == "chromalink_world_state_reference" and isinstance(step.get("payload"), dict)
                ),
                None,
            ),
            "fallbackUsed": any(
                bool(step.get("payload", {}).get("fallbackRecovered"))
                for step in steps
                if isinstance(step.get("payload"), dict)
            ),
        },
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
            "preflightSummaryJson": next(
                (
                    step.get("payload", {}).get("summaryJson")
                    for step in steps
                    if step.get("name") == "x64dbg_preflight" and isinstance(step.get("payload"), dict)
                ),
                None,
            ),
            "chromalinkReferenceJson": next(
                (
                    step.get("payload", {}).get("referenceJson")
                    for step in steps
                    if step.get("name") == "chromalink_world_state_reference" and isinstance(step.get("payload"), dict)
                ),
                None,
            ),
            "plannerSummaryJson": planner_payload.get("summaryJson"),
            "accessEventTemplateSummaryJson": template_payload.get("summaryJson"),
            "accessEventTemplateJson": template_payload.get("templateJson"),
            "compactHandoffJson": planner_payload.get("compactHandoffJson"),
            "compactHandoffMarkdown": planner_payload.get("compactHandoffMarkdown"),
        },
    }


def run_packet(args: argparse.Namespace, tool_runner: ToolRunner = run_json_tool) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    run_dir = choose_run_dir(repo_root, args.output_root)
    steps: list[dict[str, Any]] = []

    preflight_argv, preflight_blockers = build_preflight_argv(args, repo_root)
    if preflight_argv is None:
        steps.append(blocked_step("x64dbg_preflight", preflight_blockers))
        summary = build_summary(args, run_dir, steps)
        write_json(Path(summary["artifacts"]["summaryJson"]), summary)
        write_text_atomic(Path(summary["artifacts"]["summaryMarkdown"]), markdown_summary(summary))
        return summary

    preflight_step = tool_runner("x64dbg_preflight", x64dbg_preflight.main, preflight_argv)
    steps.append(preflight_step)
    if int(preflight_step.get("exitCode") or 0) != 0:
        summary = build_summary(args, run_dir, steps)
        write_json(Path(summary["artifacts"]["summaryJson"]), summary)
        write_text_atomic(Path(summary["artifacts"]["summaryMarkdown"]), markdown_summary(summary))
        return summary

    preflight_summary = preflight_step.get("payload", {}).get("summaryJson")
    if args.api_coordinate_file:
        reference_json = str(args.api_coordinate_file)
    else:
        chromalink_argv = [
            "--repo-root",
            str(repo_root),
            "--preflight-summary",
            str(preflight_summary),
        ]
        if args.world_state_file:
            chromalink_argv.extend(["--world-state-file", str(args.world_state_file)])
        if args.world_state_url:
            chromalink_argv.extend(["--world-state-url", str(args.world_state_url)])
        chromalink_argv.extend(["--timeout-seconds", str(args.timeout_seconds)])

        chromalink_step = tool_runner(
            "chromalink_world_state_reference",
            chromalink_world_state_reference.main,
            chromalink_argv,
        )
        steps.append(chromalink_step)
        if int(chromalink_step.get("exitCode") or 0) == 0:
            reference_json = chromalink_step.get("payload", {}).get("referenceJson")
        elif not args.no_api_coordinate_latest_fallback:
            payload = chromalink_step.get("payload") if isinstance(chromalink_step.get("payload"), dict) else {}
            payload["fallbackRecovered"] = True
            payload["status"] = "fallback"
            payload.setdefault("warnings", [])
            payload["warnings"].append("chromalink-reference-unavailable-using-api-coordinate-file:latest")
            chromalink_step["payload"] = payload
            reference_json = "latest"
        else:
            summary = build_summary(args, run_dir, steps)
            write_json(Path(summary["artifacts"]["summaryJson"]), summary)
            write_text_atomic(Path(summary["artifacts"]["summaryMarkdown"]), markdown_summary(summary))
            return summary

    candidate_file, candidate_id, candidate_blockers, candidate_warnings = resolve_candidate_selection(args, repo_root)
    if candidate_blockers:
        steps.append(blocked_step("candidate_selection", candidate_blockers))
        summary = build_summary(args, run_dir, steps)
        write_json(Path(summary["artifacts"]["summaryJson"]), summary)
        write_text_atomic(Path(summary["artifacts"]["summaryMarkdown"]), markdown_summary(summary))
        return summary
    if candidate_warnings:
        steps.append(
            {
                "name": "candidate_selection",
                "argv": [],
                "exitCode": 0,
                "payload": {
                    "status": "passed",
                    "blockers": [],
                    "warnings": candidate_warnings,
                },
                "stdout": "",
            }
        )

    planner_argv = [
        "--repo-root",
        str(repo_root),
        "--preflight-summary",
        str(preflight_summary),
        "--api-coordinate-file",
        str(reference_json),
        "--candidate-file",
        str(candidate_file),
        "--candidate-id",
        str(candidate_id),
        "--strict-live-debugger-readiness",
    ]
    planner_step = tool_runner("x64dbg_coord_chain_plan", x64dbg_coord_chain_plan.main, planner_argv)
    steps.append(planner_step)
    if int(planner_step.get("exitCode") or 0) != 0:
        summary = build_summary(args, run_dir, steps)
        write_json(Path(summary["artifacts"]["summaryJson"]), summary)
        write_text_atomic(Path(summary["artifacts"]["summaryMarkdown"]), markdown_summary(summary))
        return summary

    planner_summary = planner_step.get("payload", {}).get("summaryJson")
    template_argv = [
        "--repo-root",
        str(repo_root),
        "--planner-summary",
        str(planner_summary),
        "--output-root",
        str(run_dir / "access-event-template"),
    ]
    template_step = tool_runner(
        "x64dbg_access_event_template",
        x64dbg_access_event_template.main,
        template_argv,
    )
    steps.append(template_step)

    summary = build_summary(args, run_dir, steps)
    write_json(Path(summary["artifacts"]["summaryJson"]), summary)
    write_text_atomic(Path(summary["artifacts"]["summaryMarkdown"]), markdown_summary(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a no-attach x64dbg readiness packet from exact preflight, an API coordinate reference, "
            "and an explicit or current-truth coordinate candidate."
        )
    )
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--target-pid", type=int, required=True)
    parser.add_argument("--target-hwnd", required=True)
    parser.add_argument("--expected-start-time-utc", default=None)
    parser.add_argument("--expected-module-base", default=None)
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument("--world-state-file", type=Path, default=None)
    parser.add_argument("--world-state-url", default=chromalink_world_state_reference.DEFAULT_WORLD_STATE_URL)
    parser.add_argument("--timeout-seconds", type=float, default=2.0)
    parser.add_argument(
        "--candidate-file",
        type=Path,
        default=None,
        help=(
            "Planner-compatible coordinate candidate JSON. When omitted, the helper uses "
            "docs/recovery/current-truth.json bestCurrentCandidate and verifies it matches the exact target."
        ),
    )
    parser.add_argument(
        "--candidate-id",
        default=None,
        help="Candidate id inside --candidate-file. Defaults to current-truth candidate id, or 'best' only for explicit files.",
    )
    parser.add_argument(
        "--current-truth-json",
        type=Path,
        default=None,
        help=(
            "Current truth dashboard JSON used to select the candidate when --candidate-file is omitted. "
            "Defaults to docs/recovery/current-truth.json under --repo-root."
        ),
    )
    parser.add_argument(
        "--allow-latest-candidate-fallback",
        action="store_true",
        help=(
            "Explicitly allow the older planner --candidate-file latest/--candidate-id best fallback if "
            "current-truth candidate selection fails. Default is fail-closed to avoid stale candidates."
        ),
    )
    parser.add_argument(
        "--api-coordinate-file",
        default=None,
        help=(
            "Planner-compatible API coordinate file, or 'latest'. When supplied, ChromaLink capture is skipped. "
            "Without this, ChromaLink is attempted first and strict planner validation falls back to 'latest' "
            "if ChromaLink is unavailable."
        ),
    )
    parser.add_argument(
        "--no-api-coordinate-latest-fallback",
        action="store_true",
        help="Do not fall back to --api-coordinate-file latest when ChromaLink reference capture fails.",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = run_packet(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "readinessStatus": summary["readinessStatus"],
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "summaryMarkdown": summary["artifacts"]["summaryMarkdown"],
                    "preflightSummaryJson": summary["artifacts"]["preflightSummaryJson"],
                    "chromalinkReferenceJson": summary["artifacts"]["chromalinkReferenceJson"],
                    "apiCoordinateSource": summary["apiCoordinateSource"],
                    "plannerSummaryJson": summary["artifacts"]["plannerSummaryJson"],
                    "accessEventTemplateJson": summary["artifacts"]["accessEventTemplateJson"],
                    "compactHandoffMarkdown": summary["artifacts"]["compactHandoffMarkdown"],
                    "candidateSelection": summary.get("candidateSelection"),
                    "candidateEvidence": summary.get("candidateEvidence"),
                    "blockers": summary["blockers"],
                    "warnings": summary["warnings"],
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={summary['status']}")
        print(f"readinessStatus={summary['readinessStatus']}")
        print(f"summaryJson={summary['artifacts']['summaryJson']}")
        print(f"apiCoordinateSource={summary['apiCoordinateSource']}")
        print(f"plannerSummaryJson={summary['artifacts']['plannerSummaryJson']}")
        print(f"accessEventTemplateJson={summary['artifacts']['accessEventTemplateJson']}")
        if summary["blockers"]:
            print("blockers:")
            for blocker in summary["blockers"]:
                print(f"  - {blocker}")
    return 0 if summary["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
