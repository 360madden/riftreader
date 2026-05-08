from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .riftscan_coordination import DEFAULT_RIFTSCAN_ROOT, is_relative_to


@dataclass(frozen=True)
class ValidationStep:
    name: str
    command: list[str]
    cwd: Path
    kind: str = "exit-code"
    optional: bool = False


def powershell_command(executable: str, script: Path) -> list[str]:
    return [
        executable,
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
    ]


def build_validation_steps(
    *,
    repo_root: Path,
    riftscan_root: Path,
    process_id: int,
    target_window_handle: str,
    process_name: str = "rift_x64",
    include_pwsh: bool = True,
    quick: bool = False,
) -> list[ValidationStep]:
    python = sys.executable
    powershell = shutil.which("powershell") or "powershell"
    pwsh = shutil.which("pwsh")
    scripts = repo_root / "scripts"
    modules = [
        scripts / "rift_live_test" / "riftscan_coordination.py",
        scripts / "rift_live_test" / "riftscan_feedback.py",
        scripts / "rift_live_test" / "riftscan_milestone_review.py",
        scripts / "rift_live_test" / "riftscan_validation.py",
        scripts / "riftscan_coordination.py",
        scripts / "riftscan_feedback.py",
        scripts / "riftscan_milestone_review.py",
        scripts / "validate_riftscan_coordination.py",
    ]
    steps = [
        ValidationStep("git diff --check", ["git", "diff", "--check"], repo_root),
        ValidationStep("python compile riftscan modules", [python, "-m", "py_compile", *map(str, modules)], repo_root),
        ValidationStep("python test_riftscan_coordination", [python, str(scripts / "test_riftscan_coordination.py")], repo_root),
        ValidationStep("python test_riftscan_feedback", [python, str(scripts / "test_riftscan_feedback.py")], repo_root),
        ValidationStep(
            "python test_riftscan_milestone_review",
            [python, str(scripts / "test_riftscan_milestone_review.py")],
            repo_root,
        ),
        ValidationStep(
            "python test_riftscan_validation",
            [python, str(scripts / "test_riftscan_validation.py")],
            repo_root,
        ),
        ValidationStep(
            "python test_current_proof_pointer",
            [python, str(scripts / "test_current_proof_pointer.py")],
            repo_root,
        ),
        ValidationStep(
            "powershell proof-pose success",
            powershell_command(powershell, scripts / "test-capture-riftscan-proof-pose-success.ps1"),
            repo_root,
        ),
        ValidationStep(
            "powershell proof-pose reference blocker",
            powershell_command(powershell, scripts / "test-capture-riftscan-proof-pose-reference-blocker.ps1"),
            repo_root,
        ),
        ValidationStep(
            "powershell proof-pose pointer",
            powershell_command(powershell, scripts / "test-capture-riftscan-proof-pose-pointer.ps1"),
            repo_root,
        ),
        ValidationStep(
            "powershell import riftscan candidates",
            powershell_command(powershell, scripts / "test-import-riftscan-coordinate-candidates.ps1"),
            repo_root,
        ),
        ValidationStep(
            "powershell promote riftscan reference match",
            powershell_command(powershell, scripts / "test-promote-riftscan-reference-match-to-proof-anchor.ps1"),
            repo_root,
        ),
    ]
    if not quick:
        steps.insert(
            5,
            ValidationStep(
                "python test_live_test_orchestrator",
                [python, str(scripts / "test_live_test_orchestrator.py")],
                repo_root,
            ),
        )

    if include_pwsh and pwsh:
        steps.extend(
            [
                ValidationStep(
                    "pwsh import riftscan candidates",
                    powershell_command(pwsh, scripts / "test-import-riftscan-coordinate-candidates.ps1"),
                    repo_root,
                ),
                ValidationStep(
                    "pwsh promote riftscan reference match",
                    powershell_command(pwsh, scripts / "test-promote-riftscan-reference-match-to-proof-anchor.ps1"),
                    repo_root,
                ),
                ValidationStep(
                    "pwsh riftscan readback decode",
                    powershell_command(pwsh, scripts / "test-invoke-riftscan-coordinate-readback-decode.ps1"),
                    repo_root,
                ),
                ValidationStep(
                    "pwsh riftscan proof gate",
                    powershell_command(pwsh, scripts / "test-invoke-riftscan-coordinate-readback-proof-gate.ps1"),
                    repo_root,
                ),
            ]
        )
    elif include_pwsh:
        steps.append(
            ValidationStep(
                "pwsh unavailable",
                ["pwsh", "--version"],
                repo_root,
                kind="missing-tool",
                optional=True,
            )
        )

    steps.extend(
        [
            ValidationStep(
                "riftscan milestone smoke",
                [
                    python,
                    str(scripts / "riftscan_milestone_review.py"),
                    "--repo-root",
                    str(repo_root),
                    "--riftscan-root",
                    str(riftscan_root),
                    "--pid",
                    str(process_id),
                    "--hwnd",
                    target_window_handle,
                    "--process-name",
                    process_name,
                    "--compact-json",
                ],
                repo_root,
                kind="milestone-json",
            ),
            ValidationStep(
                "riftscan provider git status clean",
                ["git", "-C", str(riftscan_root), "status", "--short", "--branch"],
                repo_root,
                kind="riftscan-status-clean",
            ),
        ]
    )
    return steps


def tail_text(text: str, max_chars: int = 4000) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def validate_milestone_stdout(stdout: str) -> tuple[bool, str]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return False, f"milestone output was not JSON: {exc}"
    status = payload.get("status")
    strategy = payload.get("strategy") if isinstance(payload.get("strategy"), dict) else {}
    boundary = (
        payload.get("riftScanBoundary")
        if isinstance(payload.get("riftScanBoundary"), dict)
        else {}
    )
    if status != "ready-for-read-only-proof":
        return False, f"milestone status was {status!r}"
    if strategy.get("decision") != "proceed-read-only-proof-first":
        return False, f"milestone decision was {strategy.get('decision')!r}"
    if strategy.get("movementAllowedByReview") is not False:
        return False, "milestone review unexpectedly allowed movement"
    if boundary.get("writeAllowed") is not False:
        return False, "milestone boundary unexpectedly allowed RiftScan writes"
    if boundary.get("noCheatEngine") is not True:
        return False, "milestone boundary did not record noCheatEngine=true"
    return True, "ready-for-read-only-proof"


def validate_riftscan_status(stdout: str) -> tuple[bool, str]:
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        return False, "git status produced no branch line"
    extra = [line for line in lines[1:] if line.strip()]
    if extra:
        return False, "RiftScan working tree is not clean: " + "; ".join(extra[:5])
    return True, lines[0]


def run_step(step: ValidationStep, *, timeout_seconds: int) -> dict[str, Any]:
    started = time.perf_counter()
    if step.kind == "missing-tool":
        return {
            "name": step.name,
            "status": "skipped" if step.optional else "failed",
            "optional": step.optional,
            "kind": step.kind,
            "command": step.command,
            "cwd": str(step.cwd),
            "durationSeconds": 0.0,
            "exitCode": None,
            "detail": "Optional tool is unavailable.",
            "stdout": "",
            "stderr": "",
        }

    try:
        completed = subprocess.run(
            step.command,
            cwd=step.cwd,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        duration = time.perf_counter() - started
    except subprocess.TimeoutExpired as exc:
        return {
            "name": step.name,
            "status": "failed",
            "optional": step.optional,
            "kind": step.kind,
            "command": step.command,
            "cwd": str(step.cwd),
            "durationSeconds": time.perf_counter() - started,
            "exitCode": None,
            "detail": f"timed out after {timeout_seconds}s",
            "stdout": tail_text(exc.stdout or ""),
            "stderr": tail_text(exc.stderr or ""),
        }

    passed = completed.returncode == 0
    detail = "exit-code"
    if passed and step.kind == "milestone-json":
        passed, detail = validate_milestone_stdout(completed.stdout)
    elif passed and step.kind == "riftscan-status-clean":
        passed, detail = validate_riftscan_status(completed.stdout)
    elif not passed:
        detail = f"exit {completed.returncode}"

    return {
        "name": step.name,
        "status": "passed" if passed else "failed",
        "optional": step.optional,
        "kind": step.kind,
        "command": step.command,
        "cwd": str(step.cwd),
        "durationSeconds": round(duration, 3),
        "exitCode": completed.returncode,
        "detail": detail,
        "stdout": tail_text(completed.stdout),
        "stderr": tail_text(completed.stderr),
    }


def run_validation(
    *,
    repo_root: Path,
    riftscan_root: Path,
    process_id: int,
    target_window_handle: str,
    process_name: str,
    include_pwsh: bool,
    quick: bool,
    timeout_seconds: int,
) -> dict[str, Any]:
    steps = build_validation_steps(
        repo_root=repo_root,
        riftscan_root=riftscan_root,
        process_id=process_id,
        target_window_handle=target_window_handle,
        process_name=process_name,
        include_pwsh=include_pwsh,
        quick=quick,
    )
    results = [run_step(step, timeout_seconds=timeout_seconds) for step in steps]
    failed = [result for result in results if result["status"] == "failed"]
    return {
        "schemaVersion": 1,
        "mode": "riftscan-riftreader-coordination-validation",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if not failed else "failed",
        "repoRoot": str(repo_root),
        "riftScanRoot": str(riftscan_root),
        "requestedTarget": {
            "processName": process_name,
            "processId": process_id,
            "targetWindowHandle": target_window_handle,
        },
        "noCheatEngine": True,
        "movementSent": False,
        "writesToRiftScan": False,
        "quick": quick,
        "stepCount": len(results),
        "failedStepCount": len(failed),
        "steps": results,
    }


def dry_run_summary(steps: list[ValidationStep]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "mode": "riftscan-riftreader-coordination-validation-dry-run",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "dry-run",
        "noCheatEngine": True,
        "movementSent": False,
        "writesToRiftScan": False,
        "stepCount": len(steps),
        "steps": [
            {
                "name": step.name,
                "kind": step.kind,
                "optional": step.optional,
                "cwd": str(step.cwd),
                "command": step.command,
            }
            for step in steps
        ],
    }


def print_human_summary(summary: dict[str, Any]) -> None:
    print(f"RiftScan/RiftReader validation: {summary['status']}")
    print(f"Steps: {summary.get('stepCount')}  Failed: {summary.get('failedStepCount', 0)}")
    for result in summary.get("steps", []):
        print(f"[{result['status']}] {result['name']} - {result.get('detail', '')}")
        if result["status"] == "failed":
            if result.get("stdout"):
                print("--- stdout tail ---")
                print(result["stdout"])
            if result.get("stderr"):
                print("--- stderr tail ---")
                print(result["stderr"])


def default_summary_file(repo_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return repo_root / "scripts" / "captures" / f"riftscan-validation-{stamp}.json"


def write_summary(summary: dict[str, Any], output_file: Path, *, riftscan_root: Path) -> None:
    if is_relative_to(output_file, riftscan_root):
        raise ValueError(f"Refusing to write validation summary inside RiftScan: {output_file}")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def markdown_for_summary(summary: dict[str, Any]) -> str:
    target = summary.get("requestedTarget") if isinstance(summary.get("requestedTarget"), dict) else {}
    lines = [
        "# RiftScan/RiftReader Coordination Validation",
        "",
        "| Fact | Value |",
        "|---|---|",
        f"| Status | `{summary.get('status')}` |",
        f"| Generated | `{summary.get('generatedAtUtc')}` |",
        f"| Target | `{target.get('processName')}` PID `{target.get('processId')}`, HWND `{target.get('targetWindowHandle')}` |",
        f"| Step count | `{summary.get('stepCount')}` |",
        f"| Failed step count | `{summary.get('failedStepCount', 0)}` |",
        f"| No Cheat Engine | `{summary.get('noCheatEngine')}` |",
        f"| Movement sent | `{summary.get('movementSent')}` |",
        f"| Writes to RiftScan | `{summary.get('writesToRiftScan')}` |",
        "",
        "## Steps",
        "",
        "| # | Step | Status | Detail |",
        "|---:|---|---|---|",
    ]
    for index, result in enumerate(summary.get("steps", []), start=1):
        lines.append(
            f"| {index} | `{result.get('name')}` | `{result.get('status')}` | {result.get('detail', '')} |"
        )
    lines.append("")
    if summary.get("status") != "passed":
        lines.extend(["## Failed output tails", ""])
        for result in summary.get("steps", []):
            if result.get("status") != "failed":
                continue
            lines.append(f"### {result.get('name')}")
            if result.get("stdout"):
                lines.extend(["", "```text", str(result.get("stdout")).strip(), "```"])
            if result.get("stderr"):
                lines.extend(["", "```text", str(result.get("stderr")).strip(), "```"])
            lines.append("")
    return "\n".join(lines)


def write_markdown_summary(summary: dict[str, Any], output_file: Path, *, riftscan_root: Path) -> None:
    if is_relative_to(output_file, riftscan_root):
        raise ValueError(f"Refusing to write validation Markdown inside RiftScan: {output_file}")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(markdown_for_summary(summary), encoding="utf-8")


def default_latest_pointer_file(repo_root: Path) -> Path:
    return repo_root / "scripts" / "captures" / "latest-riftscan-validation.json"


def build_latest_pointer(summary: dict[str, Any]) -> dict[str, Any]:
    failed_steps = [
        {
            "name": result.get("name"),
            "detail": result.get("detail"),
            "exitCode": result.get("exitCode"),
        }
        for result in summary.get("steps", [])
        if result.get("status") == "failed"
    ]
    milestone = next(
        (
            result
            for result in summary.get("steps", [])
            if result.get("kind") == "milestone-json"
        ),
        None,
    )
    provider_status = next(
        (
            result
            for result in summary.get("steps", [])
            if result.get("kind") == "riftscan-status-clean"
        ),
        None,
    )
    return {
        "schemaVersion": 1,
        "mode": "latest-riftscan-coordination-validation-pointer",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "validationGeneratedAtUtc": summary.get("generatedAtUtc"),
        "status": summary.get("status"),
        "summaryFile": summary.get("summaryFile"),
        "markdownFile": summary.get("markdownFile"),
        "repoRoot": summary.get("repoRoot"),
        "riftScanRoot": summary.get("riftScanRoot"),
        "requestedTarget": summary.get("requestedTarget"),
        "noCheatEngine": summary.get("noCheatEngine"),
        "movementSent": summary.get("movementSent"),
        "writesToRiftScan": summary.get("writesToRiftScan"),
        "stepCount": summary.get("stepCount"),
        "failedStepCount": summary.get("failedStepCount"),
        "failedSteps": failed_steps,
        "milestoneStatus": milestone.get("detail") if milestone else None,
        "riftScanProviderStatus": provider_status.get("detail") if provider_status else None,
    }


def write_latest_pointer(summary: dict[str, Any], output_file: Path, *, riftscan_root: Path) -> None:
    if is_relative_to(output_file, riftscan_root):
        raise ValueError(f"Refusing to write validation latest pointer inside RiftScan: {output_file}")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(build_latest_pointer(summary), indent=2) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the no-CE/read-only RiftScan coordination validation suite."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="RiftReader repo root.",
    )
    parser.add_argument(
        "--riftscan-root",
        type=Path,
        default=DEFAULT_RIFTSCAN_ROOT,
        help="RiftScan provider repo root. This tool checks it but never writes it.",
    )
    parser.add_argument("--pid", type=int, required=True, help="Expected current RIFT process id.")
    parser.add_argument("--hwnd", required=True, help="Expected current RIFT window handle.")
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--quick", action="store_true", help="Skip the broader live-test orchestrator suite.")
    parser.add_argument("--skip-pwsh", action="store_true", help="Skip pwsh-specific duplicate regressions.")
    parser.add_argument("--dry-run", action="store_true", help="Print the commands without running them.")
    parser.add_argument(
        "--write-summary",
        action="store_true",
        help="Write the validation JSON under RiftReader scripts/captures.",
    )
    parser.add_argument("--summary-file", type=Path, help="Explicit validation JSON output file.")
    parser.add_argument(
        "--write-markdown",
        action="store_true",
        help="Write a Markdown companion next to the JSON summary.",
    )
    parser.add_argument("--markdown-file", type=Path, help="Explicit validation Markdown output file.")
    parser.add_argument(
        "--update-latest-pointer",
        action="store_true",
        help="Update scripts/captures/latest-riftscan-validation.json after writing a summary.",
    )
    parser.add_argument("--latest-pointer-file", type=Path, help="Explicit latest-pointer output file.")
    parser.add_argument("--json", action="store_true", help="Emit indented JSON.")
    parser.add_argument("--compact-json", action="store_true", help="Emit single-line JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    riftscan_root = args.riftscan_root.resolve()
    include_pwsh = not args.skip_pwsh
    if args.dry_run:
        summary = dry_run_summary(
            build_validation_steps(
                repo_root=repo_root,
                riftscan_root=riftscan_root,
                process_id=args.pid,
                target_window_handle=args.hwnd,
                process_name=args.process_name,
                include_pwsh=include_pwsh,
                quick=args.quick,
            )
        )
    else:
        summary = run_validation(
            repo_root=repo_root,
            riftscan_root=riftscan_root,
            process_id=args.pid,
            target_window_handle=args.hwnd,
            process_name=args.process_name,
            include_pwsh=include_pwsh,
            quick=args.quick,
            timeout_seconds=args.timeout_seconds,
        )

    output_file = args.summary_file or default_summary_file(repo_root)
    if args.write_summary or args.summary_file or args.write_markdown or args.markdown_file:
        summary["summaryFile"] = str(output_file)
        markdown_file = args.markdown_file or output_file.with_suffix(".md")
        if args.write_markdown or args.markdown_file:
            summary["markdownFile"] = str(markdown_file)
        latest_pointer_file = None
        if args.update_latest_pointer or args.latest_pointer_file:
            latest_pointer_file = args.latest_pointer_file or default_latest_pointer_file(repo_root)
            summary["latestPointerFile"] = str(latest_pointer_file)
        write_summary(summary, output_file, riftscan_root=riftscan_root)
        if args.write_markdown or args.markdown_file:
            write_markdown_summary(summary, markdown_file, riftscan_root=riftscan_root)
        if latest_pointer_file is not None:
            write_latest_pointer(summary, latest_pointer_file, riftscan_root=riftscan_root)
    elif args.update_latest_pointer or args.latest_pointer_file:
        raise ValueError("--update-latest-pointer requires --write-summary or an explicit summary/markdown output.")

    if args.compact_json:
        print(json.dumps(summary, separators=(",", ":")))
    elif args.json:
        print(json.dumps(summary, indent=2))
    else:
        print_human_summary(summary)
    return 0 if summary["status"] in {"passed", "dry-run"} else 1


if __name__ == "__main__":
    sys.exit(main())
