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

    planner_argv = [
        "--repo-root",
        str(repo_root),
        "--preflight-summary",
        str(preflight_summary),
        "--api-coordinate-file",
        str(reference_json),
        "--candidate-file",
        "latest",
        "--candidate-id",
        "best",
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
            "and the latest candidate scan."
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
