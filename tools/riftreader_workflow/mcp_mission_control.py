#!/usr/bin/env python3
"""MCP Mission Control dashboard for RiftReader."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, run_command_envelope, safety_flags, unique, utc_iso
    from .mcp_ci_status import current_head_ci_status
    from .mcp_final_readiness import compact_final_readiness, final_readiness
    from .mcp_workflow_state import build_mcp_workflow_state, standard_commands
    from .workflow_router import ranked_actions
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, run_command_envelope, safety_flags, unique, utc_iso
    from riftreader_workflow.mcp_ci_status import current_head_ci_status
    from riftreader_workflow.mcp_final_readiness import compact_final_readiness, final_readiness
    from riftreader_workflow.mcp_workflow_state import build_mcp_workflow_state, standard_commands
    from riftreader_workflow.workflow_router import ranked_actions


FINAL_PRODUCT_PHASES = (
    (1, "Preserve current MCP baseline"),
    (2, "Final readiness contract"),
    (3, "Final readiness gate"),
    (4, "Dependency and environment preflight"),
    (5, "Operator workflow hardening"),
    (6, "Safety/security hardening"),
    (7, "Fresh real ChatGPT trial"),
    (8, "Release handoff and maintenance loop"),
)


def build_final_product_progress(repo_root: Path, final_status: dict[str, Any], commands: dict[str, list[str]]) -> dict[str, Any]:
    """Summarize the final-product phase ladder for one operator dashboard."""

    contract_path = repo_root / "docs" / "workflow" / "riftreader-chatgpt-mcp-final-readiness.md"
    final_ok = final_status.get("ok") is True
    phase2_ready = final_status.get("phase2Ready") is True
    ci_passed = final_status.get("ciStatus") == "passed"
    upstream_passed = final_status.get("upstreamStatus") == "passed"
    dependency_passed = final_status.get("dependencyStatus") == "passed"
    environment_passed = final_status.get("environmentStatus") == "passed"
    tool_surface_passed = final_status.get("toolSurfaceStatus") == "passed"
    public_session_passed = final_status.get("publicSessionStatus") == "passed"
    phase_rows = [
        phase_row(
            1,
            "Preserve current MCP baseline",
            "completed" if phase2_ready and ci_passed and upstream_passed else "blocked",
            "Clean upstream-synced HEAD with current-head CI and replayable proof baseline.",
        ),
        phase_row(
            2,
            "Final readiness contract",
            "completed" if contract_path.is_file() else "blocked",
            "Final readiness contract document exists.",
        ),
        phase_row(
            3,
            "Final readiness gate",
            "completed" if "mcpFinalStatus" in commands and "mcpFinalCompactStatus" in commands else "blocked",
            "Final JSON and compact JSON gate commands are registered.",
        ),
        phase_row(
            4,
            "Dependency and environment preflight",
            "completed" if dependency_passed and environment_passed else "blocked",
            "Dependency and environment preflight fields are present and passing.",
        ),
        phase_row(
            5,
            "Operator workflow hardening",
            "completed",
            "Mission Control surfaces final status, progress, display-only trial command, summary, and checklist.",
        ),
        phase_row(
            6,
            "Safety/security hardening",
            "ready" if final_ok and tool_surface_passed else "pending",
            "Run/extend offline unsafe-surface fixtures before the fresh public trial if new risks are found.",
        ),
        phase_row(
            7,
            "Fresh real ChatGPT trial",
            "ready" if final_ok and public_session_passed else "pending",
            "External public trial remains explicit-only; no tunnel is started by Mission Control.",
        ),
        phase_row(
            8,
            "Release handoff and maintenance loop",
            "pending",
            "Write final release handoff after a fresh actual-client proof and final gate pass.",
        ),
    ]
    completed_count = sum(1 for row in phase_rows if row["status"] == "completed")
    next_phase = next((row for row in phase_rows if row["status"] not in {"completed"}), None)
    if next_phase and next_phase["phase"] == 6 and final_ok:
        recommended = {
            "key": "phase6-safety-security-hardening",
            "reason": "Operator workflow is hardened; next safe local slice is an offline safety/security fixture pass.",
            "command": commands["mcpFinalStatus"],
        }
    elif next_phase and next_phase["phase"] == 7 and final_ok:
        recommended = {
            "key": "prepare-fresh-chatgpt-trial",
            "reason": "Local final gate passes; the next external proof is a bounded ChatGPT trial.",
            "command": ["scripts\\riftreader-mcp-mission-control.cmd", "--trial-command", "--json"],
        }
    else:
        recommended = (final_status.get("recommendedNextAction") if isinstance(final_status.get("recommendedNextAction"), dict) else {}) or {
            "key": "inspect-final-readiness",
            "reason": "Final readiness has blockers or missing fields.",
            "command": commands["mcpFinalStatus"],
        }
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-final-product-progress",
        "status": "ready-for-next-phase" if final_ok else "blocked",
        "completedPhaseCount": completed_count,
        "totalPhaseCount": len(phase_rows),
        "currentCompletedThroughPhase": completed_count if all(row["status"] == "completed" for row in phase_rows[:completed_count]) else None,
        "nextPhase": next_phase,
        "phases": phase_rows,
        "recommendedNextAction": recommended,
        "externalTrialExplicitOnly": True,
        "publicTunnelStarted": False,
        "chatGptRegistrationPerformed": False,
    }


def phase_row(phase: int, name: str, status: str, evidence: str) -> dict[str, Any]:
    return {"phase": phase, "name": name, "status": status, "evidence": evidence}


def mission_control(repo_root: Path) -> dict[str, Any]:
    state = build_mcp_workflow_state(repo_root)
    ci_status = current_head_ci_status(repo_root)
    final_status = final_readiness(repo_root, state_payload=state)
    compact_final_status = compact_final_readiness(final_status)
    commands = standard_commands()
    progress = build_final_product_progress(repo_root, compact_final_status, commands)
    warnings = unique([
        *(state.get("warnings") if isinstance(state.get("warnings"), list) else []),
        *(ci_status.get("warnings") if isinstance(ci_status.get("warnings"), list) else []),
        *(final_status.get("warnings") if isinstance(final_status.get("warnings"), list) else []),
    ])
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-mission-control",
        "generatedAtUtc": utc_iso(),
        "status": state.get("status"),
        "ok": state.get("ok"),
        "blockers": state.get("blockers"),
        "warnings": warnings,
        "ciStatus": ci_status,
        "finalStatus": compact_final_status,
        "finalProductProgress": progress,
        "latestArtifacts": state.get("latestArtifacts"),
        "counts": state.get("counts"),
        "gitDirtyState": state.get("gitDirtyState"),
        "recommendedNextAction": state.get("recommendedNextAction"),
        "operatorNextAction": progress.get("recommendedNextAction"),
        "rankedActions": ranked_actions(state),
        "pasteSafeCommands": {
            "readiness": commands["mcpTrialReadiness"],
            "proposalSmoke": commands["proposalTransportSmoke"],
            "publicSmoke": commands["cloudflareSmoke"],
            "trialSession": commands["chatGptTrialSession"],
            "phase2Status": commands["mcpPhase2Status"],
            "phase2CompactStatus": commands["mcpPhase2CompactStatus"],
            "finalStatus": commands["mcpFinalStatus"],
            "finalCompactStatus": commands["mcpFinalCompactStatus"],
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
    action = payload.get("operatorNextAction") if isinstance(payload.get("operatorNextAction"), dict) else {}
    if not action:
        action = payload.get("recommendedNextAction") if isinstance(payload.get("recommendedNextAction"), dict) else {}
    lines = [
        "# RiftReader MCP Mission Control Summary",
        "",
        f"- Generated UTC: `{payload.get('generatedAtUtc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Operator next action: `{action.get('key')}`",
        f"- Recommended command: `{' '.join(action.get('command') or [])}`",
    ]
    progress = payload.get("finalProductProgress") if isinstance(payload.get("finalProductProgress"), dict) else {}
    if progress:
        lines.extend(
            [
                "",
                "## Final product progress",
                "",
                f"- Completed phases: `{progress.get('completedPhaseCount')}/{progress.get('totalPhaseCount')}`",
                f"- Progress status: `{progress.get('status')}`",
                "",
                "| Phase | Name | Status | Evidence |",
                "|---:|---|---|---|",
            ]
        )
        for row in progress.get("phases") or []:
            if not isinstance(row, dict):
                continue
            lines.append(f"| {row.get('phase')} | {row.get('name')} | `{row.get('status')}` | {row.get('evidence')} |")
    ci = payload.get("ciStatus") if isinstance(payload.get("ciStatus"), dict) else {}
    if ci:
        lines.extend(
            [
                "",
                "## Current-head CI",
                "",
                f"- Status: `{ci.get('status')}`",
                f"- Current HEAD: `{ci.get('currentHead')}`",
            ]
        )
    final_status = payload.get("finalStatus") if isinstance(payload.get("finalStatus"), dict) else {}
    if final_status:
        final_action = final_status.get("recommendedNextAction") if isinstance(final_status.get("recommendedNextAction"), dict) else {}
        lines.extend(
            [
                "",
                "## Final readiness",
                "",
                f"- Status: `{final_status.get('status')}`",
                f"- Environment: `{final_status.get('environmentStatus')}`",
                f"- Tool surface: `{final_status.get('toolSurfaceStatus')}`",
                f"- Dependencies: `{final_status.get('dependencyStatus')}`",
                f"- Public session: `{final_status.get('publicSessionStatus')}`",
                f"- Next: `{final_action.get('key')}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Latest artifacts",
            "",
            "| Kind | Status | Path | Notes |",
            "|---|---|---|---|",
        ]
    )
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
    progress = payload.get("finalProductProgress") if isinstance(payload.get("finalProductProgress"), dict) else {}
    return "\n".join(
        [
            "# RiftReader MCP Proof Checklist",
            "",
            "## Local final gate",
            "",
            f"- [ ] Confirm final readiness is green before any public exposure: `{' '.join(commands.get('finalCompactStatus') or [])}`",
            f"- [ ] Review dashboard summary if anything is blocked: `{' '.join(commands.get('finalStatus') or [])}`",
            f"- [ ] Confirm completed phases: `{progress.get('completedPhaseCount')}/{progress.get('totalPhaseCount')}`.",
            "",
            "## Local refresh checks",
            "",
            "- [ ] Run local readiness if the final gate reports stale readiness.",
            f"  - `{' '.join(commands.get('readiness') or [])}`",
            "- [ ] Run guarded proposal transport smoke if the final gate reports stale proposal smoke.",
            f"  - `{' '.join(commands.get('proposalSmoke') or [])}`",
            "- [ ] Run explicit public smoke only if environment changed or public endpoint verification is needed.",
            f"  - `{' '.join(commands.get('publicSmoke') or [])}`",
            "",
            "## Explicit public ChatGPT trial",
            "",
            "- [ ] Print the bounded trial command without running it.",
            "  - `scripts\\riftreader-mcp-mission-control.cmd --trial-command --json`",
            "- [ ] Start the bounded ChatGPT trial session only when ready to register in ChatGPT.",
            f"  - `{' '.join(commands.get('trialSession') or [])}`",
            "- [ ] In ChatGPT Developer Mode, confirm 8 tools, `health.repoRoot == \".\"`, and `absoluteRepoRootExposed == false`.",
            "- [ ] Submit one tiny package proposal through actual ChatGPT.",
            "- [ ] Confirm `list_inbox` sees the returned inbox ID.",
            f"  - `{' '.join(commands.get('inboxReview') or [])}`",
            "",
            "## Local package review",
            "",
            "- [ ] Export the inbox item into an inert draft.",
            f"  - `{' '.join(commands.get('draftExport') or [])}`",
            "- [ ] Dry-run the latest draft without apply.",
            f"  - `{' '.join(commands.get('draftDryRun') or [])}`",
            "- [ ] Record actual-client facts with the ChatGPT Trial Recorder.",
            "  - `scripts\\riftreader-chatgpt-trial-recorder.cmd --record --input proof.json --json`",
            "- [ ] Rerun final readiness after recording proof.",
            f"  - `{' '.join(commands.get('finalCompactStatus') or [])}`",
            "",
            "## Safety reminders",
            "",
            "- [ ] Do not use CE, x64dbg, RIFT input, package apply, Git mutation, or provider writes for this MCP proof path.",
            "- [ ] Stop if the final gate reports any blocker; fix the blocker before starting a public trial.",
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
    action = payload.get("operatorNextAction") or payload.get("recommendedNextAction")
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
