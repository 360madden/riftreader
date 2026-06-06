#!/usr/bin/env python3
"""State-based next-action router for RiftReader MCP workflow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, safety_flags, utc_iso
    from .mcp_workflow_state import build_mcp_workflow_state, has_stageable_dirty, passed
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, safety_flags, utc_iso
    from riftreader_workflow.mcp_workflow_state import build_mcp_workflow_state, has_stageable_dirty, passed


def ranked_actions(state: dict[str, Any]) -> list[dict[str, Any]]:
    commands = state.get("commands") if isinstance(state.get("commands"), dict) else {}
    latest = state.get("latestArtifacts") if isinstance(state.get("latestArtifacts"), dict) else {}
    git_state = state.get("gitDirtyState") if isinstance(state.get("gitDirtyState"), dict) else {}
    actions: list[dict[str, Any]] = []

    def add(key: str, priority: str, reason: str, command_key: str) -> None:
        actions.append({"key": key, "priority": priority, "reason": reason, "command": commands.get(command_key, [])})

    if has_stageable_dirty(git_state) and passed(latest.get("readiness")) and passed(latest.get("proposal-smoke")):
        add("safe-commit-plan", "P0", "Validated dirty MCP slice exists; generate explicit-path commit checklist.", "safeCommitPlan")
    if not passed(latest.get("readiness")):
        add("mcp-trial-readiness", "P0", "No passing local MCP trial-readiness artifact is available.", "mcpTrialReadiness")
    if not passed(latest.get("proposal-smoke")):
        add("proposal-transport-smoke", "P0", "No passing guarded proposal transport smoke artifact is available.", "proposalTransportSmoke")
    if not passed(latest.get("manual-public-ip-plan")):
        add("manual-public-ip-plan", "P1", "No manual external-IP Server URL plan artifact is available.", "manualPublicIpPlan")
    if not passed(latest.get("actual-client-proof")):
        add("chatgpt-manual-public-ip-proof", "P1", "Actual ChatGPT client proof has not been recorded.", "manualPublicIpPlan")
    if latest.get("inbox") and not latest.get("draft"):
        add("inbox-to-draft", "P1", "Inbox proposal exists but no inert draft is discovered.", "inboxPackageDraft")
    if latest.get("draft") and not passed(latest.get("dry-run")):
        add("draft-dry-run", "P1", "Draft exists but no passing dry-run artifact is discovered.", "dryRunLatestDraft")
    if passed(latest.get("actual-client-proof")):
        if not has_stageable_dirty(git_state):
            add("mcp-final-status", "P1", "Actual-client proof exists and working tree is clean; run the final readiness gate.", "mcpFinalStatus")
        add("mcp-phase2-status", "P1", "Actual-client proof exists; run the read-only Phase 2 gate for CI, replay, and freshness status.", "mcpPhase2Status")
    add("latest-artifacts", "P2", "Open latest artifact browser when evidence paths are unclear.", "mcpArtifactsLatest")
    add("mission-control", "P2", "Open consolidated MCP dashboard.", "mcpMissionControl")
    if passed(latest.get("actual-client-proof")) and not git_state.get("dirty"):
        add("expand-read-only-tooling", "P3", "Actual-client proof exists and working tree is clean; consider next read-only MCP improvement.", "mcpMissionControl")
    return actions


def route_mcp(repo_root: Path) -> dict[str, Any]:
    state = build_mcp_workflow_state(repo_root)
    actions = ranked_actions(state)
    recommended = actions[0] if actions else state.get("recommendedNextAction")
    return {
        "schemaVersion": 1,
        "kind": "riftreader-workflow-router-mcp",
        "generatedAtUtc": utc_iso(),
        "status": "ready",
        "ok": True,
        "recommendedNextAction": recommended,
        "rankedActions": actions,
        "state": {
            "status": state.get("status"),
            "blockers": state.get("blockers"),
            "warnings": state.get("warnings"),
            "counts": state.get("counts"),
            "latestArtifacts": state.get("latestArtifacts"),
            "gitDirtyState": state.get("gitDirtyState"),
        },
        "safety": {
            **safety_flags(),
            "readOnlyRouting": True,
            "publicTunnelStarted": False,
            "gitMutation": False,
        },
    }


def self_test() -> dict[str, Any]:
    state = {
        "commands": {"mcpTrialReadiness": ["readiness"], "mcpPhase2Status": ["phase2"], "mcpFinalStatus": ["final"]},
        "latestArtifacts": {},
        "gitDirtyState": {"dirty": False, "entries": []},
    }
    actions = ranked_actions(state)
    checks = [{"name": "missing-readiness-routes-first", "pass": bool(actions) and actions[0].get("key") == "mcp-trial-readiness"}]
    ok = all(check["pass"] for check in checks)
    return {
        "schemaVersion": 1,
        "kind": "riftreader-workflow-router-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if ok else "failed",
        "ok": ok,
        "checks": checks,
        "safety": {
            **safety_flags(),
            "readOnlyRouting": True,
            "gitMutation": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Route to the next safest RiftReader workflow action.")
    parser.add_argument("--mcp", action="store_true", help="Route the ChatGPT MCP/local artifact bridge lane.")
    parser.add_argument("--self-test", action="store_true", help="Run deterministic router self-test.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        payload = self_test()
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Status: {payload.get('status')}")
        return 0 if payload.get("ok") else 1
    if not args.mcp:
        print("error: --mcp is required for this MVP router", file=sys.stderr)
        return 2
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    payload = route_mcp(repo_root)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        action = payload.get("recommendedNextAction") or {}
        print(f"Recommended: {action.get('key')}")
        print("Command: " + " ".join(action.get("command") or []))
        print(f"Why: {action.get('reason')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
