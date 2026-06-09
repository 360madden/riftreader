#!/usr/bin/env python3
"""Timestamped validation ledger for RiftReader workflow checks.

This helper records validation timing and command evidence only. It must not
send live input, move the player, attach debuggers, write provider repos, or
mutate Git refs.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from .common import find_repo_root, preview_text, safety_flags
except ImportError:  # pragma: no cover - supports direct script execution.
    _project_root = str(Path(__file__).resolve().parents[1])
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
    from riftreader_workflow.common import find_repo_root, preview_text, safety_flags


TOOL_VERSION = "riftreader-validation-ledger-v0.1.0"
KIND = "riftreader-validation-ledger"
DEFAULT_OUTPUT_ROOT = Path(".riftreader-local") / "validation-runs"
SUPPORTED_TIERS = {"smoke", "targeted", "full-local", "ci-parity", "custom"}
CI_WORKFLOWS = (".NET build and test", "RiftReader Policy")

TIER_BUDGET_SECONDS: dict[str, float] = {
    "smoke": 120.0,
    "targeted": 300.0,
    "full-local": 900.0,
    "ci-parity": 900.0,
    "custom": 300.0,
}

COMMAND_BUDGET_SECONDS: dict[str, float] = {
    "py-compile": 30.0,
    "unittest-focused": 120.0,
    "unittest-discover": 420.0,
    "unittest-discover-active": 420.0,
    "policy-lint": 120.0,
    "decision-packet": 120.0,
    "dotnet-restore": 180.0,
    "dotnet-build": 300.0,
    "dotnet-test": 300.0,
    "ci-poll": 900.0,
}

STATUS_EXIT_CODES = {
    "passed": 0,
    "failed": 1,
    "blocked": 2,
}


class ValidationLedgerError(RuntimeError):
    """Controlled validation-ledger setup error."""


@dataclass(frozen=True)
class CommandSpec:
    """A command the ledger can execute and time."""

    label: str
    phase: str
    args: list[str]
    tier: str
    timeout_seconds: float = 120.0
    expected_exit_codes: list[int] = field(default_factory=lambda: [0])
    budget_seconds: float | None = None


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def slugify(value: str, *, fallback: str = "command") -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-._")
    return (slug or fallback)[:80]


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return ""
    return f"{seconds:.3f}s"


def print_progress(message: str, *, json_mode: bool) -> None:
    stream = sys.stderr if json_mode else sys.stdout
    print(message, file=stream, flush=True)


def resolve_repo_root(value: str | None) -> Path:
    start = Path(value).expanduser().resolve() if value else Path.cwd().resolve()
    return find_repo_root(start)


def make_run_directory(repo_root: Path, output_root_arg: str | None) -> Path:
    base = Path(output_root_arg).expanduser() if output_root_arg else DEFAULT_OUTPUT_ROOT
    if not base.is_absolute():
        base = repo_root / base
    base.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()
    run_dir = base / stamp
    suffix = 2
    while run_dir.exists():
        run_dir = base / f"{stamp}-{suffix}"
        suffix += 1
    (run_dir / "commands").mkdir(parents=True, exist_ok=False)
    return run_dir.resolve()


def run_quiet(args: Sequence[str], cwd: Path, *, timeout_seconds: float = 30.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=str(cwd),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        timeout=timeout_seconds,
    )


def collect_git_state(repo_root: Path) -> dict[str, Any]:
    git: dict[str, Any] = {
        "branch": "",
        "head": "",
        "dirty": False,
        "ahead": 0,
        "behind": 0,
    }
    try:
        branch = run_quiet(["git", "branch", "--show-current"], repo_root)
        git["branch"] = branch.stdout.strip() if branch.returncode == 0 else ""
        head = run_quiet(["git", "rev-parse", "HEAD"], repo_root)
        git["head"] = head.stdout.strip() if head.returncode == 0 else ""
        status = run_quiet(["git", "status", "--porcelain=v1", "--untracked-files=all"], repo_root)
        git["dirty"] = bool(status.stdout.strip()) if status.returncode == 0 else False
        upstream = run_quiet(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], repo_root)
        if upstream.returncode == 0 and upstream.stdout.strip():
            counts = run_quiet(["git", "rev-list", "--left-right", "--count", "@{upstream}...HEAD"], repo_root)
            if counts.returncode == 0:
                parts = counts.stdout.strip().split()
                if len(parts) == 2:
                    git["behind"] = int(parts[0])
                    git["ahead"] = int(parts[1])
    except Exception as exc:  # noqa: BLE001 - git state is diagnostic only.
        git["error"] = f"{type(exc).__name__}:{exc}"
    return git


def normalize_status_path(path_text: str) -> str:
    value = path_text.strip()
    if " -> " in value:
        value = value.split(" -> ", 1)[1]
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]
    return value.replace("/", os.sep)


def changed_python_files(repo_root: Path) -> list[str]:
    try:
        status = run_quiet(["git", "status", "--porcelain=v1", "--untracked-files=all"], repo_root)
        if status.returncode != 0:
            return []
        files: list[str] = []
        for line in status.stdout.splitlines():
            if len(line) < 4:
                continue
            rel = normalize_status_path(line[3:])
            if not rel.endswith(".py"):
                continue
            if rel.startswith(".riftreader-local" + os.sep):
                continue
            if (repo_root / rel).is_file():
                files.append(rel)
        return sorted(set(files))
    except Exception:  # noqa: BLE001 - changed-file discovery must not block validation plans.
        return []


def windows_command_line_to_argv(command: str) -> list[str]:
    if os.name != "nt":
        return shlex.split(command)
    argc = ctypes.c_int(0)
    shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
    shell32.CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    shell32.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
    argv = shell32.CommandLineToArgvW(command, ctypes.byref(argc))
    if not argv:
        raise ValidationLedgerError(f"Could not parse command: {command}")
    try:
        return [argv[i] for i in range(argc.value)]
    finally:
        ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]  # type: ignore[attr-defined]
        ctypes.windll.kernel32.LocalFree(argv)  # type: ignore[attr-defined]


def parse_command_string(command: str) -> list[str]:
    try:
        parsed = windows_command_line_to_argv(command)
    except Exception:
        parsed = shlex.split(command, posix=(os.name != "nt"))
    if not parsed:
        raise ValidationLedgerError("empty --command value")
    return [str(part) for part in parsed]


def command_label_from_args(args: Sequence[str]) -> str:
    joined = " ".join(args).lower()
    if "py_compile" in joined:
        return "py-compile"
    if "unittest" in joined and "discover" in joined:
        return "unittest-discover"
    if "unittest" in joined:
        return "unittest-focused"
    if "policy_lint.py" in joined:
        return "policy-lint"
    if "decision_packet.py" in joined:
        return "decision-packet"
    if len(args) >= 2 and args[0].lower() == "dotnet":
        return f"dotnet-{args[1].lower()}"
    if len(args) >= 3 and args[0].lower() == "gh" and args[1:3] == ["run", "list"]:
        return "ci-poll"
    if args:
        return slugify(" ".join(args[:3]))
    return "command"


def budget_for_label(label: str, fallback: float | None) -> float | None:
    return COMMAND_BUDGET_SECONDS.get(label, fallback)


def spec(
    label: str,
    args: list[str],
    *,
    tier: str,
    phase: str,
    timeout_seconds: float,
    budget_seconds: float | None = None,
    expected_exit_codes: Iterable[int] = (0,),
) -> CommandSpec:
    return CommandSpec(
        label=label,
        phase=phase,
        args=args,
        tier=tier,
        timeout_seconds=timeout_seconds,
        expected_exit_codes=[int(code) for code in expected_exit_codes],
        budget_seconds=budget_seconds,
    )


def smoke_specs(repo_root: Path) -> list[CommandSpec]:
    commands = [
        spec(
            "diff-check",
            ["git", "--no-pager", "diff", "--check"],
            tier="smoke",
            phase="workspace",
            timeout_seconds=120.0,
            budget_seconds=120.0,
        ),
        spec(
            "policy-lint",
            [sys.executable, "tools\\riftreader_workflow\\policy_lint.py", "--json", "validate-repo", "--scope", "changed", "--no-write-summary"],
            tier="smoke",
            phase="policy",
            timeout_seconds=120.0,
            budget_seconds=COMMAND_BUDGET_SECONDS["policy-lint"],
        ),
    ]
    changed_py = changed_python_files(repo_root)
    if changed_py:
        commands.append(
            spec(
                "py-compile-changed",
                [sys.executable, "-m", "py_compile", *changed_py],
                tier="smoke",
                phase="compile",
                timeout_seconds=120.0,
                budget_seconds=COMMAND_BUDGET_SECONDS["py-compile"],
            )
        )
    return commands


def full_local_specs() -> list[CommandSpec]:
    tier = "full-local"
    return [
        spec("diff-check", ["git", "--no-pager", "diff", "--check"], tier=tier, phase="workspace", timeout_seconds=120.0, budget_seconds=120.0),
        spec("diff-check-head30", ["git", "--no-pager", "diff", "--check", "HEAD~30..HEAD"], tier=tier, phase="workspace", timeout_seconds=120.0, budget_seconds=120.0),
        spec(
            "policy-lint",
            [sys.executable, "tools\\riftreader_workflow\\policy_lint.py", "--json", "validate-repo", "--scope", "changed", "--no-write-summary"],
            tier=tier,
            phase="policy",
            timeout_seconds=120.0,
            budget_seconds=COMMAND_BUDGET_SECONDS["policy-lint"],
        ),
        spec(
            "decision-packet",
            [sys.executable, "tools\\riftreader_workflow\\decision_packet.py", "--run-safe-checks", "--json"],
            tier=tier,
            phase="workflow",
            timeout_seconds=180.0,
            budget_seconds=COMMAND_BUDGET_SECONDS["decision-packet"],
            expected_exit_codes=(0, STATUS_EXIT_CODES["blocked"]),
        ),
        spec(
            "unittest-discover-active",
            [sys.executable, "tools\\riftreader_workflow\\unittest_discover_active.py"],
            tier=tier,
            phase="python-tests",
            timeout_seconds=900.0,
            budget_seconds=COMMAND_BUDGET_SECONDS["unittest-discover-active"],
        ),
        spec(
            "workflow-status",
            ["cmd", "/c", "scripts\\riftreader-workflow-status.cmd", "--compact-json"],
            tier=tier,
            phase="workflow",
            timeout_seconds=180.0,
            budget_seconds=120.0,
            expected_exit_codes=(0, STATUS_EXIT_CODES["blocked"]),
        ),
        spec("tool-catalog", ["cmd", "/c", "scripts\\riftreader-tool-catalog.cmd", "--compact-json"], tier=tier, phase="workflow", timeout_seconds=180.0, budget_seconds=120.0),
        spec("dotnet-restore", ["dotnet", "restore", "RiftReader.slnx"], tier=tier, phase="dotnet", timeout_seconds=300.0, budget_seconds=COMMAND_BUDGET_SECONDS["dotnet-restore"]),
        spec("dotnet-build", ["dotnet", "build", "RiftReader.slnx", "--no-restore", "--configuration", "Release"], tier=tier, phase="dotnet", timeout_seconds=420.0, budget_seconds=COMMAND_BUDGET_SECONDS["dotnet-build"]),
        spec("dotnet-test", ["dotnet", "test", "RiftReader.slnx", "--no-build", "--configuration", "Release", "--logger", "console;verbosity=minimal"], tier=tier, phase="dotnet", timeout_seconds=420.0, budget_seconds=COMMAND_BUDGET_SECONDS["dotnet-test"]),
    ]


def command_spec_from_json(value: str, *, tier: str, default_timeout: float, default_budget: float | None) -> CommandSpec:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValidationLedgerError(f"malformed --command-json: {exc}") from exc
    if isinstance(parsed, list):
        args = [str(part) for part in parsed]
        label = command_label_from_args(args)
        phase = "custom"
        expected = [0]
        timeout = default_timeout
        budget = budget_for_label(label, default_budget)
    elif isinstance(parsed, dict):
        raw_args = parsed.get("args") or parsed.get("command")
        if not isinstance(raw_args, list):
            raise ValidationLedgerError("--command-json object requires list field 'args'")
        args = [str(part) for part in raw_args]
        label = str(parsed.get("label") or command_label_from_args(args))
        phase = str(parsed.get("phase") or "custom")
        expected = [int(code) for code in parsed.get("expectedExitCodes", [0])]
        timeout = float(parsed.get("timeoutSeconds", default_timeout))
        budget = parsed.get("budgetSeconds", budget_for_label(label, default_budget))
        budget = None if budget is None else float(budget)
    else:
        raise ValidationLedgerError("--command-json must be a JSON array or object")
    if not args:
        raise ValidationLedgerError("--command-json command args cannot be empty")
    return CommandSpec(label=label, phase=phase, args=args, tier=tier, timeout_seconds=timeout, expected_exit_codes=expected, budget_seconds=budget)


def custom_specs(args: argparse.Namespace, *, tier: str) -> list[CommandSpec]:
    timeout = float(args.timeout_seconds)
    default_budget = args.default_command_budget_seconds
    commands: list[CommandSpec] = []
    for command in args.command or []:
        argv = parse_command_string(command)
        label = command_label_from_args(argv)
        commands.append(
            CommandSpec(
                label=label,
                phase="custom",
                args=argv,
                tier=tier,
                timeout_seconds=timeout,
                expected_exit_codes=[0],
                budget_seconds=budget_for_label(label, default_budget),
            )
        )
    for command_json in args.command_json or []:
        commands.append(command_spec_from_json(command_json, tier=tier, default_timeout=timeout, default_budget=default_budget))
    return commands


def build_specs(args: argparse.Namespace, repo_root: Path) -> list[CommandSpec]:
    if args.tier == "smoke":
        extra = custom_specs(args, tier=args.tier)
        return [*smoke_specs(repo_root), *extra]
    if args.tier == "full-local":
        extra = custom_specs(args, tier=args.tier)
        return [*full_local_specs(), *extra]
    if args.tier in {"targeted", "custom"}:
        commands = custom_specs(args, tier=args.tier)
        if not commands:
            raise ValidationLedgerError(f"{args.tier} tier requires at least one --command or --command-json")
        return commands
    if args.tier == "ci-parity":
        return []
    raise ValidationLedgerError(f"unsupported tier: {args.tier}")


def result_status(result: dict[str, Any]) -> str:
    if result.get("blocked"):
        return "blocked"
    if result.get("ok"):
        return "passed"
    return "failed"


def command_result_paths(commands_dir: Path, index: int, label: str) -> tuple[Path, Path]:
    stem = f"{index:03d}-{slugify(label)}"
    return commands_dir / f"{stem}.stdout.txt", commands_dir / f"{stem}.stderr.txt"


def run_command(
    command: CommandSpec,
    *,
    index: int,
    repo_root: Path,
    commands_dir: Path,
    heartbeat_seconds: float,
    enforce_budget: bool,
    json_mode: bool,
) -> dict[str, Any]:
    stdout_path, stderr_path = command_result_paths(commands_dir, index, command.label)
    started_at = utc_iso()
    start = time.monotonic()
    printable = " ".join(command.args)
    print_progress(f"[{started_at}] START {command.tier} #{index} {command.label}: {printable}", json_mode=json_mode)
    result: dict[str, Any] = {
        "index": index,
        "label": command.label,
        "phase": command.phase,
        "tier": command.tier,
        "args": command.args,
        "cwd": str(repo_root),
        "startedAtUtc": started_at,
        "endedAtUtc": None,
        "durationSeconds": 0.0,
        "timeoutSeconds": command.timeout_seconds,
        "exitCode": None,
        "expectedExitCodes": command.expected_exit_codes,
        "ok": False,
        "timedOut": False,
        "slow": False,
        "stdoutPreview": "",
        "stderrPreview": "",
        "stdoutPath": str(stdout_path.resolve()),
        "stderrPath": str(stderr_path.resolve()),
    }
    budget = command.budget_seconds
    if budget is not None:
        result["budgetSeconds"] = budget
    next_heartbeat = start + heartbeat_seconds if heartbeat_seconds > 0 else float("inf")
    deadline = start + command.timeout_seconds if command.timeout_seconds > 0 else float("inf")
    process: subprocess.Popen[str] | None = None
    try:
        with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_file, stderr_path.open("w", encoding="utf-8", errors="replace") as stderr_file:
            process = subprocess.Popen(
                command.args,
                cwd=str(repo_root),
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
                shell=False,
            )
            while True:
                exit_code = process.poll()
                now = time.monotonic()
                if exit_code is not None:
                    result["exitCode"] = exit_code
                    break
                if now >= deadline:
                    result["timedOut"] = True
                    result["error"] = f"TimeoutExpired:{command.timeout_seconds}"
                    process.kill()
                    result["exitCode"] = process.wait(timeout=5)
                    break
                if now >= next_heartbeat:
                    elapsed = now - start
                    print_progress(
                        f"[{utc_iso()}] STILL RUNNING {command.tier} #{index} {command.label} elapsed={elapsed:.1f}s",
                        json_mode=json_mode,
                    )
                    next_heartbeat = now + heartbeat_seconds
                sleep_for = min(0.25, max(0.01, min(next_heartbeat - now, deadline - now)))
                time.sleep(sleep_for)
    except FileNotFoundError as exc:
        result["blocked"] = True
        result["error"] = f"FileNotFoundError:{exc}"
        stdout_path.touch(exist_ok=True)
        stderr_path.write_text(str(exc), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - command envelope must capture unexpected local failures.
        result["error"] = f"{type(exc).__name__}:{exc}"
        stdout_path.touch(exist_ok=True)
        stderr_path.write_text(str(exc), encoding="utf-8")
        if process and process.poll() is None:
            process.kill()
    finally:
        ended_at = utc_iso()
        duration = round(time.monotonic() - start, 3)
        result["endedAtUtc"] = ended_at
        result["durationSeconds"] = duration
        try:
            result["stdoutPreview"] = preview_text(stdout_path.read_text(encoding="utf-8", errors="replace"))
            result["stderrPreview"] = preview_text(stderr_path.read_text(encoding="utf-8", errors="replace"))
        except Exception as exc:  # noqa: BLE001 - preview capture is diagnostic only.
            result["previewError"] = f"{type(exc).__name__}:{exc}"
        result["slow"] = bool(budget is not None and duration > budget)
        exit_code = result.get("exitCode")
        exit_ok = exit_code in command.expected_exit_codes if exit_code is not None else False
        result["ok"] = bool(exit_ok and not result.get("timedOut") and not result.get("error") and not result.get("blocked"))
        if result["slow"] and enforce_budget:
            result["ok"] = False
            result["budgetExceeded"] = True
            result["error"] = result.get("error") or f"BudgetExceeded:{duration:.3f}>{budget:.3f}"
        print_progress(
            f"[{ended_at}] DONE {command.tier} #{index} {command.label} exit={result.get('exitCode')} duration={duration:.3f}s status={result_status(result)}",
            json_mode=json_mode,
        )
    return result


def summarize_runs(commands: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], list[str], list[str]]:
    slow = [cmd for cmd in commands if cmd.get("slow")]
    blockers: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    for cmd in commands:
        if cmd.get("slow"):
            warnings.append(f"slow-command:{cmd.get('label')}:{cmd.get('durationSeconds')}s")
        exit_code = cmd.get("exitCode")
        if cmd.get("ok") and exit_code not in (None, 0):
            warnings.append(f"command-returned-expected-status:{cmd.get('label')}:exit={exit_code}")
        if cmd.get("blocked"):
            blockers.append(f"command-blocked:{cmd.get('label')}:{cmd.get('error')}")
        elif not cmd.get("ok"):
            errors.append(f"command-failed:{cmd.get('label')}:exit={cmd.get('exitCode')}:error={cmd.get('error')}")
    return slow, blockers, warnings, errors


def status_from_lists(blockers: list[str], errors: list[str]) -> str:
    if blockers:
        return "blocked"
    if errors:
        return "failed"
    return "passed"


def base_summary(args: argparse.Namespace, repo_root: Path, run_dir: Path, started_at: str) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": KIND,
        "toolVersion": TOOL_VERSION,
        "status": "blocked",
        "tier": args.tier,
        "startedAtUtc": started_at,
        "endedAtUtc": None,
        "durationSeconds": 0.0,
        "repoRoot": str(repo_root),
        "git": collect_git_state(repo_root),
        "budgets": {
            "totalSeconds": TIER_BUDGET_SECONDS.get(args.tier),
            "commandSeconds": COMMAND_BUDGET_SECONDS,
            "enforceBudget": bool(args.enforce_budget),
        },
        "commands": [],
        "slowCommands": [],
        "blockers": [],
        "warnings": [],
        "errors": [],
        "artifacts": {
            "summaryJson": str((run_dir / "summary.json").resolve()),
            "summaryMarkdown": str((run_dir / "summary.md").resolve()),
            "runDirectory": str(run_dir.resolve()),
        },
        "safety": {
            **safety_flags(),
            "proofPromotion": False,
        },
    }


def execute_specs(args: argparse.Namespace, repo_root: Path, run_dir: Path, specs: list[CommandSpec]) -> list[dict[str, Any]]:
    commands_dir = run_dir / "commands"
    results: list[dict[str, Any]] = []
    for index, command in enumerate(specs, start=1):
        result = run_command(
            command,
            index=index,
            repo_root=repo_root,
            commands_dir=commands_dir,
            heartbeat_seconds=float(args.heartbeat_seconds),
            enforce_budget=bool(args.enforce_budget),
            json_mode=bool(args.json),
        )
        results.append(result)
        if not result.get("ok") and not args.continue_on_failure:
            break
    return results


def parse_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def resolve_commit(repo_root: Path, commit: str) -> str:
    if commit.upper() == "HEAD":
        completed = run_quiet(["git", "rev-parse", "HEAD"], repo_root, timeout_seconds=30)
        if completed.returncode != 0:
            raise ValidationLedgerError(f"git rev-parse HEAD failed: {completed.stderr.strip()}")
        return completed.stdout.strip()
    return commit


def matching_ci_runs(raw_runs: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_runs, list):
        return []
    matches: list[dict[str, Any]] = []
    for run in raw_runs:
        if not isinstance(run, dict):
            continue
        name = str(run.get("name") or "")
        workflow_name = str(run.get("workflowName") or "")
        if name in CI_WORKFLOWS or workflow_name in CI_WORKFLOWS:
            matches.append(run)
    return matches


def execute_ci_parity(args: argparse.Namespace, repo_root: Path, run_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any], list[str], list[str], list[str]]:
    gh = args.gh_executable
    specs = [
        spec("gh-version", [gh, "--version"], tier="ci-parity", phase="ci-preflight", timeout_seconds=60.0, budget_seconds=30.0),
        spec("gh-auth-status", [gh, "auth", "status"], tier="ci-parity", phase="ci-preflight", timeout_seconds=60.0, budget_seconds=30.0),
    ]
    results = execute_specs(args, repo_root, run_dir, specs)
    slow, blockers, warnings, errors = summarize_runs(results)
    ci: dict[str, Any] = {
        "commit": None,
        "workflows": list(CI_WORKFLOWS),
        "polls": [],
        "runs": [],
        "failedLogs": [],
    }
    if blockers or errors:
        return results, ci, blockers or ["ci-preflight-blocked"], warnings, []
    try:
        commit = resolve_commit(repo_root, args.commit)
        ci["commit"] = commit
    except ValidationLedgerError as exc:
        return results, ci, [str(exc)], warnings, []

    deadline = time.monotonic() + float(args.ci_timeout_seconds)
    poll_index = len(results) + 1
    final_runs: list[dict[str, Any]] = []
    while True:
        poll_spec = spec(
            f"ci-poll-{len(ci['polls']) + 1}",
            [
                gh,
                "run",
                "list",
                "--commit",
                commit,
                "--json",
                "databaseId,name,status,conclusion,headSha,workflowName,createdAt,url",
                "--limit",
                "20",
            ],
            tier="ci-parity",
            phase="ci-poll",
            timeout_seconds=60.0,
            budget_seconds=60.0,
        )
        poll_result = run_command(
            poll_spec,
            index=poll_index,
            repo_root=repo_root,
            commands_dir=run_dir / "commands",
            heartbeat_seconds=float(args.heartbeat_seconds),
            enforce_budget=bool(args.enforce_budget),
            json_mode=bool(args.json),
        )
        results.append(poll_result)
        poll_index += 1
        if not poll_result.get("ok"):
            blockers.append(f"ci-poll-failed:{poll_result.get('error') or poll_result.get('stderrPreview')}")
            break
        raw_runs = parse_json_file(Path(str(poll_result["stdoutPath"])))
        runs = matching_ci_runs(raw_runs)
        final_runs = runs
        ci["polls"].append({"polledAtUtc": poll_result.get("endedAtUtc"), "runs": runs})
        ci["runs"] = runs
        complete = len(runs) >= len(CI_WORKFLOWS) and all(run.get("status") == "completed" for run in runs)
        if complete:
            break
        if time.monotonic() >= deadline:
            blockers.append(f"ci-poll-timeout:{args.ci_timeout_seconds}s")
            break
        time.sleep(float(args.ci_poll_seconds))

    if final_runs and all(run.get("status") == "completed" for run in final_runs):
        failed_runs = [run for run in final_runs if run.get("conclusion") != "success"]
        if failed_runs:
            errors.append("ci-workflow-failed:" + ",".join(str(run.get("name") or run.get("workflowName")) for run in failed_runs))
            for failed in failed_runs:
                run_id = str(failed.get("databaseId") or "")
                if not run_id:
                    continue
                log_spec = spec(
                    f"ci-log-failed-{run_id}",
                    [gh, "run", "view", run_id, "--log-failed"],
                    tier="ci-parity",
                    phase="ci-logs",
                    timeout_seconds=120.0,
                    budget_seconds=120.0,
                    expected_exit_codes=(0, 1),
                )
                log_result = run_command(
                    log_spec,
                    index=poll_index,
                    repo_root=repo_root,
                    commands_dir=run_dir / "commands",
                    heartbeat_seconds=float(args.heartbeat_seconds),
                    enforce_budget=bool(args.enforce_budget),
                    json_mode=bool(args.json),
                )
                results.append(log_result)
                poll_index += 1
                ci["failedLogs"].append(
                    {
                        "runId": run_id,
                        "stdoutPath": log_result.get("stdoutPath"),
                        "stderrPath": log_result.get("stderrPath"),
                        "stdoutPreview": log_result.get("stdoutPreview"),
                        "stderrPreview": log_result.get("stderrPreview"),
                    }
                )
    elif not blockers:
        blockers.append("ci-workflows-not-found-or-incomplete")

    slow2, blockers2, warnings2, errors2 = summarize_runs(results)
    warnings.extend(warnings2)
    blockers.extend(blocker for blocker in blockers2 if blocker not in blockers)
    if not blockers:
        errors.extend(error for error in errors2 if error not in errors)
    ci["slowCommands"] = slow2
    return results, ci, blockers, warnings, errors


def build_markdown(summary: dict[str, Any]) -> str:
    status = str(summary.get("status") or "blocked")
    icon = {"passed": "✅", "failed": "❌", "blocked": "⚠️"}.get(status, "⚠️")
    lines = [
        "# RiftReader validation ledger",
        "",
        "## Verdict",
        "",
        f"{icon} **{status.upper()}** — tier `{summary.get('tier')}` completed in `{format_duration(summary.get('durationSeconds'))}`.",
        "",
        "## Timing summary",
        "",
        "| # | Phase | Command | Status | Duration | Started UTC | Ended UTC |",
        "|---:|---|---|---|---:|---|---|",
    ]
    for command in summary.get("commands") or []:
        cmd_status = result_status(command)
        lines.append(
            f"| {command.get('index')} | `{command.get('phase')}` | `{command.get('label')}` | `{cmd_status}` | `{format_duration(command.get('durationSeconds'))}` | `{command.get('startedAtUtc')}` | `{command.get('endedAtUtc')}` |"
        )

    lines.extend(["", "## Slow commands", ""])
    slow = summary.get("slowCommands") or []
    if slow:
        lines.extend(["| Command | Duration | Budget |", "|---|---:|---:|"])
        for command in slow:
            lines.append(f"| `{command.get('label')}` | `{format_duration(command.get('durationSeconds'))}` | `{format_duration(command.get('budgetSeconds'))}` |")
    else:
        lines.append("None.")

    lines.extend(["", "## Failures", ""])
    failures = [cmd for cmd in summary.get("commands") or [] if not cmd.get("ok")]
    if failures:
        lines.extend(["| Command | Exit | Timed out | Error |", "|---|---:|---:|---|"])
        for command in failures:
            error = str(command.get("error") or command.get("stderrPreview") or "").replace("\n", " ")[:240]
            lines.append(f"| `{command.get('label')}` | `{command.get('exitCode')}` | `{str(command.get('timedOut')).lower()}` | {error} |")
    else:
        lines.append("None.")

    git = summary.get("git") or {}
    artifacts = summary.get("artifacts") or {}
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Run directory: `{artifacts.get('runDirectory')}`",
            f"- JSON: `{artifacts.get('summaryJson')}`",
            f"- Markdown: `{artifacts.get('summaryMarkdown')}`",
            "",
            "## Git state",
            "",
            f"- Branch: `{git.get('branch')}`",
            f"- HEAD: `{git.get('head')}`",
            f"- Dirty: `{str(git.get('dirty')).lower()}`",
            f"- Ahead/behind: `{git.get('ahead')}/{git.get('behind')}`",
            "",
            "## Next action",
            "",
        ]
    )
    if status == "passed":
        lines.append("Continue to the next validation tier, commit/push gate, or handoff update as appropriate.")
    elif status == "blocked":
        lines.append("Resolve the listed blocker before rerunning this validation tier.")
    else:
        lines.append("Diagnose the first failed command before broadening scope.")
    return "\n".join(lines).rstrip() + "\n"


def write_summary(summary: dict[str, Any]) -> None:
    artifacts = summary["artifacts"]
    summary_json = Path(str(artifacts["summaryJson"]))
    summary_md = Path(str(artifacts["summaryMarkdown"]))
    summary_json.write_text(json.dumps(summary, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    summary_md.write_text(build_markdown(summary), encoding="utf-8")


def run_validation(args: argparse.Namespace) -> dict[str, Any]:
    if args.tier not in SUPPORTED_TIERS:
        raise ValidationLedgerError(f"unsupported tier: {args.tier}")
    repo_root = resolve_repo_root(args.repo_root)
    run_dir = make_run_directory(repo_root, args.output_root)
    started_at = utc_iso()
    start = time.monotonic()
    summary = base_summary(args, repo_root, run_dir, started_at)
    try:
        if args.tier == "ci-parity":
            commands, ci, blockers, warnings, errors = execute_ci_parity(args, repo_root, run_dir)
            summary["ci"] = ci
        else:
            specs = build_specs(args, repo_root)
            commands = execute_specs(args, repo_root, run_dir, specs)
            slow, blockers, warnings, errors = summarize_runs(commands)
        summary["commands"] = commands
        summary["slowCommands"] = [cmd for cmd in commands if cmd.get("slow")]
        summary["blockers"] = blockers
        summary["warnings"] = warnings
        summary["errors"] = errors
        if summary["slowCommands"] and args.enforce_budget:
            summary["errors"].append("budget-enforced-slow-command")
        summary["status"] = status_from_lists(summary["blockers"], summary["errors"])
    except ValidationLedgerError as exc:
        summary["blockers"].append(str(exc))
        summary["status"] = "blocked"
    except Exception as exc:  # noqa: BLE001 - top-level helper must produce a summary.
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
        summary["status"] = "failed"
    finally:
        summary["endedAtUtc"] = utc_iso()
        summary["durationSeconds"] = round(time.monotonic() - start, 3)
        summary["git"] = collect_git_state(repo_root)
        write_summary(summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="Run fixture-only internal checks and exit.")
    parser.add_argument("--tier", choices=sorted(SUPPORTED_TIERS))
    parser.add_argument("--repo-root", help="Repo root or child path. Defaults to current working directory.")
    parser.add_argument("--output-root", help="Output root for ledger run directories. Defaults to .riftreader-local\\validation-runs.")
    parser.add_argument("--command", action="append", help="Custom command string for targeted/custom tiers. May be repeated.")
    parser.add_argument("--command-json", action="append", help="Exact argv JSON array or object with args/label/phase/timeoutSeconds/budgetSeconds.")
    parser.add_argument("--timeout-seconds", type=float, default=120.0, help="Default timeout for custom commands.")
    parser.add_argument("--heartbeat-seconds", type=float, default=30.0, help="Progress heartbeat interval.")
    parser.add_argument("--default-command-budget-seconds", type=float, default=120.0, help="Warning budget for custom commands without an inferred budget.")
    parser.add_argument("--enforce-budget", action="store_true", help="Treat budget overruns as validation failures.")
    parser.add_argument("--continue-on-failure", action="store_true", help="Run later commands after a failure instead of failing fast.")
    parser.add_argument("--commit", default="HEAD", help="Commit SHA/ref for ci-parity.")
    parser.add_argument("--gh-executable", default="gh", help="GitHub CLI executable for ci-parity.")
    parser.add_argument("--ci-poll-seconds", type=float, default=15.0, help="CI polling interval.")
    parser.add_argument("--ci-timeout-seconds", type=float, default=TIER_BUDGET_SECONDS["ci-parity"], help="CI polling timeout.")
    parser.add_argument("--json", action="store_true", help="Print final JSON summary to stdout; progress goes to stderr.")
    return parser


def run_self_test() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "pass": bool(ok), "detail": detail})

    try:
        parsed = parse_command_string('"python" -m unittest scripts.test_validation_ledger')
        record("windows-command-string-parse", parsed[:3] == ["python", "-m", "unittest"], str(parsed))
    except Exception as exc:  # noqa: BLE001 - self-test reports controlled failures.
        record("windows-command-string-parse", False, f"{type(exc).__name__}:{exc}")

    markdown = build_markdown(
        {
            "status": "passed",
            "tier": "custom",
            "durationSeconds": 1.0,
            "commands": [],
            "slowCommands": [],
            "git": {"branch": "main", "head": "abc", "dirty": False, "ahead": 0, "behind": 0},
            "artifacts": {"runDirectory": "run", "summaryJson": "summary.json", "summaryMarkdown": "summary.md"},
        }
    )
    record("markdown-sections", "## Timing summary" in markdown and "## Next action" in markdown)
    record("status-exit-code", STATUS_EXIT_CODES["passed"] == 0 and STATUS_EXIT_CODES["blocked"] == 2)
    record("slugify", slugify("a/b c") == "a-b-c")
    ok = all(check["pass"] for check in checks)
    return {
        "schemaVersion": 1,
        "kind": "riftreader-validation-ledger-self-test",
        "toolVersion": TOOL_VERSION,
        "status": "passed" if ok else "failed",
        "ok": ok,
        "checks": checks,
        "safety": {
            **safety_flags(),
            "proofPromotion": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        report = run_self_test()
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"validation-ledger self-test: {report['status']}")
        return 0 if report.get("ok") else 1
    if not args.tier:
        parser.error("--tier is required unless --self-test is used")
        return STATUS_EXIT_CODES["blocked"]
    try:
        summary = run_validation(args)
    except ValidationLedgerError as exc:
        print(json.dumps({"status": "blocked", "blockers": [str(exc)]}, indent=2), file=sys.stderr)
        return STATUS_EXIT_CODES["blocked"]
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Validation ledger {summary['status']}: {summary['artifacts']['summaryMarkdown']}")
    return STATUS_EXIT_CODES.get(str(summary.get("status")), 1)


if __name__ == "__main__":
    raise SystemExit(main())
