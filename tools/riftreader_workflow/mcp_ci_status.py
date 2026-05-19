#!/usr/bin/env python3
"""Read-only current-head CI status helpers for the RiftReader MCP lane."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

try:
    from .common import find_repo_root, run_command_envelope, safety_flags, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, run_command_envelope, safety_flags, utc_iso


REQUIRED_WORKFLOWS = (".NET build and test", "RiftReader Policy")
GhRunner = Callable[[list[str], Path, float], dict[str, Any]]


def _compact_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    """Drop full command streams from public status packets; previews remain."""

    return {key: value for key, value in envelope.items() if key not in {"stdout", "stderr"}}


def _sorted_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        runs,
        key=lambda run: (
            str(run.get("updatedAt") or ""),
            str(run.get("createdAt") or ""),
            int(run.get("databaseId") or 0),
        ),
        reverse=True,
    )


def evaluate_ci_runs(
    *,
    current_head: str,
    runs: list[dict[str, Any]],
    required_workflows: tuple[str, ...] = REQUIRED_WORKFLOWS,
) -> dict[str, Any]:
    """Evaluate GitHub Actions runs for *current_head* without calling GitHub."""

    blockers: list[str] = []
    workflows: dict[str, dict[str, Any]] = {}
    for workflow in required_workflows:
        candidates = [
            run
            for run in runs
            if isinstance(run, dict)
            and run.get("workflowName") == workflow
            and run.get("headSha") == current_head
        ]
        selected = _sorted_runs(candidates)[0] if candidates else None
        if selected is None:
            blockers.append(f"ci-workflow-missing-current-head:{workflow}")
            workflows[workflow] = {
                "workflowName": workflow,
                "status": "missing",
                "ok": False,
                "headSha": current_head,
                "run": None,
            }
            continue
        status = selected.get("status")
        conclusion = selected.get("conclusion")
        ok = status == "completed" and conclusion == "success"
        if status != "completed":
            blockers.append(f"ci-workflow-not-completed:{workflow}:{status}")
        elif conclusion != "success":
            blockers.append(f"ci-workflow-not-success:{workflow}:{conclusion}")
        workflows[workflow] = {
            "workflowName": workflow,
            "status": status,
            "conclusion": conclusion,
            "ok": ok,
            "headSha": selected.get("headSha"),
            "databaseId": selected.get("databaseId"),
            "createdAt": selected.get("createdAt"),
            "updatedAt": selected.get("updatedAt"),
            "event": selected.get("event"),
            "url": selected.get("url"),
            "run": selected,
        }

    status = "passed" if not blockers else "blocked"
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-current-head-ci-status",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": status == "passed",
        "currentHead": current_head,
        "requiredWorkflows": list(required_workflows),
        "workflows": workflows,
        "blockers": blockers,
        "warnings": [],
        "safety": {
            **safety_flags(),
            "readOnlyGitHubCliInspection": True,
            "gitMutation": False,
            "publicTunnelStarted": False,
        },
    }


def _git_head(repo_root: Path) -> tuple[str | None, dict[str, Any]]:
    envelope = run_command_envelope(
        "git-rev-parse-head",
        ["git", "rev-parse", "HEAD"],
        repo_root,
        timeout_seconds=15,
        capture_full_output=True,
    )
    stdout = str(envelope.get("stdout") or "").strip()
    if envelope.get("ok") and stdout:
        return stdout.splitlines()[0].strip(), envelope
    return None, envelope


def _default_gh_runner(args: list[str], cwd: Path, timeout_seconds: float) -> dict[str, Any]:
    return run_command_envelope(
        "gh-run-list-current-head",
        args,
        cwd,
        timeout_seconds=timeout_seconds,
        capture_full_output=True,
    )


def current_head_ci_status(
    repo_root: Path,
    *,
    required_workflows: tuple[str, ...] = REQUIRED_WORKFLOWS,
    gh_runner: GhRunner | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Read current HEAD's required GitHub Actions status using ``gh`` only."""

    current_head, head_envelope = _git_head(repo_root)
    if not current_head:
        return {
            "schemaVersion": 1,
            "kind": "riftreader-mcp-current-head-ci-status",
            "generatedAtUtc": utc_iso(),
            "status": "blocked",
            "ok": False,
            "currentHead": None,
            "requiredWorkflows": list(required_workflows),
            "workflows": {},
            "blockers": ["git-head-unavailable"],
            "warnings": ["ci-status-unavailable:git-head-unavailable"],
            "gitHeadCommand": _compact_envelope(head_envelope),
            "safety": {
                **safety_flags(),
                "readOnlyGitHubCliInspection": True,
                "gitMutation": False,
                "publicTunnelStarted": False,
            },
        }

    args = [
        "gh",
        "run",
        "list",
        "--limit",
        "30",
        "--json",
        "databaseId,workflowName,headSha,status,conclusion,createdAt,updatedAt,event,url",
    ]
    runner = gh_runner or _default_gh_runner
    envelope = runner(args, repo_root, timeout_seconds)
    if not envelope.get("ok"):
        detail = envelope.get("error") or f"exit:{envelope.get('exitCode')}"
        return {
            "schemaVersion": 1,
            "kind": "riftreader-mcp-current-head-ci-status",
            "generatedAtUtc": utc_iso(),
            "status": "blocked",
            "ok": False,
            "currentHead": current_head,
            "requiredWorkflows": list(required_workflows),
            "workflows": {},
            "blockers": ["ci-status-unavailable"],
            "warnings": [f"ci-status-unavailable:{detail}"],
            "gitHeadCommand": _compact_envelope(head_envelope),
            "ghCommand": _compact_envelope(envelope),
            "safety": {
                **safety_flags(),
                "readOnlyGitHubCliInspection": True,
                "gitMutation": False,
                "publicTunnelStarted": False,
            },
        }

    try:
        runs_value = json.loads(str(envelope.get("stdout") or ""))
    except json.JSONDecodeError as exc:
        return {
            "schemaVersion": 1,
            "kind": "riftreader-mcp-current-head-ci-status",
            "generatedAtUtc": utc_iso(),
            "status": "blocked",
            "ok": False,
            "currentHead": current_head,
            "requiredWorkflows": list(required_workflows),
            "workflows": {},
            "blockers": ["ci-status-json-invalid"],
            "warnings": [f"ci-status-unavailable:json-invalid:{exc}"],
            "gitHeadCommand": _compact_envelope(head_envelope),
            "ghCommand": _compact_envelope(envelope),
            "safety": {
                **safety_flags(),
                "readOnlyGitHubCliInspection": True,
                "gitMutation": False,
                "publicTunnelStarted": False,
            },
        }
    if not isinstance(runs_value, list):
        return {
            "schemaVersion": 1,
            "kind": "riftreader-mcp-current-head-ci-status",
            "generatedAtUtc": utc_iso(),
            "status": "blocked",
            "ok": False,
            "currentHead": current_head,
            "requiredWorkflows": list(required_workflows),
            "workflows": {},
            "blockers": ["ci-status-json-not-list"],
            "warnings": ["ci-status-unavailable:json-not-list"],
            "gitHeadCommand": _compact_envelope(head_envelope),
            "ghCommand": _compact_envelope(envelope),
            "safety": {
                **safety_flags(),
                "readOnlyGitHubCliInspection": True,
                "gitMutation": False,
                "publicTunnelStarted": False,
            },
        }

    runs = [run for run in runs_value if isinstance(run, dict)]
    payload = evaluate_ci_runs(current_head=current_head, runs=runs, required_workflows=required_workflows)
    payload["runCountInspected"] = len(runs)
    payload["gitHeadCommand"] = _compact_envelope(head_envelope)
    payload["ghCommand"] = _compact_envelope(envelope)
    return payload


def self_test() -> dict[str, Any]:
    good = evaluate_ci_runs(
        current_head="abc",
        runs=[
            {"workflowName": ".NET build and test", "headSha": "abc", "status": "completed", "conclusion": "success"},
            {"workflowName": "RiftReader Policy", "headSha": "abc", "status": "completed", "conclusion": "success"},
        ],
    )
    bad = evaluate_ci_runs(
        current_head="abc",
        runs=[
            {"workflowName": ".NET build and test", "headSha": "abc", "status": "completed", "conclusion": "success"},
            {"workflowName": "RiftReader Policy", "headSha": "abc", "status": "completed", "conclusion": "failure"},
        ],
    )
    checks = [
        {"name": "current-head-pass", "pass": good.get("ok") is True},
        {"name": "current-head-fail-blocks", "pass": bad.get("ok") is False and bool(bad.get("blockers"))},
    ]
    ok = all(check["pass"] for check in checks)
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-ci-status-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if ok else "failed",
        "ok": ok,
        "checks": checks,
        "safety": {
            **safety_flags(),
            "gitHubCliCalled": False,
            "gitMutation": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read current-head GitHub Actions status for the RiftReader MCP lane.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true", help="Read current HEAD CI status with gh.")
    mode.add_argument("--self-test", action="store_true", help="Run deterministic CI status self-test without gh.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
        payload = self_test() if args.self_test else current_head_ci_status(repo_root)
    except Exception as exc:  # noqa: BLE001 - CLI must fail closed with structured error.
        payload = {
            "schemaVersion": 1,
            "kind": "riftreader-mcp-current-head-ci-status",
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "ok": False,
            "blockers": [f"ci-status-exception:{type(exc).__name__}:{exc}"],
            "warnings": [],
            "safety": safety_flags(),
        }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
