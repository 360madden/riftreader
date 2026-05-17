#!/usr/bin/env python3
"""Offline-safe RiftReader Operator Lite.

This helper is a small local launcher around already-safe workflow commands.
It intentionally does not include movement, live input, ProofOnly, target
control, visual gates, CE, x64dbg, staging, committing, or pushing.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, safety_flags, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, safety_flags, utc_iso


DENIED_FRAGMENTS = (
    "send-rift-key",
    "post-rift-key",
    "cheatengine",
    "x64dbg",
    "git add",
    "git commit",
    "git push",
    "git reset",
    "git clean",
    "proofonly",
    "target-control",
    "visual-gate",
)


@dataclass(frozen=True)
class CommandSpec:
    key: str
    label: str
    args: tuple[str, ...]
    timeout_seconds: float
    description: str
    expected_exit_codes: tuple[int, ...] = (0,)

def build_command_specs(repo_root: Path) -> dict[str, CommandSpec]:
    scripts = repo_root / "scripts"
    return {
        "workflow-status": CommandSpec(
            key="workflow-status",
            label="Refresh Workflow Status",
            args=(str(scripts / "riftreader-workflow-status.cmd"), "--write"),
            timeout_seconds=90,
            description="Build a deterministic status packet under .riftreader-local.",
            expected_exit_codes=(0, 2),
        ),
        "compact-sitrep": CommandSpec(
            key="compact-sitrep",
            label="Compact OpenCode SITREP",
            args=(str(scripts / "riftreader-workflow-status.cmd"), "--compact", "--write"),
            timeout_seconds=90,
            description="Print and write a compact paste-ready OpenCode/non-Codex SITREP.",
            expected_exit_codes=(0, 2),
        ),
        "live-triage": CommandSpec(
            key="live-triage",
            label="Run Live-Test Triage",
            args=(str(scripts / "riftreader-live-triage.cmd"), "--write"),
            timeout_seconds=90,
            description="Classify the current blocker without live input.",
            expected_exit_codes=(0, 2),
        ),
        "git-status": CommandSpec(
            key="git-status",
            label="Git Status",
            args=("git", "--no-pager", "status", "--short", "--branch"),
            timeout_seconds=30,
            description="Show local branch and dirty-file state.",
        ),
    }


def package_intake_dry_run_args(repo_root: Path, package_path: Path) -> tuple[str, ...]:
    return (
        str(repo_root / "scripts" / "riftreader-package-intake.cmd"),
        "--package",
        str(package_path),
        "--json",
    )


def validate_safe_args(args: tuple[str, ...] | list[str]) -> list[str]:
    joined = " ".join(args).lower()
    return [fragment for fragment in DENIED_FRAGMENTS if fragment in joined]


def run_command(
    args: tuple[str, ...] | list[str],
    cwd: Path,
    timeout_seconds: float,
    expected_exit_codes: tuple[int, ...] = (0,),
) -> dict[str, Any]:
    started = utc_iso()
    start = time.monotonic()
    result: dict[str, Any] = {
        "args": list(args),
        "cwd": str(cwd),
        "startedAtUtc": started,
        "timeoutSeconds": timeout_seconds,
        "expectedExitCodes": list(expected_exit_codes),
        "exitCode": None,
        "ok": False,
        "stdout": "",
        "stderr": "",
    }
    denied = validate_safe_args(args)
    if denied:
        result["stderr"] = f"operator-lite-denied-command-fragment:{','.join(denied)}"
        result["exitCode"] = 2
        return result
    try:
        completed = subprocess.run(
            list(args),
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        result["exitCode"] = completed.returncode
        result["ok"] = completed.returncode in expected_exit_codes
        result["stdout"] = completed.stdout
        result["stderr"] = completed.stderr
    except subprocess.TimeoutExpired as exc:
        result["exitCode"] = 2
        result["stderr"] = f"TimeoutExpired:{exc}"
    except Exception as exc:  # noqa: BLE001
        result["exitCode"] = 1
        result["stderr"] = f"{type(exc).__name__}:{exc}"
    finally:
        result["endedAtUtc"] = utc_iso()
        result["durationSeconds"] = round(time.monotonic() - start, 3)
        result["safety"] = safety_flags()
    return result

def latest_report(repo_root: Path) -> Path | None:
    roots = [
        repo_root / ".riftreader-local" / "opencode-status",
        repo_root / ".riftreader-local" / "live-test-triage",
        repo_root / ".riftreader-local" / "package-intake",
    ]
    candidates: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        candidates.extend(path for path in root.rglob("*.md") if path.is_file())
        candidates.extend(path for path in root.rglob("*.json") if path.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def command_plan(repo_root: Path) -> dict[str, Any]:
    specs = build_command_specs(repo_root)
    commands = []
    errors: list[str] = []
    for spec in specs.values():
        denied = validate_safe_args(spec.args)
        if denied:
            errors.append(f"{spec.key}-denied:{','.join(denied)}")
        first = Path(spec.args[0])
        if (str(first).lower().endswith(".cmd") or str(first).lower().endswith(".ps1")) and not first.exists():
            errors.append(f"{spec.key}-script-missing:{first}")
        commands.append(
            {
                "key": spec.key,
                "label": spec.label,
                "args": list(spec.args),
                "timeoutSeconds": spec.timeout_seconds,
                "expectedExitCodes": list(spec.expected_exit_codes),
                "description": spec.description,
            }
        )
    return {
        "schemaVersion": 1,
        "kind": "riftreader-operator-lite-command-plan",
        "generatedAtUtc": utc_iso(),
        "status": "failed" if errors else "passed",
        "errors": errors,
        "commands": commands,
        "disabledLiveActions": [
            "target-control",
            "visual-gate",
            "proofonly",
            "movement",
            "send-input",
            "ce-x64dbg",
            "git-stage-commit-push",
        ],
        "safety": safety_flags(),
    }


def run_gui(repo_root: Path) -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext

    specs = build_command_specs(repo_root)

    root = tk.Tk()
    root.title("RiftReader Operator Lite")
    root.geometry("980x680")

    output = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=30)
    output.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def append(text: str) -> None:
        output.insert(tk.END, text.rstrip() + "\n")
        output.see(tk.END)

    def run_spec(key: str) -> None:
        spec = specs[key]
        append(f"\n## {spec.label}\n$ {' '.join(spec.args)}")
        result = run_command(spec.args, repo_root, spec.timeout_seconds, spec.expected_exit_codes)
        append(json.dumps(result, indent=2))

    def run_package_dry_run() -> None:
        selected = filedialog.askopenfilename(title="Select package .zip or manifest package file")
        if not selected:
            selected_dir = filedialog.askdirectory(title="Select package directory")
            selected = selected_dir
        if not selected:
            return
        package_path = Path(selected)
        args = package_intake_dry_run_args(repo_root, package_path)
        append(f"\n## Package Intake Dry-Run\n$ {' '.join(args)}")
        result = run_command(args, repo_root, 120)
        append(json.dumps(result, indent=2))

    def open_latest() -> None:
        report = latest_report(repo_root)
        if not report:
            messagebox.showinfo("RiftReader Operator Lite", "No .riftreader-local report found yet.")
            return
        os.startfile(report)  # type: ignore[attr-defined]
        append(f"Opened latest report: {report}")

    button_frame = tk.Frame(root)
    button_frame.pack(fill=tk.X, padx=8, pady=4)

    tk.Button(button_frame, text="Refresh Workflow Status", command=lambda: run_spec("workflow-status")).pack(side=tk.LEFT, padx=4)
    tk.Button(button_frame, text="Compact SITREP", command=lambda: run_spec("compact-sitrep")).pack(side=tk.LEFT, padx=4)
    tk.Button(button_frame, text="Run Live-Test Triage", command=lambda: run_spec("live-triage")).pack(side=tk.LEFT, padx=4)
    tk.Button(button_frame, text="Package Intake Dry-Run", command=run_package_dry_run).pack(side=tk.LEFT, padx=4)
    tk.Button(button_frame, text="Git Status", command=lambda: run_spec("git-status")).pack(side=tk.LEFT, padx=4)
    tk.Button(button_frame, text="Open Latest Report", command=open_latest).pack(side=tk.LEFT, padx=4)

    disabled_frame = tk.Frame(root)
    disabled_frame.pack(fill=tk.X, padx=8, pady=4)
    for label in ["Target-Control (disabled)", "Visual Gate (disabled)", "ProofOnly (disabled)", "Movement (disabled)"]:
        tk.Button(disabled_frame, text=label, state=tk.DISABLED).pack(side=tk.LEFT, padx=4)

    append("RiftReader Operator Lite loaded.")
    append("Live input, movement, CE/x64dbg, stage/commit/push, target-control, visual gate, and ProofOnly are disabled in v0.")
    root.mainloop()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline-safe RiftReader Operator Lite.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--command-plan", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    plan = command_plan(repo_root)
    if args.self_test or args.command_plan:
        if args.json:
            print(json.dumps(plan, indent=2))
        else:
            print(f"Status: {plan['status']}")
            for command in plan["commands"]:
                print(f"- {command['key']}: {' '.join(command['args'])}")
            for error in plan["errors"]:
                print(f"ERROR: {error}")
        return 1 if plan["status"] != "passed" else 0
    return run_gui(repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
