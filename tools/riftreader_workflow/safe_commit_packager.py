#!/usr/bin/env python3
"""Generate explicit-path safe commit plans for RiftReader workflow slices."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, safety_flags, utc_iso
    from .mcp_workflow_state import build_mcp_workflow_state, classify_dirty_path, git_dirty_state
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, safety_flags, utc_iso
    from riftreader_workflow.mcp_workflow_state import build_mcp_workflow_state, classify_dirty_path, git_dirty_state


def quote_path(path: str) -> str:
    escaped = path.replace('"', '\\"')
    return f'"{escaped}"'


def group_entries(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        slice_name = str(entry.get("slice") or classify_dirty_path(str(entry.get("path") or "")))
        grouped.setdefault(slice_name, []).append({**entry, "slice": slice_name})
    return grouped


def commit_message_for(grouped: dict[str, list[dict[str, Any]]]) -> str:
    slices = set(grouped)
    if "mcp-code" in slices or "operator-lite" in slices or "wrappers" in slices:
        return "Add MCP workflow helper apps"
    if slices <= {"docs", "handoff"}:
        return "Update MCP workflow documentation"
    if "tests" in slices and len(slices) == 1:
        return "Add MCP workflow helper tests"
    return "Update RiftReader workflow helpers"


def safe_commit_plan(repo_root: Path) -> dict[str, Any]:
    git_state = git_dirty_state(repo_root)
    entries = git_state.get("entries") if isinstance(git_state.get("entries"), list) else []
    grouped = group_entries(entries)
    normalized_entries = [entry for items in grouped.values() for entry in items]
    stageable = [entry for entry in normalized_entries if entry.get("slice") != "generated-ignored" and entry.get("path")]
    git_add_commands = [["git", "add", "--", str(entry["path"])] for entry in stageable]
    paste_commands = ["git add -- " + quote_path(str(entry["path"])) for entry in stageable]
    validation_commands = [
        "python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_local_artifact_bridge scripts.test_operator_lite scripts.test_package_draft_review scripts.test_mcp_workflow_state scripts.test_mcp_artifact_browser scripts.test_workflow_router scripts.test_mcp_mission_control scripts.test_chatgpt_trial_recorder scripts.test_safe_commit_packager",
        "git --no-pager diff --check",
    ]
    state = build_mcp_workflow_state(repo_root)
    status = "ready" if entries else "clean"
    return {
        "schemaVersion": 1,
        "kind": "riftreader-safe-commit-packager-plan",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": True,
        "gitDirtyState": git_state,
        "groups": grouped,
        "stageablePaths": [entry.get("path") for entry in stageable],
        "gitAddCommands": git_add_commands,
        "pasteSafeGitAddCommands": paste_commands,
        "containsGitAddDot": any(cmd.strip() == "git add ." for cmd in paste_commands),
        "draftCommitMessage": commit_message_for(grouped),
        "validationCommandsBeforeCommit": validation_commands,
        "latestValidationArtifacts": {
            "readiness": (state.get("latestArtifacts") or {}).get("readiness"),
            "proposalSmoke": (state.get("latestArtifacts") or {}).get("proposal-smoke"),
            "cloudflareSmoke": (state.get("latestArtifacts") or {}).get("cloudflare-smoke"),
            "actualClientProof": (state.get("latestArtifacts") or {}).get("actual-client-proof"),
        },
        "warnings": git_state.get("warnings") or [],
        "safety": {
            **safety_flags(),
            "planOnly": True,
            "gitMutation": False,
            "stagedFiles": False,
            "committed": False,
            "pushed": False,
            "usesExplicitPathsOnly": True,
        },
        "next": [
            "Run validationCommandsBeforeCommit before staging.",
            "If validation passes, stage only the explicit paths listed in pasteSafeGitAddCommands.",
            "Avoid broad staging; use only the explicit paths listed above.",
        ],
    }


def render_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# RiftReader Safe Commit Plan",
        "",
        f"- Generated UTC: `{plan.get('generatedAtUtc')}`",
        f"- Status: `{plan.get('status')}`",
        f"- Draft commit message: `{plan.get('draftCommitMessage')}`",
        f"- Stageable paths: `{len(plan.get('stageablePaths') or [])}`",
        "",
        "## Explicit staging commands",
        "",
    ]
    for command in plan.get("pasteSafeGitAddCommands") or ["none"]:
        lines.append(f"- `{command}`")
    lines.extend(["", "## Validation before commit", ""])
    for command in plan.get("validationCommandsBeforeCommit") or []:
        lines.append(f"- `{command}`")
    lines.extend(["", "## Groups", ""])
    groups = plan.get("groups") if isinstance(plan.get("groups"), dict) else {}
    for group, entries in groups.items():
        lines.append(f"### {group}")
        for entry in entries:
            lines.append(f"- `{entry.get('status')}` `{entry.get('path')}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate explicit-path Git commit checklist without mutating Git.")
    parser.add_argument("--plan", action="store_true", help="Print safe commit plan.")
    parser.add_argument("--markdown", action="store_true", help="Print the safe commit plan as Markdown.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.plan:
        print("error: --plan is required; this MVP never stages or commits", file=sys.stderr)
        return 2
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    payload = safe_commit_plan(repo_root)
    if args.markdown:
        print(render_markdown(payload))
    elif args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Status: {payload['status']}")
        print(f"Commit message: {payload['draftCommitMessage']}")
        for command in payload["pasteSafeGitAddCommands"]:
            print(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
