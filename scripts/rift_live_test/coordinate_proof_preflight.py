from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
PREVIEW_LIMIT = 4000


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def preview_text(value: str, *, limit: int = PREVIEW_LIMIT) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n...<truncated {len(value) - limit} chars>"


def json_from_stdout(stdout: str) -> dict[str, Any] | None:
    text = stdout.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def run_command(
    *,
    name: str,
    args: Sequence[str],
    cwd: Path,
    timeout_seconds: int,
    expected_exit_codes: set[int],
    blocked_exit_codes: set[int] | None = None,
) -> dict[str, Any]:
    blocked_exit_codes = blocked_exit_codes or set()
    start = time.monotonic()
    start_utc = utc_iso()
    try:
        completed = subprocess.run(
            list(args),
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        end_utc = utc_iso()
        duration = round(time.monotonic() - start, 3)
        parsed_stdout = json_from_stdout(completed.stdout)
        if completed.returncode in blocked_exit_codes:
            status = "blocked"
        elif completed.returncode in expected_exit_codes:
            status = "completed"
        else:
            status = "failed"
        parsed_status = str(parsed_stdout.get("status")) if parsed_stdout and parsed_stdout.get("status") else None
        if parsed_status == "blocked":
            status = "blocked"
        elif parsed_status in {"failed", "error"}:
            status = "failed"
        return {
            "name": name,
            "status": status,
            "args": list(args),
            "cwd": str(cwd),
            "exitCode": completed.returncode,
            "startUtc": start_utc,
            "endUtc": end_utc,
            "durationSeconds": duration,
            "stdoutPreview": preview_text(completed.stdout),
            "stderrPreview": preview_text(completed.stderr),
            "stdoutJson": parsed_stdout,
        }
    except subprocess.TimeoutExpired as exc:
        end_utc = utc_iso()
        duration = round(time.monotonic() - start, 3)
        return {
            "name": name,
            "status": "failed",
            "args": list(args),
            "cwd": str(cwd),
            "exitCode": None,
            "startUtc": start_utc,
            "endUtc": end_utc,
            "durationSeconds": duration,
            "stdoutPreview": preview_text(exc.stdout or ""),
            "stderrPreview": preview_text(exc.stderr or ""),
            "error": f"timeout-after-seconds:{timeout_seconds}",
            "stdoutJson": None,
        }


def latest_file(paths: Sequence[Path], *, min_mtime: float | None = None) -> Path | None:
    existing = [path for path in paths if path.exists() and path.is_file()]
    if min_mtime is not None:
        existing = [path for path in existing if path.stat().st_mtime >= min_mtime]
    if not existing:
        return None
    return max(existing, key=lambda path: (path.stat().st_mtime, str(path)))


def latest_rrapicoord_scan(repo_root: Path, target_pid: int, *, min_mtime: float | None = None) -> Path | None:
    return latest_file(
        list((repo_root / "scripts" / "captures").glob(f"rift-api-reference-scan-currentpid-{target_pid}-*.json")),
        min_mtime=min_mtime,
    )


def path_text(path: Path | None, repo_root: Path) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def stdout_artifact(command: Mapping[str, Any], name: str) -> str | None:
    parsed = command.get("stdoutJson") if isinstance(command.get("stdoutJson"), dict) else {}
    value = parsed.get(name)
    return str(value) if value else None


def command_failed(commands: Sequence[Mapping[str, Any]]) -> list[str]:
    failures: list[str] = []
    for command in commands:
        if command.get("status") == "failed":
            failures.append(f"command-failed:{command.get('name')}:exit={command.get('exitCode')}")
    return failures


def command_blockers(commands: Sequence[Mapping[str, Any]]) -> list[str]:
    blockers: list[str] = []
    for command in commands:
        if command.get("status") != "blocked":
            continue
        blocker = command.get("blocker")
        if blocker:
            blockers.append(f"command-blocked:{command.get('name')}:{blocker}")
    return blockers


def markdown_summary(summary: Mapping[str, Any]) -> str:
    artifacts = summary.get("artifacts") if isinstance(summary.get("artifacts"), dict) else {}
    decision = summary.get("decision") if isinstance(summary.get("decision"), dict) else {}
    lines = [
        "# Coordinate proof preflight",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Read-only proof allowed: `{str(decision.get('readOnlyProofAllowed')).lower()}`",
        f"- Movement allowed: `{str(decision.get('movementAllowed')).lower()}`",
        "",
        "## Artifacts",
        "",
        "| Artifact | Path |",
        "|---|---|",
        f"| ChromaLink summary | `{artifacts.get('chromalinkSummary')}` |",
        f"| RRAPICOORD reference | `{artifacts.get('rrapicoordReference')}` |",
        f"| RRAPICOORD scan | `{artifacts.get('rrapicoordScan')}` |",
        f"| Reference watchdog | `{artifacts.get('referenceWatchdogSummary')}` |",
        f"| Milestone review | `{artifacts.get('milestoneReviewSummary')}` |",
        f"| Readiness gate | `{artifacts.get('readinessGateSummary')}` |",
        "",
        "## Commands",
        "",
        "| Command | Status | Exit | Duration s |",
        "|---|---|---:|---:|",
    ]
    for command in summary.get("commands", []):
        if not isinstance(command, dict):
            continue
        lines.append(
            f"| `{command.get('name')}` | `{command.get('status')}` | "
            f"`{command.get('exitCode')}` | `{command.get('durationSeconds')}` |"
        )
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{blocker}`" for blocker in summary.get("blockers", []))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in summary.get("warnings", []))
    return "\n".join(lines).rstrip() + "\n"


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    output_root = args.output_root or repo_root / "scripts" / "captures" / f"coordinate-proof-preflight-{utc_stamp()}"
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    commands: list[dict[str, Any]] = []
    capture_root = repo_root / "scripts" / "captures"
    rrapi_start_mtime = time.time()

    chromalink_command = run_command(
        name="chromalink-world-state-reference",
        args=[
            sys.executable,
            str(repo_root / "scripts" / "chromalink_world_state_reference.py"),
            "--target-pid",
            str(args.target_pid),
            "--target-hwnd",
            str(args.target_hwnd),
            "--process-name",
            str(args.process_name),
            "--json",
        ],
        cwd=repo_root,
        timeout_seconds=args.chromalink_timeout_seconds,
        expected_exit_codes={0, 2},
        blocked_exit_codes={2},
    )
    commands.append(chromalink_command)
    chromalink_summary = stdout_artifact(chromalink_command, "summaryJson")

    rrapicoord_command = run_command(
        name="rrapicoord-reference-scan",
        args=[
            "pwsh",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repo_root / "scripts" / "capture-rift-api-reference-coordinate.ps1"),
            "-ProcessId",
            str(args.target_pid),
            "-TargetWindowHandle",
            str(args.target_hwnd),
            "-ProcessName",
            str(args.process_name),
            "-ScanAttempts",
            str(args.rrapicoord_scan_attempts),
            "-ScanRetryDelayMilliseconds",
            str(args.rrapicoord_retry_delay_ms),
            "-MaxHits",
            str(args.rrapicoord_max_hits),
            "-Json",
        ],
        cwd=repo_root,
        timeout_seconds=args.rrapicoord_timeout_seconds,
        expected_exit_codes={0},
    )
    no_marker = "No usable RRAPICOORD1 marker was found" in (
        f"{rrapicoord_command.get('stdoutPreview', '')}\n{rrapicoord_command.get('stderrPreview', '')}"
    )
    if no_marker:
        rrapicoord_command["status"] = "blocked"
        rrapicoord_command["blocker"] = "rrapicoord-no-usable-marker"
    commands.append(rrapicoord_command)
    rrapicoord_scan = stdout_artifact(rrapicoord_command, "ScanFile") or stdout_artifact(rrapicoord_command, "scanFile")
    rrapicoord_reference = stdout_artifact(rrapicoord_command, "ReferenceFile") or stdout_artifact(rrapicoord_command, "referenceFile")
    if not rrapicoord_scan:
        latest_scan = latest_rrapicoord_scan(repo_root, args.target_pid, min_mtime=rrapi_start_mtime - 1.0)
        rrapicoord_scan = str(latest_scan) if latest_scan else None

    reference_args = [
        sys.executable,
        str(repo_root / "scripts" / "reference_freshness_watchdog.py"),
        "--target-pid",
        str(args.target_pid),
        "--target-hwnd",
        str(args.target_hwnd),
        "--process-name",
        str(args.process_name),
    ]
    if chromalink_summary:
        reference_args.extend(["--chromalink-summary", chromalink_summary])
    if rrapicoord_reference:
        reference_args.extend(["--rrapicoord-reference-file", rrapicoord_reference])
    if rrapicoord_scan:
        reference_args.extend(["--rrapicoord-scan", rrapicoord_scan])
    reference_args.append("--json")
    reference_command = run_command(
        name="reference-freshness-watchdog",
        args=reference_args,
        cwd=repo_root,
        timeout_seconds=args.gate_timeout_seconds,
        expected_exit_codes={0, 2},
        blocked_exit_codes={2},
    )
    commands.append(reference_command)
    reference_summary = stdout_artifact(reference_command, "summaryJson")

    milestone_command = run_command(
        name="riftscan-milestone-review",
        args=[
            sys.executable,
            str(repo_root / "scripts" / "riftscan_milestone_review.py"),
            "--pid",
            str(args.target_pid),
            "--hwnd",
            str(args.target_hwnd),
            "--process-name",
            str(args.process_name),
            "--write-summary",
            "--write-markdown",
            "--compact-json",
        ],
        cwd=repo_root,
        timeout_seconds=args.gate_timeout_seconds,
        expected_exit_codes={0, 2},
        blocked_exit_codes={2},
    )
    commands.append(milestone_command)
    milestone_summary = stdout_artifact(milestone_command, "summaryFile")

    readiness_args = [
        sys.executable,
        str(repo_root / "scripts" / "coordinate_proof_readiness_gate.py"),
        "--target-pid",
        str(args.target_pid),
        "--target-hwnd",
        str(args.target_hwnd),
        "--process-name",
        str(args.process_name),
    ]
    if reference_summary:
        readiness_args.extend(["--reference-watchdog-summary", reference_summary])
    if milestone_summary:
        readiness_args.extend(["--milestone-review-summary", milestone_summary])
    readiness_args.append("--json")
    readiness_command = run_command(
        name="coordinate-proof-readiness-gate",
        args=readiness_args,
        cwd=repo_root,
        timeout_seconds=args.gate_timeout_seconds,
        expected_exit_codes={0, 2},
        blocked_exit_codes={2},
    )
    commands.append(readiness_command)
    readiness_summary = stdout_artifact(readiness_command, "summaryJson")
    readiness_json = readiness_command.get("stdoutJson") if isinstance(readiness_command.get("stdoutJson"), dict) else {}

    command_failures = command_failed(commands)
    readiness_status = readiness_json.get("status")
    readiness_verdict = readiness_json.get("verdict")
    blockers = list(command_failures)
    blockers.extend(command_blockers(commands))
    blockers.extend(readiness_json.get("blockers") or [])
    warnings = list(readiness_json.get("warnings") or [])
    if command_failures:
        status = "failed"
        verdict = "failed-command"
    elif readiness_status == "passed":
        status = "passed"
        verdict = readiness_verdict or "ready-for-read-only-proof"
    else:
        status = "blocked"
        verdict = readiness_verdict or "blocked-coordinate-proof-readiness"
    summary_json = output_root / "summary.json"
    summary_md = output_root / "summary.md"
    summary = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "coordinate-proof-preflight",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "verdict": verdict,
        "target": {
            "processName": args.process_name,
            "pid": args.target_pid,
            "hwnd": args.target_hwnd,
        },
        "decision": {
            "readOnlyProofAllowed": bool(readiness_json.get("readOnlyProofAllowed")) if readiness_json else False,
            "movementAllowed": bool(readiness_json.get("movementAllowed")) if readiness_json else False,
        },
        "commands": commands,
        "blockers": blockers,
        "warnings": warnings,
        "artifacts": {
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
            "chromalinkSummary": chromalink_summary,
            "rrapicoordReference": rrapicoord_reference,
            "rrapicoordScan": rrapicoord_scan,
            "referenceWatchdogSummary": reference_summary,
            "milestoneReviewSummary": milestone_summary,
            "readinessGateSummary": readiness_summary,
        },
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "x64dbgAttached": False,
            "cheatEngineUsed": False,
            "rrapicoordScanReadOnlyProcessMemory": True,
            "targetMemoryWritten": False,
            "savedVariablesUsedAsLiveTruth": False,
            "candidateOnly": status != "passed",
            "promotionEligible": False,
            "githubConnectorWrites": False,
        },
        "next": {
            "recommendedAction": (
                "Run same-target read-only proof/readback, then rerun ProofOnly before movement."
                if status == "passed"
                else "Fix fresh reference blockers before proof/readback or movement."
            )
        },
    }
    write_json(summary_json, summary)
    write_text_atomic(summary_md, markdown_summary(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the safe coordinate proof preflight gate sequence.")
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--target-pid", type=int, required=True)
    parser.add_argument("--target-hwnd", required=True)
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--chromalink-timeout-seconds", type=int, default=20)
    parser.add_argument("--rrapicoord-timeout-seconds", type=int, default=90)
    parser.add_argument("--rrapicoord-scan-attempts", type=int, default=3)
    parser.add_argument("--rrapicoord-retry-delay-ms", type=int, default=1000)
    parser.add_argument("--rrapicoord-max-hits", type=int, default=64)
    parser.add_argument("--gate-timeout-seconds", type=int, default=30)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = build_summary(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "verdict": summary["verdict"],
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "summaryMarkdown": summary["artifacts"]["summaryMarkdown"],
                    "readOnlyProofAllowed": summary["decision"]["readOnlyProofAllowed"],
                    "movementAllowed": summary["decision"]["movementAllowed"],
                    "blockers": summary["blockers"],
                    "warnings": summary["warnings"],
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={summary['status']}")
        print(f"verdict={summary['verdict']}")
        print(f"summaryJson={summary['artifacts']['summaryJson']}")
        if summary["blockers"]:
            print("blockers:")
            for blocker in summary["blockers"]:
                print(f"  - {blocker}")
    if summary["status"] == "passed":
        return 0
    if summary["status"] == "blocked":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
