#!/usr/bin/env python3
"""MCP Mission Control dashboard for RiftReader."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, run_command_envelope, safety_flags, utc_iso
    from .mcp_workflow_state import build_mcp_workflow_state, standard_commands
    from .workflow_router import ranked_actions
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, run_command_envelope, safety_flags, utc_iso
    from riftreader_workflow.mcp_workflow_state import build_mcp_workflow_state, standard_commands
    from riftreader_workflow.workflow_router import ranked_actions


def mission_control(repo_root: Path) -> dict[str, Any]:
    state = build_mcp_workflow_state(repo_root)
    commands = standard_commands()
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-mission-control",
        "generatedAtUtc": utc_iso(),
        "status": state.get("status"),
        "ok": state.get("ok"),
        "blockers": state.get("blockers"),
        "warnings": state.get("warnings"),
        "latestArtifacts": state.get("latestArtifacts"),
        "counts": state.get("counts"),
        "gitDirtyState": state.get("gitDirtyState"),
        "recommendedNextAction": state.get("recommendedNextAction"),
        "rankedActions": ranked_actions(state),
        "pasteSafeCommands": {
            "readiness": commands["mcpTrialReadiness"],
            "proposalSmoke": commands["proposalTransportSmoke"],
            "publicSmoke": commands["cloudflareSmoke"],
            "trialSession": commands["chatGptTrialSession"],
            "inboxReview": commands["inboxLatest"],
            "draftExport": commands["inboxPackageDraft"],
            "draftDryRun": commands["dryRunLatestDraft"],
            "artifactBrowser": commands["mcpArtifactsLatest"],
            "safeCommitPlan": commands["safeCommitPlan"],
        },
        "safety": {
            **safety_flags(),
            "missionControlDefaultReadOnly": True,
            "publicTunnelStarted": False,
            "persistentServerStarted": False,
            "chatGptRegistrationPerformed": False,
            "gitMutation": False,
            "applyFlagSent": False,
        },
    }


def trial_command_payload(repo_root: Path) -> dict[str, Any]:
    commands = standard_commands()
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-mission-control-trial-command",
        "generatedAtUtc": utc_iso(),
        "status": "ready",
        "ok": True,
        "command": commands["chatGptTrialSession"],
        "notes": [
            "This command starts a bounded public tunnel only when the operator runs it explicitly.",
            "Use the printed publicMcpUrl in ChatGPT Developer Mode while the command is still running.",
        ],
        "safety": {
            **safety_flags(),
            "publicTunnelStarted": False,
            "commandDisplayedOnly": True,
        },
    }


def render_summary_markdown(payload: dict[str, Any]) -> str:
    action = payload.get("recommendedNextAction") if isinstance(payload.get("recommendedNextAction"), dict) else {}
    lines = [
        "# RiftReader MCP Mission Control Summary",
        "",
        f"- Generated UTC: `{payload.get('generatedAtUtc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Recommended action: `{action.get('key')}`",
        f"- Recommended command: `{' '.join(action.get('command') or [])}`",
        "",
        "## Latest artifacts",
        "",
        "| Kind | Status | Path | Notes |",
        "|---|---|---|---|",
    ]
    latest = payload.get("latestArtifacts") if isinstance(payload.get("latestArtifacts"), dict) else {}
    for kind, item in latest.items():
        if not item:
            lines.append(f"| `{kind}` | none |  |  |")
            continue
        notes = []
        if item.get("selfTest"):
            notes.append("self-test")
        if item.get("publicUrlExpectedExpired"):
            notes.append("ephemeral URL stopped")
        lines.append(f"| `{kind}` | `{item.get('status')}` | `{item.get('path')}` | {', '.join(notes)} |")
    lines.extend(["", "## Warnings", ""])
    for warning in payload.get("warnings") or ["none"]:
        lines.append(f"- `{warning}`")
    return "\n".join(lines).rstrip() + "\n"


def render_proof_checklist(payload: dict[str, Any]) -> str:
    commands = payload.get("pasteSafeCommands") if isinstance(payload.get("pasteSafeCommands"), dict) else {}
    return "\n".join(
        [
            "# RiftReader MCP Proof Checklist",
            "",
            "- [ ] Run local readiness.",
            f"  - `{' '.join(commands.get('readiness') or [])}`",
            "- [ ] Run guarded proposal transport smoke.",
            f"  - `{' '.join(commands.get('proposalSmoke') or [])}`",
            "- [ ] Run explicit public smoke if environment changed.",
            f"  - `{' '.join(commands.get('publicSmoke') or [])}`",
            "- [ ] Start the bounded ChatGPT trial session only when ready to register in ChatGPT.",
            f"  - `{' '.join(commands.get('trialSession') or [])}`",
            "- [ ] In ChatGPT Developer Mode, confirm 8 tools, `health.repoRoot == \".\"`, and `absoluteRepoRootExposed == false`.",
            "- [ ] Submit one tiny package proposal through actual ChatGPT.",
            "- [ ] Confirm `list_inbox` sees the returned inbox ID.",
            f"  - `{' '.join(commands.get('inboxReview') or [])}`",
            "- [ ] Export the inbox item into an inert draft.",
            f"  - `{' '.join(commands.get('draftExport') or [])}`",
            "- [ ] Dry-run the latest draft without apply.",
            f"  - `{' '.join(commands.get('draftDryRun') or [])}`",
            "- [ ] Record actual-client facts with the ChatGPT Trial Recorder.",
            "  - `scripts\\riftreader-chatgpt-trial-recorder.cmd --record --input proof.json --json`",
            "",
        ]
    )


def run_local_action(repo_root: Path, command_key: str, label: str) -> dict[str, Any]:
    commands = standard_commands()
    args = commands[command_key]
    envelope = run_command_envelope(label, args, repo_root, timeout_seconds=180, expected_exit_codes={0, 2}, capture_full_output=True)
    status = "passed" if envelope.get("exitCode") == 0 else "blocked" if envelope.get("exitCode") == 2 else "failed"
    parsed_stdout = None
    stdout = envelope.get("stdout") if isinstance(envelope.get("stdout"), str) else ""
    if stdout.strip().startswith("{"):
        try:
            parsed_stdout = json.loads(stdout)
        except json.JSONDecodeError:
            parsed_stdout = None
    return {
        "schemaVersion": 1,
        "kind": f"riftreader-mcp-mission-control-{label}",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": status == "passed",
        "command": args,
        "commandEnvelope": envelope,
        "parsedStdout": parsed_stdout,
        "safety": {
            **safety_flags(),
            "publicTunnelStarted": False,
            "gitMutation": False,
            "applyFlagSent": False,
        },
    }


def print_human(payload: dict[str, Any]) -> None:
    print(f"Status: {payload.get('status')} ok={payload.get('ok')}")
    action = payload.get("recommendedNextAction")
    if isinstance(action, dict):
        print(f"Next: {action.get('key')} - {' '.join(action.get('command') or [])}")
        print(f"Why: {action.get('reason')}")
    latest = payload.get("latestArtifacts") if isinstance(payload.get("latestArtifacts"), dict) else {}
    for key, item in latest.items():
        if item:
            print(f"- {key}: {item.get('status')} {item.get('path')}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RiftReader MCP Mission Control dashboard.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run-readiness", action="store_true", help="Run local MCP trial-readiness only.")
    mode.add_argument("--run-proposal-smoke", action="store_true", help="Run local proposal transport smoke only.")
    mode.add_argument("--trial-command", action="store_true", help="Print bounded ChatGPT trial-session command without running it.")
    mode.add_argument("--summary-md", action="store_true", help="Print a Markdown mission-control summary.")
    mode.add_argument("--checklist-md", action="store_true", help="Print a Markdown actual-client proof checklist.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    if args.run_readiness:
        payload = run_local_action(repo_root, "mcpTrialReadiness", "run-readiness")
    elif args.run_proposal_smoke:
        payload = run_local_action(repo_root, "proposalTransportSmoke", "run-proposal-smoke")
    elif args.trial_command:
        payload = trial_command_payload(repo_root)
    elif args.summary_md:
        payload = mission_control(repo_root)
        print(render_summary_markdown(payload))
        return 0 if payload.get("ok") else 2 if payload.get("status") == "blocked" else 1
    elif args.checklist_md:
        payload = mission_control(repo_root)
        print(render_proof_checklist(payload))
        return 0
    else:
        payload = mission_control(repo_root)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_human(payload)
    return 0 if payload.get("ok") else 2 if payload.get("status") == "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
