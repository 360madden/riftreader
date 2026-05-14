#!/usr/bin/env python3
"""Python-first controller for the RiftWindowCapture .NET tool.

This script is intentionally orchestration-only: it builds/runs the C# capture
core, captures child-command envelopes, writes durable controller summaries, and
keeps all safety state explicit. It does not send game input, attach debuggers,
read process memory, or mutate Git state.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT = REPO_ROOT / "tools" / "rift-window-capture" / "RiftWindowCapture.csproj"
EXE = (
    REPO_ROOT
    / "tools"
    / "rift-window-capture"
    / "bin"
    / "Debug"
    / "net10.0-windows10.0.19041.0"
    / "RiftWindowCapture.exe"
)
CAPTURES_ROOT = REPO_ROOT / "scripts" / "captures"
CONTROLLER_SCHEMA = "rift-window-capture-controller/v1"
COMMANDS = {"capture", "benchmark", "inspect", "validate"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def preview(text: str, limit: int = 4_000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... <truncated {len(text) - limit} chars>"


def path_for_json(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def resolve_output_root(value: str | None, command: str) -> Path:
    if value:
        candidate = Path(value)
        return candidate if candidate.is_absolute() else REPO_ROOT / candidate
    return CAPTURES_ROOT / f"rift-window-capture-python-{command}-{stamp()}"


def contains_option(args: list[str], name: str) -> bool:
    return any(arg == name or arg.startswith(f"{name}=") for arg in args)


def parse_json_object(stdout: str) -> dict[str, Any] | None:
    stripped = stdout.strip()
    if not stripped:
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


@dataclass(slots=True)
class CommandEnvelope:
    name: str
    command: list[str]
    cwd: str
    startedAtUtc: str
    endedAtUtc: str
    durationMs: float
    exitCode: int
    stdoutPreview: str
    stderrPreview: str


def run_child(name: str, command: list[str], *, timeout: int) -> tuple[CommandEnvelope, str]:
    started = utc_now()
    start = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    duration_ms = (time.perf_counter() - start) * 1000.0
    envelope = CommandEnvelope(
        name=name,
        command=command,
        cwd=str(REPO_ROOT),
        startedAtUtc=started,
        endedAtUtc=utc_now(),
        durationMs=round(duration_ms, 3),
        exitCode=completed.returncode,
        stdoutPreview=preview(completed.stdout),
        stderrPreview=preview(completed.stderr),
    )
    return envelope, completed.stdout


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Python controller for the C# Rift window capture tool. Put the optional "
            "tool command first (capture, benchmark, inspect, validate); unknown "
            "arguments are forwarded to RiftWindowCapture.exe."
        ),
        allow_abbrev=False,
    )
    parser.add_argument("--output-root", help="Artifact output root. Defaults to scripts/captures/rift-window-capture-python-<command>-<stamp>.")
    parser.add_argument("--no-build", action="store_true", help="Skip dotnet build and run the existing executable.")
    parser.add_argument("--dry-run", action="store_true", help="Write the controller summary and command plan without running child commands.")
    parser.add_argument("--self-test", action="store_true", help="Run a no-input invalid-HWND blocker smoke test and treat the expected block as success.")
    parser.add_argument("--json", action="store_true", help="Print the controller summary JSON to stdout.")
    parser.add_argument("--timeout-seconds", type=int, default=90, help="Timeout per child process.")
    return parser


def split_command(argv: list[str] | None) -> tuple[str, list[str]]:
    remaining = list(sys.argv[1:] if argv is None else argv)
    if remaining and remaining[0].lower() in COMMANDS:
        return remaining[0].lower(), remaining[1:]
    return "capture", remaining


def make_tool_args(command: str, forwarded: list[str], output_root: Path, *, self_test: bool) -> list[str]:
    if self_test:
        command = "capture"
        forwarded = ["--hwnd", "0x1", "--timeout-ms", "250", "--json"]

    args = [str(EXE), command, *forwarded]
    if command in {"capture", "benchmark"} and not contains_option(forwarded, "--output-root"):
        args.extend(["--output-root", str(output_root)])
    if command in {"capture", "benchmark", "inspect", "validate"} and not contains_option(forwarded, "--json"):
        args.append("--json")
    return args


def write_summary_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Rift window capture controller summary",
        "",
        f"- Status: `{summary['status']}`",
        f"- Command: `{summary['command']}`",
        f"- Started UTC: `{summary['startedAtUtc']}`",
        f"- Ended UTC: `{summary['endedAtUtc']}`",
        f"- Output root: `{summary['artifacts']['outputRoot']}`",
        f"- Dry run: `{str(summary['dryRun']).lower()}`",
        f"- Self test: `{str(summary['selfTest']).lower()}`",
        "",
        "## Safety",
        "",
    ]
    for key, value in summary["safety"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")

    if summary["blockers"]:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {blocker}" for blocker in summary["blockers"])

    if summary["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in summary["warnings"])

    lines.extend(["", "## Child commands", ""])
    if summary["commands"]:
        for envelope in summary["commands"]:
            lines.append(f"- `{envelope['name']}` exit `{envelope['exitCode']}` in `{envelope['durationMs']:.1f} ms`")
    else:
        lines.append("- None.")

    lines.extend(["", "## Recommended action", "", f"- {summary['next']['recommendedAction']}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def finish_summary(output_root: Path, summary: dict[str, Any]) -> dict[str, Any]:
    summary_json = output_root / "controller-summary.json"
    summary_md = output_root / "controller-summary.md"
    summary["artifacts"]["summaryJson"] = path_for_json(summary_json)
    summary["artifacts"]["summaryMarkdown"] = path_for_json(summary_md)
    output_root.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    write_summary_markdown(summary_md, summary)
    return summary


def status_from_tool(exit_code: int, tool_json: dict[str, Any] | None) -> tuple[str, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    if tool_json:
        blockers.extend(str(item) for item in tool_json.get("blockers", []) if item)
        warnings.extend(str(item) for item in tool_json.get("warnings", []) if item)
        message = tool_json.get("message")
        if exit_code == 2 and message and not blockers:
            blockers.append(str(message))

    if exit_code == 0:
        return "passed", blockers, warnings
    if exit_code == 2:
        return "blocked", blockers, warnings
    return "failed", blockers, warnings


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    command, parse_args = split_command(argv)
    args, forwarded = parser.parse_known_args(parse_args)
    output_root = resolve_output_root(args.output_root, "self-test" if args.self_test else command)
    output_root.mkdir(parents=True, exist_ok=True)

    started = utc_now()
    tool_args = make_tool_args(command, forwarded, output_root, self_test=args.self_test)
    command_plan = []
    if not args.no_build:
        command_plan.append(["dotnet", "build", str(PROJECT), "--nologo", "--verbosity", "quiet"])
    command_plan.append(tool_args)

    summary: dict[str, Any] = {
        "schema": CONTROLLER_SCHEMA,
        "status": "passed",
        "command": "self-test" if args.self_test else command,
        "startedAtUtc": started,
        "endedAtUtc": started,
        "durationMs": 0.0,
        "dryRun": args.dry_run,
        "selfTest": args.self_test,
        "toolArgs": tool_args,
        "commandPlan": command_plan,
        "commands": [],
        "toolReport": None,
        "expectedBlockerObserved": None,
        "blockers": [],
        "warnings": [],
        "errors": [],
        "artifacts": {
            "outputRoot": path_for_json(output_root),
            "summaryJson": "",
            "summaryMarkdown": "",
        },
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgAttached": False,
            "providerWrite": False,
            "githubConnectorWrites": False,
        },
        "next": {
            "recommendedAction": "Review controller-summary.json and the native capture manifest before using artifacts in downstream workflows.",
        },
    }

    start = time.perf_counter()
    exit_code = 0
    try:
        if args.dry_run:
            summary["next"]["recommendedAction"] = "Run again without --dry-run after reviewing the command plan."
        else:
            if not args.no_build:
                build, _ = run_child("dotnet-build", command_plan[0], timeout=args.timeout_seconds)
                summary["commands"].append(asdict(build))
                if build.exitCode != 0:
                    summary["status"] = "failed"
                    summary["errors"].append("dotnet build failed")
                    exit_code = 1
                    return finish_and_print(summary, output_root, start, args.json, exit_code)

            capture, capture_stdout = run_child("rift-window-capture", tool_args, timeout=args.timeout_seconds)
            summary["commands"].append(asdict(capture))
            tool_json = parse_json_object(capture_stdout)
            summary["toolReport"] = tool_json
            status, blockers, warnings = status_from_tool(capture.exitCode, tool_json)
            summary["blockers"].extend(blockers)
            summary["warnings"].extend(warnings)

            if args.self_test:
                expected = capture.exitCode == 2 and bool(tool_json and tool_json.get("knownBlocker"))
                summary["expectedBlockerObserved"] = expected
                if expected:
                    summary["status"] = "passed"
                    summary["next"]["recommendedAction"] = "Self-test passed; run a real capture with exact PID/HWND/process-start gates when needed."
                    exit_code = 0
                else:
                    summary["status"] = "failed"
                    summary["errors"].append("self-test did not observe the expected known blocker")
                    exit_code = 1
            else:
                summary["status"] = status
                exit_code = 0 if status == "passed" else 2 if status == "blocked" else 1
    except subprocess.TimeoutExpired as exc:
        summary["status"] = "failed"
        summary["errors"].append(f"child command timed out after {exc.timeout} seconds")
        exit_code = 1
    except Exception as exc:  # pragma: no cover - defensive operator evidence.
        summary["status"] = "failed"
        summary["errors"].append(f"{exc.__class__.__name__}: {exc}")
        exit_code = 1

    return finish_and_print(summary, output_root, start, args.json, exit_code)


def finish_and_print(summary: dict[str, Any], output_root: Path, start: float, emit_json: bool, exit_code: int) -> int:
    summary["endedAtUtc"] = utc_now()
    summary["durationMs"] = round((time.perf_counter() - start) * 1000.0, 3)
    finish_summary(output_root, summary)
    if emit_json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"{summary['status']}: {summary['artifacts']['summaryJson']}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
