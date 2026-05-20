from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .actor_yaw_current_truth_status import build_current_truth_status
from .actor_yaw_disambiguation_validation import normalize_hex
from .commands import JsonCommandResult, command_envelope, pwsh_file_command, run_json_command
from .reports import write_json, write_text_atomic
from .riftscan_coordination import DEFAULT_RIFTSCAN_ROOT, is_relative_to


CommandRunner = Callable[[list[str], Path, str, int | None], JsonCommandResult]


def default_command_runner(
    args: list[str],
    cwd: Path,
    label: str,
    timeout_seconds: int | None,
) -> JsonCommandResult:
    return run_json_command(args, cwd=cwd, label=label, timeout_seconds=timeout_seconds)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def build_read_player_command(*, repo_root: Path, process_id: int) -> list[str]:
    reader_project = repo_root / "reader" / "RiftReader.Reader" / "RiftReader.Reader.csproj"
    return [
        "dotnet",
        "run",
        "--project",
        str(reader_project),
        "--",
        "--pid",
        str(process_id),
        "--read-player-orientation",
        "--json",
    ]


def build_capture_command(
    *,
    repo_root: Path,
    process_id: int,
    target_window_handle: str,
    process_name: str,
    output_file: Path,
    previous_file: Path,
) -> list[str]:
    return pwsh_file_command(
        repo_root / "scripts" / "capture-actor-orientation.ps1",
        [
            "-ProcessId",
            str(process_id),
            "-TargetWindowHandle",
            target_window_handle,
            "-ProcessName",
            process_name,
            "-OutputFile",
            str(output_file),
            "-PreviousFile",
            str(previous_file),
            "-Json",
        ],
    )


def selected_source_matches(value: Any, expected: Any) -> bool:
    return bool(value) and bool(expected) and normalize_hex(value) == normalize_hex(expected)


def selected_offset_matches(value: Any, expected: Any) -> bool:
    return bool(value) and bool(expected) and normalize_hex(value) == normalize_hex(expected)


def summarize_read_player(
    result: JsonCommandResult,
    *,
    expected_source: str | None,
    expected_offset: str | None,
    output_file: Path,
) -> dict[str, Any]:
    data = result.json_data if isinstance(result.json_data, dict) else {}
    selected_source = data.get("SelectedSourceAddress")
    selected_offset = data.get("BasisPrimaryForwardOffset")
    resolution_mode = data.get("ResolutionMode")
    preferred = data.get("PreferredEstimate") if isinstance(data.get("PreferredEstimate"), dict) else {}
    source_match = selected_source_matches(selected_source, expected_source)
    offset_match = selected_offset_matches(selected_offset, expected_offset)
    mode_ok = str(resolution_mode or "") == "live-behavior-backed-lead"
    ok = result.ok and source_match and offset_match and mode_ok
    return {
        "status": "passed" if ok else "failed",
        "ok": ok,
        "file": str(output_file),
        "exitCode": result.exit_code,
        "selectedSourceAddress": selected_source,
        "basisForwardOffset": selected_offset,
        "resolutionMode": resolution_mode,
        "sourceMatchesPromotedLead": source_match,
        "basisOffsetMatchesPromotedLead": offset_match,
        "preferredYawDegrees": preferred.get("YawDegrees"),
        "preferredPitchDegrees": preferred.get("PitchDegrees"),
        "jsonParseError": result.parse_error,
    }


def summarize_capture(
    result: JsonCommandResult,
    *,
    expected_source: str | None,
    expected_offset: str | None,
    output_file: Path,
) -> dict[str, Any]:
    data = result.json_data if isinstance(result.json_data, dict) else {}
    reader = data.get("ReaderOrientation") if isinstance(data.get("ReaderOrientation"), dict) else {}
    selected_source = reader.get("SelectedSourceAddress")
    selected_offset = reader.get("BasisForwardOffset")
    resolution_mode = reader.get("ResolutionMode")
    preferred = reader.get("PreferredEstimate") if isinstance(reader.get("PreferredEstimate"), dict) else {}
    source_match = selected_source_matches(selected_source, expected_source)
    offset_match = selected_offset_matches(selected_offset, expected_offset)
    mode_ok = str(resolution_mode or "") in {"behavior-backed-lead", "live-behavior-backed-lead"}
    ok = result.ok and source_match and offset_match and mode_ok
    return {
        "status": "passed" if ok else "failed",
        "ok": ok,
        "file": str(output_file),
        "exitCode": result.exit_code,
        "selectedSourceAddress": selected_source,
        "basisForwardOffset": selected_offset,
        "resolutionMode": resolution_mode,
        "sourceMatchesPromotedLead": source_match,
        "basisOffsetMatchesPromotedLead": offset_match,
        "preferredYawDegrees": preferred.get("YawDegrees"),
        "preferredPitchDegrees": preferred.get("PitchDegrees"),
        "jsonParseError": result.parse_error,
    }


def skipped_readback_summary(*, label: str, output_file: Path, reason: str) -> dict[str, Any]:
    return {
        "status": "skipped",
        "ok": False,
        "file": str(output_file),
        "exitCode": None,
        "selectedSourceAddress": None,
        "basisForwardOffset": None,
        "resolutionMode": None,
        "sourceMatchesPromotedLead": False,
        "basisOffsetMatchesPromotedLead": False,
        "preferredYawDegrees": None,
        "preferredPitchDegrees": None,
        "jsonParseError": None,
        "skipReason": f"{label}:{reason}",
    }


def build_smoke_markdown(summary: dict[str, Any]) -> str:
    lead = summary.get("currentActorYawLead") if isinstance(summary.get("currentActorYawLead"), dict) else {}
    target = summary.get("target") if isinstance(summary.get("target"), dict) else {}
    safety = summary.get("safety") if isinstance(summary.get("safety"), dict) else {}
    read_player = summary.get("readPlayerOrientation") if isinstance(summary.get("readPlayerOrientation"), dict) else {}
    capture = summary.get("captureActorOrientation") if isinstance(summary.get("captureActorOrientation"), dict) else {}
    lines = [
        "# Actor-Yaw Readback Smoke",
        "",
        "| Fact | Value |",
        "|---|---|",
        f"| Status | `{summary.get('status')}` |",
        f"| OK | `{str(summary.get('ok')).lower()}` |",
        f"| Target | `{target.get('processName')}` PID `{target.get('processId')}`, HWND `{target.get('targetWindowHandle')}` |",
        f"| Promoted lead | `{lead.get('sourceAddress')} @ {lead.get('basisForwardOffset')}` |",
        f"| Read-player orientation | `{read_player.get('status')}` / `{read_player.get('resolutionMode')}` |",
        f"| Capture actor orientation | `{capture.get('status')}` / `{capture.get('resolutionMode')}` |",
        f"| Movement sent | `{str(safety.get('movementSent')).lower()}` |",
        f"| Movement allowed | `{str(safety.get('movementAllowed')).lower()}` |",
        f"| No Cheat Engine | `{str(safety.get('noCheatEngine')).lower()}` |",
        f"| SavedVariables live truth | `{str(safety.get('savedVariablesUsedAsLiveTruth')).lower()}` |",
        f"| RiftScan writes | `{str(safety.get('writesToRiftScan')).lower()}` |",
    ]
    if summary.get("issues"):
        lines.extend(["", "## Issues", ""])
        for issue in summary.get("issues", []):
            lines.append(f"- `{issue}`")
    return "\n".join(lines).rstrip() + "\n"


def build_latest_pointer(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "mode": "latest-actor-yaw-readback-smoke-pointer",
        "generatedAtUtc": summary.get("generatedAtUtc"),
        "status": summary.get("status"),
        "ok": summary.get("ok"),
        "latestPointerFile": summary.get("latestPointerFile"),
        "summaryFile": summary.get("summaryFile"),
        "markdownFile": summary.get("markdownFile"),
        "runDirectory": summary.get("runDirectory"),
        "target": summary.get("target"),
        "currentActorYawLead": summary.get("currentActorYawLead"),
        "readPlayerOrientation": summary.get("readPlayerOrientation"),
        "captureActorOrientation": summary.get("captureActorOrientation"),
        "safety": summary.get("safety"),
        "issues": summary.get("issues", []),
    }


def run_actor_yaw_readback_smoke(
    *,
    repo_root: Path,
    process_id: int,
    target_window_handle: str,
    process_name: str = "rift_x64",
    output_root: Path | None = None,
    riftscan_root: Path = DEFAULT_RIFTSCAN_ROOT,
    update_latest_pointer: bool = True,
    timeout_seconds: int | None = 120,
    command_runner: CommandRunner = default_command_runner,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    output_root = output_root.resolve() if output_root else repo_root / "scripts" / "captures"
    riftscan_root = riftscan_root.resolve()
    if is_relative_to(output_root, riftscan_root):
        raise ValueError(f"Refusing to write actor-yaw readback smoke output inside RiftScan: {output_root}")

    run_dir = output_root / f"actor-yaw-readback-smoke-currentpid-{process_id}-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    packet_file = repo_root / "docs" / "recovery" / "current-actor-yaw-disambiguation.json"
    lead_file = repo_root / "scripts" / "actor-facing-behavior-backed-lead.json"
    status_report = build_current_truth_status(
        packet_file=packet_file,
        lead_file=lead_file,
        repo_root=repo_root,
        current_process_id=process_id,
        current_target_window_handle=target_window_handle,
    )
    lead = status_report.get("currentActorYawLead") if isinstance(status_report.get("currentActorYawLead"), dict) else {}
    expected_source = lead.get("sourceAddress")
    expected_offset = lead.get("basisForwardOffset")

    read_output_file = run_dir / "read-player-orientation.json"
    capture_output_file = run_dir / "capture-actor-orientation.json"
    capture_previous_file = run_dir / "capture-actor-orientation.previous.json"

    command_results: list[JsonCommandResult] = []
    if status_report.get("status") == "current":
        read_args = build_read_player_command(repo_root=repo_root, process_id=process_id)
        capture_args = build_capture_command(
            repo_root=repo_root,
            process_id=process_id,
            target_window_handle=target_window_handle,
            process_name=process_name,
            output_file=capture_output_file,
            previous_file=capture_previous_file,
        )

        read_result = command_runner(read_args, repo_root, "read-player-orientation", timeout_seconds)
        command_results.append(read_result)
        if read_result.json_data is not None:
            write_json(read_output_file, read_result.json_data)

        capture_result = command_runner(capture_args, repo_root, "capture-actor-orientation", timeout_seconds)
        command_results.append(capture_result)
        if capture_result.json_data is not None and not capture_output_file.exists():
            write_json(capture_output_file, capture_result.json_data)

        read_summary = summarize_read_player(
            read_result,
            expected_source=expected_source,
            expected_offset=expected_offset,
            output_file=read_output_file,
        )
        capture_summary = summarize_capture(
            capture_result,
            expected_source=expected_source,
            expected_offset=expected_offset,
            output_file=capture_output_file,
        )
    else:
        skip_reason = str(status_report.get("status") or "actor-yaw-status-not-current")
        read_summary = skipped_readback_summary(
            label="read-player-orientation",
            output_file=read_output_file,
            reason=skip_reason,
        )
        capture_summary = skipped_readback_summary(
            label="capture-actor-orientation",
            output_file=capture_output_file,
            reason=skip_reason,
        )

    issues: list[str] = []
    if status_report.get("status") != "current":
        issues.append("actor_yaw_status_not_current")
    if status_report.get("status") == "current" and not read_summary["ok"]:
        issues.append("read_player_orientation_failed")
    if status_report.get("status") == "current" and not capture_summary["ok"]:
        issues.append("capture_actor_orientation_failed")

    ok = not issues
    summary = {
        "schemaVersion": 1,
        "mode": "actor-yaw-readback-smoke",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if ok else "failed",
        "ok": ok,
        "repoRoot": str(repo_root),
        "runDirectory": str(run_dir),
        "target": {
            "processName": process_name,
            "processId": process_id,
            "targetWindowHandle": target_window_handle,
        },
        "currentActorYawLead": lead,
        "actorYawCurrentTruthStatus": status_report,
        "readPlayerOrientation": read_summary,
        "captureActorOrientation": capture_summary,
        "safety": {
            "noCheatEngine": True,
            "movementSent": False,
            "movementAttempted": False,
            "movementAllowed": False,
            "writesToRiftScan": False,
            "savedVariablesUsedAsLiveTruth": False,
        },
        "issues": issues,
        "commands": [command_envelope(result) for result in command_results],
    }
    summary_file = run_dir / "run-summary.json"
    markdown_file = run_dir / "run-summary.md"
    write_json(summary_file, summary)
    write_text_atomic(markdown_file, build_smoke_markdown(summary))
    summary["summaryFile"] = str(summary_file)
    summary["markdownFile"] = str(markdown_file)
    if update_latest_pointer:
        latest_pointer_file = output_root / "latest-actor-yaw-readback-smoke.json"
        summary["latestPointerFile"] = str(latest_pointer_file)
        write_json(latest_pointer_file, build_latest_pointer(summary))
    write_json(summary_file, summary)
    return summary


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_arg_parser() -> argparse.ArgumentParser:
    repo_root = default_repo_root()
    parser = argparse.ArgumentParser(description="Run a no-input actor-yaw readback smoke.")
    parser.add_argument("--pid", type=int, required=True, help="Exact target process id.")
    parser.add_argument("--hwnd", required=True, help="Exact target window handle, e.g. 0xE0DB2.")
    parser.add_argument("--process-name", default="rift_x64", help="Expected process name.")
    parser.add_argument("--repo-root", type=Path, default=repo_root, help="RiftReader repo root.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=repo_root / "scripts" / "captures",
        help="Output root for the smoke run directory.",
    )
    parser.add_argument(
        "--riftscan-root",
        type=Path,
        default=DEFAULT_RIFTSCAN_ROOT,
        help="RiftScan provider repo root. Output paths inside this root are refused.",
    )
    parser.add_argument(
        "--no-update-latest-pointer",
        action="store_true",
        help="Do not update latest-actor-yaw-readback-smoke.json.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=120, help="Timeout per child command.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = run_actor_yaw_readback_smoke(
        repo_root=args.repo_root,
        process_id=args.pid,
        target_window_handle=args.hwnd,
        process_name=args.process_name,
        output_root=args.output_root,
        riftscan_root=args.riftscan_root,
        update_latest_pointer=not args.no_update_latest_pointer,
        timeout_seconds=args.timeout_seconds,
    )
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(build_smoke_markdown(summary), end="")
    return 0 if summary.get("ok") else 1
